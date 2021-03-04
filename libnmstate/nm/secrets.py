#
# Copyright (c) 2021 Red Hat, Inc.
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

from .common import GLib


def get_secrets(context, nm_profile, action, setting_name):
    secrets = {}
    context.register_async(action, fast=True)
    user_data = (context, secrets, action, setting_name)
    nm_profile.get_secrets_async(
        setting_name,
        context.cancellable,
        _get_secrets_callback,
        user_data,
    )
    context.wait_all_finish()
    return secrets


def _get_secrets_callback(nm_profile, result, user_data):
    context, secrets, action, setting_name = user_data

    try:
        nm_secrets = nm_profile.get_secrets_finish(result)
    except GLib.Error as e:
        return context.fail(NmstateLibnmError(f"{action} failed: error={e}"))

    context.finish_async(action)
    secrets.update(nm_secrets[setting_name])
