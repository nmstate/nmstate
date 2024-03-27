# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright 2021 Red Hat
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

from .clib_wrapper import retrieve_net_state_json


def show(
    *, kernel_only=False, include_status_data=False, include_secrets=False
):
    return json.loads(
        retrieve_net_state_json(
            kernel_only=kernel_only,
            include_status_data=include_status_data,
            include_secrets=include_secrets,
        )
    )


def show_running_config(include_secrets=False):
    return json.loads(
        retrieve_net_state_json(
            include_secrets=include_secrets,
            running_config_only=True,
        )
    )
