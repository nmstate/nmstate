#!/bin/bash -ex

PROJECT_PATH=$(dirname $(realpath "$(dirname "$(realpath "$0")")/../"))
CONTAINER_WORKSPACE="/workspace/nmstate"
OUTPUT_DIR="$PWD/rpms"
CONTAINER_OUTPUT_DIR="$CONTAINER_WORKSPACE/rpms"

CONTAINER_IMG="quay.io/nmstate/c8s-nmstate-build"

docker run -v $PROJECT_PATH:$CONTAINER_WORKSPACE:rw \
    $CONTAINER_IMG /bin/bash -xe -c \
    "cd $CONTAINER_WORKSPACE && SKIP_VENDOR_CREATION=1 make rpm"

mkdir $OUTPUT_DIR || true
mv -v *.rpm $OUTPUT_DIR/
