#!/bin/bash -ex

function remove_container {
    res=$?
    [ "$res" -ne 0 ] && echo "*** ERROR: $res"
    container_exec 'rm -rf $CONTAINER_WORKSPACE/*nmstate*.rpm' || true
    ${CONTAINER_CMD} rm -f $CONTAINER_ID
}

function container_exec {
    time ${CONTAINER_CMD} exec $USE_TTY -i $CONTAINER_ID \
        /bin/bash -c "cd $CONTAINER_WORKSPACE && $1"
}

function container_exec_with_retry {
    local retries=5
    local i
    for ((i=1; i<=retries; i++)); do
        if time ${CONTAINER_CMD} exec $USE_TTY -i $CONTAINER_ID \
            /bin/bash -c "cd $CONTAINER_WORKSPACE && $1"
        then
            return 0
        fi
        if [ "$i" -lt "$retries" ]; then
            echo "Command failed, retrying ($i/$retries) after 10s..."
            sleep 10
        fi
    done
    return 1
}

function open_shell {
    res=$?
    [ "$res" -ne 0 ] && echo "*** ERROR: $res"
    set +o errexit
    container_exec 'echo "pytest tests/integration --pdb" >> ~/.bash_history'
    container_exec 'exec /bin/bash'
    run_exit
}

# Return 0 for changes, 1 for no changes, or 2 on error.
function is_file_changed {
    local rc=0
    git fetch -- "${NMSTATE_REPO:-https://github.com/nmstate/nmstate.git}" \
        "refs/heads/${BRANCH_NAME:-base}" || return 2
    git diff --exit-code --name-only FETCH_HEAD -- "$1" || rc=$?
    case $rc in
        0) return 1 ;;
        1) return 0 ;;
        *) return 2 ;;
    esac
}

function rebuild_container_images {
    local image_name rc=0
    if [ "${NMSTATE_SKIP_IMAGE_REBUILD:-0}" = 1 ]; then
        pull_container_image
        return
    fi
    is_file_changed "$PROJECT_PATH/packaging" || rc=$?
    case $rc in
        1) pull_container_image; return ;;
        0) ;;
        *) return "$rc" ;;
    esac
    image_name=$(basename "$CONTAINER_IMAGE")
    # build-container.sh always tags quay.io/nmstate/<name>
    if [[ "$CONTAINER_IMAGE" != quay.io/nmstate/* || \
          ! -f "$PROJECT_PATH/packaging/Dockerfile.$image_name" ]]; then
        echo "Cannot rebuild $CONTAINER_IMAGE for changed packaging/," \
            "set NMSTATE_SKIP_IMAGE_REBUILD=1" >&2
        return 2
    fi
    "${PROJECT_PATH}/packaging/build-container.sh" "$image_name"
}

function pull_container_image {
    local image i mirror="${NMSTATE_IMAGE_MIRROR:-}"
    local images=("$CONTAINER_IMAGE")
    while [[ "$mirror" == */ ]]; do
        mirror="${mirror%/}"
    done
    if [[ "$CONTAINER_IMAGE" == quay.io/nmstate/* && \
          -n "$mirror" && "$mirror" != quay.io/nmstate ]]; then
        images+=("$mirror/${CONTAINER_IMAGE#quay.io/nmstate/}")
    fi
    for i in {1..5}; do
        for image in "${images[@]}"; do
            if ${CONTAINER_CMD} pull "$image"; then
                if [ "$image" != "$CONTAINER_IMAGE" ]; then
                    echo "Using mirror image $image"
                fi
                CONTAINER_IMAGE="$image"
                return 0
            fi
        done
    done
    return 1
}

function remove_tempdir {
    rm -rf "$NMSTATE_TEMPDIR"
}

function vdsm_tests {
    trap remove_tempdir EXIT
    git -C "$NMSTATE_TEMPDIR" clone --depth 1 https://gerrit.ovirt.org/vdsm
    cd "$NMSTATE_TEMPDIR/vdsm"
    ./tests/network/functional/run-tests.sh --nmstate-source="$PROJECT_PATH" --pytest-args="-x"
    cd -
}

function collect_artifacts {
    container_exec "
      journalctl > "$CONT_EXPORT_DIR/journal.log" && \
      dmesg > "$CONT_EXPORT_DIR/dmesg.log" && \
      cat /var/log/openvswitch/ovsdb-server.log > "$CONT_EXPORT_DIR/ovsdb-server.log" && \
      mv "$CONTAINER_WORKSPACE/pytest-run.log" "$CONT_EXPORT_DIR/pytest-run.log" || true
    "
}

function container_pre_test_setup {
    set -x
    ${CONTAINER_CMD} --version && cat /etc/resolv.conf

    if [[ "$CI" == "true" ]];then
        rebuild_container_images || return $?
    elif [ -n "${NMSTATE_IMAGE_MIRROR:-}" ] && \
        ! ${CONTAINER_CMD} image inspect "$CONTAINER_IMAGE" >/dev/null 2>&1; then
        pull_container_image || return $?
    fi

    create_container || return $?

    container_exec "ulimit -c unlimited"
    container_exec "git config --global --add safe.directory \
        $CONTAINER_WORKSPACE"
}

function copy_workspace_container {
    if [[ "$CI" != "true" ]];then
        if $CONTAINER_CMD --version | grep -qv podman; then
          container_exec "cp -rf $CONTAINER_WORKSPACE /root/nmstate-workspace || true"
        else
          container_exec "cp -rf $CONTAINER_WORKSPACE /root/nmstate-workspace"
        fi
        # Change workspace to keep the original one clean
        CONTAINER_WORKSPACE="/root/nmstate-workspace"
    fi
}

function create_container {
  mkdir -p "$EXPORT_DIR" || return $?
  # The podman support wildcard when passing enviroments, but docker does not.
  CONTAINER_ID="$(${CONTAINER_CMD} run --privileged -d \
      -e CI \
      -e SHIPPABLE \
      -e NMSTATE_IPSEC_IMAGE \
      -e NMSTATE_IMAGE_MIRROR \
      -v /var/lib/containers:/var/lib/containers \
      -v $PROJECT_PATH:$CONTAINER_WORKSPACE \
      -v $EXPORT_DIR:$CONT_EXPORT_DIR "$CONTAINER_IMAGE")" || return $?
  [ -n "$debug_exit_shell" ] && trap open_shell EXIT || trap run_exit EXIT
  # Wait systemd started
  until $CONTAINER_CMD exec $CONTAINER_ID sh -c "
      [ $(systemctl is-system-running) == 'degraded' ] || \
      [ $(systemctl is-system-running) == 'running' ]"
  do
      echo "Waiting for systemd in container to be ready..."
      sleep 0.1;
  done
}
