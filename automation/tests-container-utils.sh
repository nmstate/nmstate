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
    if [ -n "$TRAVIS_BRANCH" ]; then
        git diff --exit-code --name-only upstream/$TRAVIS_BRANCH -- $1
    else
        git diff -exit-code --name-only upstream/master -- $1
    fi

    if [ $? -eq 0 ];then
        return 1
    else
        return 0
    fi
}

function rebuild_container_images {
    set +x
    if is_file_changed "$PROJECT_PATH/packaging"; then
        if [ $CONTAINER_IMAGE == $CENTOS_IMAGE_DEV ];then
            ${PROJECT_PATH}/packaging/build-container.sh centos8-nmstate-dev
        elif [ $CONTAINER_IMAGE == $FEDORA_IMAGE_DEV ];then
            ${PROJECT_PATH}/packaging/build-container.sh fedora-nmstate-dev
        fi
    fi
}

function remove_tempdir {
    rm -rf "$NMSTATE_TEMPDIR"
}

function vdsm_tests {
    trap remove_tempdir EXIT
    git -C "$NMSTATE_TEMPDIR" clone --depth 1 https://gerrit.ovirt.org/vdsm
    cd "$NMSTATE_TEMPDIR/vdsm"
    ./tests/network/functional/run-tests.sh --nmstate-source="$PROJECT_PATH"
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
    ${CONTAINER_CMD} --version && cat /etc/resolv.conf

    if [[ "$CI" == "true" ]];then
        rebuild_container_images
    fi

    create_container

    container_exec "echo '$CONT_EXPORT_DIR/core.%h.%e.%t' > \
        /proc/sys/kernel/core_pattern"
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
      -e COVERALLS_REPO_TOKEN \
      -e CODECOV_TOKEN \
      -e TRAVIS \
      -e TRAVIS_BRANCH \
      -e TRAVIS_COMMIT \
      -e TRAVIS_JOB_NUMBER \
      -e TRAVIS_PULL_REQUEST \
      -e TRAVIS_JOB_ID \
      -e TRAVIS_REPO_SLUG \
      -e TRAVIS_TAG \
      -e TRAVIS_OS_NAME \
      -e SHIPPABLE \
      -v /sys/fs/cgroup:/sys/fs/cgroup:ro \
      -v $PROJECT_PATH:$CONTAINER_WORKSPACE \
      -v $EXPORT_DIR:$CONT_EXPORT_DIR $CONTAINER_IMAGE)"
  [ -n "$debug_exit_shell" ] && trap open_shell EXIT || trap run_exit EXIT
}
