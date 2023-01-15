#!/bin/bash -x

JOB_TYPE="$1"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
TEST_ARTIFACTS_DIR="${SCRIPT_DIR}/../../test_artifacts"
TEST_CMD="${SCRIPT_DIR}/../../automation/run-tests.sh"

if [ -z "$JOB_TYPE" ];then
    echo 'Need $1 as JOB type type'
    exit 1
fi


IFS='-' read -r -a array <<< "$JOB_TYPE"

OS_TYPE="${array[0]}"
NM_TYPE="${array[1]}"
TEST_TYPE="${array[2]}"
TEST_ARG="--test-type $TEST_TYPE"

CUSTOMIZE_ARG=""
COPR_ARG=""
RPM_DIR="rpms/el8"

if [ $OS_TYPE == "c8s" ];then
    CONTAINER_IMAGE="quay.io/nmstate/c8s-nmstate-dev"
elif [ $OS_TYPE == "c9s" ];then
    CONTAINER_IMAGE="quay.io/nmstate/c9s-nmstate-dev"
    RPM_DIR="rpms/el9"
elif [ $OS_TYPE == "ovs2_11" ];then
    CONTAINER_IMAGE="quay.io/nmstate/c8s-nmstate-dev"
    CUSTOMIZE_ARG='--customize=
        dnf remove -y openvswitch2.11 python3-openvswitch2.11;
        dnf install -y openvswitch2.13 python3-openvswitch2.13;
        systemctl restart openvswitch'
elif [ $OS_TYPE == "vdsm_el8" ]; then
    CONTAINER_IMAGE="quay.io/ovirt/vdsm-network-tests-functional"
else
    echo "Invalid OS type ${OS_TYPE}"
    exit 1
fi

if [ $NM_TYPE == "nm_main" ];then
    COPR_ARG="--copr networkmanager/NetworkManager-main"
fi

if [ $NM_TYPE == "nm_1.36" ];then
    COPR_ARG="--copr networkmanager/NetworkManager-1.36"
fi

if [ $TEST_TYPE == "vdsm" ];then
    TEST_ARG="--test-vdsm"
fi

mkdir $TEST_ARTIFACTS_DIR || exit 1

env \
    # Workaround for https://github.com/actions/runner/issues/1994
    XDG_RUNTIME_DIR="" \
    CONTAINER_IMAGE="$CONTAINER_IMAGE" \
    CONTAINER_CMD="podman" \
    CI="true" \
    BRANCH_NAME="$GITHUB_BASE_REF" \
    CODECOV_TOKEN="$CODECOV_TOKEN" \
    GITHUB_ACTIONS="$GITHUB_ACTIONS"\
    GITHUB_REF="$GITHUB_REF"\
    GITHUB_REPOSITORY="$GITHUB_REPOSITORY"\
    GITHUB_HEAD_REF="$GITHUB_HEAD_REF"\
    GITHUB_SHA="$GITHUB_SHA"\
    GITHUB_RUN_ID="$GITHUB_RUN_ID"\
    $TEST_CMD \
        $TEST_ARG \
        --artifacts-dir $TEST_ARTIFACTS_DIR \
        --compiled-rpms-dir $RPM_DIR \
        $COPR_ARG "$CUSTOMIZE_ARG"
