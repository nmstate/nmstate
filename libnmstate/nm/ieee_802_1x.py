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

from libnmstate.error import NmstateLibnmError
from libnmstate.schema import Ieee8021X

from .common import NM
from .common import GLib

_NM_PROP_MAP = {
    NM.SETTING_802_1X_IDENTITY: Ieee8021X.IDENTITY,
    NM.SETTING_802_1X_EAP: Ieee8021X.EAP_METHODS,
    NM.SETTING_802_1X_PRIVATE_KEY: Ieee8021X.PRIVATE_KEY,
    NM.SETTING_802_1X_CLIENT_CERT: Ieee8021X.CLIENT_CERT,
    NM.SETTING_802_1X_CA_CERT: Ieee8021X.CA_CERT,
}


def get_802_1x_info(context, nm_ac):
    if not nm_ac:
        return {}
    nm_profile = nm_ac.get_connection()
    if not nm_profile:
        return {}
    nm_setting = nm_profile.get_setting_802_1x()
    if not nm_setting:
        return {}

    secrets = _get_secrets(context, nm_profile)

    info = {}
    for nm_prop, key_name in _NM_PROP_MAP.items():
        value = getattr(nm_setting.props, nm_prop)
        if isinstance(value, GLib.Bytes):
            value = _file_path_from_glib_bytes(value)
        info[key_name] = value

    if secrets.get(NM.SETTING_802_1X_PRIVATE_KEY_PASSWORD):
        info[Ieee8021X.PRIVATE_KEY_PASSWORD] = secrets[
            NM.SETTING_802_1X_PRIVATE_KEY_PASSWORD
        ]

    return {Ieee8021X.CONFIG_SUBTREE: info}


def create_802_1x_setting(ieee_802_1x_conf):
    nm_setting = NM.Setting8021x.new()

    for nm_prop, key_name in (
        (NM.SETTING_802_1X_IDENTITY, Ieee8021X.IDENTITY),
        (NM.SETTING_802_1X_EAP, Ieee8021X.EAP_METHODS),
        (
            NM.SETTING_802_1X_PRIVATE_KEY_PASSWORD,
            Ieee8021X.PRIVATE_KEY_PASSWORD,
        ),
    ):
        if key_name in ieee_802_1x_conf:
            setattr(nm_setting.props, nm_prop, ieee_802_1x_conf[key_name])

    for nm_prop, key_name in (
        (NM.SETTING_802_1X_PRIVATE_KEY, Ieee8021X.PRIVATE_KEY),
        (NM.SETTING_802_1X_CA_CERT, Ieee8021X.CA_CERT),
        (NM.SETTING_802_1X_CLIENT_CERT, Ieee8021X.CLIENT_CERT),
    ):
        if key_name in ieee_802_1x_conf:
            setattr(
                nm_setting.props,
                nm_prop,
                _file_path_to_glib_bytes(ieee_802_1x_conf[key_name]),
            )

    return nm_setting


def _file_path_from_glib_bytes(nm_bytes):
    file_path = nm_bytes.get_data().decode("utf8")
    if file_path.startswith("file://"):
        # Black is conflicting with flake for below line:
        #   https://github.com/psf/black/issues/315
        file_path = file_path[len("file://") : (-len("\\0") + 1)]  # noqa: E203

    return file_path


def _file_path_to_glib_bytes(file_path):
    file_path_bytes = bytearray(f"file://{file_path}".encode("utf8"))
    file_path_bytes.append(0)
    return GLib.Bytes.new(file_path_bytes)


def _get_secrets(context, nm_profile):
    secrets = {}
    action = f"Retrieve 802.1x secrets of profile {nm_profile.get_uuid()}"
    context.register_async(action, fast=True)
    user_data = (context, secrets, action)
    nm_profile.get_secrets_async(
        NM.SETTING_802_1X_SETTING_NAME,
        context.cancellable,
        _get_secrets_callback,
        user_data,
    )
    context.wait_all_finish()
    return secrets


def _get_secrets_callback(nm_profile, result, user_data):
    context, secrets, action = user_data

    try:
        nm_secrets = nm_profile.get_secrets_finish(result)
    except GLib.Error as e:
        context.fail(NmstateLibnmError(f"{action} failed: error={e}"))

    context.finish_async(action)
    secrets.update(nm_secrets[NM.SETTING_802_1X_SETTING_NAME])
