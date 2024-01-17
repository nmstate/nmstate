#!/bin/bash -ex
# SPDX-License-Identifier: Apache-2.0

if [ "$(objdump -p $1 |sed -ne 's/.*SONAME \+\(libnmstate.\+\)/\1/p')" \
    != "libnmstate.so.2" ];then
    exit 1
fi
