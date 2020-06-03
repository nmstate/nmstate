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

from libnmstate.error import NmstateValueError
from libnmstate.schema import LinuxBridge

from .bridge import BridgeIface


class LinuxBridgeIface(BridgeIface):
    def pre_edit_validation_and_cleanup(self):
        self._validate()
        self._fix_vlan_filtering_mode()
        super().pre_edit_validation_and_cleanup()

    @property
    def slaves(self):
        return [p[LinuxBridge.Port.NAME] for p in self.port_configs]

    def _validate(self):
        self._validate_vlan_filtering_trunk_tags()
        self._validate_vlan_filtering_tag()
        self._validate_vlan_filtering_enable_native()

    def _validate_vlan_filtering_trunk_tags(self):
        for port_config in self.original_dict.get(
            LinuxBridge.CONFIG_SUBTREE, {}
        ).get(LinuxBridge.PORT_SUBTREE, []):
            port_vlan_state = port_config.get(
                LinuxBridge.Port.VLAN_SUBTREE, {}
            )
            vlan_mode = port_vlan_state.get(LinuxBridge.Port.Vlan.MODE)
            trunk_tags = port_vlan_state.get(
                LinuxBridge.Port.Vlan.TRUNK_TAGS, []
            )

            if vlan_mode == LinuxBridge.Port.Vlan.Mode.ACCESS:
                if trunk_tags:
                    raise NmstateValueError(
                        "Access port cannot have trunk tags"
                    )
            elif port_vlan_state:
                if not trunk_tags:
                    raise NmstateValueError(
                        "A trunk port needs to specify trunk tags"
                    )
            for trunk_tag in trunk_tags:
                _assert_vlan_filtering_trunk_tag(trunk_tag)

    def _validate_vlan_filtering_tag(self):
        """
        The "tag" is valid in access mode or tunk mode with
        "enable-native:True".
        """
        for port_config in self.original_dict.get(
            LinuxBridge.CONFIG_SUBTREE, {}
        ).get(LinuxBridge.PORT_SUBTREE, []):
            vlan_config = _get_port_vlan_config(port_config)
            if (
                vlan_config.get(LinuxBridge.Port.Vlan.TAG)
                and _vlan_is_trunk_mode(vlan_config)
                and not _vlan_is_enable_native(vlan_config)
            ):
                raise NmstateValueError(
                    "Tag cannot be use in trunk mode without enable-native"
                )

    def _validate_vlan_filtering_enable_native(self):
        for port_config in self.original_dict.get(
            LinuxBridge.CONFIG_SUBTREE, {}
        ).get(LinuxBridge.PORT_SUBTREE, []):
            vlan_config = _get_port_vlan_config(port_config)
            if _vlan_is_access_mode(vlan_config) and _vlan_is_enable_native(
                vlan_config
            ):
                raise NmstateValueError(
                    "enable-native cannot be set in access mode"
                )

    def _fix_vlan_filtering_mode(self):
        for port_config in self.port_configs:
            _vlan_config_clean_up(_get_port_vlan_config(port_config))

    def gen_metadata(self, ifaces):
        super().gen_metadata(ifaces)
        if not self.is_absent:
            for port_config in self.port_configs:
                ifaces[port_config[LinuxBridge.Port.NAME]].update(
                    {BridgeIface.BRPORT_OPTIONS_METADATA: port_config}
                )

    def remove_slave(self, slave_name):
        if self._bridge_config:
            self.raw[LinuxBridge.CONFIG_SUBTREE][LinuxBridge.PORT_SUBTREE] = [
                port_config
                for port_config in self.port_configs
                if port_config[LinuxBridge.Port.NAME] != slave_name
            ]
        self.sort_slaves()


def _assert_vlan_filtering_trunk_tag(trunk_tag_state):
    vlan_id = trunk_tag_state.get(LinuxBridge.Port.Vlan.TrunkTags.ID)
    vlan_id_range = trunk_tag_state.get(
        LinuxBridge.Port.Vlan.TrunkTags.ID_RANGE
    )

    if vlan_id and vlan_id_range:
        raise NmstateValueError(
            "Trunk port cannot be configured by both id and range: {}".format(
                trunk_tag_state
            )
        )
    elif vlan_id_range:
        if not (
            {
                LinuxBridge.Port.Vlan.TrunkTags.MIN_RANGE,
                LinuxBridge.Port.Vlan.TrunkTags.MAX_RANGE,
            }
            <= set(vlan_id_range)
        ):
            raise NmstateValueError(
                "Trunk port range requires min / max keys: {}".format(
                    vlan_id_range
                )
            )


def _get_port_vlan_config(port_config):
    return port_config.get(LinuxBridge.Port.VLAN_SUBTREE, {})


# TODO: Group them into class _LinuxBridgePort
def _vlan_is_access_mode(vlan_config):
    return (
        vlan_config.get(LinuxBridge.Port.Vlan.MODE)
        == LinuxBridge.Port.Vlan.Mode.ACCESS
    )


def _vlan_is_trunk_mode(vlan_config):
    return (
        vlan_config.get(LinuxBridge.Port.Vlan.MODE)
        == LinuxBridge.Port.Vlan.Mode.TRUNK
    )


def _vlan_is_enable_native(vlan_config):
    return vlan_config.get(LinuxBridge.Port.Vlan.ENABLE_NATIVE) is True


def _vlan_config_clean_up(vlan_config):
    _vlan_remove_enable_native_if_access_mode(vlan_config)
    _vlan_remove_tag_if_trunk_mode_without_enable_native(vlan_config)
    _vlan_remove_trunk_tag_if_access_mode(vlan_config)


def _vlan_remove_enable_native_if_access_mode(vlan_config):
    if _vlan_is_access_mode(vlan_config):
        vlan_config.pop(LinuxBridge.Port.Vlan.ENABLE_NATIVE, None)


def _vlan_remove_tag_if_trunk_mode_without_enable_native(vlan_config):
    if _vlan_is_trunk_mode(vlan_config) and not _vlan_is_enable_native(
        vlan_config
    ):
        vlan_config.pop(LinuxBridge.Port.Vlan.TAG, None)


def _vlan_remove_trunk_tag_if_access_mode(vlan_config):
    if _vlan_is_access_mode(vlan_config):
        vlan_config.pop(LinuxBridge.Port.Vlan.TRUNK_TAGS, None)
