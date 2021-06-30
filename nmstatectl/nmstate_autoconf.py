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

import argparse
import fnmatch
import logging
import os
import sys

import libnmstate
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import LLDP
from libnmstate.schema import VLAN


VLAN_TLV_NAME = "ieee-802-1-vlans"
VLAN_ID = "vid"
VLAN_NAME = "name"
BOND_NAME_PREFIX = "bond"


def main():
    logging.basicConfig(
        format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
        level=logging.DEBUG,
    )

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version", action="store_true", help="Display nmstate version"
    )
    parser.add_argument(
        "-d",
        "--dry-run",
        default=False,
        action="store_true",
        dest="dry_run",
        help=(
            "Generate the network state that is going to be applied and print "
            "it out without applying any change."
        ),
    )
    parser.add_argument(
        "only",
        default="*",
        nargs="?",
        metavar=Interface.KEY,
        help="Use only the specified NICs (comma-separated)",
    )

    args = parser.parse_args()
    if args.version:
        print(libnmstate.__version__)
    else:
        bond_vlans(args)


def bond_vlans(args):
    state = _filter_state(libnmstate.show(), args.only)

    if not state[Interface.KEY]:
        sys.stderr.write("ERROR: No such interface\n")
        return os.EX_USAGE

    vlan_to_ifaces = _identify_connected_vlans(state[Interface.KEY])

    desired_state = {Interface.KEY: []}
    for (vlan_id, vlan_name), ifaces_name in vlan_to_ifaces.items():
        if len(ifaces_name) > 1:
            bond_iface = _generate_bond_iface(vlan_id, ifaces_name)
            vlan_iface = _generate_vlan_iface(
                vlan_name, vlan_id, bond_iface[Interface.NAME]
            )
            desired_state[Interface.KEY].extend([bond_iface, vlan_iface])
        else:
            vlan_iface = _generate_vlan_iface(
                vlan_name, vlan_id, ifaces_name[0]
            )
            desired_state[Interface.KEY].append(vlan_iface)

    if args.dry_run:
        desired_state = libnmstate.PrettyState(desired_state)
        sys.stdout.write(desired_state.yaml)
    else:
        libnmstate.apply(desired_state)


def _filter_state(state, allowlist):
    if allowlist != "*":
        patterns = [p for p in allowlist.split(",")]
        # LLDP-autoconf only cares about Interfaces, will not touch routes or
        # route rules.
        state[Interface.KEY] = _filter_interfaces(state, patterns)

    return {Interface.KEY: state[Interface.KEY]}


def _filter_interfaces(state, patterns):
    """
    return the states for all the interfaces from `state` that match at least
    one of the provided patterns.
    """
    show_interfaces = []

    for interface in state[Interface.KEY]:
        for pattern in patterns:
            if fnmatch.fnmatch(interface[Interface.NAME], pattern):
                show_interfaces.append(interface)
                break
    return show_interfaces


def _identify_connected_vlans(ifaces):
    vlan_to_ifaces = {}
    for iface in ifaces:
        if iface.get(LLDP.CONFIG_SUBTREE, {}).get(LLDP.ENABLED):
            neighbors = iface[LLDP.CONFIG_SUBTREE].get(
                LLDP.NEIGHBORS_SUBTREE, []
            )
            for neighbor in neighbors:
                for tlv in neighbor:
                    if tlv.get(VLAN_TLV_NAME):
                        vlan_id = tlv[VLAN_TLV_NAME][0].get(VLAN_ID)
                        vlan_name = tlv[VLAN_TLV_NAME][0].get(VLAN_NAME)
                        identifier = (vlan_id, vlan_name)
                        existing_vlan_info = vlan_to_ifaces.get(identifier, [])
                        existing_vlan_info.append(iface.get(Interface.NAME))
                        vlan_to_ifaces.update({identifier: existing_vlan_info})

    return vlan_to_ifaces


def _generate_bond_iface(vlan_id, ifaces_name):
    bond_state = {
        Interface.NAME: BOND_NAME_PREFIX + str(vlan_id),
        Interface.TYPE: InterfaceType.BOND,
        Interface.STATE: InterfaceState.UP,
        Bond.CONFIG_SUBTREE: {
            Bond.MODE: BondMode.ROUND_ROBIN,
            Bond.PORT: ifaces_name,
        },
    }

    return bond_state


def _generate_vlan_iface(vlan_name, vlan_id, base_iface):
    vlan_state = {
        Interface.NAME: vlan_name,
        Interface.TYPE: InterfaceType.VLAN,
        Interface.STATE: InterfaceState.UP,
        VLAN.CONFIG_SUBTREE: {
            VLAN.BASE_IFACE: base_iface,
            VLAN.ID: vlan_id,
        },
    }

    return vlan_state
