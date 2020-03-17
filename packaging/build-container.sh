#! /bin/bash -e
#
# Copyright 2019 Red Hat, Inc.
#
# This file is part of nmstate
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

EXEC_PATH="$(dirname "$(realpath "$0")")"
PROJECT_PATH="$(dirname $EXEC_PATH)"

DEFAULT_BUILD_FLAGS="--no-cache --rm"
DEFAULT_TAG_PREFIX="docker.io/nmstate"

: ${CONTAINER_CMD:=podman}

options=$(getopt --options "" \
    --longoptions extra-args: \
    -- "${@}")


eval set -- "${options}"
while :
do
    case "${1}" in
        --extra-args)
            shift
            extra_args="${1}"
            ;;
        --)
            shift
            break
            ;;
    esac
    shift
done

rebuild_container() {
    local container_name
    local extra_args

    extra_args="${1}"
    shift

    # remove leading tag prefix
    container_name="${1#*/}"

    # remove container name suffix
    echo "${1}" | grep -q "/" && tag_prefix="${1%/*}"

    # assign default value in case argument did not contain a tag prefix
    : ${tag_prefix:=${DEFAULT_TAG_PREFIX}}

    build_tag="${tag_prefix}/${container_name}:nmstate-0.2"
    container_spec="$PROJECT_PATH/packaging/Dockerfile.${container_name}"

    echo >/dev/stderr "Building '${container_spec}' into tag '${build_tag}'..."

    $CONTAINER_CMD build ${DEFAULT_BUILD_FLAGS} ${extra_args} \
        -t "${build_tag}" \
        -f "${container_spec}" "$PROJECT_PATH/packaging"
}

for container_name in "${@}"
do
    if [[ "${container_name}" == "all" ]]
    then
        for container_name in \
            fedora-nmstate-dev \
            centos8-nmstate-dev
        do
            rebuild_container "${extra_args}" "${container_name}"
        done
    else
        rebuild_container "${extra_args}" "${container_name}"
    fi
done
