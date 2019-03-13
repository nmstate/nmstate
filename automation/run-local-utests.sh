#!/bin/bash

PROJECT=${PROJECT:-${PWD##*/}}
TOXWORKDIR="$HOME/.cache/.tox-$PROJECT"
CONTAINER_IMAGE="localhost/$PROJECT/centos7-$PROJECT-utest"

mkdir -p "$TOXWORKDIR"

podman run \
       --rm \
       -ti \
       -v $PWD:/workspace/$PROJECT:Z \
       -v $TOXWORKDIR:$TOXWORKDIR:Z \
       $CONTAINER_IMAGE \
       /bin/bash -c " \
         cp -rf /workspace/$PROJECT /tmp/ \
         && \
         cd /tmp/$PROJECT \
         && \
         tox --workdir $TOXWORKDIR"
