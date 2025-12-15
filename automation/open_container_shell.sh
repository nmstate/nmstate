#! /bin/bash -e
# SPDX-License-Identifier: Apache 2.0

: ${CONTAINER_CMD:=podman}


container_ps() {
    $CONTAINER_CMD ps --format '{{.ID}} {{.Image}}' | grep nmstate-dev
}

number_of_containers="$(container_ps | wc -l)"

if [[ "${number_of_containers}" == "0" ]]
then

    echo >/dev/stderr \
        "ERROR: no containers found"
    exit 1
elif [[ "${number_of_containers}" != "1" ]]
then
    echo >/dev/stderr \
        "WARNING: ${number_of_containers} of containers found, using first"
fi

container_id="$(container_ps \
    | head -n 1 | cut -d " " -f 1)"
$CONTAINER_CMD exec -it "${container_id}" /bin/bash
