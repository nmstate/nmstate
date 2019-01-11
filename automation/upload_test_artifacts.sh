#!/bin/bash -ex

SCP_SRV="grisge.info"
SCP_BASEDIR="upload"
SCP_USERNAME="nmstate"
CODE_BASE_DIR="/workspace/nmstate"
SCP_KEY="$CODE_BASE_DIR/automation/id_rsa_nmstate"
BASE_URL="http://grisge.info/nmstate"

if [ -z "$TRAVIS_JOB_ID" ];then
    echo "Need to be run in traivs-CI, quiting"
    exit 1
fi

TMP_DIR=$(mktemp -d)
LOG_DIR=$TMP_DIR/$TRAVIS_JOB_ID
mkdir $LOG_DIR
LOG_FILE_LIST="$LOG_DIR/LOG_FILE_LIST.txt"
LOG_TAR_FILE="$LOG_DIR/nmstate_test_$TRAVIS_JOB_ID.tar.xz"

trap 'rm -rf "$TMP_DIR"' INT TERM HUP EXIT


cd $CODE_BASE_DIR

git ls-files --full-name -o  --exclude=*.pyc --exclude=htmlcov* \
    --exclude=*.py --exclude=*.py > $LOG_FILE_LIST
tar cfJ $LOG_TAR_FILE -T $LOG_FILE_LIST

scp -o StrictHostKeyChecking=no -r -i $SCP_KEY \
    $LOG_DIR "$SCP_USERNAME@$SCP_SRV:$SCP_BASEDIR/"

echo "Log uploaded to $BASE_URL/$TRAVIS_JOB_ID"
