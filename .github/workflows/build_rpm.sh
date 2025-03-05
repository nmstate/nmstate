#!/bin/bash -ex

PROJECT_PATH=$(dirname $(realpath "$(dirname "$(realpath "$0")")/../"))
CONTAINER_WORKSPACE="/workspace/nmstate"
OUTPUT_DIR="$PWD/rpms"
CONTAINER_OUTPUT_DIR="$CONTAINER_WORKSPACE/rpms"

CONTAINER_C8S_IMG="quay.io/nmstate/c8s-nmstate-build"
CONTAINER_C9S_IMG="quay.io/nmstate/c9s-nmstate-build"


if [ $1 == "el8" ];then
    # pull the image to local, and retry if fails up to 5 times
    for i in {1..5};do
        ${CONTAINER_CMD} pull $CONTAINER_C8S_IMG && break
    done

    podman run -v $PROJECT_PATH:$CONTAINER_WORKSPACE:rw \
        $CONTAINER_C8S_IMG /bin/bash -c \
        "cd $CONTAINER_WORKSPACE && make rpm"

    mkdir -p $OUTPUT_DIR/el8 || true
    mv -v *.rpm $OUTPUT_DIR/el8/
else
    # pull the image to local, and retry if fails up to 5 times
    for i in {1..5};do
        ${CONTAINER_CMD} pull $CONTAINER_C9S_IMG && break
    done

    podman run -v $PROJECT_PATH:$CONTAINER_WORKSPACE:rw \
        $CONTAINER_C9S_IMG /bin/bash -c \
        "cd $CONTAINER_WORKSPACE && make rpm"

    mkdir -p $OUTPUT_DIR/el9 || true
    mv -v *.rpm $OUTPUT_DIR/el9/
fi
