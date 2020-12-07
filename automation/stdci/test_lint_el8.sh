#!/bin/bash

export CI=true
export CONTAINER_CMD=docker
./automation/run-tests.sh --el8 --test-type lint
