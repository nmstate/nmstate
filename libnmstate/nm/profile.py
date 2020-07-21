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

import logging
import itertools

from libnmstate.error import NmstateLibnmError
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
from . import dns as nm_dns
from . import ipv4
from . import ipv6
from . import lldp
from . import ovs as nm_ovs
from . import sriov
from . import team
from . import translator
from . import user
from . import vlan
from . import vxlan
from . import wired

from .common import NM
from .device import list_devices
from libnmstate.ifaces import ovs


MASTER_METADATA = "_master"
MASTER_TYPE_METADATA = "_master_type"
MASTER_IFACE_TYPES = (
    InterfaceType.OVS_BRIDGE,
    bond.BOND_TYPE,
    LB.TYPE,
    Team.TYPE,
)


class NmProfiles:
    def __init__(self, context, save_to_disk):
        self._ctx = context
        self._save_to_disk = save_to_disk

    def apply_config(self, net_state):
        self._prepare_state_for_profiles(net_state)
        self._profiles = [
            NmProfile(self._ctx, self._save_to_disk, iface)
            for iface in net_state.ifaces.values()
            if iface.is_changed or iface.is_desired
        ]

        proxy_profiles = []
        for profile in self._profiles:
            proxy = profile.create_proxy_profile()
            if proxy:
                proxy_profiles.append(proxy)
        self._profiles.extend(proxy_profiles)

        for profile in self._profiles:
            profile.store_config()

        grouped_profiles = self._group_profile_by_action_order()
        for profile_group in grouped_profiles:
            for profile in profile_group:
                profile.apply_config()

    @staticmethod
    def _filter_new_ifaces(profiles):
        ifaces_without_device = set()
        for profile in profiles:
            if not profile.nmdev:
                ifaces_without_device.add(profile)
        return ifaces_without_device

    @staticmethod
    def _get_affected_profiles(profile, profiles):
        devs = []
        affected_profiles = []
        if profile.nmdev:
            devs += [profile.nmdev]
            iface_type = profile.iface_state[Interface.TYPE]
            if iface_type == InterfaceType.OVS_BRIDGE:
                port_slaves = nm_ovs.get_slaves(profile.nmdev)
                iface_slaves = [
                    iface
                    for port in port_slaves
                    for iface in nm_ovs.get_slaves(port)
                ]
                devs += port_slaves + iface_slaves
            elif iface_type == LB.TYPE:
                devs += bridge.get_slaves(profile.nmdev)
            elif iface_type == bond.BOND_TYPE:
                devs += bond.get_slaves(profile.nmdev)

            ovs_port_dev = nm_ovs.get_port_by_slave(profile.nmdev)
            if ovs_port_dev:
                devs.append(ovs_port_dev)

            for dev in devs:
                for nm_profile in profiles:
                    ac = dev.get_active_connection()
                    if ac and nm_profile.uuid == ac.get_uuid():
                        affected_profiles.append(nm_profile)

        return affected_profiles

    def _group_profile_by_action_order(self):
        new_ifaces = self._filter_new_ifaces(self._profiles)
        new_master_not_enslaved = set()
        new_ovs_interface_to_activate = set()
        new_ovs_port_to_activate = set()
        new_vlan_x_to_activate = set()
        new_ifaces_to_activate = set()
        master_ifaces_to_edit = set()
        profiles_to_delete = set()
        profiles_to_deactivate = set()
        profiles_to_deactivate_beforehand = set()
        devs_to_delete = set()
        ifaces_to_edit = set()
        for profile in self._profiles:
            ifname = profile.iface_state[Interface.NAME]
            if not profile.nmdev:
                if (
                    profile in new_ifaces
                    and profile.iface_state[Interface.STATE]
                    == InterfaceState.UP
                ):
                    profile.to_activate = True
                    if profile.iface_state[
                        Interface.TYPE
                    ] in MASTER_IFACE_TYPES and not profile.iface_state.get(
                        MASTER_METADATA
                    ):
                        new_master_not_enslaved.add(profile)
                    elif (
                        profile.iface_state[Interface.TYPE]
                        == InterfaceType.OVS_INTERFACE
                    ):
                        new_ovs_interface_to_activate.add(profile)
                    elif (
                        profile.iface_state[Interface.TYPE]
                        == InterfaceType.OVS_PORT
                    ):
                        new_ovs_port_to_activate.add(profile)
                    elif profile.iface_state[Interface.TYPE] in (
                        InterfaceType.VLAN,
                        InterfaceType.VXLAN,
                    ):
                        new_vlan_x_to_activate.add(profile)
                    else:
                        new_ifaces_to_activate.add(profile)
                elif (
                    profile.iface_state[Interface.STATE]
                    == InterfaceState.ABSENT
                ):
                    # Delete absent profiles
                    profile.to_delete = True
                    profiles_to_delete.add(profile)
            else:
                if profile.iface_state[Interface.STATE] == InterfaceState.UP:
                    if (
                        profile.iface_state[Interface.TYPE]
                        == InterfaceType.BOND
                    ):
                        iface = BondIface(profile.iface_state)
                        # NetworkManager leaves leftover in sysfs for bond
                        # options when changing bond mode, bug:
                        # https://bugzilla.redhat.com/show_bug.cgi?id=1819137
                        # Workaround: delete the bond interface from kernel and
                        # create again via full deactivation beforehand.
                        if iface.is_bond_mode_changed:
                            logging.debug(
                                f"Bond interface {ifname} is changing bond "
                                "mode, will do full deactivation before "
                                "applying changes"
                            )
                            profile.to_deactivate_beforehand = True
                            profiles_to_deactivate_beforehand.add(profile)
                    profile.to_modify = True
                    if (
                        profile.iface_state[Interface.TYPE]
                        in MASTER_IFACE_TYPES
                    ):
                        master_ifaces_to_edit.add(profile)
                    else:
                        ifaces_to_edit.add(profile)
                elif profile.iface_state[Interface.STATE] in (
                    InterfaceState.DOWN,
                    InterfaceState.ABSENT,
                ):
                    affected_profiles = self._get_affected_profiles(
                        profile, self._profiles
                    )
                    is_absent = (
                        profile.iface_state[Interface.STATE]
                        == InterfaceState.ABSENT
                    )
                    profile.to_deactivate = True
                    profiles_to_deactivate.update(affected_profiles)
                    if is_absent:
                        profile.to_delete = True
                        profiles_to_delete.update(affected_profiles)
                    if (
                        is_absent
                        and profile.nmdev.is_software()
                        and profile.nmdev.get_device_type()
                        != NM.DeviceType.VETH
                    ):
                        profile.delete_dev = True
                        devs_to_delete.add(profile)
                else:
                    raise NmstateValueError(
                        "Invalid state {} for interface {}".format(
                            profile.iface_state[Interface.STATE],
                            profile.iface_state[Interface.NAME],
                        )
                    )

        for profile in itertools.chain(master_ifaces_to_edit, ifaces_to_edit):
            profile.to_deactivate = False
            profile.to_delete = False
            profile.delete_dev = False

        return [
            profiles_to_deactivate_beforehand,
            profiles_to_delete,
            new_master_not_enslaved,
            new_ifaces_to_activate,
            master_ifaces_to_edit,
            new_ovs_port_to_activate,
            new_ovs_interface_to_activate,
            ifaces_to_edit,
            new_vlan_x_to_activate,
            profiles_to_deactivate,
            profiles_to_delete,
            devs_to_delete,
        ]

    def _prepare_state_for_profiles(self, net_state):
        nm_dns.preapply_dns_fix_for_profiles(self._ctx, net_state)


class NmProfile:
    def __init__(self, context, save_to_disk, iface=None, iface_state=None):
        self._ctx = context
        self._iface = iface
        self._iface_state = iface_state
        self._save_to_disk = save_to_disk
        self._nmdev = None
        self._nm_ac = None
        self._ac_handlers = set()
        self._dev_handlers = set()
        self._remote_conn = None
        self._simple_conn = None
        self.to_activate = False
        self.to_deactivate = False
        self.to_delete = False
        self.to_deactivate_beforehand = False
        self.to_modify = False
        self.delete_dev = False

    @property
    def iface_state(self):
        return self._iface.to_dict() if self._iface else self._iface_state

    @property
    def original_iface_state(self):
        return self._iface.original_dict if self._iface else self._iface_state

    @property
    def nmdev(self):
        return (
            self._nmdev
            if self._nmdev
            else self._ctx.get_nm_dev(self.iface_state[Interface.NAME])
        )

    @nmdev.setter
    def nmdev(self, dev):
        self._nmdev = dev

    @property
    def uuid(self):
        if self._remote_conn:
            return self._remote_conn.get_uuid()
        elif self._simple_conn:
            return self._simple_conn.get_uuid()
        else:
            return None

    @property
    def devname(self):
        if self._remote_conn:
            return self._remote_conn.get_interface_name()
        elif self._simple_conn:
            return self._simple_conn.get_interface_name()
        else:
            return None

    @property
    def profile(self):
        return self._simple_conn if self._simple_conn else self._remote_conn

    def apply_config(self):
        if self.to_deactivate_beforehand:
            device.deactivate(self._ctx, self.nmdev)
            self.to_deactivate_beforehand = False
        elif self.to_delete:
            self._delete()
            self.to_delete = False
        elif self.to_activate:
            self.activate()
            self.to_activate = False
        elif self.to_modify:
            device.modify(self._ctx, self)
            self.to_modify = False
        elif self.to_deactivate:
            device.deactivate(self._ctx, self.nmdev)
            self.to_deactivate = False
        elif self.delete_dev:
            device.delete_device(self._ctx, self.nmdev)
            self.delete_dev = False
        self._ctx.wait_all_finish()

    def activate(self):
        specific_object = None
        action = f"Activate profile: {self.profile.get_uuid()}"
        user_data = action
        self._ctx.register_async(action)
        self._ctx.client.activate_connection_async(
            self._remote_conn,
            self.nmdev,
            specific_object,
            self._ctx.cancellable,
            self._activate_connection_callback,
            user_data,
        )

    def _activate_connection_callback(self, src_object, result, user_data):
        nm_act_con = None
        if self._ctx.is_cancelled():
            self._activation_clean_up()
            return
        action = user_data
        try:
            nm_act_con = src_object.activate_connection_finish(result)
        except Exception as e:
            self._ctx.fail(NmstateLibnmError(f"{action} failed: error={e}"))

        if nm_act_con is None:
            self._ctx.fail(
                NmstateLibnmError(
                    f"{action} failed: "
                    "error='None return from activate_connection_finish()'"
                )
            )
        else:
            logging.debug(
                "Connection activation initiated: dev=%s, con-state=%s",
                self.devname,
                nm_act_con.props.state,
            )
            self._nm_ac = nm_act_con
            self._nmdev = self._ctx.get_nm_dev(self.devname)

            if connection.is_activated(self._nm_ac, self.nmdev):
                logging.debug(
                    "Connection activation succeeded: dev=%s, con-state=%s, "
                    "dev-state=%s, state-flags=%s",
                    self.devname,
                    self._nm_ac.get_state(),
                    self.nmdev.get_state(),
                    self._nm_ac.get_state_flags(),
                )
                self._activation_clean_up()
                self._ctx.finish_async(action)
            elif connection.is_activating(self._nm_ac, self.nmdev):
                self._wait_ac_activation(action)
                if self.nmdev:
                    self.wait_dev_activation(action)
            else:
                if self.nmdev:
                    error_msg = (
                        f"Connection {self._simple_conn.get_uuid()} failed: "
                        f"state={self._nm_ac.get_state()} "
                        f"reason={self._nm_ac.get_state_reason()} "
                        f"dev_state={self.nmdev.get_state()} "
                        f"dev_reason={self.nmdev.get_state_reason()}"
                    )
                else:
                    error_msg = (
                        f"Connection {self._simple_conn.get_id()} failed: "
                        f"state={self._nm_ac.get_state()} "
                        f"reason={self._nm_ac.get_state_reason()} dev=None"
                    )
                logging.error(error_msg)
                self._ctx.fail(
                    NmstateLibnmError(f"{action} failed: {error_msg}")
                )

    def wait_dev_activation(self, action):
        self._dev_handlers.add(
            self.nmdev.connect(
                "state-changed", self._dev_state_change_callback, action
            )
        )

    def _dev_state_change_callback(
        self, _dev, _new_state, _old_state, _reason, _action
    ):
        if self._ctx.is_cancelled():
            self._activation_clean_up()
            return
        self._activation_progress_check(_action)

    def _wait_ac_activation(self, action):
        self._ac_handlers.add(
            self._nm_ac.connect(
                "state-changed", self._ac_state_change_callback, action
            )
        )
        self._ac_handlers.add(
            self._nm_ac.connect(
                "notify::state-flags",
                self._ac_state_flags_change_callback,
                action,
            )
        )

    def _ac_state_flags_change_callback(self, _nm_act_con, _state, action):
        if self._ctx.is_cancelled():
            self._activation_clean_up()
            return
        self._activation_progress_check(action)

    def _ac_state_change_callback(self, _nm_act_con, _state, _reason, action):
        if self._ctx.is_cancelled():
            self._activation_clean_up()
            return
        self._activation_progress_check(action)

    def _activation_progress_check(self, action):
        if self._ctx.is_cancelled():
            self._activation_clean_up()
            return
        cur_nm_dev = self._ctx.get_nm_dev(self.devname)
        if cur_nm_dev and cur_nm_dev != self.nmdev:
            logging.debug(f"The NM.Device of profile {self.devname} changed")
            self._remove_dev_handlers()
            self.nmdev = cur_nm_dev
            self.wait_dev_activation(action)

        cur_nm_ac = connection.get_device_active_connection(self.nmdev)
        if cur_nm_ac and cur_nm_ac != self._nm_ac:
            logging.debug(
                "Active connection of device {} has been replaced".format(
                    self.devname
                )
            )
            self._remove_ac_handlers()
            self._nm_ac = cur_nm_ac
            self._wait_ac_activation(action)
        if connection.is_activated(self._nm_ac, self.nmdev):
            logging.debug(
                "Connection activation succeeded: dev=%s, con-state=%s, "
                "dev-state=%s, state-flags=%s",
                self.devname,
                self._nm_ac.get_state(),
                self.nmdev.get_state(),
                self._nm_ac.get_state_flags(),
            )
            self._activation_clean_up()
            self._ctx.finish_async(action)
        elif not connection.is_activating(self._nm_ac, self.nmdev):
            reason = f"{self._nm_ac.get_state_reason()}"
            if self.nmdev:
                reason += f" {self.nmdev.get_state_reason()}"
            self._activation_clean_up()
            self._ctx.fail(
                NmstateLibnmError(f"{action} failed: reason={reason}")
            )

    def _activation_clean_up(self):
        self._remove_ac_handlers()
        self._remove_dev_handlers()

    def _remove_ac_handlers(self):
        for handler_id in self._ac_handlers:
            self._nm_ac.handler_disconnect(handler_id)
        self._ac_handlers = set()

    def _remove_dev_handlers(self):
        for handler_id in self._dev_handlers:
            self.nmdev.handler_disconnect(handler_id)
        self._dev_handlers = set()

    def _delete(self):
        if self._remote_conn:
            action = f"Delete profile: uuid:{self._remote_conn.get_uuid()}"
            user_data = action
            self._ctx.register_async(action, fast=True)
            self._remote_conn.delete_async(
                self._ctx.cancellable,
                self._delete_profile_callback,
                user_data,
            )

    def _delete_profile_callback(self, src_object, result, user_data):
        if self._ctx.is_cancelled():
            return
        action = user_data
        try:
            success = src_object.delete_finish(result)
        except Exception as e:
            self._ctx.fail(NmstateLibnmError(f"{action} failed: error={e}"))
            return

        if success:
            self._ctx.finish_async(action)
        else:
            self._ctx.fail(
                NmstateLibnmError(
                    f"{action} failed: "
                    "error='None returned from delete_finish'"
                )
            )

    def _update(self):
        flags = NM.SettingsUpdate2Flags.BLOCK_AUTOCONNECT
        if self._save_to_disk:
            flags |= NM.SettingsUpdate2Flags.TO_DISK
        else:
            flags |= NM.SettingsUpdate2Flags.IN_MEMORY
        action = f"Update profile: {self._remote_conn.get_uuid()}"
        user_data = action
        args = None

        self._ctx.register_async(action, fast=True)
        self._remote_conn.update2(
            self._simple_conn.to_dbus(NM.ConnectionSerializationFlags.ALL),
            flags,
            args,
            self._ctx.cancellable,
            self._update2_callback,
            user_data,
        )

    def _update2_callback(self, src_object, result, user_data):
        if self._ctx.is_cancelled():
            return
        action = user_data
        try:
            ret = src_object.update2_finish(result)
        except Exception as e:
            self._ctx.fail(
                NmstateLibnmError(f"{action} failed with error={e}")
            )
            return
        if ret is None:
            self._ctx.fail(
                NmstateLibnmError(
                    f"{action} failed with error='None returned from "
                    "update2_finish()'"
                )
            )
        else:
            self._ctx.finish_async(action)

    def _add(self):
        nm_add_conn2_flags = NM.SettingsAddConnection2Flags
        flags = nm_add_conn2_flags.BLOCK_AUTOCONNECT
        if self._save_to_disk:
            flags |= nm_add_conn2_flags.TO_DISK
        else:
            flags |= nm_add_conn2_flags.IN_MEMORY

        action = f"Add profile: {self._simple_conn.get_uuid()}"
        self._ctx.register_async(action, fast=True)

        user_data = action
        args = None
        ignore_out_result = False  # Don't fall back to old AddConnection()
        self._ctx.client.add_connection2(
            self._simple_conn.to_dbus(NM.ConnectionSerializationFlags.ALL),
            flags,
            args,
            ignore_out_result,
            self._ctx.cancellable,
            self._add_connection2_callback,
            user_data,
        )

    def _add_connection2_callback(self, src_object, result, user_data):
        if self._ctx.is_cancelled():
            return
        action = user_data
        try:
            self._remote_conn = src_object.add_connection2_finish(result)[0]
        except Exception as e:
            self._ctx.fail(
                NmstateLibnmError(f"{action} failed with error: {e}")
            )
            return

        if self._remote_conn is None:
            self._ctx.fail(
                NmstateLibnmError(
                    f"{action} failed with error: 'None returned from "
                    "add_connection2_finish()'"
                )
            )
        else:
            self._ctx.finish_async(action)

    def store_config(self):
        ifname = self.iface_state[Interface.NAME]
        self._import_existing_profile(ifname)
        if (
            not (
                set(self._iface.original_dict.keys())
                <= set([Interface.STATE, Interface.NAME, Interface.TYPE])
            )
            or not self._remote_conn
            or self._iface.is_changed
        ):
            if self.iface_state[Interface.STATE] != InterfaceState.ABSENT:
                settings = self._generate_connection_settings(ifname)
                self._create_new_simple_connection(settings)
                set_conn = self._simple_conn.get_setting_connection()
                set_conn.props.interface_name = self.iface_state[
                    Interface.NAME
                ]
                if self._remote_conn:
                    self._update()
                else:
                    connection.delete_iface_inactive_connections(
                        self._ctx, ifname
                    )
                    self._add()
        self._ctx.wait_all_finish()

    def _create_new_simple_connection(self, settings):
        self._simple_conn = NM.SimpleConnection.new()
        for setting in settings:
            self._simple_conn.add_setting(setting)

    def _generate_connection_settings(self, ifname):
        nm_iface_type = translator.Api2Nm.get_iface_type(
            self.iface_state[Interface.TYPE]
        )

        settings = [
            ipv4.create_setting(
                self.iface_state.get(Interface.IPV4), self._remote_conn
            ),
            ipv6.create_setting(
                self.iface_state.get(Interface.IPV6), self._remote_conn
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
        lldp.apply_lldp_setting(con_setting, self.iface_state)

        master = self.iface_state.get(MASTER_METADATA)
        master_type = self.iface_state.get(MASTER_TYPE_METADATA)
        if master_type == LB.TYPE:
            self.iface_state[MASTER_TYPE_METADATA] = bridge.BRIDGE_TYPE
            master_type = bridge.BRIDGE_TYPE
        con_setting.set_master(master, master_type)
        settings.append(con_setting.setting)

        # Only apply wired/ethernet configuration based on original desire
        # state rather than the merged one.
        wired_setting = wired.create_setting(
            self.original_iface_state, self._remote_conn
        )
        if wired_setting:
            settings.append(wired_setting)

        user_setting = user.create_setting(self.iface_state, self._remote_conn)
        if user_setting:
            settings.append(user_setting)

        bond_opts = translator.Api2Nm.get_bond_options(self.iface_state)
        iface_type = self.iface_state[Interface.TYPE]
        if bond_opts:
            settings.append(bond.create_setting(bond_opts, wired_setting))
        elif iface_type == bridge.BRIDGE_TYPE:
            bridge_config = self.iface_state.get(bridge.BRIDGE_TYPE, {})
            bridge_options = bridge_config.get(LB.OPTIONS_SUBTREE)
            bridge_ports = bridge_config.get(LB.PORT_SUBTREE)

            if bridge_options or bridge_ports:
                linux_bridge_setting = bridge.create_setting(
                    self.iface_state,
                    self._remote_conn,
                    self.original_iface_state,
                )
                settings.append(linux_bridge_setting)
        elif iface_type == InterfaceType.OVS_BRIDGE:
            ovs_bridge_state = self.iface_state.get(OvsB.CONFIG_SUBTREE, {})
            ovs_bridge_options = ovs_bridge_state.get(OvsB.OPTIONS_SUBTREE)
            if ovs_bridge_options:
                settings.append(
                    nm_ovs.create_bridge_setting(ovs_bridge_options)
                )
        elif iface_type == InterfaceType.OVS_PORT:
            ovs_port_options = self.iface_state.get(OvsB.OPTIONS_SUBTREE)
            settings.append(nm_ovs.create_port_setting(ovs_port_options))
        elif iface_type == InterfaceType.OVS_INTERFACE:
            patch_state = self.iface_state.get(
                OVSInterface.PATCH_CONFIG_SUBTREE
            )
            settings.extend(nm_ovs.create_interface_setting(patch_state))

        bridge_port_options = self.iface_state.get(
            BridgeIface.BRPORT_OPTIONS_METADATA
        )
        if bridge_port_options and master_type == bridge.BRIDGE_TYPE:
            settings.append(
                bridge.create_port_setting(
                    bridge_port_options, self._remote_conn
                )
            )

        vlan_setting = vlan.create_setting(self.iface_state, self._remote_conn)
        if vlan_setting:
            settings.append(vlan_setting)

        vxlan_setting = vxlan.create_setting(
            self.iface_state, self._remote_conn
        )
        if vxlan_setting:
            settings.append(vxlan_setting)

        sriov_setting = sriov.create_setting(
            self._ctx, self.iface_state, self._remote_conn
        )
        if sriov_setting:
            settings.append(sriov_setting)

        team_setting = team.create_setting(self.iface_state, self._remote_conn)
        if team_setting:
            settings.append(team_setting)

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

    def create_proxy_profile(self):
        """
        Prepare the state of the "proxy" interface. These are interfaces that
        exist as NM entities/profiles, but are invisible to the API.
        These proxy interfaces state is created as a side effect of other
        ifaces definition.
        In OVS case, the port profile is the proxy, it is not part of the
        public state of the system, but internal to the NM provider.
        """
        iface_state = self.iface_state
        master_type = iface_state.get(MASTER_TYPE_METADATA)
        if master_type != InterfaceType.OVS_BRIDGE:
            return None
        port_opts_metadata = iface_state.get(
            BridgeIface.BRPORT_OPTIONS_METADATA
        )
        if port_opts_metadata is None:
            return None
        port_iface_desired_state = self._create_ovs_port_iface_desired_state(
            port_opts_metadata, iface_state
        )
        # The "visible" slave/interface needs to point to the port profile
        iface_state[MASTER_METADATA] = port_iface_desired_state[Interface.NAME]
        iface_state[MASTER_TYPE_METADATA] = InterfaceType.OVS_PORT

        return NmProfile(
            self._ctx, self._save_to_disk, iface_state=port_iface_desired_state
        )

    def _create_ovs_port_iface_desired_state(self, port_options, iface_state):
        iface_name = self._iface.name
        if ovs.is_ovs_lag_port(port_options):
            port_name = port_options[OvsB.Port.NAME]
        else:
            port_name = ovs.PORT_PROFILE_PREFIX + iface_name
        return {
            Interface.NAME: port_name,
            Interface.TYPE: InterfaceType.OVS_PORT,
            Interface.STATE: self.iface_state,
            OvsB.OPTIONS_SUBTREE: port_options,
            MASTER_METADATA: iface_state[MASTER_METADATA],
            MASTER_TYPE_METADATA: iface_state[MASTER_TYPE_METADATA],
        }


def get_all_applied_configs(context):
    applied_configs = {}
    for nm_dev in list_devices(context.client):
        if nm_dev.get_state() in (
            NM.DeviceState.ACTIVATED,
            NM.DeviceState.IP_CONFIG,
        ):
            iface_name = nm_dev.get_iface()
            if iface_name:
                action = f"Retrieve applied config: {iface_name}"
                context.register_async(action, fast=True)
                nm_dev.get_applied_connection_async(
                    flags=0,
                    cancellable=context.cancellable,
                    callback=_get_applied_config_callback,
                    user_data=(iface_name, action, applied_configs, context),
                )
    context.wait_all_finish()
    return applied_configs


def _get_applied_config_callback(nm_dev, result, user_data):
    iface_name, action, applied_configs, context = user_data
    context.finish_async(action)
    try:
        remote_conn, _ = nm_dev.get_applied_connection_finish(result)
        applied_configs[nm_dev.get_iface()] = remote_conn
    except Exception as e:
        logging.warning(
            "Failed to retrieve applied config for device "
            f"{iface_name}: {e}"
        )
