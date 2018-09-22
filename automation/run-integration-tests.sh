#!/bin/sh -ex

EXEC_PATH=$(dirname "$(realpath "$0")")
PROJECT_PATH="$(dirname $EXEC_PATH)"
DOCKER_IMAGE="nmstate/centos7-nmstate-dev"

test -t 1 && USE_TTY="-t"

function remove_container {
    res=$?
    [ "$res" -ne 0 ] && echo "*** ERROR: $res"
    docker stop $CONTAINER_ID
    docker rm $CONTAINER_ID
}

function pyclean {
        find . -type f -name "*.py[co]" -delete
        find . -type d -name "__pycache__" -delete
}

cd "$EXEC_PATH"

CONTAINER_ID="$(docker run --privileged -d -v /sys/fs/cgroup:/sys/fs/cgroup:ro -v $PROJECT_PATH:/workspace/nmstate $DOCKER_IMAGE)"
trap remove_container EXIT

pyclean
docker exec $USE_TTY -i $CONTAINER_ID /bin/bash -c 'cd /workspace/nmstate && tox -e check-integ-py27'
