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
TEST_TYPE_INTEG_RUST="integ_rust"

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
        if [ -n "$COMPILED_RPMS_DIR" ];then
            exec_cmd "rpm -ivh ${COMPILED_RPMS_DIR}/*.rpm || exit 1"
        else
            exec_cmd '
                rpm -ivh `./packaging/make_rpm.sh|tail -1 || exit 1`
            '
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
       [ $TEST_TYPE == $TEST_TYPE_UNIT_PY36 ];then
        if [[ $CONTAINER_IMAGE == $CENTOS_STREAM_IMAGE_DEV ]]; then
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

    if [ $TEST_TYPE == $TEST_TYPE_ALL ] || \
       [ $TEST_TYPE == $TEST_TYPE_INTEG_RUST ];then
        exec_cmd "cd $CONTAINER_WORKSPACE"
        exec_cmd "dnf remove python3-libnmstate -y"
        exec_cmd "
          env  \
          PYTHONPATH=$CONTAINER_WORKSPACE/rust/src/python \
          pytest \
            $PYTEST_OPTIONS \
            tests/integration/static_ip_address_test.py \
            tests/integration/preserve_ip_config_test.py \
            tests/integration/dns_test.py \
            tests/integration/mac_vlan_test.py \
            tests/integration/mac_vtap_test.py \
            tests/integration/vxlan_test.py \
            tests/integration/veth_test.py \
            ${nmstate_pytest_extra_args}"
        exec_cmd "
          env  \
          PYTHONPATH=$CONTAINER_WORKSPACE/rust/src/python \
          pytest \
            $PYTEST_OPTIONS \
            tests/integration/ovs_test.py \
            -k '\
            test_create_and_remove_ovs_bridge_with_min_desired_state or \
            test_create_and_save_ovs_bridge_then_remove_and_apply_again or \
            test_create_and_remove_ovs_bridge_options_specified or \
            test_create_and_remove_ovs_bridge_with_a_system_port or \
            test_create_and_remove_ovs_bridge_with_internal_port_static_ip_and_mac or \
            ovsdb' \
            ${nmstate_pytest_extra_args}"
        exec_cmd "
          env  \
          PYTHONPATH=$CONTAINER_WORKSPACE/rust/src/python \
          pytest \
            $PYTEST_OPTIONS \
            tests/integration/ethernet_mtu_test.py \
            -k '\
            test_increase_iface_mtu or \
            test_decrease_iface_mtu or \
            test_upper_limit_jumbo_iface_mtu or \
            test_increse_more_than_jumbo_iface_mtu or \
            test_decrease_to_ipv6_min_ethernet_frame_size_iface_mtu or \
            test_decrease_to_lower_than_min_ipv6_iface_mtu or \
            test_mtu_without_ipv6 or \
            test_change_mtu_with_stable_link_up or \
            test_empty_state_preserve_the_old_mtu' \
            ${nmstate_pytest_extra_args}"
        exec_cmd "
          env  \
          PYTHONPATH=$CONTAINER_WORKSPACE/rust/src/python \
          pytest \
            $PYTEST_OPTIONS \
            tests/integration/vlan_test.py \
            -k '\
            test_add_and_remove_vlan or \
            test_vlan_iface_uses_the_mac_of_base_iface or \
            test_add_and_remove_two_vlans_on_same_iface or \
            test_two_vlans_on_eth1_change_base_iface_mtu or \
            test_two_vlans_on_eth1_change_mtu or \
            test_two_vlans_on_eth1_change_mtu_rollback or \
            test_rollback_for_vlans or \
            test_set_vlan_iface_down or \
            test_add_new_base_iface_with_vlan' \
            ${nmstate_pytest_extra_args}"
        exec_cmd "
          env  \
          PYTHONPATH=$CONTAINER_WORKSPACE/rust/src/python \
          pytest \
            $PYTEST_OPTIONS \
            tests/integration/linux_bridge_test.py \
            -k '\
            not test_linux_bridge_multicast_router and \
            not test_linux_bridge_over_bond_over_port_in_one_transaction and \
            not test_explicitly_ignore_a_bridge_port' \
            ${nmstate_pytest_extra_args}"
        exec_cmd "
          env  \
          PYTHONPATH=$CONTAINER_WORKSPACE/rust/src/python \
          pytest \
            $PYTEST_OPTIONS \
            tests/integration/interface_common_test.py \
            -k '\
            test_enable_and_disable_accept_all_mac_addresses' \
            ${nmstate_pytest_extra_args}"
        exec_cmd "
          env  \
          PYTHONPATH=$CONTAINER_WORKSPACE/rust/src/python \
          pytest \
            $PYTEST_OPTIONS \
            tests/integration/route_test.py \
            -k 'not test_route_rule_add_with_auto_route_table_id ' \
            ${nmstate_pytest_extra_args}"
        exec_cmd "
          env  \
          PYTHONPATH=$CONTAINER_WORKSPACE/rust/src/python \
          pytest \
            $PYTEST_OPTIONS \
            tests/integration/bond_test.py \
            -k '\
            not test_preserve_bond_after_bridge_removal and \
            not test_bond_mac_restriction_without_mac_in_desire and \
            not test_bond_mac_restriction_with_mac_in_desire and \
            not test_bond_mac_restriction_in_desire_mac_in_current and \
            not test_remove_mode4_bond_and_create_mode5_with_the_same_port and \
            not test_bond_mac_restriction_in_current_mac_in_desire' \
            ${nmstate_pytest_extra_args}"
        exec_cmd "
          env  \
          PYTHONPATH=$CONTAINER_WORKSPACE/rust/src/python \
          pytest \
            $PYTEST_OPTIONS \
            tests/integration/dynamic_ip_test.py \
            -k 'not test_show_running_config_does_not_include_auto_config' \
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

function install_deps {
    exec_cmd "dnf install -y \
        python3-varlink libvarlink-util python3-jsonschema \
        python3-nispor python3dist\(ovs\);"
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
        echo "     * $TEST_TYPE_INTEG_RUST"
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
: ${CONTAINER_IMAGE:=$CENTOS_STREAM_IMAGE_DEV}
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
    #start_machine_services
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

if [[ "$CI" != "true" ]];then
    install_deps
fi

exec_cmd '(source /etc/os-release; echo $PRETTY_NAME); rpm -q NetworkManager'

dump_network_info

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
