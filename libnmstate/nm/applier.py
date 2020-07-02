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

import logging
import itertools

from libnmstate.error import NmstateValueError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import LinuxBridge as LB
from libnmstate.schema import OVSBridge as OvsB
from libnmstate.schema import OVSInterface
from libnmstate.schema import Team
from libnmstate.ifaces.bond import BondIface
from libnmstate.ifaces.bridge import BridgeIface

from . import bond
from . import bridge
from . import connection
from . import device
from . import ipv4
from . import ipv6
from . import lldp
from . import ovs
from . import sriov
from . import team
from . import translator
from . import user
from . import vlan
from . import vxlan
from . import wired
from .common import NM
from .dns import get_dns_config_iface_names


MAXIMUM_INTERFACE_LENGTH = 15

MASTER_METADATA = "_master"
MASTER_TYPE_METADATA = "_master_type"
MASTER_IFACE_TYPES = (
    InterfaceType.OVS_BRIDGE,
    bond.BOND_TYPE,
    LB.TYPE,
    Team.TYPE,
)


def apply_changes(context, net_state, save_to_disk):
    con_profiles = []

    _preapply_dns_fix(context, net_state)

    ifaces_desired_state = net_state.ifaces.state_to_edit
    ifaces_desired_state.extend(
        _create_proxy_ifaces_desired_state(ifaces_desired_state)
    )

    for iface_desired_state in filter(
        lambda s: s.get(Interface.STATE)
        not in (InterfaceState.ABSENT, InterfaceState.DOWN),
        ifaces_desired_state,
    ):
        ifname = iface_desired_state[Interface.NAME]
        nmdev = context.get_nm_dev(ifname)
        cur_con_profile = None
        if nmdev:
            cur_con_profile = connection.ConnectionProfile(context)
            cur_con_profile.import_by_device(nmdev)
        else:
            # Profile for virtual interface will remove interface when down
            # hence search on existing NM.RemoteConnections
            con_profile = context.client.get_connection_by_id(ifname)
            if con_profile and con_profile.get_interface_name() == ifname:
                cur_con_profile = connection.ConnectionProfile(
                    context, profile=con_profile
                )
        original_desired_iface_state = {}
        if net_state.ifaces.get(ifname):
            iface = net_state.ifaces[ifname]
            if iface.is_desired:
                original_desired_iface_state = iface.original_dict
            if (
                set(original_desired_iface_state.keys())
                <= set([Interface.STATE, Interface.NAME, Interface.TYPE])
                and cur_con_profile
                and cur_con_profile.profile
                and not net_state.ifaces[ifname].is_changed
            ):
                # Don't create new profile if original desire does not ask
                # anything besides state:up and not been marked as changed.
                # We don't need to do this once we support querying on-disk
                # configure
                con_profiles.append(cur_con_profile)
                continue
        new_con_profile = _build_connection_profile(
            context,
            iface_desired_state,
            cur_con_profile,
            original_desired_iface_state,
        )
        if not new_con_profile.devname:
            set_conn = new_con_profile.profile.get_setting_connection()
            set_conn.props.interface_name = iface_desired_state[Interface.NAME]
        if cur_con_profile and cur_con_profile.profile:
            cur_con_profile.update(new_con_profile, save_to_disk)
            con_profiles.append(new_con_profile)
        else:
            # Missing connection, attempting to create a new one.
            connection.delete_iface_inactive_connections(context, ifname)
            new_con_profile.add(save_to_disk)
            con_profiles.append(new_con_profile)
    context.wait_all_finish()

    _set_ifaces_admin_state(context, ifaces_desired_state, con_profiles)
    context.wait_all_finish()


def _set_ifaces_admin_state(context, ifaces_desired_state, con_profiles):
    """
    Control interface admin state by activating, deactivating and deleting
    devices connection profiles.

    The `absent` state results in deactivating the device and deleting
    the connection profile.

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
    new_ifaces = _get_new_ifaces(context, con_profiles)
    new_ifaces_to_activate = set()
    new_vlan_ifaces_to_activate = set()
    new_vxlan_ifaces_to_activate = set()
    new_ovs_interface_to_activate = set()
    new_ovs_port_to_activate = set()
    new_master_not_enslaved_ifaces = set()
    master_ifaces_to_edit = set()
    ifaces_to_edit = set()
    devs_to_deactivate = {}
    devs_to_delete_profile = {}
    devs_to_delete = {}
    devs_to_deactivate_beforehand = []
    profiles_to_delete = []

    current_profiles = context.client.get_connections()

    for iface_desired_state in ifaces_desired_state:
        ifname = iface_desired_state[Interface.NAME]
        nmdev = context.get_nm_dev(ifname)
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
                    == InterfaceType.OVS_INTERFACE
                ):
                    new_ovs_interface_to_activate.add(ifname)
                elif (
                    iface_desired_state[Interface.TYPE]
                    == InterfaceType.OVS_PORT
                ):
                    new_ovs_port_to_activate.add(ifname)
                elif iface_desired_state[Interface.TYPE] == InterfaceType.VLAN:
                    new_vlan_ifaces_to_activate.add(ifname)
                elif (
                    iface_desired_state[Interface.TYPE] == InterfaceType.VXLAN
                ):
                    new_vxlan_ifaces_to_activate.add(ifname)
                else:
                    new_ifaces_to_activate.add(ifname)
            elif iface_desired_state[Interface.STATE] == InterfaceState.ABSENT:
                # Delete the down profiles
                iface_name = iface_desired_state[Interface.NAME]
                for current_profile in current_profiles:
                    if current_profile.get_interface_name() == iface_name:
                        profile = connection.ConnectionProfile(
                            context, current_profile
                        )
                        profiles_to_delete.append(profile)

        else:
            if iface_desired_state[Interface.STATE] == InterfaceState.UP:
                if (
                    iface_desired_state.get(Interface.TYPE)
                    == InterfaceType.BOND
                ):
                    iface = BondIface(iface_desired_state)
                    if iface.is_bond_mode_changed:
                        # NetworkManager leaves leftover in sysfs for bond
                        # options when changing bond mode, bug:
                        # https://bugzilla.redhat.com/show_bug.cgi?id=1819137
                        # Workaround: delete the bond interface from kernel and
                        # create again via full deactivation beforehand.
                        logging.debug(
                            f"Bond interface {ifname} is changing bond mode, "
                            "will do full deactivation before applying changes"
                        )
                        devs_to_deactivate_beforehand.append(nmdev)

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
                nmdevs = _get_affected_devices(context, iface_desired_state)
                is_absent = (
                    iface_desired_state[Interface.STATE]
                    == InterfaceState.ABSENT
                )
                for affected_nmdev in nmdevs:
                    devs_to_deactivate[
                        affected_nmdev.get_iface()
                    ] = affected_nmdev
                    if is_absent:
                        devs_to_delete_profile[
                            affected_nmdev.get_iface()
                        ] = affected_nmdev
                if (
                    is_absent
                    and nmdev.is_software()
                    and nmdev.get_device_type() != NM.DeviceType.VETH
                ):
                    devs_to_delete[nmdev.get_iface()] = nmdev
            else:
                raise NmstateValueError(
                    "Invalid state {} for interface {}".format(
                        iface_desired_state[Interface.STATE],
                        iface_desired_state[Interface.NAME],
                    )
                )

    for dev in devs_to_deactivate_beforehand:
        device.deactivate(context, dev)

    # Do not remove devices that are marked for editing.
    for dev, _ in itertools.chain(master_ifaces_to_edit, ifaces_to_edit):
        devs_to_deactivate.pop(dev.get_iface(), None)
        devs_to_delete_profile.pop(dev.get_iface(), None)
        devs_to_delete.pop(dev.get_iface(), None)

    for profile in profiles_to_delete:
        profile.delete()
        context.wait_all_finish()

    for ifname in new_master_not_enslaved_ifaces:
        device.activate(context, dev=None, connection_id=ifname)
    context.wait_all_finish()

    for ifname in new_ifaces_to_activate:
        device.activate(context, dev=None, connection_id=ifname)
    context.wait_all_finish()

    for dev, con_profile in master_ifaces_to_edit:
        device.modify(context, dev, con_profile)
    context.wait_all_finish()

    for ifname in new_ovs_port_to_activate:
        device.activate(context, dev=None, connection_id=ifname)
    context.wait_all_finish()

    for ifname in new_ovs_interface_to_activate:
        device.activate(context, dev=None, connection_id=ifname)
    context.wait_all_finish()

    for dev, con_profile in ifaces_to_edit:
        device.modify(context, dev, con_profile)
    context.wait_all_finish()

    for ifname in new_vlan_ifaces_to_activate:
        device.activate(context, dev=None, connection_id=ifname)
    context.wait_all_finish()

    for ifname in new_vxlan_ifaces_to_activate:
        device.activate(context, dev=None, connection_id=ifname)
    context.wait_all_finish()

    for dev in devs_to_deactivate.values():
        device.deactivate(context, dev)
    context.wait_all_finish()

    for dev in devs_to_delete_profile.values():
        device.delete(context, dev)
    context.wait_all_finish()

    for dev in devs_to_delete.values():
        device.delete_device(context, dev)
    context.wait_all_finish()


def _index_profiles_by_devname(con_profiles):
    return {con_profile.devname: con_profile for con_profile in con_profiles}


def _get_new_ifaces(context, con_profiles):
    ifaces_without_device = set()
    for con_profile in con_profiles:
        ifname = con_profile.devname
        nmdev = context.get_nm_dev(ifname)
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


def _get_affected_devices(context, iface_state):
    nmdev = context.get_nm_dev(iface_state[Interface.NAME])
    devs = []
    if nmdev:
        devs += [nmdev]
        iface_type = iface_state[Interface.TYPE]
        if iface_type == InterfaceType.OVS_BRIDGE:
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


def _create_proxy_ifaces_desired_state(ifaces_desired_state):
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
    new_ifaces_names = set()
    for iface_desired_state in ifaces_desired_state:
        master_type = iface_desired_state.get(MASTER_TYPE_METADATA)
        if master_type != InterfaceType.OVS_BRIDGE:
            continue
        port_opts_metadata = iface_desired_state.get(
            BridgeIface.BRPORT_OPTIONS_METADATA
        )
        if port_opts_metadata is None:
            continue
        port_iface_desired_state = _create_ovs_port_iface_desired_state(
            iface_desired_state, port_opts_metadata
        )
        port_iface_name = port_iface_desired_state[Interface.NAME]
        if port_iface_name not in new_ifaces_names:
            new_ifaces_names.add(port_iface_name)
            new_ifaces_desired_state.append(port_iface_desired_state)
        # The "visible" slave/interface needs to point to the port profile
        iface_desired_state[MASTER_METADATA] = port_iface_desired_state[
            Interface.NAME
        ]
        iface_desired_state[MASTER_TYPE_METADATA] = InterfaceType.OVS_PORT
    return new_ifaces_desired_state


def _create_ovs_port_iface_desired_state(iface_desired_state, port_options):
    iface_name = iface_desired_state[Interface.NAME]
    if _is_ovs_lag_port(port_options):
        port_name = port_options[OvsB.Port.NAME]
    else:
        port_name = ovs.PORT_PROFILE_PREFIX + iface_name
    return {
        Interface.NAME: port_name,
        Interface.TYPE: InterfaceType.OVS_PORT,
        Interface.STATE: iface_desired_state[Interface.STATE],
        OvsB.OPTIONS_SUBTREE: port_options,
        MASTER_METADATA: iface_desired_state[MASTER_METADATA],
        MASTER_TYPE_METADATA: iface_desired_state[MASTER_TYPE_METADATA],
    }


def _is_ovs_lag_port(port_state):
    return port_state.get(OvsB.Port.LINK_AGGREGATION_SUBTREE) is not None


def _build_connection_profile(
    context,
    iface_desired_state,
    base_con_profile,
    original_desired_iface_state,
):
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
    iface_name = iface_desired_state[Interface.NAME]
    if base_profile:
        con_setting.import_by_profile(base_con_profile)
        con_setting.set_profile_name(iface_name)
    else:
        con_setting.create(
            con_name=iface_name, iface_name=iface_name, iface_type=iface_type,
        )
    lldp.apply_lldp_setting(con_setting, iface_desired_state)

    master = iface_desired_state.get(MASTER_METADATA)
    _translate_master_type(iface_desired_state)
    master_type = iface_desired_state.get(MASTER_TYPE_METADATA)
    con_setting.set_master(master, master_type)
    settings.append(con_setting.setting)

    # Only apply wired/ethernet configuration based on original desire
    # state rather than the merged one.
    wired_setting = wired.create_setting(
        original_desired_iface_state, base_profile
    )
    if wired_setting:
        settings.append(wired_setting)

    user_setting = user.create_setting(iface_desired_state, base_profile)
    if user_setting:
        settings.append(user_setting)

    bond_opts = translator.Api2Nm.get_bond_options(iface_desired_state)
    if bond_opts:
        settings.append(bond.create_setting(bond_opts, wired_setting))
    elif iface_type == bridge.BRIDGE_TYPE:
        bridge_config = iface_desired_state.get(bridge.BRIDGE_TYPE, {})
        bridge_options = bridge_config.get(LB.OPTIONS_SUBTREE)
        bridge_ports = bridge_config.get(LB.PORT_SUBTREE)

        if bridge_options or bridge_ports:
            linux_bridge_setting = bridge.create_setting(
                iface_desired_state,
                base_profile,
                original_desired_iface_state,
            )
            settings.append(linux_bridge_setting)
    elif iface_type == InterfaceType.OVS_BRIDGE:
        ovs_bridge_state = iface_desired_state.get(OvsB.CONFIG_SUBTREE, {})
        ovs_bridge_options = ovs_bridge_state.get(OvsB.OPTIONS_SUBTREE)
        if ovs_bridge_options:
            settings.append(ovs.create_bridge_setting(ovs_bridge_options))
    elif iface_type == InterfaceType.OVS_PORT:
        ovs_port_options = iface_desired_state.get(OvsB.OPTIONS_SUBTREE)
        settings.append(ovs.create_port_setting(ovs_port_options))
    elif iface_type == InterfaceType.OVS_INTERFACE:
        patch_state = iface_desired_state.get(
            OVSInterface.PATCH_CONFIG_SUBTREE
        )
        settings.extend(ovs.create_interface_setting(patch_state))

    bridge_port_options = iface_desired_state.get(
        BridgeIface.BRPORT_OPTIONS_METADATA
    )
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

    sriov_setting = sriov.create_setting(
        context, iface_desired_state, base_con_profile
    )
    if sriov_setting:
        settings.append(sriov_setting)

    team_setting = team.create_setting(iface_desired_state, base_con_profile)
    if team_setting:
        settings.append(team_setting)

    new_profile = connection.ConnectionProfile(context)
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


def _preapply_dns_fix(context, net_state):
    """
     * When DNS configuration does not changed and old interface hold DNS
       configuration is not included in `ifaces_desired_state`, preserve
       the old DNS configure by removing DNS metadata from
       `ifaces_desired_state`.
     * When DNS configuration changed, include old interface which is holding
       DNS configuration, so it's DNS configure could be removed.
    """
    cur_dns_iface_names = get_dns_config_iface_names(
        ipv4.acs_and_ip_profiles(context.client),
        ipv6.acs_and_ip_profiles(context.client),
    )

    # Whether to mark interface as changed which is used for holding old DNS
    # configurations
    remove_existing_dns_config = False
    # Whether to preserve old DNS config by DNS metadata to be removed from
    # desired state
    preserve_old_dns_config = False
    if net_state.dns.config == net_state.dns.current_config:
        for cur_dns_iface_name in cur_dns_iface_names:
            iface = net_state.ifaces[cur_dns_iface_name]
            if iface.is_changed or iface.is_desired:
                remove_existing_dns_config = True
        if not remove_existing_dns_config:
            preserve_old_dns_config = True
    else:
        remove_existing_dns_config = True

    if remove_existing_dns_config:
        for cur_dns_iface_name in cur_dns_iface_names:
            iface = net_state.ifaces[cur_dns_iface_name]
            iface.mark_as_changed()

    if preserve_old_dns_config:
        for iface in net_state.ifaces.values():
            if iface.is_changed or iface.is_desired:
                iface.remove_dns_metadata()
