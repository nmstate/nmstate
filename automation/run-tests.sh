#!/bin/bash -ex

EXEC_PATH=$(dirname "$(realpath "$0")")
PROJECT_PATH="$(dirname $EXEC_PATH)"
EXPORT_DIR="$PWD/exported-artifacts"
CONT_EXPORT_DIR="/exported-artifacts"

CONTAINER_WORKSPACE="/workspace/nmstate"

NET0="nmstate-net0"
NET1="nmstate-net1"

TEST_TYPE_ALL="all"
TEST_TYPE_FORMAT="format"
TEST_TYPE_LINT="lint"
TEST_TYPE_UNIT_PY27="unit_py27"
TEST_TYPE_UNIT_PY36="unit_py36"
TEST_TYPE_UNIT_PY37="unit_py37"
TEST_TYPE_INTEG="integ"

FEDORA_IMAGE_DEV="nmstate/fedora-nmstate-dev"
CENTOS_IMAGE_DEV="nmstate/centos7-nmstate-dev"

test -t 1 && USE_TTY="-t"

function remove_container {
    res=$?
    [ "$res" -ne 0 ] && echo "*** ERROR: $res"
    docker_exec 'rm -rf $CONTAINER_WORKSPACE/*nmstate*.rpm'
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
        /bin/bash -c "cd $CONTAINER_WORKSPACE && $1"
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
       [ $TEST_TYPE == $TEST_TYPE_FORMAT ];then
        if [[ $DOCKER_IMAGE == *"centos"* ]]; then
            echo "Running formatter in $DOCKER_IMAGE container is not " \
                 "support yet"
        else
            docker_exec 'tox -e black'
        fi
    fi

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
          cd $CONTAINER_WORKSPACE &&
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

function rebuild_container_images {
    if is_file_changed "$PROJECT_PATH/packaging"; then

        ${PROJECT_PATH}/packaging/build-container.sh all
    fi
}

function upgrade_nm_from_copr {
    local copr_repo=$1
    # The repoid for a Copr repo is the name with the slash replaces by a colon
    local copr_repo_id="copr:copr.fedorainfracloud.org:${copr_repo/\//:}"
    docker_exec "command -v dnf && plugin='dnf-command(copr)' || plugin='yum-plugin-copr'; yum install --assumeyes \$plugin;"
    docker_exec "yum copr enable --assumeyes ${copr_repo}"
    # Update only from Copr to limit the changes in the environment
    docker_exec "yum update --assumeyes --disablerepo '*' --enablerepo '${copr_repo_id}'"
    docker_exec "systemctl restart NetworkManager"
}

function modprobe_ovs {
    lsmod | grep -q ^openvswitch || modprobe openvswitch || { echo 1>&2 "Please run 'modprobe openvswitch' as root"; exit 1; }
}

options=$(getopt --options "" \
    --long customize:,pytest-args:,help,debug-shell,test-type:,el7,copr:,artifacts-dir:\
    -- "${@}")
eval set -- "$options"
while true; do
    case "$1" in
    --pytest-args)
        shift
        nmstate_pytest_extra_args="$1"
        ;;
    --copr)
        shift
        copr_repo="$1"
        ;;
    --customize)
        shift
        customize_cmd="$1"
        ;;
    --debug-shell)
        debug_exit_shell="1"
        ;;
    --test-type)
        shift
        TEST_TYPE="$1"
        ;;
    --el7)
        DOCKER_IMAGE=$CENTOS_IMAGE_DEV
        ;;
    --artifacts-dir)
        shift
        EXPORT_DIR="$1"
        ;;
    --help)
        set +x
        echo -n "$0 [--copr=...] [--customize=...] [--debug-shell] [--el7] "
        echo -n "[--help] [--pytest-args=...] "
        echo "[--test-type=<TEST_TYPE>]"
        echo "    Valid TEST_TYPE are:"
        echo "     * $TEST_TYPE_ALL (default)"
        echo "     * $TEST_TYPE_FORMAT"
        echo "     * $TEST_TYPE_LINT"
        echo "     * $TEST_TYPE_INTEG"
        echo "     * $TEST_TYPE_UNIT_PY27"
        echo "     * $TEST_TYPE_UNIT_PY36"
        echo "     * $TEST_TYPE_UNIT_PY37"
        echo -n "--customize allows to specify a command to customize the "
        echo "container before running the tests"
        exit
        ;;
    --)
        shift
        break
        ;;
    esac
    shift
done

: ${TEST_TYPE:=$TEST_TYPE_ALL}
: ${DOCKER_IMAGE:=$FEDORA_IMAGE_DEV}

docker --version && cat /etc/resolv.conf

modprobe_ovs

if [[ "$CI" == "true" ]];then
    rebuild_container_images
fi

mkdir -p $EXPORT_DIR
CONTAINER_ID="$(docker run --privileged -d -v /sys/fs/cgroup:/sys/fs/cgroup:ro -v $PROJECT_PATH:$CONTAINER_WORKSPACE -v $EXPORT_DIR:$CONT_EXPORT_DIR $DOCKER_IMAGE)"
[ -n "$debug_exit_shell" ] && trap open_shell EXIT || trap run_exit EXIT

if [[ -v copr_repo ]];then
    upgrade_nm_from_copr "${copr_repo}"
fi

if [[ -v customize_cmd ]];then
    docker_exec "${customize_cmd}"
fi

docker_exec 'while ! systemctl is-active dbus; do sleep 1; done'
docker_exec 'systemctl start systemd-udevd
             while ! systemctl is-active systemd-udevd; do sleep 1; done
'
docker_exec '
    systemctl restart NetworkManager
    while ! systemctl is-active NetworkManager; do sleep 1; done
'
add_extra_networks
dump_network_info

pyclean
docker_exec "cp -rf $CONTAINER_WORKSPACE /tmp/"
# Change workspace to keep the original one clean
CONTAINER_WORKSPACE="/tmp/nmstate"
install_nmstate
run_tests
