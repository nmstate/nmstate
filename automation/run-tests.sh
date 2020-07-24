#!/bin/bash -ex

EXEC_PATH=$(dirname "$(realpath "$0")")
PROJECT_PATH="$(dirname $EXEC_PATH)"
EXPORT_DIR="$PWD/exported-artifacts"
CONT_EXPORT_DIR="/exported-artifacts"

CONTAINER_WORKSPACE="/workspace/nmstate"

TEST_TYPE_ALL="all"
TEST_TYPE_FORMAT="format"
TEST_TYPE_LINT="lint"
TEST_TYPE_UNIT_PY36="unit_py36"
TEST_TYPE_UNIT_PY38="unit_py38"
TEST_TYPE_INTEG="integ"
TEST_TYPE_INTEG_TIER1="integ_tier1"
TEST_TYPE_INTEG_TIER2="integ_tier2"
TEST_TYPE_INTEG_SLOW="integ_slow"

FEDORA_IMAGE_DEV="docker.io/nmstate/fedora-nmstate-dev"
CENTOS_IMAGE_DEV="docker.io/nmstate/centos8-nmstate-dev"

CREATED_INTERFACES=""
INTERFACES="eth1 eth2"

PYTEST_OPTIONS="--verbose --verbose \
        --log-level=DEBUG \
        --log-date-format='%Y-%m-%d %H:%M:%S' \
        --log-format='%(asctime)s %(filename)s:%(lineno)d %(levelname)s %(message)s' \
        --durations=5 \
        --cov /usr/lib/python*/site-packages/libnmstate \
        --cov /usr/lib/python*/site-packages/nmstatectl \
        --cov-report=term \
        --cov-report=xml \
        --log-file=pytest-run.log"

NMSTATE_TEMPDIR=$(mktemp -d /tmp/nmstate-test-XXXX)

VETH_PEER_NS="nmstate_test"

: ${CONTAINER_CMD:=podman}

test -t 1 && USE_TTY="-t"
source automation/tests-container-utils.sh
source automation/tests-machine-utils.sh

function pyclean {
    exec_cmd '
        find . -type f -name "*.py[co]" -delete
        find . -type d -name "__pycache__" -delete
    '
}

function exec_cmd {
    if [ -z ${RUN_BAREMETAL} ];then
        container_exec "$1"
    else
        bash -c "$1"
    fi
}

function dump_network_info {
    exec_cmd '
      nmcli dev; \
      # Use empty PAGER variable to stop nmcli send output to less which hang \
      # the CI. \
      PAGER= nmcli con; \
      ip addr; \
      ip route; \
      cat /etc/resolv.conf; \
      head /proc/sys/net/ipv6/conf/*/disable_ipv6; \
    '
}

function install_nmstate {
    if [ $INSTALL_NMSTATE == "true" ];then
        exec_cmd '
          rpm -ivh `./packaging/make_rpm.sh|tail -1 || exit 1`
        '
    fi
}

function run_tests {
    if [ $TEST_TYPE == $TEST_TYPE_ALL ] || \
       [ $TEST_TYPE == $TEST_TYPE_FORMAT ];then
        exec_cmd "tox -e black"
    fi

    if [ $TEST_TYPE == $TEST_TYPE_ALL ] || \
       [ $TEST_TYPE == $TEST_TYPE_LINT ];then
        exec_cmd "tox -e flake8,pylint"
    fi

    if [ $TEST_TYPE == $TEST_TYPE_ALL ] || \
       [ $TEST_TYPE == $TEST_TYPE_UNIT_PY36 ];then
        if [[ $CONTAINER_IMAGE == *"centos"* ]]; then
            # Due to https://github.com/pypa/virtualenv/issues/1009
            # Instruct virtualenv not to upgrade to the latest versions of pip,
            # setuptools, wheel and etc
            exec_cmd 'env VIRTUALENV_NO_DOWNLOAD=1 \
                            tox --sitepackages -e py36'
        else
            exec_cmd "tox -e py36"
        fi
    fi

    if [ $TEST_TYPE == $TEST_TYPE_ALL ] || \
       [ $TEST_TYPE == $TEST_TYPE_UNIT_PY38 ];then
        if [[ $CONTAINER_IMAGE == *"centos"* ]]; then
            echo "Running unit test in $CONTAINER_IMAGE container is not " \
                 "support yet"
        else
            exec_cmd "tox -e py38"
        fi
    fi

    if [ $TEST_TYPE == $TEST_TYPE_ALL ] || \
       [ $TEST_TYPE == $TEST_TYPE_INTEG ];then
        exec_cmd "cd $CONTAINER_WORKSPACE"
        exec_cmd "
            pytest \
            $PYTEST_OPTIONS \
            --cov-report=html:htmlcov-integ \
            tests/integration \
            ${nmstate_pytest_extra_args}"
    fi

    if  [ $TEST_TYPE == $TEST_TYPE_INTEG_TIER1 ];then
        exec_cmd "cd $CONTAINER_WORKSPACE"
        exec_cmd "
          pytest \
            $PYTEST_OPTIONS \
            --cov-report=html:htmlcov-integ_tier1 \
            -m tier1 \
            tests/integration \
            ${nmstate_pytest_extra_args}"
    fi

    if  [ $TEST_TYPE == $TEST_TYPE_INTEG_TIER2 ];then
        exec_cmd "cd $CONTAINER_WORKSPACE"
        exec_cmd "
          pytest \
            $PYTEST_OPTIONS \
            --cov-report=html:htmlcov-integ_tier2 \
            -m tier2 \
            tests/integration \
            ${nmstate_pytest_extra_args}"
    fi

    if [ $TEST_TYPE == $TEST_TYPE_ALL ] || \
       [ $TEST_TYPE == $TEST_TYPE_INTEG_SLOW ];then
        exec_cmd "cd $CONTAINER_WORKSPACE"
        exec_cmd "
          pytest \
            $PYTEST_OPTIONS \
            --cov-report=html:htmlcov-integ_slow \
            -m slow --runslow \
            tests/integration \
            ${nmstate_pytest_extra_args}"
    fi
}

function write_separator {
    set +x
    local text="$(echo "${1}" | sed 's,., \0,g') "
    local char="="

    local textlength=$(echo -n "${text}" | wc --chars)
    local cols="$(tput cols)"
    local wraplength=$(((cols - textlength) / 2))

    eval printf %.1s "${char}"'{1..'"${wraplength}"\}
    echo -n "${text}"
    wraplength=$((wraplength + ((cols - textlength) % 2)))
    eval printf %.1s "${char}"'{1..'"${wraplength}"\}
    echo
    set -x
}

function run_exit {
    write_separator "TEARDOWN"
    dump_network_info
    if [ -z ${RUN_BAREMETAL} ];then
        collect_artifacts
        remove_container
        remove_tempdir
    else
        teardown_network_environment
    fi
}

function modprobe_ovs {
    lsmod | grep -q ^openvswitch || modprobe openvswitch || { echo 1>&2 "Please run 'modprobe openvswitch' as root"; exit 1; }
}

function check_services {
    exec_cmd 'while ! systemctl is-active dbus; do sleep 1; done'
    exec_cmd 'systemctl start systemd-udevd
                 while ! systemctl is-active systemd-udevd; do sleep 1; done
    '
    exec_cmd '
        systemctl restart NetworkManager
        while ! systemctl is-active NetworkManager; do sleep 1; done
    '
}

function upload_coverage {
    if [[ "$CI" == "true" ]] ;then
        container_exec "
            cd $CONTAINER_WORKSPACE &&
            COVERALLS_PARALLEL=true COVERALLS_SERVICE_NAME=travis-ci coveralls
        " || true
        container_exec "
            cd $CONTAINER_WORKSPACE &&
            bash <(curl -s https://codecov.io/bash)
        " || true
    fi
}

function check_iface_exist {
    exec_cmd "ip link | grep -q $1"
}

function prepare_network_environment {
    set +e
    exec_cmd "ip netns add ${VETH_PEER_NS}"
    for device in $INTERFACES;
    do
        peer="${device}peer"
        check_iface_exist $device
        if [ $? -eq 1 ]; then
            CREATED_INTERFACES="${CREATED_INTERFACES} ${device}"
            exec_cmd "ip link add ${device} type veth peer name ${peer}"
            exec_cmd "ip link set ${peer} netns ${VETH_PEER_NS}"
            exec_cmd "ip netns exec ${VETH_PEER_NS} ip link set ${peer} up"
            exec_cmd "ip link set ${device} up"
            exec_cmd "nmcli device set ${device} managed yes"
        fi
    done
    set -e
}

function teardown_network_environment {
    for device in $CREATED_INTERFACES;
    do
        exec_cmd "ip link del ${device}"
    done
    exec_cmd "ip netns del ${VETH_PEER_NS}"
}

function upgrade_nm_from_copr {
    local copr_repo=$1
    # The repoid for a Copr repo is the name with the slash replaces by a colon
    local copr_repo_id="copr:copr.fedorainfracloud.org:${copr_repo/\//:}"
    # Workaround for dnf failure:
    # [Errno 2] No such file or directory: '/var/cache/dnf/metadata_lock.pid'
    if [[ "$CI" == "true" ]];then
        exec_cmd "rm -fv /var/cache/dnf/metadata_lock.pid"
        exec_cmd "dnf clean all"
        exec_cmd "dnf makecache || :"
    fi
    exec_cmd "command -v dnf && plugin='dnf-command(copr)' || plugin='yum-plugin-copr'; yum install --assumeyes \$plugin;"
    exec_cmd "yum copr enable --assumeyes ${copr_repo}"
    # Update only from Copr to limit the changes in the environment
    exec_cmd "yum update --assumeyes --disablerepo '*' --enablerepo '${copr_repo_id}'"
    exec_cmd "systemctl restart NetworkManager"
}

function run_customize_command {
    if [[ -n "$customize_cmd" ]];then
        clean_dnf_cache
        exec_cmd "${customize_cmd}"
    fi
}

options=$(getopt --options "" \
    --long customize:,pytest-args:,help,debug-shell,test-type:,el8,copr:,artifacts-dir:,test-vdsm,machine,use-installed-nmstate\
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
    --el8)
        CONTAINER_IMAGE=$CENTOS_IMAGE_DEV
        ;;
    --artifacts-dir)
        shift
        EXPORT_DIR="$1"
        ;;
    --test-vdsm)
        vdsm_tests
        exit
        ;;
    --machine)
        RUN_BAREMETAL="true"
        ;;
    --use-installed-nmstate)
        INSTALL_NMSTATE="false"
        ;;
    --help)
        set +x
        echo -n "$0 [--copr=...] [--customize=...] [--debug-shell] [--el8] "
        echo -n "[--help] [--pytest-args=...] [--machine] "
        echo "[--use-installed-nmstate] [--test-type=<TEST_TYPE>] [--test-vdsm]"
        echo "    Valid TEST_TYPE are:"
        echo "     * $TEST_TYPE_ALL (default)"
        echo "     * $TEST_TYPE_FORMAT"
        echo "     * $TEST_TYPE_LINT"
        echo "     * $TEST_TYPE_INTEG"
        echo "     * $TEST_TYPE_INTEG_TIER1"
        echo "     * $TEST_TYPE_INTEG_TIER2"
        echo "     * $TEST_TYPE_INTEG_SLOW"
        echo "     * $TEST_TYPE_UNIT_PY36"
        echo "     * $TEST_TYPE_UNIT_PY38"
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
: ${CONTAINER_IMAGE:=$FEDORA_IMAGE_DEV}
: ${INSTALL_NMSTATE:="true"}
: ${INSTALL_DEPS:="false"}

modprobe_ovs

if [ -n "${RUN_BAREMETAL}" ];then
    CONTAINER_WORKSPACE="."
    run_customize_command
    start_machine_services
else
    container_pre_test_setup
    run_customize_command
fi

if [[ -v copr_repo ]];then
    upgrade_nm_from_copr "${copr_repo}"
fi

check_services
prepare_network_environment

if [ -n "$RUN_BAREMETAL" ];then
    trap run_exit ERR EXIT
fi

exec_cmd '(source /etc/os-release; echo $PRETTY_NAME); rpm -q NetworkManager'

dump_network_info

pyclean
if [ -z ${RUN_BAREMETAL} ];then
    copy_workspace_container
fi

install_nmstate
run_tests
upload_coverage
