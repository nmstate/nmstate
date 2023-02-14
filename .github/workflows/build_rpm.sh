#!/bin/bash -ex

PROJECT_PATH=$(dirname $(realpath "$(dirname "$(realpath "$0")")/../"))
CONTAINER_WORKSPACE="/workspace/nmstate"
OUTPUT_DIR="$PWD/rpms"
CONTAINER_OUTPUT_DIR="$CONTAINER_WORKSPACE/rpms"

CONTAINER_IMG="quay.io/nmstate/c8s-nmstate-build"

mkdir $OUTPUT_DIR || true

podman run -v $PROJECT_PATH:$CONTAINER_WORKSPACE:rw \
    -v $OUTPUT_DIR:$CONTAINER_OUTPUT_DIR:rw \
    $CONTAINER_IMG /bin/bash -c "cd $CONTAINER_OUTPUT_DIR && \
    $CONTAINER_WORKSPACE/packaging/make_rpm.sh"
