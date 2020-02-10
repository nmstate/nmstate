#
# Copyright (c) 2019-2020 Red Hat, Inc.
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

from libnmstate import iplib
from libnmstate.appliers import linux_bridge
from libnmstate.error import NmstateValueError
from libnmstate import nm
from libnmstate.schema import Bond
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge


BRPORT_OPTIONS = "_brport_options"
MASTER = "_master"
MASTER_TYPE = "_master_type"
ROUTES = "_routes"
DNS_METADATA = "_dns"
DNS_METADATA_PRIORITY = "_priority"
ROUTE_RULES_METADATA = "_route_rules"


def generate_ifaces_metadata(desired_state, current_state):
    """
    The described desired state for each interface may include references to
    other interfaces. As the provider handles the interface setting in an
    isolated manner, it is sometime necessary to specify a property on an
    interface based on a property from a different interface.
    An exmaple of this, is the bond slaves property, which should mark each
    slave with the setting of it being a slave.

    For such relationships between interfaces or some other potential inputs,
    metadata is generated on interfaces, usable by the provider when
    configuring the interface.
    """
    _generate_link_master_metadata(
        desired_state.interfaces,
        current_state.interfaces,
        master_type=InterfaceType.BOND,
        get_slaves_func=_get_bond_slaves_from_state,
        set_metadata_func=_set_common_slaves_metadata,
    )
    _generate_link_master_metadata(
        desired_state.interfaces,
        current_state.interfaces,
        master_type=InterfaceType.OVS_BRIDGE,
        get_slaves_func=_get_ovs_slaves_from_state,
        set_metadata_func=_set_ovs_bridge_ports_metadata,
    )
    _generate_link_master_metadata(
        desired_state.interfaces,
        current_state.interfaces,
        master_type=InterfaceType.LINUX_BRIDGE,
        get_slaves_func=linux_bridge.get_slaves_from_state,
        set_metadata_func=linux_bridge.set_bridge_ports_metadata,
    )
    _generate_dns_metadata(desired_state, current_state)
    _generate_route_metadata(desired_state, current_state)
    _generate_route_rule_metadata(desired_state)


def remove_ifaces_metadata(ifaces_state):
    for iface_state in ifaces_state.interfaces.values():
        iface_state.pop(MASTER, None)
        iface_state.pop(MASTER_TYPE, None)
        iface_state.pop(BRPORT_OPTIONS, None)
        iface_state.get(Interface.IPV4, {}).pop(ROUTES, None)
        iface_state.get(Interface.IPV6, {}).pop(ROUTES, None)
        iface_state.get(Interface.IPV4, {}).pop(DNS_METADATA, None)
        iface_state.get(Interface.IPV6, {}).pop(DNS_METADATA, None)
        iface_state.get(Interface.IPV4, {}).pop(ROUTE_RULES_METADATA, None)
        iface_state.get(Interface.IPV6, {}).pop(ROUTE_RULES_METADATA, None)


def _get_bond_slaves_from_state(iface_state, default=()):
    return iface_state.get(Bond.CONFIG_SUBTREE, {}).get(Bond.SLAVES, default)


def _set_ovs_bridge_ports_metadata(master_state, slave_state):
    _set_common_slaves_metadata(master_state, slave_state)

    bridge = master_state.get(OVSBridge.CONFIG_SUBTREE, {})
    ports = bridge.get(OVSBridge.PORT_SUBTREE, [])
    slave_name = slave_state[Interface.NAME]
    port = next(
        filter(lambda n: n[OVSBridge.Port.NAME] == slave_name, ports,), {},
    )
    slave_state[BRPORT_OPTIONS] = port


def _set_common_slaves_metadata(master_state, slave_state):
    slave_state[MASTER] = master_state[Interface.NAME]
    slave_state[MASTER_TYPE] = master_state.get(Interface.TYPE)


def _get_ovs_slaves_from_state(iface_state, default=()):
    bridge = iface_state.get(OVSBridge.CONFIG_SUBTREE, {})
    ports = bridge.get(OVSBridge.PORT_SUBTREE)
    if ports is None:
        return default
    return [p[OVSBridge.Port.NAME] for p in ports]


def _generate_link_master_metadata(
    ifaces_desired_state,
    ifaces_current_state,
    master_type,
    get_slaves_func,
    set_metadata_func,
):
    """
    Given master's slaves, add to the slave interface the master information.

    Possible scenarios for a given desired and current sate:
    - The desired state contains both the masters and their slaves.
    - The desired state contains the masters and partially (or not at all)
      the slaves. Some or all the slaves are in the current state.
    - Master is in the current state and some of the slaves are in the desired
      state.
    """
    desired_masters = [
        (ifname, ifstate)
        for ifname, ifstate in ifaces_desired_state.items()
        if ifstate.get(Interface.TYPE) == master_type
        and ifstate.get(Interface.STATE)
        not in (InterfaceState.DOWN, InterfaceState.ABSENT)
    ]
    for master_name, master_state in desired_masters:
        desired_slaves = get_slaves_func(master_state)
        for slave in desired_slaves:
            if slave in ifaces_desired_state:
                set_metadata_func(master_state, ifaces_desired_state[slave])
            elif slave in ifaces_current_state:
                ifaces_desired_state[slave] = {
                    Interface.NAME: slave,
                    Interface.STATE: master_state[Interface.STATE],
                }
                set_metadata_func(master_state, ifaces_desired_state[slave])

    for master_name, master_state in desired_masters:
        desired_slaves = get_slaves_func(master_state)
        current_master_state = ifaces_current_state.get(master_name)
        if desired_slaves and current_master_state:
            current_slaves = get_slaves_func(current_master_state)
            slaves2remove = set(current_slaves) - set(desired_slaves)
            for slave in slaves2remove:
                if (
                    slave not in ifaces_desired_state
                    and _is_managed_interface(slave, ifaces_current_state)
                ):
                    ifaces_desired_state[slave] = {Interface.NAME: slave}

    current_masters = (
        (ifname, ifstate)
        for ifname, ifstate in ifaces_current_state.items()
        if ifstate.get(Interface.TYPE) == master_type
    )
    for master_name, master_state in current_masters:
        current_slaves = get_slaves_func(master_state)
        for slave in current_slaves:
            if slave in ifaces_desired_state:
                iface_state = ifaces_desired_state.get(master_name, {})
                if iface_state.get(Interface.STATE) not in (
                    InterfaceState.DOWN,
                    InterfaceState.ABSENT,
                ):
                    master_has_no_slaves_specified_in_desired = (
                        get_slaves_func(iface_state, None) is None
                    )
                    slave_has_no_master_specified_in_desired = (
                        ifaces_desired_state[slave].get(MASTER) is None
                    )
                    if (
                        slave_has_no_master_specified_in_desired
                        and master_has_no_slaves_specified_in_desired
                    ):
                        set_metadata_func(
                            master_state, ifaces_desired_state[slave]
                        )


def _is_managed_interface(ifname, ifaces_state):
    return (
        ifaces_state[ifname][Interface.STATE] == InterfaceState.UP
        and ifaces_state[ifname][Interface.TYPE] != InterfaceType.UNKNOWN
    )


def _generate_route_metadata(desired_state, current_state):
    """
    Save routes metadata under interface IP protocol for future processing by
    the providers.
    Currently route['next-hop-interface'] is mandatory.
    Routes which do not match any current or desired interface are ignored.
    """
    for iface_name, routes in desired_state.config_iface_routes.items():
        desired_iface_state = desired_state.interfaces.get(iface_name)
        current_iface_state = current_state.interfaces.get(iface_name)
        if desired_iface_state:
            _attach_route_metadata(desired_iface_state, routes)
        elif current_iface_state:
            desired_iface_state = desired_state.interfaces[iface_name] = {
                Interface.NAME: iface_name,
                Interface.TYPE: current_iface_state[Interface.TYPE],
            }
            _attach_route_metadata(desired_iface_state, routes)


def _attach_route_metadata(iface_state, routes):
    _init_iface_route_metadata(iface_state, Interface.IPV4)
    _init_iface_route_metadata(iface_state, Interface.IPV6)

    for route in routes:
        if iplib.is_ipv6_address(route.destination):
            iface_state[Interface.IPV6][ROUTES].append(route.to_dict())
        else:
            iface_state[Interface.IPV4][ROUTES].append(route.to_dict())


def _init_iface_route_metadata(iface_state, ip_key):
    ip_state = iface_state.get(ip_key)
    if not ip_state:
        ip_state = iface_state[ip_key] = {}
    ip_state[ROUTES] = []


def _generate_dns_metadata(desired_state, current_state):
    """
    Save DNS configuration on chosen interfaces as metadata.
    """
    _clear_current_dns_config(desired_state, current_state)
    servers = desired_state.config_dns.get(DNS.SERVER, [])
    searches = desired_state.config_dns.get(DNS.SEARCH, [])
    if not servers and not searches:
        return
    if _dns_config_not_changed(desired_state, current_state):
        _preserve_current_dns_metadata(desired_state, current_state)
    else:
        ifaces_routes = {
            ifname: [r.to_dict() for r in routes]
            for ifname, routes in desired_state.config_iface_routes.items()
        }
        ipv4_iface, ipv6_iface = nm.dns.find_interfaces_for_name_servers(
            ifaces_routes
        )
        _save_dns_metadata(
            desired_state,
            current_state,
            ipv4_iface,
            ipv6_iface,
            servers,
            searches,
        )


def _save_dns_metadata(
    desired_state, current_state, ipv4_iface, ipv6_iface, servers, searches
):
    index = 0
    searches_saved = False
    for server in servers:
        iface_name = None
        if iplib.is_ipv6_address(server):
            iface_name = ipv6_iface
            family = Interface.IPV6
        else:
            iface_name = ipv4_iface
            family = Interface.IPV4
        if not iface_name:
            raise NmstateValueError(
                "Failed to find suitable interface for saving DNS "
                "name servers: %s" % server
            )

        _include_name_only_iface_state(
            desired_state, current_state, [iface_name]
        )
        iface_state = desired_state.interfaces[iface_name]
        if family not in iface_state:
            iface_state[family] = {}

        if DNS_METADATA not in iface_state[family]:
            iface_state[family][DNS_METADATA] = {
                DNS.SERVER: [server],
                DNS.SEARCH: [] if searches_saved else searches,
                DNS_METADATA_PRIORITY: nm.dns.DNS_PRIORITY_STATIC_BASE + index,
            }
        else:
            iface_state[family][DNS_METADATA][DNS.SERVER].append(server)
        searches_saved = True
        index += 1


def _include_name_only_iface_state(desired_state, current_state, iface_names):
    ifnames = set(iface_names) & set(current_state.interfaces) - set(
        desired_state.interfaces
    )
    for ifname in ifnames:
        desired_state.interfaces[ifname] = {Interface.NAME: ifname}

    for iface_name in iface_names:
        if (
            iface_name not in desired_state.interfaces
            and iface_name in current_state.interfaces
        ):
            desired_state.interfaces[iface_name] = {Interface.NAME: iface_name}


def _clear_current_dns_config(desired_state, current_state):
    client = nm.nmclient.client()
    current_dns_ifaces = nm.dns.get_dns_config_iface_names(
        nm.ipv4.acs_and_ip_profiles(client),
        nm.ipv6.acs_and_ip_profiles(client),
    )
    _include_name_only_iface_state(
        desired_state, current_state, current_dns_ifaces
    )


def _dns_config_not_changed(desired_state, current_state):
    """
    Return True if desired_state DNS config equal to current_state and
    interface holding current DNS config is UP and corresponding IP family
    is enabled.
    """
    if desired_state.config_dns != current_state.config_dns:
        return False
    client = nm.nmclient.client()
    iface_dns_configs = nm.dns.get_indexed_dns_config_by_iface(
        nm.ipv4.acs_and_ip_profiles(client),
        nm.ipv6.acs_and_ip_profiles(client),
    )
    for iface_name, iface_dns_config in iface_dns_configs.items():
        if iface_name not in desired_state.interfaces:
            continue
        iface_state = desired_state.interfaces[iface_name]
        if (
            Interface.STATE in iface_state
            and iface_state[Interface.STATE] != InterfaceState.UP
        ):
            return False
        for family in iface_dns_config:
            if family in iface_state and not iface_state[family].get(
                InterfaceIP.ENABLED
            ):
                return False
    return True


def _preserve_current_dns_metadata(desired_state, current_state):
    client = nm.nmclient.client()
    iface_dns_configs = nm.dns.get_indexed_dns_config_by_iface(
        nm.ipv4.acs_and_ip_profiles(client),
        nm.ipv6.acs_and_ip_profiles(client),
    )
    for iface_name, iface_dns_config in iface_dns_configs.items():
        if iface_name not in desired_state.interfaces:
            continue
        for family, dns_metadata in iface_dns_config.items():
            iface_state = desired_state.interfaces[iface_name]
            if family not in iface_state:
                iface_state[family] = {}
            iface_state[family][DNS_METADATA] = dns_metadata


def _generate_route_rule_metadata(desired_state):
    routes_v4 = []
    routes_v6 = []
    for routes in desired_state.config_iface_routes.values():
        for route in routes:
            if iplib.is_ipv6_address(route.destination):
                routes_v6.append(route)
            else:
                routes_v4.append(route)

    _generate_route_rule_per_stack_metadata(
        Interface.IPV4,
        desired_state.config_route_table_rules_v4,
        routes_v4,
        desired_state,
    )
    _generate_route_rule_per_stack_metadata(
        Interface.IPV6,
        desired_state.config_route_table_rules_v6,
        routes_v6,
        desired_state,
    )


def _generate_route_rule_per_stack_metadata(
    family, indexed_rules, routes, desired_state
):
    for route_table, rules in indexed_rules.items():
        iface_name = _find_iface_for_route_table(routes, route_table)
        if not iface_name:
            raise NmstateValueError(
                "Failed to find suitable interface for saving route rule: "
                "{}".format(rules[0])
            )
        iface_state = desired_state.interfaces[iface_name]
        _attach_route_rule_metadata(iface_state, rules, family)


def _find_iface_for_route_table(routes, route_table):
    for route in routes:
        if route.table_id == route_table:
            return route.next_hop_interface
    return None


def _attach_route_rule_metadata(iface_state, rules, family):
    _init_iface_route_rule_metadata(iface_state, family)
    for rule in rules:
        iface_state[family][ROUTE_RULES_METADATA].append(rule.to_dict())


def _init_iface_route_rule_metadata(iface_state, ip_key):
    ip_state = iface_state.get(ip_key)
    if not ip_state:
        ip_state = iface_state[ip_key] = {}
    ip_state[ROUTE_RULES_METADATA] = []
