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

PRETEST_EXEC="true"
COPR_ARG=""

if [ $OS_TYPE == "c8s" ];then
    CONTAINER_IMAGE="quay.io/nmstate/c8s-nmstate-dev"
    TEST_ARG="$TEST_ARG --compiled-rpms-dir rpms/el8"
elif [ $OS_TYPE == "fed" ];then
    CONTAINER_IMAGE="quay.io/nmstate/fed-nmstate-dev:latest"
elif [ $OS_TYPE == "c9s" ];then
    CONTAINER_IMAGE="quay.io/nmstate/c9s-nmstate-dev"
    TEST_ARG="$TEST_ARG --compiled-rpms-dir rpms/el9"
elif [ $OS_TYPE == "c10s" ];then
    CONTAINER_IMAGE="quay.io/nmstate/c10s-nmstate-dev"
else
    echo "Invalid OS type ${OS_TYPE}"
    exit 1
fi

if [ $NM_TYPE == "nm_main" ];then
    TEST_ARG="$TEST_ARG --copr networkmanager/NetworkManager-main"
fi

if [ $NM_TYPE == "nm_1.42" ];then
    TEST_ARG="$TEST_ARG --copr networkmanager/NetworkManager-1.42"
    PRETEST_EXEC='dnf copr enable -y nmstate/nm-libreswan-rhel9.2; dnf install -y NetworkManager-libreswan-1.2.14-4.el9'
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
        --pretest-exec "$PRETEST_EXEC"
