#!/bin/bash -ex

function remove_container {
    res=$?
    [ "$res" -ne 0 ] && echo "*** ERROR: $res"
    container_exec 'rm -rf $CONTAINER_WORKSPACE/*nmstate*.rpm' || true
    ${CONTAINER_CMD} rm -f $CONTAINER_ID
}

function container_exec {
    ${CONTAINER_CMD} exec $USE_TTY -i $CONTAINER_ID \
        /bin/bash -c "cd $CONTAINER_WORKSPACE && $1"
}

function open_shell {
    res=$?
    [ "$res" -ne 0 ] && echo "*** ERROR: $res"
    set +o errexit
    container_exec 'echo "pytest tests/integration --pdb" >> ~/.bash_history'
    container_exec 'exec /bin/bash'
    run_exit
}

# Return 0 if file is changed else 1
function is_file_changed {
    git remote add upstream https://github.com/nmstate/nmstate.git
    git fetch upstream
    if [ -n "$BRANCH_NAME" ]; then
        git diff --exit-code --name-only upstream/$BRANCH_NAME -- $1
    else
        git diff --exit-code --name-only upstream/base -- $1
    fi

    if [ $? -eq 0 ];then
        return 1
    else
        return 0
    fi
}

function rebuild_container_images {
    if is_file_changed "$PROJECT_PATH/packaging"; then
        IMAGE_NAME=$(basename $CONTAINER_IMAGE)
        ${PROJECT_PATH}/packaging/build-container.sh $IMAGE_NAME
    fi
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

    create_container

    container_exec "ulimit -c unlimited"
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
  mkdir -p $EXPORT_DIR
  # The podman support wildcard when passing enviroments, but docker does not.
  CONTAINER_ID="$(${CONTAINER_CMD} run --privileged -d \
      -e CI \
      -e SHIPPABLE \
      -v /sys/fs/cgroup:/sys/fs/cgroup:ro \
      -v $PROJECT_PATH:$CONTAINER_WORKSPACE \
      -v $EXPORT_DIR:$CONT_EXPORT_DIR $CONTAINER_IMAGE)"
  [ -n "$debug_exit_shell" ] && trap open_shell EXIT || trap run_exit EXIT
}
