#
# Copyright (c) 2020 Red Hat, Inc.
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
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#

# This file is targeting:
#   * NM.RemoteConnection, NM.SimpleConnection releated

import logging

from .common import NM
from .device import list_devices


def get_all_applied_configs(context):
    applied_configs = {}
    for nm_dev in list_devices(context.client):
        if (
            nm_dev.get_state()
            in (NM.DeviceState.ACTIVATED, NM.DeviceState.IP_CONFIG,)
            and nm_dev.get_managed()
        ):
            iface_name = nm_dev.get_iface()
            if iface_name:
                action = f"Retrieve applied config: {iface_name}"
                context.register_async(action, fast=True)
                nm_dev.get_applied_connection_async(
                    flags=0,
                    cancellable=context.cancellable,
                    callback=_get_applied_config_callback,
                    user_data=(iface_name, action, applied_configs, context),
                )
    context.wait_all_finish()
    return applied_configs


def _get_applied_config_callback(nm_dev, result, user_data):
    iface_name, action, applied_configs, context = user_data
    context.finish_async(action)
    try:
        remote_conn, _ = nm_dev.get_applied_connection_finish(result)
        applied_configs[nm_dev.get_iface()] = remote_conn
    except Exception as e:
        logging.warning(
            "Failed to retrieve applied config for device "
            f"{iface_name}: {e}"
        )
