#!/bin/bash -x

JOB_TYPE="$1"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
TEST_ARTIFACTS_DIR="${SCRIPT_DIR}/../../test_artifacts"
TEST_CMD="${SCRIPT_DIR}/../../automation/run-tests.sh"

if [ -z "$JOB_TYPE" ];then
    echo 'Need $1 as JOB type type'
    exit 1
fi


IFS=':' read -r -a array <<< "$JOB_TYPE"

OS_TYPE="${array[0]}"
NM_TYPE="${array[1]}"
TEST_TYPE="${array[2]}"

if [ $OS_TYPE == "el8" ];then
    export CONTAINER_IMAGE="docker.io/nmstate/centos8-nmstate-dev"
elif [ $OS_TYPE == "stream" ];then
    export CONTAINER_IMAGE="docker.io/nmstate/centos-stream-nmstate-dev"
else
    echo "Invalid OS type ${OS_TYPE}"
    exit 1
fi

if [ $NM_TYPE == "nm_master" ];then
    COPR_ARG="--copr networkmanager/NetworkManager-master"
else
    COPR_ARG=""
fi

mkdir $TEST_ARTIFACTS_DIR || exit 1

sudo env \
    CONTAINER_IMAGE="$CONTAINER_IMAGE" \
    CONTAINER_CMD="docker" \
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
        --pytest-args='-x' \
        --test-type $TEST_TYPE \
        --artifacts-dir $TEST_ARTIFACTS_DIR \
        $COPR_ARG
