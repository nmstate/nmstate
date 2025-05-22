#!/bin/bash -ex

# This script run lint and format checking on python script and YAML files.
# For rust code, please run `cargo clippy` and `cargo fmt` directly.

EXEC_PATH=$(dirname "$(realpath "$0")")
PROJECT_PATH="$(dirname $EXEC_PATH)"

cd $PROJECT_PATH

black \
    --check \
    --diff \
    rust/src/python/setup.py \
    rust/src/python/libnmstate \
    tests/integration

flake8 \
    --statistics \
    rust/src/python/setup.py \
    rust/src/python/libnmstate \
    tests/integration

yamllint examples/
