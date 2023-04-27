#!/bin/bash -e

GOFLAGS=-mod=mod go run sigs.k8s.io/controller-tools/cmd/controller-gen@v0.8.0 $@
