#
# Copyright (c) 2020-2021 Red Hat, Inc.
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
from libnmstate.schema import Bridge
from libnmstate.schema import LinuxBridge
from libnmstate.validator import validate_boolean
from libnmstate.validator import validate_integer
from libnmstate.validator import validate_string

from .bridge import BridgeIface
from .linux_bridge_port_vlan import NmstateLinuxBridgePortVlan

# The aging_time, forward_delay, hello_time, max_age options are multipled by
# 100(USER_HZ) when apply to kernel(via NM), so they are not impacted by this
# integer round up/down issue.
INTEGER_ROUNDED_OPTIONS = [
    LinuxBridge.Options.MULTICAST_LAST_MEMBER_INTERVAL,
    LinuxBridge.Options.MULTICAST_MEMBERSHIP_INTERVAL,
    LinuxBridge.Options.MULTICAST_QUERIER_INTERVAL,
    LinuxBridge.Options.MULTICAST_QUERY_RESPONSE_INTERVAL,
    LinuxBridge.Options.MULTICAST_STARTUP_QUERY_INTERVAL,
]

READ_ONLY_OPTIONS = [
    LinuxBridge.Options.HELLO_TIMER,
    LinuxBridge.Options.GC_TIMER,
]

INTEGER_OPTIONS = [
    LinuxBridge.Options.MULTICAST_LAST_MEMBER_INTERVAL,
    LinuxBridge.Options.MULTICAST_MEMBERSHIP_INTERVAL,
    LinuxBridge.Options.MULTICAST_QUERIER_INTERVAL,
    LinuxBridge.Options.MULTICAST_QUERY_RESPONSE_INTERVAL,
    LinuxBridge.Options.MULTICAST_STARTUP_QUERY_INTERVAL,
    LinuxBridge.Options.HASH_MAX,
    LinuxBridge.Options.MULTICAST_LAST_MEMBER_COUNT,
    LinuxBridge.Options.MULTICAST_QUERY_INTERVAL,
    LinuxBridge.Options.MULTICAST_STARTUP_QUERY_COUNT,
]

BOOLEAN_OPTIONS = [
    LinuxBridge.Options.MULTICAST_SNOOPING,
    LinuxBridge.Options.MULTICAST_QUERIER,
    LinuxBridge.Options.MULTICAST_QUERY_USE_IFADDR,
]

VALID_VLAN_FILTERING_MODES = [
    Bridge.Port.Vlan.Mode.ACCESS,
    Bridge.Port.Vlan.Mode.TRUNK,
    Bridge.Port.Vlan.Mode.UNKNOWN,
]


class LinuxBridgeIface(BridgeIface):
    @property
    def _options(self):
        return self.raw.get(LinuxBridge.CONFIG_SUBTREE, {}).get(
            LinuxBridge.OPTIONS_SUBTREE, {}
        )

    def pre_edit_validation_and_cleanup(self):
        self._validate_bridge_properties()
        if self.is_up:
            self._validate()
            self._fix_vlan_filtering_mode()
        super().pre_edit_validation_and_cleanup()

    def _validate_bridge_properties(self):
        for port_info in self.port_configs:
            validate_string(port_info.get(Bridge.Port.NAME), Bridge.Port.NAME)
            validate_integer(
                port_info.get(LinuxBridge.Port.STP_PRIORITY),
                LinuxBridge.Port.STP_PRIORITY,
            )
            validate_integer(
                port_info.get(LinuxBridge.Port.STP_PATH_COST),
                LinuxBridge.Port.STP_PATH_COST,
            )
            validate_boolean(
                port_info.get(LinuxBridge.Port.STP_HAIRPIN_MODE),
                LinuxBridge.Port.STP_HAIRPIN_MODE,
            )
            vlan_filtering_info = port_info.get(Bridge.Port.VLAN_SUBTREE)
            if vlan_filtering_info:
                validate_string(
                    vlan_filtering_info.get(Bridge.Port.Vlan.MODE),
                    Bridge.Port.Vlan.MODE,
                    VALID_VLAN_FILTERING_MODES,
                )
                validate_boolean(
                    vlan_filtering_info.get(Bridge.Port.Vlan.ENABLE_NATIVE),
                    Bridge.Port.Vlan.ENABLE_NATIVE,
                )
                validate_integer(
                    vlan_filtering_info.get(Bridge.Port.Vlan.TAG),
                    Bridge.Port.Vlan.TAG,
                    minimum=0,
                    maximum=4095,
                )

        for option in INTEGER_OPTIONS:
            validate_integer(self._options.get(option), option)

        for option in BOOLEAN_OPTIONS:
            validate_boolean(self._options.get(option), option)

    @property
    def port(self):
        return [p[LinuxBridge.Port.NAME] for p in self.port_configs]

    def _validate(self):
        self._validate_vlan_filtering_trunk_tags()
        self._validate_vlan_filtering_tag()
        self._validate_vlan_filtering_enable_native()

    def _validate_vlan_filtering_trunk_tags(self):
        for port_config in self.original_desire_dict.get(
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
        for port_config in self.original_desire_dict.get(
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
        for port_config in self.original_desire_dict.get(
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
                port_iface = ifaces.all_kernel_ifaces.get(
                    port_config[LinuxBridge.Port.NAME]
                )
                if port_iface:
                    port_iface.update(
                        {BridgeIface.BRPORT_OPTIONS_METADATA: port_config}
                    )

    def remove_port(self, port_name):
        if self._bridge_config:
            self.raw[LinuxBridge.CONFIG_SUBTREE][LinuxBridge.PORT_SUBTREE] = [
                port_config
                for port_config in self.port_configs
                if port_config[LinuxBridge.Port.NAME] != port_name
            ]
        self.sort_port()

    def state_for_verify(self):
        self._normalize_bridge_port_vlan()
        self._remove_read_only_bridge_options()
        self._change_to_upper_group_addr()
        return super().state_for_verify()

    @staticmethod
    def is_integer_rounded(iface_state, current_iface_state):
        for key, value in iface_state._options.items():
            if key in INTEGER_ROUNDED_OPTIONS:
                try:
                    value = int(value)
                    cur_value = int(current_iface_state._options.get(key))
                except (TypeError, ValueError):
                    continue
                # With 250 HZ and 100 USER_HZ, every 8,000,000 will have 1
                # deviation, caused by:
                # * kernel set the value using clock_t_to_jiffies():
                #       jiffies = int(clock * 100 / 250)
                # * kernel showing the value using jiffies_to_clock_t():
                #       clock =  int(int(jiffies * ( (10 ** 9 + 250/2) / 250)
                #                    / 10 ** 9 * 100)
                #
                # The number 8,000,000 is found by exhaustion.
                # There is no good way to detect kernel HZ in user space. Hence
                # we check whether certain value is rounded.
                if cur_value != value:
                    if value >= 8 * (10 ** 6):
                        if abs(value - cur_value) <= int(
                            value / 8 * (10 ** 6)
                        ):
                            return key, value, cur_value
                    else:
                        if abs(value - cur_value) == 1:
                            return key, value, cur_value

        return None, None, None

    def _normalize_bridge_port_vlan(self):
        """
        * Set Bridge.Port.VLAN_SUBTREE as {} when not defined.
        * Expand VLAN ranges to single VLANs
        """
        for port_config in self.port_configs:
            if not port_config.get(LinuxBridge.Port.VLAN_SUBTREE):
                port_config[LinuxBridge.Port.VLAN_SUBTREE] = {}
            else:
                vlan_config = NmstateLinuxBridgePortVlan(
                    port_config[LinuxBridge.Port.VLAN_SUBTREE]
                ).to_dict(expand_vlan_range=True)
                port_config[LinuxBridge.Port.VLAN_SUBTREE] = vlan_config

    def _remove_read_only_bridge_options(self):
        for key in READ_ONLY_OPTIONS:
            self._bridge_config.get(LinuxBridge.OPTIONS_SUBTREE, {}).pop(
                key, None
            )

    def _change_to_upper_group_addr(self):
        cur_group_addr = self._bridge_config.get(
            LinuxBridge.OPTIONS_SUBTREE, {}
        ).get(LinuxBridge.Options.GROUP_ADDR)
        if cur_group_addr:
            self.raw[LinuxBridge.CONFIG_SUBTREE][LinuxBridge.OPTIONS_SUBTREE][
                LinuxBridge.Options.GROUP_ADDR
            ] = cur_group_addr.upper()


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
