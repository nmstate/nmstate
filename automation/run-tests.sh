#!/bin/bash -ex

EXEC_PATH=$(dirname "$(realpath "$0")")
PROJECT_PATH="$(dirname $EXEC_PATH)"
EXPORT_DIR="$PWD/exported-artifacts"
CONT_EXPORT_DIR="/exported-artifacts"

NET0="nmstate-net0"
NET1="nmstate-net1"

TEST_TYPE_ALL="all"
TEST_TYPE_LINT="lint"
TEST_TYPE_UNIT_PY27="unit_py27"
TEST_TYPE_UNIT_PY36="unit_py36"
TEST_TYPE_UNIT_PY37="unit_py37"
TEST_TYPE_INTEG="integ"

test -t 1 && USE_TTY="-t"

function remove_container {
    res=$?
    [ "$res" -ne 0 ] && echo "*** ERROR: $res"
    docker_exec 'rm -rf /workspace/nmstate/*nmstate*.rpm'
    docker rm $CONTAINER_ID -f
    docker network rm $NET0
    docker network rm $NET1
}

function pyclean {
        find . -type f -name "*.py[co]" -delete
        find . -type d -name "__pycache__" -delete
}

function docker_exec {
    docker exec $USE_TTY -i $CONTAINER_ID \
        /bin/bash -c "cd /workspace/nmstate && $1"
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
      rpm -ivh `./packaging/make_rpm.sh|tail -1 || exit 1`
    '
}

function run_tests {
    if [ $TEST_TYPE == $TEST_TYPE_ALL ] || \
       [ $TEST_TYPE == $TEST_TYPE_LINT ];then
        if [[ $DOCKER_IMAGE == *"centos"* ]]; then
            echo "Running unit test in $DOCKER_IMAGE container is not " \
                 "support yet"
        else
            docker_exec 'tox -e flake8,pylint'
        fi
    fi

    if [ $TEST_TYPE == $TEST_TYPE_ALL ] || \
       [ $TEST_TYPE == $TEST_TYPE_UNIT_PY27 ];then
        if [[ $DOCKER_IMAGE == *"centos"* ]]; then
            echo "Running unit test in $DOCKER_IMAGE container is not " \
                 "support yet"
        else
            docker_exec 'tox -e check-py27'
        fi
    fi

    if [ $TEST_TYPE == $TEST_TYPE_ALL ] || \
       [ $TEST_TYPE == $TEST_TYPE_UNIT_PY36 ];then
        if [[ $DOCKER_IMAGE == *"centos"* ]]; then
            echo "Running unit test in $DOCKER_IMAGE container is not " \
                 "support yet"
        else
            docker_exec 'tox -e check-py36'
        fi
    fi

    if [ $TEST_TYPE == $TEST_TYPE_ALL ] || \
       [ $TEST_TYPE == $TEST_TYPE_UNIT_PY37 ];then
        if [[ $DOCKER_IMAGE == *"centos"* ]]; then
            echo "Running unit test in $DOCKER_IMAGE container is not " \
                 "support yet"
        else
            docker_exec 'tox -e check-py37'
        fi
    fi

    if [ $TEST_TYPE == $TEST_TYPE_ALL ] || \
       [ $TEST_TYPE == $TEST_TYPE_INTEG ];then
        docker_exec "
          cd /workspace/nmstate &&
          pytest \
            --verbose --verbose \
            --log-level=DEBUG \
            --log-date-format='%Y-%m-%d %H:%M:%S' \
            --log-format='%(asctime)s %(filename)s:%(lineno)d %(levelname)s %(message)s' \
            --durations=5 \
            --cov /usr/lib/python*/site-packages/libnmstate \
            --cov /usr/lib/python*/site-packages/nmstatectl \
            --cov-report=html:htmlcov-integ \
            --cov-report=term \
            tests/integration \
            ${nmstate_pytest_extra_args}"
    fi
}

function collect_artifacts {
    docker_exec "
      journalctl > "$CONT_EXPORT_DIR/journal.log" && \
      cp core* "$CONT_EXPORT_DIR/" || true
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
    docker_exec 'exec /bin/bash'
    run_exit
}

# Return 0 if file is changed else 1
function is_file_changed {
    git diff --exit-code --name-only origin/master -- $1
    if [ $? -eq 0 ];then
        return 1
    else
        return 0
    fi
}

function rebuild_el7_base_container_image {
    docker build --no-cache -t nmstate/centos7-nmstate-base \
        -f "$PROJECT_PATH/packaging/Dockerfile.centos7-nmstate-base" \
        "$PROJECT_PATH/packaging"
}

function rebuild_el7_container_image {
    docker build --no-cache -t nmstate/centos7-nmstate-dev \
        -f "$PROJECT_PATH/automation/Dockerfile" \
        "$PROJECT_PATH/automation"
}

function rebuild_fed_container_image {
    docker build --no-cache -t nmstate/fedora-nmstate-dev \
        -f "$PROJECT_PATH/automation/Dockerfile.fedora" \
        "$PROJECT_PATH/automation"
}

function rebuild_container_images {
    if (is_file_changed "$PROJECT_PATH/packaging" ||
        is_file_changed "$PROJECT_PATH/automation"); then

        rebuild_el7_base_container_image
        rebuild_el7_container_image
        rebuild_fed_container_image
    fi
}

options=$(getopt --options "" \
    --long pytest-args:,help,debug-shell,test-type:,el7\
    -- "${@}")
eval set -- "$options"
while true; do
    case "$1" in
    --pytest-args)
        shift
        nmstate_pytest_extra_args="$1"
        ;;
    --debug-shell)
        debug_exit_shell="1"
        ;;
    --test-type)
        shift
        TEST_TYPE="$1"
        ;;
    --el7)
        DOCKER_IMAGE="nmstate/centos7-nmstate-dev"
        ;;
    --help)
        echo -n "$0 [--pytest-args=...] [--help] [--debug-shell] "
        echo -n "[--el7] "
        echo "[--test-type=<TEST_TYPE>]"
        echo "    Valid TEST_TYPE are:"
        echo "     * $TEST_TYPE_ALL (default)"
        echo "     * $TEST_TYPE_LINT"
        echo "     * $TEST_TYPE_INTEG"
        echo "     * $TEST_TYPE_UNIT_PY27"
        echo "     * $TEST_TYPE_UNIT_PY36"
        echo "     * $TEST_TYPE_UNIT_PY37"
        exit
        ;;
    --)
        shift
        break
        ;;
    esac
    shift
done

#Valid TEST_TYPE are: all, lint, unit_py27, unit_py36, unit_py37, integ.
: ${TEST_TYPE:=$TEST_TYPE_ALL}
: ${DOCKER_IMAGE:=nmstate/fedora-nmstate-dev}

cd $EXEC_PATH
docker --version && cat /etc/resolv.conf

mkdir -p $EXPORT_DIR

lsmod | grep -q ^openvswitch || modprobe openvswitch || { echo 1>&2 "Please run 'modprobe openvswitch' as root"; exit 1; }

if [[ "$CI" == "true" ]];then
    rebuild_container_images
fi

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
