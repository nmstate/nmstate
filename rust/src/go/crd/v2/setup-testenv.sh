#!/bin/bash

# This script install ectd and kube-apiserver at build/_output/bin the steps
# has being copied from kubebuilder container [1]
#
# [1] https://github.com/kubernetes-sigs/kubebuilder/blob/master/build/thirdparty/linux/Dockerfile

set -xe

etcd_version=v3.4.27
apisever_version=v1.26.0
output_dir=.k8s
bin_dir=$output_dir/bin/

etcd_tarball=etcd-${etcd_version}-linux-amd64.tar.gz
apiserver_tarball=kubernetes-server-linux-amd64.tar.gz

mkdir -p $bin_dir

if [ ! -f $bin_dir/kube-apiserver ]; then
    curl -L https://dl.k8s.io/$apisever_version/$apiserver_tarball | tar xz -C $output_dir
    mv $output_dir/kubernetes/server/bin/kube-apiserver $bin_dir
fi

if [ ! -f $bin_dir/etcd ]; then
    curl -L https://github.com/coreos/etcd/releases/download/$etcd_version/$etcd_tarball | tar xz -C $output_dir
    mv $output_dir/etcd-$etcd_version-linux-amd64/etcd $bin_dir
fi
