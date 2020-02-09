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

import base64
import hashlib
import itertools

from libnmstate.error import NmstateValueError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import LinuxBridge as LB
from libnmstate.schema import OVSBridge as OvsB

from . import bond
from . import bridge
from . import connection
from . import device
from . import ipv4
from . import ipv6
from . import nmclient
from . import ovs
from . import sriov
from . import team
from . import translator
from . import user
from . import vlan
from . import vxlan
from . import wired


MAXIMUM_INTERFACE_LENGTH = 15

MASTER_METADATA = "_master"
MASTER_TYPE_METADATA = "_master_type"
MASTER_IFACE_TYPES = ovs.BRIDGE_TYPE, bond.BOND_TYPE, LB.TYPE

BRPORT_OPTIONS_METADATA = "_brport_options"

IFACE_NAME_METADATA = "_iface_name"


def create_new_ifaces(con_profiles):
    for connection_profile in con_profiles:
        connection_profile.add(save_to_disk=True)


def prepare_new_ifaces_configuration(ifaces_desired_state):
    # Delete the existing profiles before create the new ones
    for iface_desired_state in ifaces_desired_state:
        connection.delete_iface_inactive_connections(
            iface_desired_state[Interface.NAME]
        )

    return [
        _build_connection_profile(iface_desired_state)
        for iface_desired_state in ifaces_desired_state
    ]


def edit_existing_ifaces(con_profiles):
    for connection_profile in con_profiles:
        devname = connection_profile.devname
        nmdev = device.get_device_by_name(devname)
        cur_con_profile = None
        if nmdev:
            cur_con_profile = connection.ConnectionProfile()
            cur_con_profile.import_by_device(nmdev)
        if cur_con_profile and cur_con_profile.profile:
            connection_profile.commit(nmdev=nmdev)
        else:
            # Missing connection, attempting to create a new one.
            connection_profile.add(save_to_disk=True)


def prepare_edited_ifaces_configuration(ifaces_desired_state):
    con_profiles = []

    for iface_desired_state in ifaces_desired_state:
        ifname = iface_desired_state[Interface.NAME]
        nmdev = device.get_device_by_name(ifname)
        cur_con_profile = None
        if nmdev:
            cur_con_profile = connection.ConnectionProfile()
            cur_con_profile.import_by_device(nmdev)
        new_con_profile = _build_connection_profile(
            iface_desired_state, base_con_profile=cur_con_profile
        )
        if not new_con_profile.devname:
            set_conn = new_con_profile.profile.get_setting_connection()
            set_conn.props.interface_name = iface_desired_state[Interface.NAME]
        if cur_con_profile and cur_con_profile.profile:
            cur_con_profile.update(new_con_profile)
            con_profiles.append(cur_con_profile)
        else:
            # Missing connection, attempting to create a new one.
            connection.delete_iface_inactive_connections(ifname)
            con_profiles.append(new_con_profile)

    return con_profiles


def set_ifaces_admin_state(ifaces_desired_state, con_profiles=()):
    """
    Control interface admin state by activating, deactivating and deleting
    devices connection profiles.

    The `absent` state results in deactivating the device and deleting
    the connection profile.
    FIXME: The `down` state is currently handled in the same way.

    For new virtual devices, the `up` state is handled by activating the
    new connection profile. For existing devices, the device is activated,
    leaving it to choose the correct profile.

    In order to activate correctly the interfaces, the order is significant:
    - Master-less master interfaces.
    - New interfaces (virtual interfaces, but not OVS ones).
    - Master interfaces.
    - OVS ports.
    - OVS internal.
    - All the rest.
    """
    con_profiles_by_devname = _index_profiles_by_devname(con_profiles)
    new_ifaces = _get_new_ifaces(con_profiles)
    new_ifaces_to_activate = set()
    new_vlan_ifaces_to_activate = set()
    new_vxlan_ifaces_to_activate = set()
    new_ovs_interface_to_activate = set()
    new_ovs_port_to_activate = set()
    new_master_not_enslaved_ifaces = set()
    master_ifaces_to_edit = set()
    ifaces_to_edit = set()
    remove_devs_actions = {}

    for iface_desired_state in ifaces_desired_state:
        ifname = iface_desired_state[Interface.NAME]
        nmdev = device.get_device_by_name(ifname)
        if not nmdev:
            if (
                ifname in new_ifaces
                and iface_desired_state[Interface.STATE] == InterfaceState.UP
            ):
                if _is_master_iface(
                    iface_desired_state
                ) and not _is_slave_iface(iface_desired_state):
                    new_master_not_enslaved_ifaces.add(ifname)
                elif (
                    iface_desired_state[Interface.TYPE]
                    == ovs.INTERNAL_INTERFACE_TYPE
                ):
                    new_ovs_interface_to_activate.add(ifname)
                elif iface_desired_state[Interface.TYPE] == ovs.PORT_TYPE:
                    new_ovs_port_to_activate.add(ifname)
                elif iface_desired_state[Interface.TYPE] == InterfaceType.VLAN:
                    new_vlan_ifaces_to_activate.add(ifname)
                elif (
                    iface_desired_state[Interface.TYPE] == InterfaceType.VXLAN
                ):
                    new_vxlan_ifaces_to_activate.add(ifname)
                else:
                    new_ifaces_to_activate.add(ifname)
        else:
            if iface_desired_state[Interface.STATE] == InterfaceState.UP:
                if _is_master_iface(iface_desired_state):
                    master_ifaces_to_edit.add(
                        (nmdev, con_profiles_by_devname[ifname].profile)
                    )
                else:
                    ifaces_to_edit.add(
                        (nmdev, con_profiles_by_devname[ifname].profile)
                    )
            elif iface_desired_state[Interface.STATE] in (
                InterfaceState.DOWN,
                InterfaceState.ABSENT,
            ):
                nmdevs = _get_affected_devices(iface_desired_state)
                for affected_nmdev in nmdevs:
                    remove_devs_actions[affected_nmdev] = [
                        device.deactivate,
                        device.delete,
                    ]
                if (
                    nmdev.is_software()
                    and nmdev.get_device_type() != nmclient.NM.DeviceType.VETH
                ):
                    remove_devs_actions[nmdev].append(device.delete_device)
            else:
                raise NmstateValueError(
                    "Invalid state {} for interface {}".format(
                        iface_desired_state[Interface.STATE],
                        iface_desired_state[Interface.NAME],
                    )
                )

    # Do not remove devices that are marked for editing.
    for dev, _ in itertools.chain(master_ifaces_to_edit, ifaces_to_edit):
        remove_devs_actions.pop(dev, None)

    for ifname in new_master_not_enslaved_ifaces:
        device.activate(dev=None, connection_id=ifname)

    for ifname in new_ifaces_to_activate:
        device.activate(dev=None, connection_id=ifname)

    for dev, con_profile in master_ifaces_to_edit:
        device.modify(dev, con_profile)

    for ifname in new_ovs_port_to_activate:
        device.activate(dev=None, connection_id=ifname)

    for ifname in new_ovs_interface_to_activate:
        device.activate(dev=None, connection_id=ifname)

    for dev, con_profile in ifaces_to_edit:
        device.modify(dev, con_profile)

    for ifname in new_vlan_ifaces_to_activate:
        device.activate(dev=None, connection_id=ifname)

    for ifname in new_vxlan_ifaces_to_activate:
        device.activate(dev=None, connection_id=ifname)

    for dev, actions in remove_devs_actions.items():
        for action in actions:
            action(dev)


def _index_profiles_by_devname(con_profiles):
    return {con_profile.devname: con_profile for con_profile in con_profiles}


def _get_new_ifaces(con_profiles):
    ifaces_without_device = set()
    for con_profile in con_profiles:
        ifname = con_profile.devname
        nmdev = device.get_device_by_name(ifname)
        if not nmdev:
            # When the profile id is different from the iface name, use the
            # profile id.
            if ifname != con_profile.con_id:
                ifname = con_profile.con_id
            ifaces_without_device.add(ifname)
    return ifaces_without_device


def _is_master_iface(iface_state):
    return iface_state[Interface.TYPE] in MASTER_IFACE_TYPES


def _is_slave_iface(iface_state):
    return iface_state.get(MASTER_METADATA)


def _get_affected_devices(iface_state):
    nmdev = device.get_device_by_name(iface_state[Interface.NAME])
    devs = []
    if nmdev:
        devs += [nmdev]
        iface_type = iface_state[Interface.TYPE]
        if iface_type == ovs.BRIDGE_TYPE:
            port_slaves = ovs.get_slaves(nmdev)
            iface_slaves = [
                iface for port in port_slaves for iface in ovs.get_slaves(port)
            ]
            devs += port_slaves + iface_slaves
        elif iface_type == LB.TYPE:
            devs += bridge.get_slaves(nmdev)
        elif iface_type == bond.BOND_TYPE:
            devs += bond.get_slaves(nmdev)

        ovs_port_dev = ovs.get_port_by_slave(nmdev)
        if ovs_port_dev:
            devs.append(ovs_port_dev)
    return devs


def prepare_proxy_ifaces_desired_state(ifaces_desired_state):
    """
    Prepare the state of the "proxy" interfaces. These are interfaces that
    exist as NM entities/profiles, but are invisible to the API.
    These proxy interfaces state is created as a side effect of other ifaces
    definition.
    Note: This function modifies the ifaces_desired_state content in addition
    to returning a new set of states for the proxy interfaces.

    In OVS case, the port profile is the proxy, it is not part of the public
    state of the system, but internal to the NM provider.
    """
    new_ifaces_desired_state = []
    for iface_desired_state in ifaces_desired_state:
        master_type = iface_desired_state.get(MASTER_TYPE_METADATA)
        if master_type != ovs.BRIDGE_TYPE:
            continue
        port_opts_metadata = iface_desired_state.get(BRPORT_OPTIONS_METADATA)
        if port_opts_metadata is None:
            continue
        port_iface_desired_state = _create_ovs_port_iface_desired_state(
            iface_desired_state, port_opts_metadata
        )
        new_ifaces_desired_state.append(port_iface_desired_state)
        # The "visible" slave/interface needs to point to the port profile
        iface_desired_state[MASTER_METADATA] = port_iface_desired_state[
            IFACE_NAME_METADATA
        ]
        iface_desired_state[MASTER_TYPE_METADATA] = ovs.PORT_TYPE
    return new_ifaces_desired_state


def _create_ovs_port_iface_desired_state(iface_desired_state, port_options):
    port_name = ovs.PORT_PROFILE_PREFIX + iface_desired_state[Interface.NAME]
    return {
        Interface.NAME: port_name,
        Interface.TYPE: ovs.PORT_TYPE,
        Interface.STATE: iface_desired_state[Interface.STATE],
        OvsB.OPTIONS_SUBTREE: port_options,
        MASTER_METADATA: iface_desired_state[MASTER_METADATA],
        MASTER_TYPE_METADATA: iface_desired_state[MASTER_TYPE_METADATA],
        IFACE_NAME_METADATA: _generate_hash_iface_name(port_name),
    }


def _generate_hash_iface_name(name):
    """
    Given a name, generate a hash string that may be used as an interface name.

    The OVS port does not have an actual interface in the kernel, but
    its length is still limited by NM connection.interface-name.
    https://bugzilla.redhat.com/1788432
    As a workaround, hash the full name and use it as an alternative device
    name (assigned as a metadata). The profile/connection name format has
    an OVS PORT prefix
    """
    name_ = base64.urlsafe_b64encode(hashlib.sha256(name.encode()).digest())
    return name_[:MAXIMUM_INTERFACE_LENGTH].decode()


def _build_connection_profile(iface_desired_state, base_con_profile=None):
    iface_type = translator.Api2Nm.get_iface_type(
        iface_desired_state[Interface.TYPE]
    )

    base_profile = base_con_profile.profile if base_con_profile else None

    settings = [
        ipv4.create_setting(
            iface_desired_state.get(Interface.IPV4), base_profile
        ),
        ipv6.create_setting(
            iface_desired_state.get(Interface.IPV6), base_profile
        ),
    ]

    con_setting = connection.ConnectionSetting()
    if base_profile:
        con_setting.import_by_profile(base_con_profile)
    else:
        iface_name = (
            iface_desired_state.get(IFACE_NAME_METADATA)
            or iface_desired_state[Interface.NAME]
        )
        con_setting.create(
            con_name=iface_desired_state[Interface.NAME],
            iface_name=iface_name,
            iface_type=iface_type,
        )
    master = iface_desired_state.get(MASTER_METADATA)
    _translate_master_type(iface_desired_state)
    master_type = iface_desired_state.get(MASTER_TYPE_METADATA)
    con_setting.set_master(master, master_type)
    settings.append(con_setting.setting)

    wired_setting = wired.create_setting(iface_desired_state, base_profile)
    if wired_setting:
        settings.append(wired_setting)

    user_setting = user.create_setting(iface_desired_state, base_profile)
    if user_setting:
        settings.append(user_setting)

    bond_opts = translator.Api2Nm.get_bond_options(iface_desired_state)
    if bond_opts:
        settings.append(bond.create_setting(bond_opts))
    elif iface_type == bridge.BRIDGE_TYPE:
        bridge_options = iface_desired_state.get(bridge.BRIDGE_TYPE, {}).get(
            LB.OPTIONS_SUBTREE
        )
        if bridge_options:
            linux_bridge_setting = bridge.create_setting(
                bridge_options, base_profile
            )
            settings.append(linux_bridge_setting)
    elif iface_type == ovs.BRIDGE_TYPE:
        ovs_bridge_state = iface_desired_state.get(OvsB.CONFIG_SUBTREE, {})
        ovs_bridge_options = ovs_bridge_state.get(OvsB.OPTIONS_SUBTREE)
        if ovs_bridge_options:
            settings.append(ovs.create_bridge_setting(ovs_bridge_options))
    elif iface_type == ovs.PORT_TYPE:
        ovs_port_options = iface_desired_state.get(OvsB.OPTIONS_SUBTREE)
        settings.append(ovs.create_port_setting(ovs_port_options))
    elif iface_type == ovs.INTERNAL_INTERFACE_TYPE:
        settings.append(ovs.create_interface_setting())

    bridge_port_options = iface_desired_state.get(BRPORT_OPTIONS_METADATA)
    if bridge_port_options and master_type == bridge.BRIDGE_TYPE:
        settings.append(
            bridge.create_port_setting(bridge_port_options, base_profile)
        )

    vlan_setting = vlan.create_setting(iface_desired_state, base_profile)
    if vlan_setting:
        settings.append(vlan_setting)

    vxlan_setting = vxlan.create_setting(iface_desired_state, base_profile)
    if vxlan_setting:
        settings.append(vxlan_setting)

    sriov_setting = sriov.create_setting(iface_desired_state, base_con_profile)
    if sriov_setting:
        settings.append(sriov_setting)

    team_setting = team.create_setting(iface_desired_state, base_con_profile)
    if team_setting:
        settings.append(team_setting)

    new_profile = connection.ConnectionProfile()
    new_profile.create(settings)
    return new_profile


def _translate_master_type(iface_desired_state):
    """
    Translates the master type metadata names to their equivalent
    NM type names.
    """
    master_type = iface_desired_state.get(MASTER_TYPE_METADATA)
    if master_type == LB.TYPE:
        iface_desired_state[MASTER_TYPE_METADATA] = bridge.BRIDGE_TYPE
