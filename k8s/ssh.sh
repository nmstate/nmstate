#!/bin/bash

set -e

source ./k8s/kubevirtci.sh
kubevirtci::install

$(kubevirtci::path)/cluster-up/cli.sh ssh "$@"
