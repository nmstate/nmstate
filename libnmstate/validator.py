#
# Copyright (c) 2018-2020 Red Hat, Inc.
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

import copy
import logging

import jsonschema as js

from . import nm
from . import schema
from libnmstate.appliers.bond import is_in_mac_restricted_mode
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import LinuxBridge as LB
from libnmstate.schema import OVSBridge
from libnmstate.schema import VXLAN
from libnmstate.schema import Bond
from libnmstate.error import NmstateDependencyError
from libnmstate.error import NmstateNotImplementedError
from libnmstate.error import NmstateValueError
from libnmstate.iplib import is_ipv6_address


class NmstateRouteWithNoInterfaceError(NmstateValueError):
    pass


class NmstateRouteWithNoUpInterfaceError(NmstateValueError):
    pass


class NmstateRouteWithNoIPInterfaceError(NmstateValueError):
    pass


class NmstateDuplicateInterfaceNameError(NmstateValueError):
    pass


class NmstateOvsLagValueError(NmstateValueError):
    pass


def validate(data, validation_schema=schema.ifaces_schema):
    data = copy.deepcopy(data)
    for ifstate in data.get(schema.Interface.KEY, ()):
        if not ifstate.get(schema.Interface.TYPE):
            ifstate[schema.Interface.TYPE] = schema.InterfaceType.UNKNOWN
    js.validate(data, validation_schema)


def validate_capabilities(state, capabilities):
    validate_interface_capabilities(state.get(Interface.KEY, []), capabilities)


def validate_interface_capabilities(ifaces_state, capabilities):
    ifaces_types = [iface_state.get("type") for iface_state in ifaces_state]
    has_ovs_capability = nm.ovs.CAPABILITY in capabilities
    has_team_capability = nm.team.CAPABILITY in capabilities
    for iface_type in ifaces_types:
        is_ovs_type = iface_type in (
            nm.ovs.BRIDGE_TYPE,
            nm.ovs.PORT_TYPE,
            nm.ovs.INTERNAL_INTERFACE_TYPE,
        )
        if is_ovs_type and not has_ovs_capability:
            raise NmstateDependencyError(
                "Open vSwitch NetworkManager support not installed "
                "and started"
            )
        if iface_type == InterfaceType.TEAM and not has_team_capability:
            raise NmstateDependencyError(
                "NetworkManager-team plugin not installed and started"
            )


def validate_interfaces_state(
    original_desired_state, desired_state, current_state
):
    validate_link_aggregation_state(original_desired_state, current_state)
    _validate_linux_bond(original_desired_state, current_state)


def validate_link_aggregation_state(desired_state, current_state):
    available_ifaces = {
        ifname
        for ifname, ifstate in desired_state.interfaces.items()
        if ifstate.get("state") != "absent"
    }
    available_ifaces |= set(current_state.interfaces)

    specified_slaves = set()
    for iface_state in desired_state.interfaces.values():
        if iface_state.get("state") != "absent":
            link_aggregation = iface_state.get("link-aggregation")
            if link_aggregation:
                slaves = set(link_aggregation.get("slaves", []))
                if not (slaves <= available_ifaces):
                    raise NmstateValueError(
                        "Link aggregation has missing slave: {}".format(
                            iface_state
                        )
                    )
                if slaves & specified_slaves:
                    raise NmstateValueError(
                        "Link aggregation has reused slave: {}".format(
                            iface_state
                        )
                    )
                specified_slaves |= slaves


def validate_unique_interface_name(state):
    ifaces_names = [
        ifstate[schema.Interface.NAME]
        for ifstate in state.get(schema.Interface.KEY, [])
    ]
    if len(ifaces_names) != len(set(ifaces_names)):
        raise NmstateDuplicateInterfaceNameError(
            f"Duplicate interfaces names detected: {sorted(ifaces_names)}"
        )


def validate_dhcp(state):
    for iface_state in state.get(Interface.KEY, []):
        for family in ("ipv4", "ipv6"):
            ip = iface_state.get(family, {})
            if (
                ip.get(InterfaceIP.ENABLED)
                and ip.get(InterfaceIP.ADDRESS)
                and (
                    ip.get(InterfaceIP.DHCP) or ip.get(InterfaceIPv6.AUTOCONF)
                )
            ):
                logging.warning(
                    "%s addresses are ignored when " "dynamic IP is enabled",
                    family,
                )


def validate_dns(state):
    """
    Only support at most 2 name servers now:
    https://nmstate.atlassian.net/browse/NMSTATE-220
    """
    dns_servers = (
        state.get(DNS.KEY, {}).get(DNS.CONFIG, {}).get(DNS.SERVER, [])
    )
    if len(dns_servers) > 2:
        raise NmstateNotImplementedError(
            "Nmstate only support at most 2 DNS name servers"
        )


def validate_routes(desired_state, current_state):
    """
    A route has several requirements it must comply with:
    - Next-hop interface must be provided
    - The next-hop interface must:
        - Exist and be up (no down/absent)
        - Have the relevant IPv4/6 stack enabled.
    """
    for iface_name, routes in desired_state.config_iface_routes.items():
        if not routes:
            continue

        desired_iface_state = desired_state.interfaces.get(iface_name)
        current_iface_state = current_state.interfaces.get(iface_name)
        if desired_iface_state or current_iface_state:
            _assert_iface_is_up(desired_iface_state, current_iface_state)
            if any(is_ipv6_address(route.destination) for route in routes):
                _assert_iface_ipv6_enabled(
                    desired_iface_state, current_iface_state
                )
            if any(not is_ipv6_address(route.destination) for route in routes):
                _assert_iface_ipv4_enabled(
                    desired_iface_state, current_iface_state
                )
        else:
            raise NmstateRouteWithNoInterfaceError(str(routes))


def validate_vxlan(state):
    for iface_state in state.get(schema.Interface.KEY, []):
        if iface_state.get(schema.Interface.TYPE) == VXLAN.TYPE:
            _assert_vxlan_has_missing_attribute(
                iface_state, VXLAN.ID, VXLAN.BASE_IFACE, VXLAN.REMOTE
            )


def validate_bridge(state):
    for iface_state in state.get(schema.Interface.KEY, []):
        if iface_state.get(schema.Interface.TYPE) == LB.TYPE:
            _assert_vlan_filtering_trunk_tags(
                iface_state.get(LB.PORT_SUBTREE, [])
            )


def validate_ovs_link_aggregation(state):
    for iface_state in state.get(schema.Interface.KEY, []):
        if iface_state.get(schema.Interface.TYPE) == OVSBridge.TYPE:
            _assert_ovs_lag_slave_count(iface_state)


def _assert_iface_is_up(desired_iface_state, current_iface_state):
    """
    Validates that the interface has an UP state.
    Prioritize the desired state over the current state.
    """
    if desired_iface_state:
        state = desired_iface_state.get(schema.Interface.STATE)
        if state is not None:
            if state == schema.InterfaceState.UP:
                return
            raise NmstateRouteWithNoUpInterfaceError(desired_iface_state)
    if current_iface_state:
        state = current_iface_state.get(schema.Interface.STATE)
        if state != schema.InterfaceState.UP:
            raise NmstateRouteWithNoUpInterfaceError(current_iface_state)


def _assert_iface_ipv4_enabled(desired_iface_state, current_iface_state):
    _assert_iface_ip_enabled(
        desired_iface_state, current_iface_state, schema.Interface.IPV4
    )


def _assert_iface_ipv6_enabled(desired_iface_state, current_iface_state):
    _assert_iface_ip_enabled(
        desired_iface_state, current_iface_state, schema.Interface.IPV6
    )


def _assert_iface_ip_enabled(desired_iface_state, current_iface_state, ipkey):
    """
    Validates that the interface has IPv4/6 (ipkey) enabled.
    Prioritize the desired state over the current state.
    """
    if desired_iface_state:
        ip_state = desired_iface_state.get(ipkey)
        if ip_state is not None:
            ip_enabled = ip_state.get(InterfaceIP.ENABLED)
            if ip_enabled is True:
                return
            elif ip_enabled is False:
                raise NmstateRouteWithNoIPInterfaceError(desired_iface_state)
    if current_iface_state:
        ip_state = current_iface_state.get(ipkey)
        if not ip_state.get(InterfaceIP.ENABLED):
            raise NmstateRouteWithNoIPInterfaceError(current_iface_state)


def _assert_vxlan_has_missing_attribute(state, *attributes):
    vxlan_config = state.get(VXLAN.CONFIG_SUBTREE, {})
    if not vxlan_config:
        return
    attributes_set = set(attributes)
    vxlan_config_set = set(vxlan_config)
    if not (attributes_set <= vxlan_config_set):
        raise NmstateValueError(
            "Vxlan tunnel {} has missing {}: {}".format(
                state[schema.Interface.NAME],
                attributes_set.difference(vxlan_config_set),
                state,
            )
        )


def _assert_vlan_filtering_trunk_tags(ports_state):
    for port_state in ports_state:
        port_vlan_state = port_state.get(LB.Port.VLAN_SUBTREE, {})
        vlan_mode = port_vlan_state.get(LB.Port.Vlan.MODE)
        trunk_tags = port_vlan_state.get(LB.Port.Vlan.TRUNK_TAGS, [])

        if vlan_mode == LB.Port.Vlan.Mode.ACCESS:
            if trunk_tags:
                raise NmstateValueError("Access port cannot have trunk tags")
        elif port_vlan_state:
            if not trunk_tags:
                raise NmstateValueError(
                    "A trunk port needs to specify trunk tags"
                )
        for trunk_tag in trunk_tags:
            _assert_vlan_filtering_trunk_tag(trunk_tag)


def _assert_vlan_filtering_trunk_tag(trunk_tag_state):
    vlan_id = trunk_tag_state.get(LB.Port.Vlan.TrunkTags.ID)
    vlan_id_range = trunk_tag_state.get(LB.Port.Vlan.TrunkTags.ID_RANGE)

    if vlan_id and vlan_id_range:
        raise NmstateValueError(
            "Trunk port cannot be configured by both id and range: {}".format(
                trunk_tag_state
            )
        )
    elif vlan_id_range:
        if not (
            {
                LB.Port.Vlan.TrunkTags.MIN_RANGE,
                LB.Port.Vlan.TrunkTags.MAX_RANGE,
            }
            <= set(vlan_id_range)
        ):
            raise NmstateValueError(
                "Trunk port range requires min / max keys: {}".format(
                    vlan_id_range
                )
            )


def _assert_ovs_lag_slave_count(iface_state):
    bridge_state = iface_state.get(OVSBridge.CONFIG_SUBTREE)
    if bridge_state:
        for port in bridge_state.get(OVSBridge.PORT_SUBTREE, ()):
            slaves_subtree = OVSBridge.Port.LinkAggregation.SLAVES_SUBTREE
            lag = port.get(OVSBridge.Port.LINK_AGGREGATION_SUBTREE)
            if lag and len(lag.get(slaves_subtree, ())) < 2:
                ifname = iface_state[schema.Interface.NAME]
                raise NmstateOvsLagValueError(
                    f"OVS {ifname} LAG port {lag} has less than 2 slaves."
                )


def _validate_linux_bond(original_desired_state, current_state):
    """
    Raise NmstateValueError on these scenarios:
        * Bond mode not defined.
        * Original desire state contains illegal bond config.
        * After merge, user's intention will cause illegal bong config.
          For example: mac specified in desired_state without any bond options
                       defined. While current state is fail_over_mac=1 with
                       active-backup mode.
    """
    merged_desired_state = copy.deepcopy(original_desired_state)
    merged_desired_state.merge_interfaces(current_state)

    original_iface_states = {}
    for iface_name, iface_state in original_desired_state.interfaces.items():
        original_iface_states[iface_name] = iface_state

    for iface_state in merged_desired_state.interfaces.values():
        if iface_state[Interface.STATE] != InterfaceState.UP:
            continue
        if iface_state[Interface.TYPE] == InterfaceType.BOND:
            if not iface_state.get(Bond.CONFIG_SUBTREE, {}).get(Bond.MODE):
                raise NmstateValueError("Bond mode is not defined")

            original_iface_state = original_iface_states.get(
                iface_state[Interface.NAME], {}
            )
            _assert_bond_config_is_legal(iface_state, original_iface_state)


def _assert_bond_config_is_legal(iface_state, original_iface_state):
    """
    When MAC address defined in original_iface_state and bond is MAC
    address restricted mode(cannot define MAC), raise NmstateValueError.
    """
    mac = original_iface_state.get(Interface.MAC)
    bond_options = iface_state[Bond.CONFIG_SUBTREE].get(
        Bond.OPTIONS_SUBTREE, {}
    )
    bond_options[Bond.MODE] = iface_state[Bond.CONFIG_SUBTREE].get(Bond.MODE)

    if mac and is_in_mac_restricted_mode(bond_options):
        raise NmstateValueError(
            "MAC address cannot be specified in bond interface along with "
            "specified bond options"
        )
