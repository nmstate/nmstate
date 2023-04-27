#!/usr/bin/env bash

set -xe

if [[ -n "$(git status --porcelain)" ]]; then
    echo "Git missing generated files"
    git status --porcelain
    exit 1
fi
