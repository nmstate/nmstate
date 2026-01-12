# SPDX-License-Identifier: Apache-2.0

from contextlib import contextmanager

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import LinuxBridge


@contextmanager
def linux_bridge(
    name,
    bridge_subtree_state,
    extra_iface_state=None,
    create=True,
    kernel_mode=False,
    ports=None,
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: name,
                Interface.TYPE: InterfaceType.LINUX_BRIDGE,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {InterfaceIPv4.ENABLED: False},
                Interface.IPV6: {InterfaceIPv6.ENABLED: False},
            }
        ]
    }
    desired_iface_state = desired_state[Interface.KEY][0]
    if bridge_subtree_state:
        desired_iface_state[LinuxBridge.CONFIG_SUBTREE] = bridge_subtree_state
    if extra_iface_state:
        desired_iface_state.update(extra_iface_state)
    if ports:
        for port in ports:
            desired_iface_state.setdefault(LinuxBridge.CONFIG_SUBTREE, {})
            add_port_to_bridge(
                desired_iface_state[LinuxBridge.CONFIG_SUBTREE], port
            )
    if create:
        libnmstate.apply(desired_state, kernel_only=kernel_mode)

    try:
        yield desired_state
    finally:
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: name,
                        Interface.TYPE: InterfaceType.LINUX_BRIDGE,
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            },
            kernel_only=kernel_mode,
        )


def add_port_to_bridge(bridge_subtree_state, port_name, port_state=None):
    if LinuxBridge.PORT_SUBTREE not in bridge_subtree_state:
        bridge_subtree_state[LinuxBridge.PORT_SUBTREE] = []

    if port_state is None:
        port_state = {}

    port_state[LinuxBridge.Port.NAME] = port_name
    bridge_subtree_state[LinuxBridge.PORT_SUBTREE].append(port_state)

    return bridge_subtree_state


def create_bridge_subtree_state(options_state=None):
    if options_state is None:
        options_state = {
            LinuxBridge.STP_SUBTREE: {LinuxBridge.STP.ENABLED: False}
        }
    return {LinuxBridge.OPTIONS_SUBTREE: options_state}


def generate_vlan_filtering_config(
    port_type, trunk_tags=None, tag=None, native_vlan=None
):
    vlan_filtering_state = {
        LinuxBridge.Port.Vlan.MODE: port_type,
        LinuxBridge.Port.Vlan.TRUNK_TAGS: trunk_tags or [],
    }

    if tag:
        vlan_filtering_state[LinuxBridge.Port.Vlan.TAG] = tag
    if native_vlan is not None:
        vlan_filtering_state[LinuxBridge.Port.Vlan.ENABLE_NATIVE] = native_vlan

    return {LinuxBridge.Port.VLAN_SUBTREE: vlan_filtering_state}


def generate_vlan_id_config(*vlan_ids):
    return [
        {LinuxBridge.Port.Vlan.TrunkTags.ID: vlan_id} for vlan_id in vlan_ids
    ]


def generate_vlan_id_range_config(min_vlan_id, max_vlan_id):
    return {
        LinuxBridge.Port.Vlan.TrunkTags.ID_RANGE: {
            LinuxBridge.Port.Vlan.TrunkTags.MIN_RANGE: min_vlan_id,
            LinuxBridge.Port.Vlan.TrunkTags.MAX_RANGE: max_vlan_id,
        }
    }
