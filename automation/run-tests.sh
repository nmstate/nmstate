#!/bin/bash -ex

EXEC_PATH=$(dirname "$(realpath "$0")")
PROJECT_PATH="$(dirname $EXEC_PATH)"
EXPORT_DIR="$PWD/exported-artifacts"
CONT_EXPORT_DIR="/exported-artifacts"

CONTAINER_WORKSPACE="/workspace/nmstate"

TEST_TYPE_ALL="all"
TEST_TYPE_FORMAT="format"
TEST_TYPE_LINT="lint"
TEST_TYPE_RUST_GO="rust_go"
TEST_TYPE_INTEG="integ"
TEST_TYPE_INTEG_TIER1="integ_tier1"
TEST_TYPE_INTEG_TIER2="integ_tier2"
TEST_TYPE_INTEG_SLOW="integ_slow"

FEDORA_IMAGE_DEV="docker.io/nmstate/fedora-nmstate-dev"
CENTOS_IMAGE_DEV="quay.io/nmstate/c8s-nmstate-dev"
CENTOS_STREAM_IMAGE_DEV="quay.io/nmstate/c8s-nmstate-dev"

CREATED_INTERFACES=""
INTERFACES="eth1 eth2"

PYTEST_OPTIONS="--verbose --verbose \
        --log-level=DEBUG \
        --log-date-format='%Y-%m-%d %H:%M:%S' \
        --log-format='%(asctime)s %(filename)s:%(lineno)d %(levelname)s %(message)s' \
        --durations=5 \
        --log-file=pytest-run.log"

NMSTATE_TEMPDIR=$(mktemp -d /tmp/nmstate-test-XXXX)

VETH_PEER_NS="nmstate_test"

: ${CONTAINER_CMD:=podman}
: ${KUBECTL_CMD:=k8s/kubectl.sh}

test -t 1 && USE_TTY="-t"
source automation/tests-container-utils.sh
source automation/tests-machine-utils.sh
source automation/tests-k8s-utils.sh

function pyclean {
    exec_cmd '
        find . -type f -name "*.py[co]" -delete
        find . -type d -name "__pycache__" -delete
    '
}

function exec_cmd {
    if [ ! -z ${RUN_BAREMETAL} ];then
        bash -c "$1"
    elif [ ! -z ${RUN_K8S} ]; then
        k8s::kubectl_exec "$1"
    else
        container_exec "$1"
    fi
}

function install_nmstate {
    if [ $INSTALL_NMSTATE == "true" ];then
        if [ -n "$COMPILED_RPMS_DIR" ];then
            exec_cmd "rpm -ivh ${COMPILED_RPMS_DIR}/*.rpm || exit 1"
        else
            exec_cmd "make rpm"
            exec_cmd "rpm -ivh *.rpm"
        fi
    fi
}

function run_tests {
    if [ $TEST_TYPE == $TEST_TYPE_ALL ] || \
       [ $TEST_TYPE == $TEST_TYPE_FORMAT ];then
        exec_cmd "tox -e black"
    fi

    if [ $TEST_TYPE == $TEST_TYPE_ALL ] || \
       [ $TEST_TYPE == $TEST_TYPE_LINT ];then
        exec_cmd "tox -e flake8,pylint,yamllint"
    fi

    if [ $TEST_TYPE == $TEST_TYPE_ALL ] || \
       [ $TEST_TYPE == $TEST_TYPE_RUST_GO ];then
        if [[ $CONTAINER_IMAGE == *"centos"* ]]; then
            echo "Running rust go binding test in $CONTAINER_IMAGE container is not " \
                 "support yet"
        else
            exec_cmd "make go_check"
        fi
    fi

    if [ $TEST_TYPE == $TEST_TYPE_ALL ] || \
       [ $TEST_TYPE == $TEST_TYPE_INTEG ];then
        exec_cmd "cd $CONTAINER_WORKSPACE"
        exec_cmd "
            pytest \
            $PYTEST_OPTIONS \
            --junitxml=junit.integ.xml \
            tests/integration \
            ${nmstate_pytest_extra_args}"
    fi

    if  [ $TEST_TYPE == $TEST_TYPE_INTEG_TIER1 ];then
        exec_cmd "cd $CONTAINER_WORKSPACE"
        exec_cmd "
          pytest \
            $PYTEST_OPTIONS \
            --junitxml=junit.integ_tier1.xml \
            -m tier1 \
            tests/integration \
            ${nmstate_pytest_extra_args}"
    fi

    if  [ $TEST_TYPE == $TEST_TYPE_INTEG_TIER2 ];then
        exec_cmd "cd $CONTAINER_WORKSPACE"
        exec_cmd "
          pytest \
            $PYTEST_OPTIONS \
            --junitxml=junit.integ_tier2.xml \
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
            --junitxml=junit.integ_slow.xml \
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
    if [ -n "${RUN_BAREMETAL}" ]; then
        teardown_network_environment
    elif [ -n "${RUN_K8S}" ]; then
        k8s::collect_artifacts
        k8s::cleanup
    else
        collect_artifacts
        remove_container
        remove_tempdir
    fi
}

function modprobe_ovs {
    if [ -z "${RUN_K8S}" ]; then
        lsmod | grep -q ^openvswitch || modprobe openvswitch || { echo 1>&2 "Please run 'modprobe openvswitch' as root"; exit 1; }
    fi
    #TODO: Install ovs on k8s cluster
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

function check_iface_exist {
    exec_cmd "ip link | grep -q ' $1'"
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

function clean_dnf_cache {
    # Workaround for dnf failure:
    # [Errno 2] No such file or directory: '/var/cache/dnf/metadata_lock.pid'
    if [[ "$CI" == "true" ]];then
        exec_cmd "rm -fv /var/cache/dnf/metadata_lock.pid"
        exec_cmd "dnf clean all"
        exec_cmd "dnf makecache || :"
    fi
}

function upgrade_nm_from_copr {
    local copr_repo=$1
    # The repoid for a Copr repo is the name with the slash replaces by a colon
    local copr_repo_id="copr:copr.fedorainfracloud.org:${copr_repo/\//:}"
    clean_dnf_cache
    exec_cmd "command -v dnf && plugin='dnf-command(copr)' || plugin='yum-plugin-copr'; yum install --assumeyes \$plugin;"
    exec_cmd "yum copr enable --assumeyes ${copr_repo}"
    if [ $CONTAINER_IMAGE == $CENTOS_STREAM_IMAGE_DEV ];then
	# centos-stream NetworkManager package is providing the alpha builds.
	# Sometimes it could be greater than the one packaged on Copr.
        exec_cmd "dnf remove --assumeyes --noautoremove NetworkManager"
        exec_cmd "dnf install --assumeyes NetworkManager NetworkManager-team NetworkManager-ovs --disablerepo '*' --enablerepo '${copr_repo_id}'"
    fi
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
    --long "customize:,pytest-args:,help,debug-shell,test-type:,\
    el8,centos-stream,copr:,artifacts-dir:,test-vdsm,machine,k8s,\
    use-installed-nmstate,compiled-rpms-dir:" \
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
    --centos-stream)
        CONTAINER_IMAGE=$CENTOS_STREAM_IMAGE_DEV
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
    --k8s)
        RUN_K8S="true"
        ;;
    --use-installed-nmstate)
        INSTALL_NMSTATE="false"
        ;;
    --compiled-rpms-dir)
        shift
        COMPILED_RPMS_DIR="$1"
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
        echo "     * $TEST_TYPE_RUST_GO"
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
: ${COMPILED_RPMS_DIR:=""}

if [ $TEST_TYPE != $TEST_TYPE_ALL ] && \
   [ $TEST_TYPE != $TEST_TYPE_LINT ] && \
   [ $TEST_TYPE != $TEST_TYPE_FORMAT ];then
    modprobe_ovs
fi

if [ -n "${RUN_BAREMETAL}" ];then
    CONTAINER_WORKSPACE="."
    run_customize_command
    start_machine_services
elif [ -n "${RUN_K8S}" ]; then
    export CONTAINER_CMD=docker
    k8s::start_cluster
    k8s::pre_test_setup
    run_customize_command
else
    container_pre_test_setup
    run_customize_command
fi

if [[ -v copr_repo ]];then
    upgrade_nm_from_copr "${copr_repo}"
fi

if [ -z "${RUN_K8S}" ]; then
    check_services
fi

if [ $TEST_TYPE != $TEST_TYPE_ALL ] && \
   [ $TEST_TYPE != $TEST_TYPE_LINT ] && \
   [ $TEST_TYPE != $TEST_TYPE_FORMAT ];then
    prepare_network_environment
fi

if [ -n "$RUN_BAREMETAL" ];then
    trap run_exit ERR EXIT
fi

exec_cmd '(source /etc/os-release; echo $PRETTY_NAME); rpm -q NetworkManager'

pyclean
if [ -z "${RUN_BAREMETAL}" ] && [ -z "${RUN_K8S}" ];then
    copy_workspace_container
fi

if [ $TEST_TYPE != $TEST_TYPE_ALL ] && \
   [ $TEST_TYPE != $TEST_TYPE_LINT ] && \
   [ $TEST_TYPE != $TEST_TYPE_FORMAT ];then
    install_nmstate
fi
run_tests
