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
# You should have received a copy of the GNU Lesse General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

docker_ps() {
    docker ps --format '{{.ID}} {{.Image}}' | grep nmstate-dev
}

number_of_containers="$(docker_ps | wc -l)"

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

container_id="$(docker_ps \
    | head -n 1 | cut -d " " -f 1)"
docker exec -it "${container_id}" /bin/bash
