#!/bin/bash -e

if [ "$1" != "--help" ]; then
    set -x
fi

EXEC_PATH=$(dirname "$(realpath "$0")")
PROJECT_PATH="$(dirname $EXEC_PATH)"
EXPORT_DIR="$PWD/exported-artifacts"
CONT_EXPORT_DIR="/exported-artifacts"

CONTAINER_WORKSPACE="/workspace/nmstate"

TEST_TYPE_ALL="all"
TEST_TYPE_RUST_GO="rust_go"
TEST_TYPE_INTEG="integ"
TEST_TYPE_INTEG_TIER1="integ_tier1"
TEST_TYPE_INTEG_TIER2="integ_tier2"
TEST_TYPE_INTEG_SLOW="integ_slow"
TEST_TYPE_INTEG_KERNEL="integ_kernel"

FEDORA_IMAGE_DEV="quay.io/nmstate/fed-nmstate-dev:latest"
RAWHIDE_IMAGE_DEV="quay.io/nmstate/fed-nmstate-dev:rawhide"
CENTOS_8_STREAM_IMAGE_DEV="quay.io/nmstate/c8s-nmstate-dev"
CENTOS_9_STREAM_IMAGE_DEV="quay.io/nmstate/c9s-nmstate-dev"
CENTOS_10_STREAM_IMAGE_DEV="quay.io/nmstate/c10s-nmstate-dev"

COLLECT_LOGS="true"

PYTEST_OPTIONS="--verbose --verbose \
        --log-file-level=DEBUG \
        --log-level=INFO \
        --log-date-format='%Y-%m-%d %H:%M:%S' \
        --log-format='%(asctime)s %(filename)s:%(lineno)d %(levelname)s %(message)s' \
        --durations=5 \
        --log-file=$CONT_EXPORT_DIR/pytest-run.log"

NMSTATE_TEMPDIR=$(mktemp -d /tmp/nmstate-test-XXXX)

: ${CONTAINER_CMD:=podman}

test -t 1 && USE_TTY="-t"
source automation/tests-container-utils.sh
source automation/tests-machine-utils.sh

function print_help() {
    echo "Usage: $0 [OPTIONS]"
    echo "Target environment:"
    echo "  --el8, --el9, --el10, --fed, --rawhide"
    echo "                           Choose the container image"
    echo "  --machine                Run in baremetal instead"
    echo "Test options:"
    echo "  --test-type=TYPE         all (default), integ, integ_tier1, integ_tier2, integ_slow, integ_kernel, rust_go"
    echo "  --debug-shell            On failure open a debug shell, don't exit"
    echo "  --pytest-args=ARGS"
    echo "  --test-vdsm"
    echo "Installation options:"
    echo "  --use-installed-nmstate  Don't install nmstate, use the system's one"
    echo "  --compiled-rpms-dir=DIR  Install nmstate from rpm"
    echo "  --nm-rpm-dir=DIR         Install NetworkManager from rpm"
    echo "  --copr=REPO              Install NetworkManager from COPR"
    echo "Advanced:"
    echo "  --customize=CMD          Command to customize the container image"
    echo "  --artifacts-dir=DIR"
    echo "  --nolog"
    echo "  --pretest-exec=CMD"
    echo "  --help"
}

function pyclean {
    exec_cmd '
        find . -type f -name "*.py[co]" -delete
        find . -type d -name "__pycache__" -delete
    '
}

function exec_cmd {
    if [ ! -z ${RUN_BAREMETAL} ];then
        bash -c "$1"
    else
        container_exec "$1"
    fi
}

# Some command like DNF might fail in container, hence we retry on failure
function exec_cmd_with_retry {
    if [ ! -z ${RUN_BAREMETAL} ];then
        bash -c "$1"
    else
        container_exec_with_retry "$1"
    fi
}

function install_nmstate {
    if [ $INSTALL_NMSTATE == "true" ];then
        if [ -n "$COMPILED_RPMS_DIR" ];then
            exec_cmd "rpm -ivh ${COMPILED_RPMS_DIR}/*.rpm || exit 1"
        else
            exec_cmd "make srpm"
            exec_cmd_with_retry "dnf install -y 'dnf-command(builddep)'"
            exec_cmd_with_retry "dnf builddep -y *.src.rpm"
            exec_cmd "rm -f *.src.rpm"
            exec_cmd "make rpm"
            exec_cmd "rpm -ivh *.rpm"
        fi
    fi
}

function run_tests {
    if [ $TEST_TYPE == $TEST_TYPE_ALL ];then
        if [[ $CONTAINER_IMAGE == *"centos"* ]]; then
            echo "Running rust go binding test in $CONTAINER_IMAGE container is not " \
                 "support yet"
        else
            exec_cmd "make go_check"
        fi
        exec_cmd "cd $CONTAINER_WORKSPACE"
        exec_cmd "
            pytest \
            $PYTEST_OPTIONS \
            --junitxml=junit.integ.xml \
            --dump-states \
            tests/integration \
            ${nmstate_pytest_extra_args}"
        exec_cmd "cd $CONTAINER_WORKSPACE"
        exec_cmd "
          pytest \
            $PYTEST_OPTIONS \
            --junitxml=junit.integ_slow.xml \
            --dump-states \
            -m slow --runslow \
            tests/integration \
            ${nmstate_pytest_extra_args}"
    elif [ $TEST_TYPE == $TEST_TYPE_RUST_GO ];then
        if [[ $CONTAINER_IMAGE == *"centos"* ]]; then
            echo "Running rust go binding test in $CONTAINER_IMAGE container is not " \
                 "support yet"
        else
            exec_cmd "make go_check"
        fi
    elif [ $TEST_TYPE == $TEST_TYPE_INTEG ];then
        exec_cmd "cd $CONTAINER_WORKSPACE"
        exec_cmd "
            pytest \
            $PYTEST_OPTIONS \
            --junitxml=junit.integ.xml \
            --dump-states \
            tests/integration \
            ${nmstate_pytest_extra_args}"
    elif [ $TEST_TYPE == $TEST_TYPE_INTEG_TIER1 ];then
        exec_cmd "cd $CONTAINER_WORKSPACE"
        exec_cmd "
          pytest \
            $PYTEST_OPTIONS \
            --junitxml=junit.integ_tier1.xml \
            --dump-states \
            -m tier1 \
            tests/integration \
            ${nmstate_pytest_extra_args}"
    elif [ $TEST_TYPE == $TEST_TYPE_INTEG_TIER2 ];then
        exec_cmd "cd $CONTAINER_WORKSPACE"
        exec_cmd "
          pytest \
            $PYTEST_OPTIONS \
            --junitxml=junit.integ_tier2.xml \
            --dump-states \
            -m tier2 \
            tests/integration \
            ${nmstate_pytest_extra_args}"
    elif [ $TEST_TYPE == $TEST_TYPE_INTEG_KERNEL ];then
        exec_cmd "cd $CONTAINER_WORKSPACE"
        exec_cmd "
          pytest \
            $PYTEST_OPTIONS \
            --junitxml=junit.integ_kernel.xml \
            --dump-states \
            -m kernel \
            tests/integration \
            ${nmstate_pytest_extra_args}"
    elif [ $TEST_TYPE == $TEST_TYPE_INTEG_SLOW ];then
        exec_cmd "cd $CONTAINER_WORKSPACE"
        exec_cmd "
          pytest \
            $PYTEST_OPTIONS \
            --junitxml=junit.integ_slow.xml \
            --dump-states \
            -m slow --runslow \
            tests/integration \
            ${nmstate_pytest_extra_args}"
    else
        echo "Invalid --test-type value: '$TEST_TYPE'" >&2
        echo "Expected one of: all, integ, integ_tier1, integ_tier2, integ_slow, integ_kernel, rust_go" >&2
        exit 1
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
    if [ $COLLECT_LOGS == "true" ];then
        collect_artifacts
    fi
    remove_container
    remove_tempdir
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

function upgrade_nm_from_copr {
    local copr_repo=$1
    # The repoid for a Copr repo is the name with the slash replaces by a colon
    local copr_repo_id="copr:copr.fedorainfracloud.org:${copr_repo/\//:}"
    exec_cmd_with_retry "dnf5 install --assumeyes 'dnf5-command(copr)' || \
                         dnf install --assumeyes 'dnf-command(copr)'"
    exec_cmd "dnf copr enable --assumeyes ${copr_repo}"
    # centos-stream NetworkManager package is providing the alpha builds.
    # Sometimes it could be greater than the one packaged on Copr.
    exec_cmd "systemctl stop NetworkManager"
    exec_cmd "dnf remove --assumeyes --noautoremove NetworkManager"
    exec_cmd_with_retry "dnf install --assumeyes NetworkManager \
        NetworkManager-ovs --setopt='${copr_repo_id}.priority=1'"
    exec_cmd_with_retry "dnf install --assumeyes NetworkManager-libreswan"
}

function upgrade_nm_from_rpm_dir {
    local nm_rpm_dir=$1
    mkdir $EXPORT_DIR/nm_rpms || true
    find $nm_rpm_dir -name \*.rpm -exec cp -v {} "${EXPORT_DIR}/nm_rpms/" \;
    exec_cmd "systemctl stop NetworkManager"
    exec_cmd "dnf remove --assumeyes --noautoremove NetworkManager"
    exec_cmd_with_retry "dnf install -y ${CONT_EXPORT_DIR}/nm_rpms/*.rpm"
    exec_cmd_with_retry "rpm -q NetworkManager-libreswan || \
        dnf install -y NetworkManager-libreswan"
    # It is fragile for the system to have connectivity check enabled in the
    # integration testing, NM will add the penalty metric to the route when the
    # machine is not connected to the Internet
    exec_cmd "dnf remove --assumeyes NetworkManager-config-connectivity"
}

function run_customize_command {
    if [[ -n "$customize_cmd" ]];then
        exec_cmd "${customize_cmd}"
    fi
}

options=$(getopt --options "" \
    --long "customize:,pytest-args:,help,debug-shell,test-type:,\
    el8,el9,el10,centos-stream,fed,rawhide,copr:,artifacts-dir:,test-vdsm,\
    machine,use-installed-nmstate,compiled-rpms-dir:,nm-rpm-dir:,nolog,\
    pretest-exec:" \
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
    --nm-rpm-dir)
        shift
        nm_rpm_dir="$1"
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
        if [[ -z "$1" || "$1" =~ [[:space:]] ]]; then
            echo "Invalid --test-type value: '$1'" >&2
            echo "Expected a single token without whitespace" >&2
            exit 1
        fi
        TEST_TYPE="$1"
        ;;
    --el8)
        CONTAINER_IMAGE=$CENTOS_8_STREAM_IMAGE_DEV
        ;;
    --centos-stream)
        CONTAINER_IMAGE=$CENTOS_9_STREAM_IMAGE_DEV
        ;;
    --el9)
        CONTAINER_IMAGE=$CENTOS_9_STREAM_IMAGE_DEV
        ;;
    --el10)
        CONTAINER_IMAGE=$CENTOS_10_STREAM_IMAGE_DEV
        ;;
    --fed)
        CONTAINER_IMAGE=$FEDORA_IMAGE_DEV
        ;;
    --rawhide)
        CONTAINER_IMAGE=$RAWHIDE_IMAGE_DEV
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
    --nolog)
        COLLECT_LOGS="false"
        ;;
    --use-installed-nmstate)
        INSTALL_NMSTATE="false"
        ;;
    --compiled-rpms-dir)
        shift
        COMPILED_RPMS_DIR="$1"
        ;;
    --pretest-exec)
        shift
        PRETEST_EXEC="$1"
        ;;
    --help)
        print_help
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
: ${COMPILED_RPMS_DIR:=""}

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

if [[ -v nm_rpm_dir ]];then
    upgrade_nm_from_rpm_dir "${nm_rpm_dir}"
fi

check_services

if [ -n "$RUN_BAREMETAL" ];then
    trap run_exit ERR EXIT
fi

exec_cmd '(source /etc/os-release; echo $PRETTY_NAME); rpm -q NetworkManager'

pyclean
if [ -z "${RUN_BAREMETAL}" ];then
    copy_workspace_container
fi

install_nmstate

if [[ -v PRETEST_EXEC ]];then
    exec_cmd "$PRETEST_EXEC"
fi

run_tests
