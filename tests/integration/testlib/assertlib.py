#
# Copyright (c) 2018-2019 Red Hat, Inc.
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

from operator import itemgetter

import libnmstate
from libnmstate.schema import Bond
from libnmstate.schema import DNS
from libnmstate.schema import Route
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import LinuxBridge as LB
from libnmstate.schema import OvsDB

from . import statelib


def assert_state(desired_state_data):
    """Given a state, assert it against the current state."""
    desired_state, current_state = _prepare_state_for_verify(
        desired_state_data
    )

    assert desired_state.state == current_state.state


def assert_absent(*ifnames):
    """ Assert that a interface is not present in the current state """

    current_state = statelib.show_only(ifnames)
    assert not current_state[Interface.KEY]


def assert_state_match(desired_state_data):
    """
    Given a state, assert it against the current state by treating missing
    value in desired_state as match.
    """
    desired_state, current_state = _prepare_state_for_verify(
        desired_state_data
    )
    assert desired_state.match(current_state)


def assert_mac_address(state, expected_mac=None):
    """ Asserts that all MAC addresses of ifaces in a state are the same """
    macs = _iface_macs(state)
    if not expected_mac:
        expected_mac = next(macs)
    for mac in macs:
        assert expected_mac.upper() == mac


def _iface_macs(state):
    for ifstate in state[Interface.KEY]:
        yield ifstate[Interface.MAC]


def _prepare_state_for_verify(desired_state_data):
    current_state_data = libnmstate.show()
    # Ignore route and dns for assert check as the check are done in the test
    # case code.
    current_state_data.pop(Route.KEY, None)
    current_state_data.pop(DNS.KEY, None)
    desired_state_data = copy.deepcopy(desired_state_data)
    desired_state_data.pop(Route.KEY, None)
    desired_state_data.pop(DNS.KEY, None)

    current_state = statelib.State(current_state_data)
    current_state.filter(desired_state_data)
    current_state.normalize()

    full_desired_state = statelib.State(current_state.state)
    full_desired_state.update(desired_state_data)
    full_desired_state.remove_absent_entries()
    full_desired_state.normalize()
    _fix_bond_state(current_state)
    _fix_ovsdb_external_ids(full_desired_state)
    _remove_iface_state_for_verify(full_desired_state)
    _remove_iface_state_for_verify(current_state)
    _expand_vlan_filter_range(current_state)
    _expand_vlan_filter_range(full_desired_state)
    _remove_linux_bridge_read_only_options(current_state)
    _remove_linux_bridge_read_only_options(full_desired_state)

    return full_desired_state, current_state


def assert_no_config_route_to_iface(iface_name):
    """
    Asserts no config route next hop to specified interface.
    """
    current_state = libnmstate.show()

    assert not any(
        route
        for route in current_state[Route.KEY][Route.CONFIG]
        if route[Route.NEXT_HOP_INTERFACE] == iface_name
    )


def _fix_bond_state(current_state):
    """
    Allow current state include default value of "arp_ip_target"
    when not found in bond_options and "arp_interval" is found in bond_options.
    """
    for iface_state in current_state.state[Interface.KEY]:
        if iface_state.get(Interface.TYPE) == InterfaceType.BOND:
            bond_options = iface_state[Bond.CONFIG_SUBTREE][
                Bond.OPTIONS_SUBTREE
            ]
            if (
                "arp_interval" in bond_options
                and "arp_ip_target" not in bond_options
            ):
                bond_options["arp_ip_target"] = ""


def _fix_ovsdb_external_ids(state):
    for iface_state in state.state[Interface.KEY]:
        external_ids = iface_state.get(OvsDB.OVS_DB_SUBTREE, {}).get(
            OvsDB.EXTERNAL_IDS, {}
        )
        for key, value in external_ids.items():
            external_ids[key] = str(value)


def _remove_iface_state_for_verify(state):
    for iface_state in state.state[Interface.KEY]:
        iface_state.pop(Interface.STATE, None)


def _expand_vlan_filter_range(state):
    for iface_state in state.state[Interface.KEY]:
        if (
            iface_state.get(Interface.TYPE) != InterfaceType.LINUX_BRIDGE
            or LB.CONFIG_SUBTREE not in iface_state
            or LB.PORT_SUBTREE not in iface_state[LB.CONFIG_SUBTREE]
        ):
            continue
        port_configs = iface_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE]
        for port_config in port_configs:
            if LB.Port.VLAN_SUBTREE not in port_config:
                continue
            vlan_config = port_config[LB.Port.VLAN_SUBTREE]
            if LB.Port.Vlan.TRUNK_TAGS not in vlan_config:
                continue
            new_trunk_tags = []
            for trunk_tag in vlan_config[LB.Port.Vlan.TRUNK_TAGS]:
                if LB.Port.Vlan.TrunkTags.ID_RANGE in trunk_tag:
                    vid_range = trunk_tag[LB.Port.Vlan.TrunkTags.ID_RANGE]
                    vid_min = vid_range[LB.Port.Vlan.TrunkTags.MIN_RANGE]
                    vid_max = vid_range[LB.Port.Vlan.TrunkTags.MAX_RANGE]
                    for vid in range(vid_min, vid_max + 1):
                        new_trunk_tags.append({LB.Port.Vlan.TrunkTags.ID: vid})
                elif LB.Port.Vlan.TrunkTags.ID in trunk_tag:
                    new_trunk_tags.append(
                        {
                            LB.Port.Vlan.TrunkTags.ID: trunk_tag[
                                LB.Port.Vlan.TrunkTags.ID
                            ]
                        }
                    )

            new_trunk_tags.sort(key=itemgetter(LB.Port.Vlan.TrunkTags.ID))
            port_config[LB.Port.VLAN_SUBTREE][
                LB.Port.Vlan.TRUNK_TAGS
            ] = new_trunk_tags


def _remove_linux_bridge_read_only_options(state):
    for iface_state in state.state[Interface.KEY]:
        bridge_options = iface_state.get(LB.CONFIG_SUBTREE, {}).get(
            LB.OPTIONS_SUBTREE, {}
        )
        if bridge_options:
            for key in (LB.Options.HELLO_TIMER, LB.Options.GC_TIMER):
                bridge_options.pop(key, None)
