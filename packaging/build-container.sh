#! /bin/bash -e
# SPDX-License-Identifier: Apache 2.0

EXEC_PATH="$(dirname "$(realpath "$0")")"
PROJECT_PATH="$(dirname $EXEC_PATH)"

DEFAULT_BUILD_FLAGS="--no-cache --rm"
DEFAULT_TAG_PREFIX="quay.io/nmstate"

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

    build_tag="${tag_prefix}/${container_name}"
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
            c8s-nmstate-dev
        do
            rebuild_container "${extra_args}" "${container_name}"
        done
    else
        rebuild_container "${extra_args}" "${container_name}"
    fi
done
