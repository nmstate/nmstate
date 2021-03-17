#!/bin/bash

set -ex

source ./k8s/kubevirtci.sh
kubevirtci::install

$(kubevirtci::path)/cluster-up/down.sh
