#!/bin/sh -ex

EXEC_PATH=$(dirname "$(realpath "$0")")
PROJECT_PATH="$(dirname $EXEC_PATH)"
: ${DOCKER_IMAGE:=nmstate/centos7-nmstate-dev}
EXPORT_DIR="$PWD/exported-artifacts"
CONT_EXPORT_DIR="/exported-artifacts"

NET0="nmstate-net0"
NET1="nmstate-net1"

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
    docker exec $USE_TTY -i $CONTAINER_ID /bin/bash -c "$1"
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
    docker_exec '
      cd /workspace/nmstate &&
      pytest \
        --verbose --verbose \
        --log-level=DEBUG \
        --durations=5 \
        --cov=libnmstate \
        --cov=nmstatectl \
        --cov-report=html:htmlcov-py27 \
        tests/integration \
    '"${nmstate_pytest_extra_args}"
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
pyclean

dump_network_info
install_nmstate
add_extra_networks
dump_network_info
run_tests
