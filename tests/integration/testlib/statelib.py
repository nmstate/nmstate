# SPDX-License-Identifier: LGPL-2.1-or-later

from collections.abc import Mapping
from collections.abc import Sequence
import contextlib
import copy
from ipaddress import ip_address
from operator import itemgetter

import libnmstate
from libnmstate.schema import Bond
from libnmstate.schema import Description
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import LinuxBridge
from libnmstate.schema import Mptcp
from libnmstate.schema import OVSBridge


def show_only(ifnames, include_secrets=False):
    """
    Report the current state, filtering based on the given interface names.
    """
    base_filter_state = {
        Interface.KEY: [{Interface.NAME: ifname} for ifname in ifnames]
    }
    if include_secrets:
        current_state = State(libnmstate.show(include_secrets=True))
    else:
        current_state = State(libnmstate.show())
    current_state.filter(base_filter_state)
    return current_state.state


class State:
    def __init__(self, state):
        self._state = copy.deepcopy(state)

    def __eq__(self, other):
        return self._state == other

    def __hash__(self):
        return hash(self._state)

    def __str__(self):
        return self._state

    def __repr__(self):
        return self.__str__()

    @property
    def state(self):
        return self._state

    def filter(self, based_on_state):
        """
        Given the based_on_state, update the sate with a filtered version
        which includes only entities such as interfaces that have been
        mentioned in the based_on_state.
        In case there are no entities for filtering, all are reported.
        """
        base_iface_names = {
            ifstate[Interface.NAME]
            for ifstate in based_on_state.get(Interface.KEY, [])
        }

        if not base_iface_names:
            return

        filtered_iface_state = [
            ifstate
            for ifstate in self._state[Interface.KEY]
            if ifstate[Interface.NAME] in base_iface_names
        ]
        self._state = {Interface.KEY: filtered_iface_state}

    def update(self, other_state):
        """
        Given the other_state, update the state with the other_state data.
        """
        other_state = copy.deepcopy(other_state)
        other_interfaces_state = other_state.get(Interface.KEY, [])

        for base_iface_state in self._state[Interface.KEY]:
            ifname = base_iface_state[Interface.NAME]
            other_iface_state = _lookup_iface_state_by_name(
                other_interfaces_state, ifname
            )
            if other_iface_state is not None:
                iface_state = _dict_update(base_iface_state, other_iface_state)
                other_iface_state.update(iface_state)

        self._state = other_state

    def normalize(self):
        self._convert_lag_numeric_value_options_to_integer()
        self._sort_iface_lag_port()
        self._sort_iface_bridge_ports()
        self._ipv4_skeleton_canonicalization()
        self._ipv6_skeleton_canonicalization()
        self._ignore_addr_with_lifetime()
        self._ignore_dhcp_option_when_off()
        self._ignore_ipv6_link_local()
        self._sort_ip_addresses()
        self._sort_interfaces_by_name()
        self._canonicalize_iface_ipv6_addresses()
        self._normalize_linux_bridge_port_vlan()
        self._upper_linux_bridge_group_addr()
        self._sort_ovs_lag_ports()
        self._sort_mptcp_flags()
        self._remove_mptcp_flags_of_ip_addr()
        self._remove_top_descriptions()

    def match(self, other):
        return state_match(self.state, other.state)

    def _sort_interfaces_by_name(self):
        self._state[Interface.KEY].sort(key=lambda d: d[Interface.NAME])

    def _canonicalize_iface_ipv6_addresses(self):
        for iface_state in self.state[Interface.KEY]:
            iface_ipv6_state = iface_state.get(Interface.IPV6)
            if iface_ipv6_state:
                iface_ipv6_addresses_state = iface_ipv6_state.get(
                    InterfaceIP.ADDRESS
                )
                if iface_ipv6_addresses_state:
                    iface_ipv6_state[InterfaceIP.ADDRESS] = [
                        _canonicalize_ipv6_addr(iface_ipv6_addr)
                        for iface_ipv6_addr in iface_ipv6_addresses_state
                    ]

    def remove_absent_entries(self):
        self._state[Interface.KEY] = [
            ifstate
            for ifstate in self._state.get(Interface.KEY, [])
            if ifstate.get(Interface.STATE) != InterfaceState.ABSENT
        ]

    def _sort_iface_lag_port(self):
        for ifstate in self._state[Interface.KEY]:
            ifstate.get(Bond.CONFIG_SUBTREE, {}).get(Bond.PORT, []).sort()

    def _sort_iface_bridge_ports(self):
        for ifstate in self._state[Interface.KEY]:
            ifstate.get(LinuxBridge.CONFIG_SUBTREE, {}).get(
                LinuxBridge.PORT_SUBTREE, []
            ).sort(key=itemgetter(LinuxBridge.Port.NAME))

    def _ipv6_skeleton_canonicalization(self):
        for iface_state in self._state.get(Interface.KEY, []):
            iface_state.setdefault(Interface.IPV6, {})
            iface_state[Interface.IPV6].setdefault(
                InterfaceIPv6.ENABLED, False
            )
            iface_state[Interface.IPV6].setdefault(InterfaceIPv6.ADDRESS, [])
            iface_state[Interface.IPV6].setdefault(InterfaceIPv6.DHCP, False)
            iface_state[Interface.IPV6].setdefault(
                InterfaceIPv6.AUTOCONF, False
            )

    def _ipv4_skeleton_canonicalization(self):
        for iface_state in self._state.get(Interface.KEY, []):
            iface_state.setdefault(Interface.IPV4, {})
            iface_state[Interface.IPV4].setdefault(
                InterfaceIPv4.ENABLED, False
            )
            iface_state[Interface.IPV4].setdefault(InterfaceIPv4.ADDRESS, [])
            iface_state[Interface.IPV4].setdefault(InterfaceIPv4.DHCP, False)

    def _ignore_ipv6_link_local(self):
        for iface_state in self._state.get(Interface.KEY, []):
            iface_state[Interface.IPV6][InterfaceIPv6.ADDRESS] = list(
                addr
                for addr in iface_state[Interface.IPV6][InterfaceIPv6.ADDRESS]
                if not _is_ipv6_link_local(
                    addr[InterfaceIPv6.ADDRESS_IP],
                    addr[InterfaceIPv6.ADDRESS_PREFIX_LENGTH],
                )
            )

    def _sort_ip_addresses(self):
        for iface_state in self._state.get(Interface.KEY, []):
            for family in (Interface.IPV4, Interface.IPV6):
                iface_state.get(family, {}).get(InterfaceIP.ADDRESS, []).sort(
                    key=itemgetter(InterfaceIP.ADDRESS_IP)
                )

    def _ignore_addr_with_lifetime(self):
        for iface_state in self._state.get(Interface.KEY, []):
            for family in (Interface.IPV4, Interface.IPV6):
                new_addrs = []
                for addr in iface_state[family][InterfaceIP.ADDRESS]:
                    if addr.get(
                        InterfaceIP.ADDRESS_VALID_LEFT,
                    ) in (None, InterfaceIP.ADDRESS_LIFETIME_FOREVER):
                        new_addrs.append(addr)
                iface_state[family][InterfaceIP.ADDRESS] = new_addrs

    def _ignore_dhcp_option_when_off(self):
        for iface_state in self._state.get(Interface.KEY, []):
            for family in (Interface.IPV4, Interface.IPV6):
                ip = iface_state.get(family, {})
                if not (
                    ip.get(InterfaceIP.ENABLED)
                    and (
                        ip.get(InterfaceIP.DHCP)
                        or ip.get(InterfaceIPv6.AUTOCONF)
                    )
                ):
                    for dhcp_option in (
                        InterfaceIP.AUTO_ROUTES,
                        InterfaceIP.AUTO_GATEWAY,
                        InterfaceIP.AUTO_DNS,
                    ):
                        ip.pop(dhcp_option, None)

    def _convert_lag_numeric_value_options_to_integer(self):
        for iface_state in self._state.get(Interface.KEY, []):
            if iface_state.get(Interface.TYPE) == Bond.KEY:
                bond_state = iface_state.get(Bond.CONFIG_SUBTREE, {})
                options = bond_state.get(Bond.OPTIONS_SUBTREE)
                if options:
                    for option_name, option_value in options.items():
                        with contextlib.suppress(ValueError):
                            option_value = int(option_value)
                        options[option_name] = option_value

    def _normalize_linux_bridge_port_vlan(self):
        linux_bridges = (
            iface
            for iface in self._state.get(Interface.KEY, [])
            if iface[Interface.TYPE] == LinuxBridge.TYPE
        )
        for lb in linux_bridges:
            ports = lb.get(LinuxBridge.CONFIG_SUBTREE, {}).get(
                LinuxBridge.PORT_SUBTREE, []
            )
            for port in ports:
                if not port.get(LinuxBridge.Port.VLAN_SUBTREE):
                    port[LinuxBridge.Port.VLAN_SUBTREE] = {}

    def _upper_linux_bridge_group_addr(self):
        linux_bridges = (
            iface
            for iface in self._state.get(Interface.KEY, [])
            if iface[Interface.TYPE] == LinuxBridge.TYPE
        )
        for lb in linux_bridges:
            cur_group_addr = (
                lb.get(LinuxBridge.CONFIG_SUBTREE, {})
                .get(LinuxBridge.OPTIONS_SUBTREE, {})
                .get(LinuxBridge.Options.GROUP_ADDR)
            )
            if cur_group_addr:
                lb[LinuxBridge.CONFIG_SUBTREE][LinuxBridge.OPTIONS_SUBTREE][
                    LinuxBridge.Options.GROUP_ADDR
                ] = cur_group_addr.upper()

    def _sort_ovs_lag_ports(self):
        for iface_state in self._state[Interface.KEY]:
            for port_config in iface_state.get(
                OVSBridge.CONFIG_SUBTREE, {}
            ).get(OVSBridge.PORT_SUBTREE, []):
                port_config.get(
                    OVSBridge.Port.LINK_AGGREGATION_SUBTREE, {}
                ).get(OVSBridge.Port.LinkAggregation.PORT_SUBTREE, []).sort(
                    key=itemgetter(OVSBridge.Port.LinkAggregation.Port.NAME)
                )

    def _sort_mptcp_flags(self):
        for iface_state in self._state[Interface.KEY]:
            iface_state.get(Interface.MPTCP, {}).get(
                Mptcp.ADDRESS_FLAGS, []
            ).sort()
            for addr in iface_state.get(Interface.IPV4, {}).get(
                InterfaceIPv4.ADDRESS, []
            ):
                addr.get(InterfaceIPv4.MPTCP_FLAGS, []).sort()
            for addr in iface_state.get(Interface.IPV6, {}).get(
                InterfaceIPv6.ADDRESS, []
            ):
                addr.get(InterfaceIPv6.MPTCP_FLAGS, []).sort()

    def _remove_mptcp_flags_of_ip_addr(self):
        for iface_state in self._state[Interface.KEY]:
            for addr in iface_state.get(Interface.IPV4, {}).get(
                InterfaceIPv4.ADDRESS, []
            ):
                addr.pop(InterfaceIPv4.MPTCP_FLAGS, None)
            for addr in iface_state.get(Interface.IPV6, {}).get(
                InterfaceIPv6.ADDRESS, []
            ):
                addr.pop(InterfaceIPv6.MPTCP_FLAGS, None)

    def _remove_top_descriptions(self):
        self._state.pop(Description.KEY, None)


def _lookup_iface_state_by_name(interfaces_state, ifname):
    for iface_state in interfaces_state:
        if iface_state[Interface.NAME] == ifname:
            return iface_state
    return None


def _dict_update(origin_data, to_merge_data):
    """
    Recursively performs a dict update (merge), taking the to_merge_data and
    updating the origin_data.
    The function changes the origin_data in-place.
    """
    if not to_merge_data:
        return to_merge_data

    for key, val in to_merge_data.items():
        if isinstance(val, Mapping):
            origin_data[key] = _dict_update(origin_data.get(key, {}), val)
        else:
            origin_data[key] = val
    return origin_data


def filter_current_state(desired_state):
    """
    Given the desired state, return a filtered version of the current state
    which includes only entities such as interfaces that have been mentioned
    in the desired state.
    In case there are no entities for filtering, all are reported.
    """
    current_state = libnmstate.show()
    desired_iface_names = {
        ifstate[Interface.NAME] for ifstate in desired_state[Interface.KEY]
    }

    if not desired_iface_names:
        return current_state

    filtered_iface_current_state = [
        ifstate
        for ifstate in current_state[Interface.KEY]
        if ifstate[Interface.NAME] in desired_iface_names
    ]
    return {Interface.KEY: filtered_iface_current_state}


def _is_ipv6_link_local(ip, prefix):
    """
    The IPv6 link local address range is fe80::/10.
    """
    return ip[:3] in ["fe8", "fe9", "fea", "feb"] and prefix >= 10


def state_match(desire, current):
    if isinstance(desire, Mapping):
        return isinstance(current, Mapping) and all(
            state_match(val, current.get(key)) for key, val in desire.items()
        )
    elif isinstance(desire, Sequence) and not isinstance(desire, str):
        return (
            isinstance(current, Sequence)
            and not isinstance(current, str)
            and len(current) == len(desire)
            and all(state_match(d, c) for d, c in zip(desire, current))
        )
    else:
        return desire == current


def _canonicalize_ipv6_addr(addr):
    address = addr[InterfaceIP.ADDRESS_IP]
    if _is_ipv6_address(address):
        addr[InterfaceIP.ADDRESS_IP] = str(ip_address(address))
    return addr


def _is_ipv6_address(addr):
    return ":" in addr
