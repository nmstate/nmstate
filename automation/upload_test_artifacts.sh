#!/bin/bash -ex

SCP_SRV="grisge.info"
SCP_BASEDIR="upload"
SCP_USERNAME="nmstate"
SCP_KEY="./automation/upload_test_artifacts.key"
BASE_URL="https://grisge.info/nmstate"
ARTIFACTS_DIR="exported-artifacts"

if [ -z "$TRAVIS_JOB_ID" ];then
    echo "Need to be run in travis-CI, quiting"
    exit 1
fi

TMP_DIR=$(mktemp -d)
LOG_DIR=$TMP_DIR/$TRAVIS_JOB_ID
mkdir $LOG_DIR
LOG_TAR_FILE="$LOG_DIR/nmstate_test_$TRAVIS_JOB_ID.tar.xz"

trap 'rm -rf "$TMP_DIR"' INT TERM HUP EXIT

tar cfJv $LOG_TAR_FILE $ARTIFACTS_DIR
chmod 600 $SCP_KEY
scp -o StrictHostKeyChecking=no -r -i $SCP_KEY \
    $LOG_DIR "$SCP_USERNAME@$SCP_SRV:$SCP_BASEDIR/"

echo "Log uploaded to $BASE_URL/$TRAVIS_JOB_ID"
