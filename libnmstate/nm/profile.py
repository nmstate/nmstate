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
from libnmstate.error import NmstateInternalError
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
from . import profile
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


class Profiles:
    def __init__(self, context, net_state, save_to_disk):
        self._ctx = context
        self._net_state = net_state
        self._preapply_dns_fix()
        self._profiles = [
            Profile(context, iface)
            for iface in net_state.ifaces.values()
            if iface.is_changed or iface.is_desired
        ]
        self._save_to_disk = save_to_disk

    def apply_changes(self):
        proxy_profiles = []
        for profile in self.profiles:
            proxy_profile = profile.create_proxy_profile()
            if proxy_profile:
                proxy_profiles.append(proxy_profile)
            profile.store_config(self._save_to_disk)

        for profile in self.proxy_profiles:
            profile.store_config(self._save_to_disk)
        self.profiles.extend(self.proxy_profiles)

        profiles._apply_config()
        self._context.wait_all_finish()

    def apply_changes(self):
        """
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
        devs_to_deactivate_beforehand = []
        profiles_to_delete = []
        top_masters = set()
        new_ifaces = set()
        changed_masters = set()
        new_ovs_ports = set()
        new_ovs_ifaces = set()
        changed_ifaces = []
        new_vlans = set()
        new_vxlans = set()
        devs_to_deactivate = {}
        devs_to_delete_profile = {}
        devs_to_delete = {}

        for profile in self._profiles:
            if not profile.nmdevice:
                if profile.iface_state[Interface.TYPE] == InterfaceState.UP:
                    if (
                        profile.is_master_iface()
                        and not profile.is_slave_iface()
                    ):
                        top_masters.add(profile)
                    elif (
                        profile.iface_state[Interface.TYPE]
                        == InterfaceType.OVS_INTERFACE
                    ):
                        new_ovs_ifaces.add(profile)
                    elif (
                        profile.iface_state[Interface.TYPE]
                        == InterfaceType.OVS_PORT
                    ):
                        new_ovs_ports.add(profile)
                    elif (
                        profile.iface_state[Interface.TYPE]
                        == InterfaceType.VLAN
                    ):
                        new_vlans.add(profile)
                    elif (
                        profile.iface_state[Interface.TYPE]
                        == InterfaceType.VXLAN
                    ):
                        new_vxlans.add(profile)
                    else:
                        new_ifaces.add(profile)
                elif (
                    profile.iface_state[Interface.STATE]
                    == InterfaceState.ABSENT
                ):
                    profiles_to_delete.append(profile)
            else:
                if profile.iface_state[Interface.STATE] == InterfaceState.UP:
                    if (
                        profile.iface_state.get(Interface.STATE)
                        == InterfaceType.BOND
                    ):
                        iface = BondIface(profile.iface_state)
                        if iface.is_bond_mode_changed:
                            # NetworkManager leaves leftover in sysfs for bond
                            # options when changing bond mode, bug:
                            # https://bugzilla.redhat.com/1819137
                            # Workaround: delete the bond interface from kernel
                            # and create again via full deactivation
                            # beforehand.
                            logging.debug(
                                f"Bond interface {ifname} is changing bond "
                                "mode, will do full deactivation before "
                                "applying changes"
                            )
                            devs_to_deactivate_beforehand.append(profile)
                    if profile._is_master_iface():
                        changed_masters.add(profile)
                    else:
                        changed_ifaces.add(profile)
                elif profile.iface_state[Interface.STATE] in (
                    InterfaceState.DOWN,
                    InterfaceState.ABSENT,
                ):
                    nmdevs = self._get_affected_devices()
                    is_absent = (
                        profile.iface_state[Interface.STATE]
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
                            profile.iface_state[Interface.STATE],
                            profile.iface_state[Interface.NAME],
                        )
                    )

            for dev in devs_to_deactivate_beforehand:
                device.deactivate(self._ctx, dev)

            # Do not remove devices that are marked for editing.
            for profile in itertools.chain(changed_masters, changed_ifaces):
                devs_to_deactivate.pop(profile.nmdevice.get_iface(), None)
                devs_to_delete_profile.pop(profile.nmdevice.get_iface(), None)
                devs_to_delete.pop(profile.nmdevice.get_iface(), None)

            for profile in profiles_to_delete:
                profile.delete()
                self._ctx.wait_all_finish()

            for profile in top_masters:
                device.activate(context, dev=None, profile=profile)
            self._ctx.wait_all_finish()

            for profile in new_ifaces:
                device.activate(context, dev=None, profile=profile)
            self._ctx.wait_all_finish()

            for profile in changed_masters:
                device.modify(context, profile.nmdevice, profile.profile)
            self._ctx.wait_all_finish()

            for profile in new_ovs_ports:
                device.activate(context, dev=None, profile=profile)
            self._ctx.wait_all_finish()

            for profile in new_ovs_ifaces:
                device.activate(context, dev=None, profile=profile)
            self._ctx.wait_all_finish()

            for profile in changed_ifaces:
                device.modify(context, profile.nmdevice, profile.profile)
            self._ctx.wait_all_finish()

            for profile in new_vlans:
                device.activate(context, dev=None, profile=profile)
            self._ctx.wait_all_finish()

            for profile in new_vxlans:
                device.activate(context, dev=None, profile=profile)
            self._ctx.wait_all_finish()

            for dev in devs_to_deactivate.values():
                device.deactivate(context, dev)
            self._ctx.wait_all_finish()

            for dev in devs_to_delete_profile.values():
                device.delete(context, dev)
            self._ctx.wait_all_finish()

            for dev in devs_to_delete.values():
                device.delete_device(context, dev)
            self._ctx.wait_all_finish()

    def _get_affected_devices(self):
        nmdev = self.context.get_nm_dev(self.iface_state[Interface.NAME])
        devs = []
        if nmdev:
            devs += [nmdev]
            iface_type = self.iface_state[Interface.TYPE]
            if iface_type == InterfaceType.OVS_BRIDGE:
                port_slaves = ovs.get_slaves(nmdev)
                iface_slaves = [
                    iface
                    for port in port_slaves
                    for iface in ovs.get_slaves(port)
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

    def _preapply_dns_fix(self):
        """
         * When DNS configuration does not changed and old interface hold DNS
           configuration is not included in `ifaces_desired_state`, preserve
           the old DNS configure by removing DNS metadata from
           `ifaces_desired_state`.
         * When DNS configuration changed, include old interface which is holding
           DNS configuration, so it's DNS configure could be removed.
        """
        cur_dns_iface_names = get_dns_config_iface_names(
            ipv4.acs_and_ip_profiles(self._ctx.client),
            ipv6.acs_and_ip_profiles(self._ctx.client),
        )

        # Whether to mark interface as changed which is used for holding old DNS
        # configurations
        remove_existing_dns_config = False
        # Whether to preserve old DNS config by DNS metadata to be removed from
        # desired state
        preserve_old_dns_config = False
        if self._net_state.dns.config == self._net_state.dns.current_config:
            for cur_dns_iface_name in cur_dns_iface_names:
                iface = self._net_state.ifaces[cur_dns_iface_name]
                if iface.is_changed or iface.is_desired:
                    remove_existing_dns_config = True
            if not remove_existing_dns_config:
                preserve_old_dns_config = True
        else:
            remove_existing_dns_config = True

        if remove_existing_dns_config:
            for cur_dns_iface_name in cur_dns_iface_names:
                iface = _net_state.ifaces[cur_dns_iface_name]
                iface.mark_as_changed()

        if preserve_old_dns_config:
            for iface in self._net_state.ifaces.values():
                if iface.is_changed or iface.is_desired:
                    iface.remove_dns_metadata()


class Profile:
    def __init__(self, context, iface=None, profile=None):
        self._ctx = context
        self.rofile = profile
        self.iface = iface
        self._iface_state = iface.to_dict() if iface else None
        self._original_iface_state = iface.original_dict if iface else None
        self._nm_dev = None
        self._con_id = None
        self._uuid = None
        self._nm_ac = None
        self._ac_handlers = set()
        self._dev_handlers = set()
        self.ignore = False

    def create(self, settings):
        self.profile = NM.SimpleConnection.new()
        for setting in settings:
            self.profile.add_setting(setting)

    def create_proxy_profile(self):
        """
        Prepare the state of the "proxy" interface. These are interfaces that
        exist as NM entities/profiles, but are invisible to the API.
        These proxy interfaces state is created as a side effect of other ifaces
        definition.

        In OVS case, the port profile is the proxy, it is not part of the public
        state of the system, but internal to the NM provider.
        """

        master_type = self.iface_state.get(MASTER_TYPE_METADATA)
        if master_type != InterfaceType.OVS_BRIDGE:
            return None
        port_opts_metadata = self.iface_state.get(
            BridgeIface.BRPORT_OPTIONS_METADATA
        )
        if port_opts_metadata is None:
            return None
        port_iface_desired_state = self._create_ovs_port_iface_desired_state(
            port_opts_metadata
        )
        port_iface_name = port_iface_desired_state[Interface.NAME]
        # The "visible" slave/interface needs to point to the port profile
        self.iface_state[MASTER_METADATA] = port_iface_desired_state[
            Interface.NAME
        ]
        self.iface_state[MASTER_TYPE_METADATA] = InterfaceType.OVS_PORT

        return Profile(context, port_iface_desired_state)

    def _create_ovs_port_iface_desired_state(self, port_options):
        iface_name = self.iface_state[Interface.NAME]
        if _is_ovs_lag_port(port_options):
            port_name = port_options[OvsB.Port.NAME]
        else:
            port_name = ovs.PORT_PROFILE_PREFIX + iface_name
        return {
            Interface.NAME: port_name,
            Interface.TYPE: InterfaceType.OVS_PORT,
            Interface.STATE: self.iface_state[Interface.STATE],
            OvsB.OPTIONS_SUBTREE: port_options,
            MASTER_METADATA: self.iface_state[MASTER_METADATA],
            MASTER_TYPE_METADATA: self.iface_state[MASTER_TYPE_METADATA],
        }

    @staticmethod
    def _is_ovs_lag_port(port_state):
        return port_state.get(OvsB.Port.LINK_AGGREGATION_SUBTREE) is not None

    def store_config(self, save_to_disk):
        if self.iface_state.get(Interface.STATE) not in (
            Interface.ABSENT,
            InterfaceState.DOWN,
        ):
            ifname = self.iface_state.get(Interface.NAME)
            nmdev = context.get_nm_dev(ifname)
            if nmdev:
                self.import_by_device(nmdev)
            else:
                # Profile for virtual interface will remove interface when down
                # hence search on existing NM.RemoteConnection
                con_profile = context.client.get_connection_by_id(ifname)
                if con_profile and con_profile.get_interface_name() == ifname:
                    self._profile = con_profile
            if (
                not set(self._original_iface_state.keys())
                <= set([Interface.STATE, Interface.NAME, Interface.TYPE])
                or not self.profile
                or self.iface.is_changed
            ):
                # Create new profile if original desire ask
                # anything else besides state:up or has been marked as changed.
                self._build_connection_profile()
                if not self.devname:
                    set_conn = self.profile.get_setting_connection()
                    set_conn.props.interface_name = ifname
                if self._profile:
                    self.profile.update(save_to_disk)
                else:
                    # Missing connection, attempting to create a new one.
                    connection.delete_iface_inactive_connections(
                        self.context, ifname
                    )
                    self.add(save_to_disk)
            self.context.wait_all_finish()

    def _build_connection_profile(self):
        iface_type = translator.Api2Nm.get_iface_type(
            self.iface_state[Interface.TYPE]
        )

        settings = [
            ipv4.create_setting(
                self.iface_state.get(Interface.IPV4), self.profile
            ),
            ipv6.create_setting(
                self.iface_state.get(Interface.IPV6), self.profile
            ),
        ]

        con_setting = connection.ConnectionSetting()
        iface_name = self.iface_state[Interface.NAME]
        if self._profile:
            con_setting.import_by_profile(self._profile)
            con_setting.set_profile_name(iface_name)
        else:
            con_setting.create(
                con_name=iface_name,
                iface_name=iface_name,
                iface_type=iface_type,
            )
        lldp.apply_lldp_setting(con_setting, self.iface_state)

        master = self.iface_state.get(MASTER_METADATA)
        _translate_master_type(self.iface_state)
        master_type = self.iface_state.get(MASTER_TYPE_METADATA)
        con_setting.set_master(master, master_type)
        settings.append(con_setting.setting)

        # Only apply wired/ethernet configuration based on original desire
        # state rather than the merged one.
        wired_setting = wired.create_setting(
            self.original_iface_state, self.profile
        )
        if wired_setting:
            settings.append(wired_setting)

        user_setting = user.create_setting(self.iface_state, self._profile)
        if user_setting:
            settings.append(user_setting)

        bond_opts = translator.Api2Nm.get_bond_options(self.iface_state)
        if bond_opts:
            settings.append(bond.create_setting(bond_opts, wired_setting))
        elif iface_type == bridge.BRIDGE_TYPE:
            bridge_config = self.iface_state.get(bridge.BRIDGE_TYPE, {})
            bridge_options = bridge_config.get(LB.OPTIONS_SUBTREE)
            bridge_ports = bridge_config.get(LB.PORT_SUBTREE)

            if bridge_options or bridge_ports:
                linux_bridge_setting = bridge.create_setting(
                    self.iface_state, self._profile, self.original_iface_state,
                )
                settings.append(linux_bridge_setting)
        elif iface_type == InterfaceType.OVS_BRIDGE:
            ovs_bridge_state = self.iface_state.get(OvsB.CONFIG_SUBTREE, {})
            ovs_bridge_options = ovs_bridge_state.get(OvsB.OPTIONS_SUBTREE)
            if ovs_bridge_options:
                settings.append(ovs.create_bridge_setting(ovs_bridge_options))
        elif iface_type == InterfaceType.OVS_PORT:
            ovs_port_options = self.iface_state.get(OvsB.OPTIONS_SUBTREE)
            settings.append(ovs.create_port_setting(ovs_port_options))
        elif iface_type == InterfaceType.OVS_INTERFACE:
            patch_state = self.iface_state.get(
                OVSInterface.PATCH_CONFIG_SUBTREE
            )
            settings.extend(ovs.create_interface_setting(patch_state))

        bridge_port_options = self.iface_state.get(
            BridgeIface.BRPORT_OPTIONS_METADATA
        )
        if bridge_port_options and master_type == bridge.BRIDGE_TYPE:
            settings.append(
                bridge.create_port_setting(bridge_port_options, self._profile)
            )

        vlan_setting = vlan.create_setting(self.iface_state, self._profile)
        if vlan_setting:
            settings.append(vlan_setting)

        vxlan_setting = vxlan.create_setting(self.iface_state, self._profile)
        if vxlan_setting:
            settings.append(vxlan_setting)

        sriov_setting = sriov.create_setting(
            self.context, self.iface_state, self.profile
        )
        if sriov_setting:
            settings.append(sriov_setting)

        team_setting = team.create_setting(self.iface_state, self._profile)
        if team_setting:
            settings.append(team_setting)

        self.create(settings)

    @staticmethod
    def _translate_master_type(iface_desired_state):
        """
        Translates the master type metadata names to their equivalent
        NM type names.
        """
        master_type = iface_desired_state.get(MASTER_TYPE_METADATA)
        if master_type == LB.TYPE:
            iface_desired_state[MASTER_TYPE_METADATA] = bridge.BRIDGE_TYPE

    @property
    def iface_state(self):
        return self._iface_state

    def is_master_iface(self):
        return self.iface_state in MASTER_IFACE_TYPES

    def is_slave_iface(self):
        return self.iface_state.get(MASTER_METADATA)

    @property
    def context(self):
        return self._ctx

    def import_by_device(self, nmdev=None):
        ac = get_device_active_connection(nmdev or self.nmdevice)
        if ac:
            if nmdev:
                self.nmdevice = nmdev
            self.profile = ac.props.connection
            self._profile = ac.props.connection

    def import_by_id(self, con_id=None):
        if con_id:
            self.con_id = con_id
        if self.con_id:
            self.profile = self._ctx.client.get_connection_by_id(self.con_id)

    def import_by_uuid(self, uuid=None):
        if uuid:
            self.uuid = uuid
        if self.uuid:
            self.profile = self._ctx.client.get_connection_by_uuid(self.uuid)

    def update(self, save_to_disk=True):
        flags = NM.SettingsUpdate2Flags.BLOCK_AUTOCONNECT
        if save_to_disk:
            flags |= NM.SettingsUpdate2Flags.TO_DISK
        else:
            flags |= NM.SettingsUpdate2Flags.IN_MEMORY
        action = f"Update profile: {self.profile.get_id()}"
        user_data = action
        args = None

        self._ctx.register_async(action, fast=True)
        self.profile.update2(
            self.profile.to_dbus(NM.ConnectionSerializationFlags.ALL),
            flags,
            args,
            self._ctx.cancellable,
            self._update2_callback,
            user_data,
        )

    def add(self, save_to_disk=True):
        nm_add_conn2_flags = NM.SettingsAddConnection2Flags
        flags = nm_add_conn2_flags.BLOCK_AUTOCONNECT
        if save_to_disk:
            flags |= nm_add_conn2_flags.TO_DISK
        else:
            flags |= nm_add_conn2_flags.IN_MEMORY

        action = f"Add profile: {self.profile.get_id()}"
        self._ctx.register_async(action, fast=True)

        user_data = action
        args = None
        ignore_out_result = False  # Don't fall back to old AddConnection()
        self._ctx.client.add_connection2(
            self.profile.to_dbus(NM.ConnectionSerializationFlags.ALL),
            flags,
            args,
            ignore_out_result,
            self._ctx.cancellable,
            self._add_connection2_callback,
            user_data,
        )

    def delete(self):
        if self._profile:
            action = (
                f"Delete profile: id:{self.profile.get_id()}, "
                f"uuid:{self.profile.get_uuid()}"
            )
            user_data = action
            self._ctx.register_async(action, fast=True)
            self.profile.delete_async(
                self._ctx.cancellable,
                self._delete_connection_callback,
                user_data,
            )

    def activate(self):
        if self.uuid:
            self.import_by_uuid()
        elif not self.profile:
            raise NmstateInternalError(
                "BUG: Failed  to find valid profile to activate: "
                f"id={self.con_id}, dev={self.devname} uuid={self.uuid}"
            )

        specific_object = None
        if self.profile:
            action = f"Activate profile: {self.profile.get_id()}"
        elif self.nmdevice:
            action = f"Activate profile: {self.nmdevice.get_iface()}"
        else:
            raise NmstateInternalError(
                "BUG: Cannot activate a profile with empty profile id and "
                "empty NM.Device"
            )
        user_data = action
        self._ctx.register_async(action)
        self._ctx.client.activate_connection_async(
            self.profile,
            self.nmdevice,
            specific_object,
            self._ctx.cancellable,
            self._active_connection_callback,
            user_data,
        )

    @property
    def profile(self):
        return self.profile

    @profile.setter
    def profile(self, con_profile):
        assert self.profile is None
        self.profile = con_profile

    @property
    def devname(self):
        if self.profile:
            return self.profile.get_interface_name()
        return None

    @property
    def nmdevice(self):
        return self._nm_dev

    @nmdevice.setter
    def nmdevice(self, dev):
        assert self._nm_dev is None
        self._nm_dev = dev

    @property
    def con_id(self):
        con_id = self.profile.get_id() if self._con_profile else None
        return self._con_id or con_id

    @con_id.setter
    def con_id(self, connection_id):
        assert self._con_id is None
        self._con_id = connection_id

    @property
    def uuid(self):
        uuid = self.profile.get_uuid() if self._con_profile else None
        return self._uuid or uuid

    @uuid.setter
    def uuid(self, connection_uuid):
        assert self._uuid is None
        self._uuid = connection_uuid

    def get_setting_duplicate(self, setting_name):
        setting = None
        if self.profile:
            setting = self.profile.get_setting_by_name(setting_name)
            if setting:
                setting = setting.duplicate()
        return setting

    def _active_connection_callback(self, src_object, result, user_data):
        if self._ctx.is_cancelled():
            self._activation_clean_up()
            return
        action = user_data

        try:
            nm_act_con = src_object.activate_connection_finish(result)
        except Exception as e:
            self._ctx.fail(NmstateLibnmError(f"{action} failed: error={e}"))
            return

        if nm_act_con is None:
            self._ctx.fail(
                NmstateLibnmError(
                    f"{action} failed: "
                    "error='None return from activate_connection_finish()'"
                )
            )
        else:
            devname = self.devname
            logging.debug(
                "Connection activation initiated: dev=%s, con-state=%s",
                devname,
                nm_act_con.props.state,
            )
            self._nm_ac = nm_act_con
            self._nm_dev = self._ctx.get_nm_dev(devname)

            if is_activated(self._nm_ac, self._nm_dev):
                self._ctx.finish_async(action)
            elif self._is_activating():
                self._wait_ac_activation(action)
                if self._nm_dev:
                    self.wait_dev_activation(action)
            else:
                if self._nm_dev:
                    error_msg = (
                        f"Connection {self.profile.get_id()} failed: "
                        f"state={self._nm_ac.get_state()} "
                        f"reason={self._nm_ac.get_state_reason()} "
                        f"dev_state={self._nm_dev.get_state()} "
                        f"dev_reason={self._nm_dev.get_state_reason()}"
                    )
                else:
                    error_msg = (
                        f"Connection {self.profile.get_id()} failed: "
                        f"state={self._nm_ac.get_state()} "
                        f"reason={self._nm_ac.get_state_reason()} dev=None"
                    )
                logging.error(error_msg)
                self._ctx.fail(
                    NmstateLibnmError(f"{action} failed: {error_msg}")
                )

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

    def wait_dev_activation(self, action):
        if self._nm_dev:
            self._dev_handlers.add(
                self._nm_dev.connect(
                    "state-changed", self._dev_state_change_callback, action
                )
            )

    def _dev_state_change_callback(
        self, _dev, _new_state, _old_state, _reason, action,
    ):
        if self._ctx.is_cancelled():
            self._activation_clean_up()
            return
        self._activation_progress_check(action)

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
        devname = self._nm_dev.get_iface()
        cur_nm_dev = self._ctx.get_nm_dev(devname)
        if cur_nm_dev and cur_nm_dev != self._nm_dev:
            logging.debug(f"The NM.Device of profile {devname} changed")
            self._remove_dev_handlers()
            self._nm_dev = cur_nm_dev
            self.wait_dev_activation(action)

        cur_nm_ac = get_device_active_connection(self.nmdevice)
        if cur_nm_ac and cur_nm_ac != self._nm_ac:
            logging.debug(
                "Active connection of device {} has been replaced".format(
                    self.devname
                )
            )
            self._remove_ac_handlers()
            self._nm_ac = cur_nm_ac
            self._wait_ac_activation(action)
        if is_activated(self._nm_ac, self._nm_dev):
            logging.debug(
                "Connection activation succeeded: dev=%s, con-state=%s, "
                "dev-state=%s, state-flags=%s",
                devname,
                self._nm_ac.get_state(),
                self._nm_dev.get_state(),
                self._nm_ac.get_state_flags(),
            )
            self._activation_clean_up()
            self._ctx.finish_async(action)
        elif not self._is_activating():
            reason = f"{self._nm_ac.get_state_reason()}"
            if self.nmdevice:
                reason += f" {self.nmdevice.get_state_reason()}"
            self._activation_clean_up()
            self._ctx.fail(
                NmstateLibnmError(f"{action} failed: reason={reason}")
            )

    def _activation_clean_up(self):
        self._remove_ac_handlers()
        self._remove_dev_handlers()

    def _is_activating(self):
        if not self._nm_ac or not self._nm_dev:
            return True
        if (
            self._nm_dev.get_state_reason()
            == NM.DeviceStateReason.NEW_ACTIVATION
        ):
            return True

        return (
            self._nm_ac.get_state() == NM.ActiveConnectionState.ACTIVATING
        ) and not is_activated(self._nm_ac, self._nm_dev)

    def _remove_dev_handlers(self):
        for handler_id in self._dev_handlers:
            self._nm_dev.handler_disconnect(handler_id)
        self._dev_handlers = set()

    def _remove_ac_handlers(self):
        for handler_id in self._ac_handlers:
            self._nm_ac.handler_disconnect(handler_id)
        self._ac_handlers = set()

    def _add_connection2_callback(self, src_object, result, user_data):
        if self._ctx.is_cancelled():
            return
        action = user_data
        try:
            profile = src_object.add_connection2_finish(result)[0]
        except Exception as e:
            self._ctx.fail(
                NmstateLibnmError(f"{action} failed with error: {e}")
            )
            return

        if profile is None:
            self._ctx.fail(
                NmstateLibnmError(
                    f"{action} failed with error: 'None returned from "
                    "add_connection2_finish()"
                )
            )
        else:
            self._ctx.finish_async(action)

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

    def _delete_connection_callback(self, src_object, result, user_data):
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
                    "error='None returned from delete_finish()'"
                )
            )

    def _reset_profile(self):
        self.profile = None


def get_all_applied_configs(context):
    applied_configs = {}
    for nm_dev in _list_devices(context.client):
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


def _list_devices(client):
    return client.get_devices()


def get_device_active_connection(nm_device):
    active_conn = None
    if nm_device:
        active_conn = nm_device.get_active_connection()
    return active_conn


def is_activated(nm_ac, nm_dev):
    if not (nm_ac and nm_dev):
        return False

    state = nm_ac.get_state()
    if state == NM.ActiveConnectionState.ACTIVATED:
        return True
    elif state == NM.ActiveConnectionState.ACTIVATING:
        ac_state_flags = nm_ac.get_state_flags()
        nm_flags = NM.ActivationStateFlags
        ip4_is_dynamic = ipv4.is_dynamic(nm_ac)
        ip6_is_dynamic = ipv6.is_dynamic(nm_ac)
        if (
            ac_state_flags & nm_flags.IS_MASTER
            or (ip4_is_dynamic and ac_state_flags & nm_flags.IP6_READY)
            or (ip6_is_dynamic and ac_state_flags & nm_flags.IP4_READY)
            or (ip4_is_dynamic and ip6_is_dynamic)
        ):
            # For interface meet any condition below will be
            # treated as activated when reach IP_CONFIG state:
            #   * Is master device.
            #   * DHCPv4 enabled with IP6_READY flag.
            #   * DHCPv6/Autoconf with IP4_READY flag.
            #   * DHCPv4 enabled with DHCPv6/Autoconf enabled.
            return (
                NM.DeviceState.IP_CONFIG
                <= nm_dev.get_state()
                <= NM.DeviceState.ACTIVATED
            )

    return False
