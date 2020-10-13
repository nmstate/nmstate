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

# This file is targeting:
#   * NM.RemoteConnection, NM.SimpleConnection releated

from distutils.version import StrictVersion
import logging

from libnmstate.error import NmstateNotSupportedError
from libnmstate.error import NmstateValueError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import LinuxBridge as LB
from libnmstate.schema import OVSBridge as OvsB
from libnmstate.schema import OVSInterface
from libnmstate.schema import Team
from libnmstate.schema import VRF
from libnmstate.ifaces.base_iface import BaseIface
from libnmstate.ifaces.bond import BondIface
from libnmstate.ifaces.bridge import BridgeIface

from . import bond
from . import bridge
from . import connection
from . import device
from . import dns as nm_dns
from . import ipv4
from . import ipv6
from . import lldp
from . import macvlan
from . import ovs as nm_ovs
from . import profile_state
from . import sriov
from . import team
from . import translator
from . import user
from . import vlan
from . import vxlan
from . import wired

from .common import NM
from .device import mark_device_as_managed
from .device import list_devices
from .device import is_externally_managed
from .vrf import create_vrf_setting
from .infiniband import create_setting as create_infiniband_setting


ACTION_DEACTIVATE_BEFOREHAND = "deactivate-beforehand"
ACTION_DELETE_PROFILE = "delete-profile"
ACTION_ACTIVATE = "activate"
ACTION_MODIFY = "modify"
ACTION_DEACTIVATE = "deactivate"
ACTION_DELETE_DEV_PROFILES = "delete-dev-profiles"
ACTION_DELETE_DEV = "delete-dev"

CONTROLLER_METADATA = "_controller"
CONTROLLER_TYPE_METADATA = "_controller_type"
CONTROLLER_IFACE_TYPES = (
    InterfaceType.OVS_BRIDGE,
    bond.BOND_TYPE,
    LB.TYPE,
    Team.TYPE,
)


class NmProfiles:
    def __init__(self, context):
        self._ctx = context

    def apply_config(self, net_state, save_to_disk):
        self._prepare_state_for_profiles(net_state)
        self._profiles = [
            NmProfile(self._ctx, save_to_disk, iface)
            for iface in net_state.ifaces.values()
            if (iface.is_changed or iface.is_desired) and not iface.is_ignore
        ]

        for profile in self._profiles:
            profile.store_config()
        self._ctx.wait_all_finish()

        grouped_profiles = self._group_profile_by_action_order()
        for profile_group in grouped_profiles:
            for profile in profile_group:
                profile.apply_config()
            self._ctx.wait_all_finish()

    def _group_profile_by_action_order(self):
        groups = {
            "profiles_to_deactivate_beforehand": set(),
            "profiles_to_delete": set(),
            "new_controller_not_as_port": set(),
            "new_ifaces_to_activate": set(),
            "controller_ifaces_to_edit": set(),
            "new_ovs_port_to_activate": set(),
            "new_ovs_interface_to_activate": set(),
            "ifaces_to_edit": set(),
            "new_vlan_x_to_activate": set(),
            "profiles_to_deactivate": set(),
            "devs_to_delete_profile": set(),
            "devs_to_delete": set(),
        }

        for profile in self._profiles:
            profile.classify_profile_for_actions(groups)

        return groups.values()

    def _prepare_state_for_profiles(self, net_state):
        _preapply_dns_fix_for_profiles(self._ctx, net_state)
        _mark_nm_external_subordinate_changed(self._ctx, net_state)
        _mark_mode_changed_bond_child_interface_as_changed(net_state)

        proxy_ifaces = {}
        for iface in net_state.ifaces.values():
            proxy_iface_info = nm_ovs.create_ovs_proxy_iface_info(iface)
            if proxy_iface_info:
                proxy_iface = BaseIface(proxy_iface_info)
                proxy_iface.mark_as_changed()
                proxy_ifaces[proxy_iface.name] = proxy_iface
        net_state.ifaces.update(proxy_ifaces)


class NmProfile:
    def __init__(self, context, save_to_disk, iface=None):
        self._ctx = context
        self._iface = iface
        self._save_to_disk = save_to_disk
        self._nmdev = None
        self._nm_ac = None
        self._nm_profile_state = profile_state.NmProfileState(context)
        self._remote_conn = None
        self._simple_conn = None
        self._actions_needed = []

    @property
    def iface_info(self):
        return self._iface.to_dict()

    @property
    def iface(self):
        return self._iface

    @property
    def original_iface_info(self):
        return self._iface.original_dict

    @property
    def profile_state(self):
        return self._nm_profile_state

    @property
    def nmdev(self):
        if self._nmdev:
            return self._nmdev
        elif self.devname:
            return self._ctx.get_nm_dev(self.devname)
        else:
            return None

    @nmdev.setter
    def nmdev(self, dev):
        self._nmdev = dev

    @property
    def nm_ac(self):
        return self._nm_ac

    @nm_ac.setter
    def nm_ac(self, ac):
        self._nm_ac = ac

    @property
    def remote_conn(self):
        return self._remote_conn

    @remote_conn.setter
    def remote_conn(self, con):
        self._remote_conn = con

    @property
    def simple_conn(self):
        return self._simple_conn

    @property
    def uuid(self):
        if self._remote_conn:
            return self._remote_conn.get_uuid()
        elif self._simple_conn:
            return self._simple_conn.get_uuid()
        else:
            return self.iface.name

    @property
    def devname(self):
        if self._remote_conn:
            return self._remote_conn.get_interface_name()
        elif self._simple_conn:
            return self._simple_conn.get_interface_name()
        else:
            return self.iface.name

    @property
    def profile(self):
        return self._simple_conn if self._simple_conn else self._remote_conn

    @property
    def is_memory_only(self):
        if self._remote_conn:
            profile_flags = self._remote_conn.get_flags()
            return (
                NM.SettingsConnectionFlags.UNSAVED & profile_flags
                or NM.SettingsConnectionFlags.VOLATILE & profile_flags
            )
        return False

    def apply_config(self):
        if ACTION_DEACTIVATE_BEFOREHAND in self._actions_needed:
            device.deactivate(self._ctx, self.nmdev)
        elif ACTION_DELETE_PROFILE in self._actions_needed:
            self.delete()
        elif ACTION_ACTIVATE in self._actions_needed:
            self.activate()
        elif ACTION_MODIFY in self._actions_needed:
            device.modify(self._ctx, self)
        elif ACTION_DEACTIVATE in self._actions_needed:
            device.deactivate(self._ctx, self.nmdev)
        elif ACTION_DELETE_DEV_PROFILES in self._actions_needed:
            self.delete()
        elif ACTION_DELETE_DEV in self._actions_needed:
            device.delete_device(self._ctx, self.nmdev)
        self._next_action()

    def _next_action(self):
        if self._actions_needed:
            self._actions_needed.pop(0)

    def activate(self):
        specific_object = None
        action = (
            f"Activate profile uuid:{self.profile.get_uuid()} "
            f"id:{self.profile.get_id()}"
        )
        user_data = action, self
        self._ctx.register_async(action)
        self._ctx.client.activate_connection_async(
            self._remote_conn,
            self.nmdev,
            specific_object,
            self._ctx.cancellable,
            self._nm_profile_state.activate_connection_callback,
            user_data,
        )

    def delete(self):
        if self._remote_conn:
            action = (
                f"Delete profile: uuid:{self._remote_conn.get_uuid()} "
                f"id:{self._remote_conn.get_id()}"
            )
            user_data = action
            self._ctx.register_async(action, fast=True)
            self._remote_conn.delete_async(
                self._ctx.cancellable,
                self._nm_profile_state.delete_profile_callback,
                user_data,
            )

    def _update(self):
        flags = NM.SettingsUpdate2Flags.BLOCK_AUTOCONNECT
        if self._save_to_disk:
            flags |= NM.SettingsUpdate2Flags.TO_DISK
        else:
            flags |= NM.SettingsUpdate2Flags.IN_MEMORY
        action = (
            f"Update profile uuid:{self._remote_conn.get_uuid()} "
            f"id:{self._remote_conn.get_id()}"
        )
        user_data = action
        args = None

        self._ctx.register_async(action, fast=True)
        self._remote_conn.update2(
            self._simple_conn.to_dbus(NM.ConnectionSerializationFlags.ALL),
            flags,
            args,
            self._ctx.cancellable,
            self._nm_profile_state.update2_callback,
            user_data,
        )

    def _add(self):
        nm_add_conn2_flags = NM.SettingsAddConnection2Flags
        flags = nm_add_conn2_flags.BLOCK_AUTOCONNECT
        if self._save_to_disk:
            flags |= nm_add_conn2_flags.TO_DISK
        else:
            flags |= nm_add_conn2_flags.IN_MEMORY

        action = f"Add profile: {self._simple_conn.get_uuid()}"
        self._ctx.register_async(action, fast=True)

        user_data = action, self
        args = None
        ignore_out_result = False  # Don't fall back to old AddConnection()
        self._ctx.client.add_connection2(
            self._simple_conn.to_dbus(NM.ConnectionSerializationFlags.ALL),
            flags,
            args,
            ignore_out_result,
            self._ctx.cancellable,
            self._nm_profile_state.add_connection2_callback,
            user_data,
        )

    def store_config(self):
        if (
            not self._save_to_disk
            and StrictVersion(self._ctx.client.get_version())
            < StrictVersion("1.28.0")
            and self.iface.type
            in (
                InterfaceType.OVS_BRIDGE,
                InterfaceType.OVS_INTERFACE,
                InterfaceType.OVS_PORT,
            )
        ):
            raise NmstateNotSupportedError(
                f"NetworkManager version {self._ctx.client.get_version()}"
                f" does not support 'save_to_disk=False' against"
                " OpenvSwitch interface."
            )

        ifname = self.iface.name
        self._import_existing_profile(ifname)

        if self._save_to_disk:
            connections = connection.list_connections_by_ifname(
                self._ctx, ifname
            )
            for con in connections:
                if (
                    not self._remote_conn
                    or con.get_uuid() != self._remote_conn.get_uuid()
                ):
                    nmprofile = NmProfile(self._ctx, self._save_to_disk)
                    nmprofile.remote_conn = con
                    nmprofile.delete()
        if not (
            set(self.original_iface_info.keys())
            <= set([Interface.STATE, Interface.NAME, Interface.TYPE])
            and self._remote_conn
            and not self._iface.is_changed
            and self.is_memory_only != self._save_to_disk
        ):
            if self.iface.state not in (
                InterfaceState.ABSENT,
                InterfaceState.DOWN,
            ):
                settings = self._generate_connection_settings(ifname)
                self._simple_conn = connection.create_new_simple_connection(
                    settings
                )
                set_conn = self._simple_conn.get_setting_connection()
                set_conn.props.interface_name = ifname
                if self._remote_conn:
                    self._update()
                else:
                    self._add()

    def _generate_connection_settings(self, ifname):
        nm_iface_type = translator.Api2Nm.get_iface_type(self.iface.type)
        settings = [
            ipv4.create_setting(
                self.iface_info.get(Interface.IPV4), self._remote_conn
            ),
            ipv6.create_setting(
                self.iface_info.get(Interface.IPV6), self._remote_conn
            ),
        ]

        con_setting = connection.ConnectionSetting()
        if self._remote_conn:
            con_setting.import_by_profile(self._remote_conn)
            con_setting.set_profile_name(ifname)
        else:
            con_setting.create(
                con_name=ifname, iface_name=ifname, iface_type=nm_iface_type,
            )

        lldp.apply_lldp_setting(con_setting, self.iface_info)

        controller = self.iface_info.get(CONTROLLER_METADATA)
        controller_type = self.iface_info.get(CONTROLLER_TYPE_METADATA)
        if controller_type == LB.TYPE:
            self.iface_info[CONTROLLER_TYPE_METADATA] = bridge.BRIDGE_TYPE
            controller_type = bridge.BRIDGE_TYPE
        con_setting.set_controller(controller, controller_type)
        settings.append(con_setting.setting)

        # Only apply wired/ethernet configuration based on original desire
        # state rather than the merged one.
        original_state_wired = {}
        if self._iface.is_desired:
            original_state_wired = self.original_iface_info
        if self.iface.type != InterfaceType.INFINIBAND:
            # The IP over InfiniBand has its own setting for MTU and does not
            # have ethernet layer.
            wired_setting = wired.create_setting(
                original_state_wired, self._remote_conn
            )
            if wired_setting:
                settings.append(wired_setting)

        user_setting = user.create_setting(self.iface_info, self._remote_conn)
        if user_setting:
            settings.append(user_setting)

        if self.iface.type == InterfaceType.BOND:
            settings.append(
                bond.create_setting(
                    self.iface, wired_setting, self._remote_conn
                )
            )
        elif nm_iface_type == bridge.BRIDGE_TYPE:
            bridge_config = self.iface_info.get(LB.CONFIG_SUBTREE, {})
            bridge_options = bridge_config.get(LB.OPTIONS_SUBTREE)
            bridge_ports = bridge_config.get(LB.PORT_SUBTREE)
            if bridge_options or bridge_ports:
                linux_bridge_setting = bridge.create_setting(
                    self.iface_info,
                    self._remote_conn,
                    self.original_iface_info,
                )
                settings.append(linux_bridge_setting)
        elif nm_iface_type == InterfaceType.OVS_BRIDGE:
            ovs_bridge_state = self.iface_info.get(OvsB.CONFIG_SUBTREE, {})
            ovs_bridge_options = ovs_bridge_state.get(OvsB.OPTIONS_SUBTREE)
            if ovs_bridge_options:
                settings.append(
                    nm_ovs.create_bridge_setting(ovs_bridge_options)
                )
        elif nm_iface_type == InterfaceType.OVS_PORT:
            ovs_port_options = self.iface_info.get(OvsB.OPTIONS_SUBTREE)
            settings.append(nm_ovs.create_port_setting(ovs_port_options))
        elif nm_iface_type == InterfaceType.OVS_INTERFACE:
            patch_state = self.iface_info.get(
                OVSInterface.PATCH_CONFIG_SUBTREE
            )
            settings.extend(nm_ovs.create_interface_setting(patch_state))
        elif self.iface.type == InterfaceType.INFINIBAND:
            ib_setting = create_infiniband_setting(
                self.iface_info, self._remote_conn, self.original_iface_info,
            )
            if ib_setting:
                settings.append(ib_setting)

        bridge_port_options = self.iface_info.get(
            BridgeIface.BRPORT_OPTIONS_METADATA
        )
        if bridge_port_options and controller_type == bridge.BRIDGE_TYPE:
            settings.append(
                bridge.create_port_setting(
                    bridge_port_options, self._remote_conn
                )
            )

        vlan_setting = vlan.create_setting(self.iface_info, self._remote_conn)
        if vlan_setting:
            settings.append(vlan_setting)

        vxlan_setting = vxlan.create_setting(
            self.iface_info, self._remote_conn
        )
        if vxlan_setting:
            settings.append(vxlan_setting)

        sriov_setting = sriov.create_setting(
            self._ctx, self.iface_info, self._remote_conn
        )
        if sriov_setting:
            settings.append(sriov_setting)

        team_setting = team.create_setting(self.iface_info, self._remote_conn)
        if team_setting:
            settings.append(team_setting)

        if VRF.CONFIG_SUBTREE in self.iface_info:
            settings.append(
                create_vrf_setting(self.iface_info[VRF.CONFIG_SUBTREE])
            )

        macvlan_setting = macvlan.create_setting(
            self.iface_info, self._remote_conn
        )
        if macvlan_setting:
            settings.append(macvlan_setting)

        return settings

    def _import_existing_profile(self, ifname):
        self._nmdev = self._ctx.get_nm_dev(ifname)
        if self._nmdev:
            self._remote_conn = self._import_remote_conn_by_device()
        else:
            # Profile for virtual interface does not have a NM.Device
            # associated.
            self._remote_conn = self._ctx.client.get_connection_by_id(ifname)

    def _import_remote_conn_by_device(self):
        act_conn = self._nmdev.get_active_connection()
        if act_conn:
            self._nm_ac = act_conn
            return act_conn.get_connection()

        return None

    def classify_profile_for_actions(self, groups):
        if not self.nmdev:
            if self.iface.state == InterfaceState.UP:
                self._actions_needed.append(ACTION_ACTIVATE)
                if (
                    self.iface.type in CONTROLLER_IFACE_TYPES
                    and not self.iface_info.get(CONTROLLER_METADATA)
                ):
                    groups["new_controller_not_as_port"].add(self)
                elif self.iface.type == InterfaceType.OVS_INTERFACE:
                    groups["new_ovs_interface_to_activate"].add(self)
                elif self.iface.type == InterfaceType.OVS_PORT:
                    groups["new_ovs_port_to_activate"].add(self)
                elif self.iface.type in (
                    InterfaceType.VLAN,
                    InterfaceType.VXLAN,
                ):
                    groups["new_vlan_x_to_activate"].add(self)
                else:
                    groups["new_ifaces_to_activate"].add(self)
            elif self.iface.state == InterfaceState.ABSENT:
                # Delete absent profiles
                self._actions_needed.append(ACTION_DELETE_PROFILE)
                groups["profiles_to_delete"].add(self)
        else:
            if not self.nmdev.get_managed():
                mark_device_as_managed(self._ctx, self.nmdev)
            if self.iface.state == InterfaceState.UP:
                if self.iface.type == InterfaceType.BOND:
                    iface = BondIface(self.iface_info)
                    # NetworkManager leaves leftover in sysfs for bond
                    # options when changing bond mode, bug:
                    # https://bugzilla.redhat.com/show_bug.cgi?id=1819137
                    # Workaround: delete the bond interface from kernel and
                    # create again via full deactivation beforehand.
                    if iface.is_bond_mode_changed:
                        logging.debug(
                            f"Bond interface {self.iface.name} is changing "
                            "bond mode, will do full deactivation before "
                            "applying changes"
                        )
                        self._actions_needed.append(
                            ACTION_DEACTIVATE_BEFOREHAND
                        )
                        groups["profiles_to_deactivate_beforehand"].add(self)
                elif self.iface.type == InterfaceType.MAC_VLAN:
                    self._actions_needed.append(ACTION_DEACTIVATE_BEFOREHAND)
                    groups["profiles_to_deactivate_beforehand"].add(self)
                self._actions_needed.append(ACTION_MODIFY)
                if self.iface.type in CONTROLLER_IFACE_TYPES:
                    groups["controller_ifaces_to_edit"].add(self)
                else:
                    groups["ifaces_to_edit"].add(self)
            elif self.iface.state in (
                InterfaceState.DOWN,
                InterfaceState.ABSENT,
            ):
                is_absent = self.iface.state == InterfaceState.ABSENT
                self._actions_needed.append(ACTION_DEACTIVATE)
                groups["profiles_to_deactivate"].add(self)
                if is_absent:
                    self._actions_needed.append(ACTION_DELETE_DEV_PROFILES)
                    groups["devs_to_delete_profile"].add(self)
                if (
                    is_absent
                    and self.nmdev.is_software()
                    and self.nmdev.get_device_type() != NM.DeviceType.VETH
                ):
                    self._actions_needed.append(ACTION_DELETE_DEV)
                    groups["devs_to_delete"].add(self)
            else:
                raise NmstateValueError(
                    "Invalid state {} for interface {}".format(
                        self.iface.state, self.iface.name,
                    )
                )


def get_all_applied_configs(context):
    applied_configs = {}
    for nm_dev in list_devices(context.client):
        if (
            nm_dev.get_state()
            in (NM.DeviceState.ACTIVATED, NM.DeviceState.IP_CONFIG,)
            and nm_dev.get_managed()
        ):
            iface_name = nm_dev.get_iface()
            if iface_name:
                iface_type_str = nm_dev.get_type_description()
                action = (
                    f"Retrieve applied config: {iface_type_str} {iface_name}"
                )
                context.register_async(action, fast=True)
                nm_dev.get_applied_connection_async(
                    flags=0,
                    cancellable=context.cancellable,
                    callback=profile_state.get_applied_config_callback,
                    user_data=(iface_name, action, applied_configs, context),
                )
    context.wait_all_finish()
    return applied_configs


def _preapply_dns_fix_for_profiles(context, net_state):
    """
    * When DNS configuration does not changed and old interface hold DNS
      configuration is not included in `ifaces_desired_state`, preserve
      the old DNS configure by removing DNS metadata from
      `ifaces_desired_state`.
    * When DNS configuration changed, include old interface which is holding
      DNS configuration, so it's DNS configure could be removed.
    """
    cur_dns_iface_names = nm_dns.get_dns_config_iface_names(
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


def _mark_nm_external_subordinate_changed(context, net_state):
    """
    When certain main interface contains subordinates is marked as
    connected(externally), it means its profile is memory only and will lost
    on next deactivation.
    For this case, we should mark the subordinate as changed.
    that subordinate should be marked as changed for NM to take over.
    """
    for iface in net_state.ifaces.values():
        if iface.type in CONTROLLER_IFACE_TYPES:
            for subordinate in iface.port:
                nmdev = context.get_nm_dev(subordinate)
                if nmdev:
                    if is_externally_managed(nmdev):
                        subordinate_iface = net_state.ifaces.get(subordinate)
                        if subordinate_iface:
                            subordinate_iface.mark_as_changed()


def _mark_mode_changed_bond_child_interface_as_changed(net_state):
    """
    When bond mode changed, due to NetworkManager bug
    https://bugzilla.redhat.com/show_bug.cgi?id=1881318
    the bond child will be deactivated.
    This is workaround would be manually activate the childs.
    """
    for iface in net_state.ifaces.values():
        if not iface.parent:
            continue
        parent_iface = net_state.ifaces[iface.parent]
        if (
            parent_iface.is_up
            and parent_iface.type == InterfaceType.BOND
            and parent_iface.is_bond_mode_changed
        ):
            iface.mark_as_changed()
