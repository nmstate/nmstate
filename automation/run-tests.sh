#!/bin/bash -ex

EXEC_PATH=$(dirname "$(realpath "$0")")
PROJECT_PATH="$(dirname $EXEC_PATH)"
: ${DOCKER_IMAGE:=nmstate/fedora-nmstate-dev}
EXPORT_DIR="$PWD/exported-artifacts"
CONT_EXPORT_DIR="/exported-artifacts"
if [[ $DOCKER_IMAGE == *"fedora"* ]];then
    PYTHON_SITE_PATH_CMD="rpm -E %{python3_sitelib}"
else
    PYTHON_SITE_PATH_CMD="rpm -E %{python_sitelib}"
fi

NET0="nmstate-net0"
NET1="nmstate-net1"

#Valid TEST_TYPE are: all, tox_code_style, tox_py27, tox_py36, tox_py37, integ
: ${TEST_TYPE:="integ"}

test -t 1 && USE_TTY="-t"

function remove_container {
    res=$?
    [ "$res" -ne 0 ] && echo "*** ERROR: $res"
    docker rm $CONTAINER_ID -f
    docker network rm $NET0
    docker network rm $NET1
    rm -f *nmstate*.rpm
}

function pyclean {
        find . -type f -name "*.py[co]" -delete
        find . -type d -name "__pycache__" -delete
}

function docker_exec {
    docker exec \
        -e TRAVIS="$TRAVIS" \
        -e TRAVIS_JOB_ID="$TRAVIS_JOB_ID" \
        -e TRAVIS_BRANCH="$TRAVIS_BRANCH" \
        $USE_TTY -i $CONTAINER_ID /bin/bash -c "$1"
}

function add_extra_networks {
    docker network create $NET0 || true
    docker network create $NET1 || true
    docker network connect $NET0 $CONTAINER_ID
    docker network connect $NET1 $CONTAINER_ID
    docker_exec '
      ip addr flush eth1 && \
      ip addr flush eth2
    '
}

function dump_network_info {
    docker_exec '
      nmcli dev; \
      nmcli con; \
      ip addr; \
      ip route; \
      cat /etc/resolv.conf; \
      head /proc/sys/net/ipv6/conf/*/disable_ipv6; \
    '
}

function install_nmstate {
    docker_exec '
      cd /workspace/nmstate &&
      rpm -ivh `./packaging/make_rpm.sh|tail -1 || exit 1`
    '
}

function run_tests {
    if [ $TEST_TYPE == "all" ] || [ $TEST_TYPE == "tox_code_style" ];then
        docker_exec 'cd /workspace/nmstate && tox -e flake8,pylint'
    fi

    if [ $TEST_TYPE == "all" ] || [ $TEST_TYPE == "tox_py27" ];then
        docker_exec 'cd /workspace/nmstate && tox -e check-py27'
    fi

    if [ $TEST_TYPE == "all" ] || [ $TEST_TYPE == "tox_py36" ];then
        docker_exec 'cd /workspace/nmstate && tox -e check-py36'
    fi

    if [ $TEST_TYPE == "all" ] || [ $TEST_TYPE == "tox_py37" ];then
        docker_exec 'cd /workspace/nmstate && tox -e check-py37'
    fi

    if [ $TEST_TYPE == "all" ] || [ $TEST_TYPE == "integ" ];then
        docker_exec "
          cd /workspace/nmstate &&
          pytest \
            --verbose --verbose \
            --log-level=DEBUG \
            --durations=5 \
            --cov=\$($PYTHON_SITE_PATH_CMD)/libnmstate \
            --cov=\$($PYTHON_SITE_PATH_CMD)/nmstatectl \
            --cov-report=html:htmlcov-integ \
            tests/integration \
        ${nmstate_pytest_extra_args}"
    fi
    if [ -n "$TRAVIS" ];then
        docker_exec 'cd /workspace/nmstate && coveralls'
    fi
}

function collect_artifacts {
    docker_exec "
      journalctl > "$CONT_EXPORT_DIR/journal.log" && \
      cd /workspace/nmstate && cp core* "$CONT_EXPORT_DIR/" || true
    "
}

function run_exit {
    dump_network_info
    collect_artifacts
    remove_container
}

function open_shell {
    res=$?
    [ "$res" -ne 0 ] && echo "*** ERROR: $res"
    set +o errexit
    docker_exec 'echo "pytest tests/integration --pdb" >> ~/.bash_history'
    docker_exec 'cd /workspace/nmstate; exec /bin/bash'
    run_exit
}

cd $EXEC_PATH 
docker --version && cat /etc/resolv.conf

mkdir -p $EXPORT_DIR

CONTAINER_ID="$(docker run --privileged -d -v /sys/fs/cgroup:/sys/fs/cgroup:ro -v $PROJECT_PATH:/workspace/nmstate -v $EXPORT_DIR:$CONT_EXPORT_DIR $DOCKER_IMAGE)"
[ -n "$debug_exit_shell" ] && trap open_shell EXIT || trap run_exit EXIT
docker_exec 'while ! systemctl is-active dbus; do sleep 1; done'
docker_exec '
    systemctl start NetworkManager
    while ! systemctl is-active NetworkManager; do sleep 1; done
'
pyclean

dump_network_info
install_nmstate
add_extra_networks
dump_network_info
run_tests
