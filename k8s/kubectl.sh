#!/bin/bash

source ./k8s/kubevirtci.sh
kubevirtci::install

$(kubevirtci::path)/cluster-up/kubectl.sh "$@"
