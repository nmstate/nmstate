#
# Copyright (c) 2020-2021 Red Hat, Inc.
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
import time

from libnmstate.error import NmstateInternalError
from libnmstate.error import NmstateLibnmError
from libnmstate.error import NmstateNotSupportedError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType

from .active_connection import ActiveConnectionDeactivate
from .active_connection import ProfileActivation
from .active_connection import is_activated
from .common import GLib
from .common import Gio
from .common import NM
from .connection import create_new_nm_simple_conn
from .connection import is_multiconnect_profile
from .connection import nm_simple_conn_update_controller
from .connection import nm_simple_conn_update_parent
from .device import DeviceDelete
from .device import DeviceReapply
from .device import get_nm_dev
from .translator import Api2Nm
from .vrf import is_vrf_table_id_changed


IMPORT_NM_DEV_TIMEOUT = 5
IMPORT_NM_DEV_RETRY_INTERNAL = 0.5
FALLBACK_CHECKER_INTERNAL = 15
ROUTE_REMOVED = "_route_removed"


class NmProfile:
    # For unmanged iface and desired to down
    ACTION_ACTIVATE_FIRST = "activate_first"
    ACTION_SRIOV_PF = "activate_sriov_pf"
    ACTION_DEACTIVATE = "deactivate"
    ACTION_DEACTIVATE_FIRST = "deactivate_first"
    ACTION_DELETE_DEVICE = "delete_device"
    ACTION_MODIFIED = "modified"
    ACTION_NEW_IFACES = "new_ifaces"
    ACTION_NEW_OVS_IFACE = "new_ovs_iface"
    ACTION_NEW_OVS_PORT = "new_ovs_port"
    ACTION_NEW_VETH = "new_veth"
    ACTION_NEW_VLAN = "new_vlan"
    ACTION_NEW_VXLAN = "new_vxlan"
    ACTION_OTHER_CONTROLLER = "other_controller"
    ACTION_DELETE_PROFILE = "delete_profile"
    ACTION_TOP_CONTROLLER = "top_controller"
    ACTION_MODIFIED_OVS_PORT = "modified_ovs_port"
    ACTION_MODIFIED_OVS_IFACE = "modified_ovs_iface"

    # This is order on group for activation/deactivation
    ACTIONS = (
        ACTION_ACTIVATE_FIRST,
        ACTION_DEACTIVATE_FIRST,
        ACTION_TOP_CONTROLLER,
        ACTION_SRIOV_PF,
        ACTION_NEW_IFACES,
        ACTION_OTHER_CONTROLLER,
        ACTION_NEW_OVS_PORT,
        ACTION_NEW_OVS_IFACE,
        ACTION_NEW_VETH,
        ACTION_MODIFIED_OVS_PORT,
        ACTION_MODIFIED_OVS_IFACE,
        ACTION_MODIFIED,
        ACTION_NEW_VLAN,
        ACTION_NEW_VXLAN,
        ACTION_DEACTIVATE,
        ACTION_DELETE_PROFILE,
        ACTION_DELETE_DEVICE,
    )

    def __init__(self, ctx, iface):
        self._ctx = ctx
        self._iface = iface
        self._nm_iface_type = None
        if self._iface.type != InterfaceType.UNKNOWN:
            self._nm_iface_type = Api2Nm.get_iface_type(self._iface.type)
        self._nm_ac = None
        self._nm_dev = None
        self._nm_profile = None
        self._nm_simple_conn = None
        self._actions = set()
        self._activated = False
        self._deactivated = False
        self._profile_deleted = False
        self._device_deleted = False

    @property
    def iface(self):
        return self._iface

    @property
    def has_pending_change(self):
        return (
            self.iface.is_changed or self.iface.is_desired
        ) and not self.iface.is_ignore

    @property
    def config_file_name(self):
        """
        Return the profile file name used NetworkManager for key-file mode.
        """
        if self._nm_simple_conn:
            return f"{self._nm_simple_conn.get_id()}.nmconnection"
        elif self._nm_profile:
            return f"{self._nm_profile.get_id()}.nmconnection"
        else:
            return ""

    @property
    def uuid(self):
        if self._nm_simple_conn:
            return self._nm_simple_conn.get_uuid()
        elif self._nm_profile:
            return self._nm_profile.get_uuid()
        else:
            return ""

    def disable_autoconnect(self):
        if self._nm_simple_conn:
            nm_conn_setting = self._nm_simple_conn.get_setting_connection()
            nm_conn_setting.props.autoconnect = False

    def update_controller(self, controller):
        nm_simple_conn_update_controller(self._nm_simple_conn, controller)

    def update_parent(self, parent):
        nm_simple_conn_update_parent(
            self._nm_simple_conn, self.iface.type, parent
        )

    def to_key_file_string(self):
        self._nm_simple_conn.normalize()
        # pylint: disable=no-member
        key_file = NM.keyfile_write(
            self._nm_simple_conn, NM.KeyfileHandlerFlags.NONE, None, None
        )
        # pylint: enable=no-member
        return key_file.to_data()[0]

    def _gen_actions(self):
        if not self.has_pending_change:
            return
        if self._iface.is_absent:
            self._add_action(NmProfile.ACTION_DELETE_PROFILE)
            if self._iface.is_virtual and self._nm_dev:
                self._add_action(NmProfile.ACTION_DELETE_DEVICE)
        elif self._iface.is_up and not self._needs_veth_activation():
            if not self._nm_dev:
                if self._iface.type == InterfaceType.OVS_PORT:
                    self._add_action(NmProfile.ACTION_NEW_OVS_PORT)
                elif self._iface.type == InterfaceType.OVS_INTERFACE:
                    self._add_action(NmProfile.ACTION_NEW_OVS_IFACE)
                elif self._iface.type == InterfaceType.VLAN:
                    self._add_action(NmProfile.ACTION_NEW_VLAN)
                elif self._iface.type == InterfaceType.VXLAN:
                    self._add_action(NmProfile.ACTION_NEW_VXLAN)
                else:
                    self._add_action(NmProfile.ACTION_NEW_IFACES)
            else:
                if (
                    self._nm_dev.props.capabilities
                    & NM.DeviceCapabilities.SRIOV
                ):
                    self._add_action(NmProfile.ACTION_SRIOV_PF)
                if self._iface.type == InterfaceType.OVS_PORT:
                    self._add_action(NmProfile.ACTION_MODIFIED_OVS_PORT)
                if self._iface.type == InterfaceType.OVS_INTERFACE:
                    self._add_action(NmProfile.ACTION_MODIFIED_OVS_IFACE)
                else:
                    self._add_action(NmProfile.ACTION_MODIFIED)

        elif self._iface.is_down:
            if self._nm_ac:
                self._add_action(NmProfile.ACTION_DEACTIVATE)
            if self._iface.is_virtual and self._nm_dev:
                self._add_action(NmProfile.ACTION_DELETE_DEVICE)
            if self._nm_dev and not self._nm_dev.get_managed():
                self._add_action(NmProfile.ACTION_DEACTIVATE)

        if self._iface.raw.get(ROUTE_REMOVED):
            # This is a workaround for NM bug:
            # https://bugzilla.redhat.com/1837254
            # https://bugzilla.redhat.com/1962551
            self._add_action(NmProfile.ACTION_DEACTIVATE_FIRST)

        if (
            self._iface.type == InterfaceType.VRF
            and self._nm_dev
            and is_vrf_table_id_changed(self._iface, self._nm_dev)
        ):
            # NM cannot change VRF table ID online
            self._add_action(NmProfile.ACTION_DEACTIVATE_FIRST)

        if self._iface.is_controller and self._iface.is_up:
            if self._iface.controller:
                self._add_action(NmProfile.ACTION_OTHER_CONTROLLER)
            else:
                self._add_action(NmProfile.ACTION_TOP_CONTROLLER)

        if self._iface.is_up and self._needs_veth_activation():
            self._add_action(NmProfile.ACTION_NEW_VETH)

        if (
            self._iface.is_up
            and self._iface.type == InterfaceType.BOND
            and self._iface.is_bond_mode_changed
        ):
            # NetworkManager leaves leftover in sysfs for bond
            # options when changing bond mode, bug:
            # https://bugzilla.redhat.com/show_bug.cgi?id=1819137
            # Workaround: delete the bond interface from kernel and
            # create again via full deactivation beforehand.
            self._add_action(NmProfile.ACTION_DEACTIVATE_FIRST)

        if self._iface.is_up and self._iface.type in (
            InterfaceType.MAC_VLAN,
            InterfaceType.MAC_VTAP,
        ):
            # NetworkManager requires the profile to be deactivated in
            # order to modify it. Therefore if the profile is modified
            # it needs to be deactivated beforehand in order to apply
            # the changes and activate it again.
            self._add_action(NmProfile.ACTION_DEACTIVATE_FIRST)

        if (
            self._iface.is_up
            and self._iface.type == InterfaceType.VETH
            and self._iface.is_peer_changed
        ):
            # NetworkManager requires the profile to be deactivated in order to
            # modify the peer. Therefore if the profile is modified it needs to
            # deactivated beforehand in order to apply the changes and activate
            # it again.
            self._add_action(NmProfile.ACTION_DEACTIVATE_FIRST)

        if self._iface.is_up and (
            (
                self._iface.type == InterfaceType.VLAN
                and self._iface.is_vlan_id_changed
            )
            or (
                self._iface.type == InterfaceType.VXLAN
                and self._iface.is_vxlan_id_changed
            )
        ):
            # NetworkManager does not allow to modify the vlan/vxlan id of an
            # existing VLAN/VXLAN. In order to support it, Nmstate is removing
            # the interface and creating it again.
            self._add_action(NmProfile.ACTION_DEACTIVATE_FIRST)

        if (
            self._iface.is_down
            and self._nm_dev
            and not self._nm_dev.get_managed()
        ):
            # In order to deactivate an unmanaged interface, we have to
            # activate the newly created profile to remove all kernel
            # settings.
            self._add_action(NmProfile.ACTION_ACTIVATE_FIRST)

    def _needs_veth_activation(self):
        return self._iface.type == InterfaceType.VETH or (
            self._iface.type == InterfaceType.ETHERNET and self._iface.is_peer
        )

    def prepare_config(self, save_to_disk, gen_conf_mode=False):
        if self._iface.is_absent or (
            self._iface.is_down
            and not gen_conf_mode
            and self._nm_dev
            and self._nm_dev.get_managed()
        ):
            return

        # Don't create new profile if original desire does not ask
        # anything besides state:up and not been marked as changed.
        # We don't need to do this once we support querying on-disk
        # configure
        if (
            not gen_conf_mode
            and self._nm_profile is None
            and not self._iface.is_changed
            and set(self._iface.original_desire_dict)
            <= set([Interface.STATE, Interface.NAME, Interface.TYPE])
        ):
            cur_nm_profile = self._get_first_nm_profile()
            if (
                cur_nm_profile
                and _is_memory_only(cur_nm_profile) != save_to_disk
            ):
                self._nm_profile = cur_nm_profile
                self._nm_simple_conn = cur_nm_profile
                return

        # TODO: Use applied config as base profile
        #       Or even better remove the base profile argument as top level
        #       of nmstate should provide full/merged configure.
        self._nm_simple_conn = create_new_nm_simple_conn(
            self._iface, self._nm_profile
        )

    def save_config(self, save_to_disk):
        self._check_sriov_support()
        self._check_unsupported_memory_only(save_to_disk)
        self._gen_actions()
        if not self.has_pending_change:
            return
        if self._iface.is_absent or (
            self._iface.is_down and self._nm_dev and self._nm_dev.get_managed()
        ):
            return
        # Don't create new profile if original desire does not ask
        # anything besides state:up and not been marked as changed.
        # We don't need to do this once we support querying on-disk
        if self._nm_simple_conn == self._nm_profile:
            cur_nm_profile = self._get_first_nm_profile()
            if (
                cur_nm_profile
                and _is_memory_only(cur_nm_profile) != save_to_disk
            ):
                self._nm_profile = cur_nm_profile
                return

        if self._nm_profile and not is_multiconnect_profile(self._nm_profile):
            ProfileUpdate(
                self._ctx,
                self._iface.name,
                self._iface.type,
                self._nm_simple_conn,
                self._nm_profile,
                save_to_disk,
            ).run()
        else:
            self._nm_profile = None
            ProfileAdd(
                self._ctx,
                self._iface.name,
                self._iface.type,
                self._nm_simple_conn,
                save_to_disk,
            ).run()

    def _check_unsupported_memory_only(self, save_to_disk):
        if (
            not save_to_disk
            and StrictVersion(self._ctx.client.get_version())
            < StrictVersion("1.28.0")
            and self._iface.type
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

    def _check_sriov_support(self):
        if (
            self._nm_dev
            and self._iface.type == InterfaceType.ETHERNET
            and self._iface.sriov_total_vfs
        ):
            if (
                not self._nm_dev.props.capabilities
                & NM.DeviceCapabilities.SRIOV
            ):
                raise NmstateNotSupportedError(
                    f"Interface {self._iface.name}  {self._iface.type} "
                    "does not support SR-IOV"
                )

    def _activate(self):
        if self._activated:
            return

        if not self._nm_profile:
            self._import_nm_profile_by_simple_conn()

        profile_activation = ProfileActivation(
            self._ctx,
            self._iface.name,
            self._iface.type,
            self._nm_profile,
            self._nm_dev,
        )
        if is_activated(self._nm_ac, self._nm_dev):
            # After ProfileUpdate(), the self._nm_profile is still hold
            # the old settings, DeviceReapply should use the
            # self._nm_simple_conn for updated settings.
            DeviceReapply(
                self._ctx,
                self._iface.name,
                self._iface.type,
                self._nm_dev,
                self._nm_simple_conn,
                profile_activation,
            ).run()
        else:
            profile_activation.run()
        self._activated = True

    def _deactivate(self):
        if self._deactivated:
            return
        self._nm_ac = (
            self._nm_dev.get_active_connection() if self._nm_dev else None
        )
        if self._nm_ac:
            ActiveConnectionDeactivate(
                self._ctx, self._iface.name, self._iface.type, self._nm_ac
            ).run()
        self._deactivated = True

    def _delete_profile(self):
        if self._profile_deleted:
            return
        if self._nm_profile:
            ProfileDelete(
                self._ctx, self._iface.name, self._iface.type, self._nm_profile
            ).run()

        self._profile_deleted = True

    def _delete_device(self):
        if self._device_deleted:
            return
        self.import_current()
        if self._nm_dev:
            DeviceDelete(
                self._ctx, self._iface.name, self._iface.type, self._nm_dev
            ).run()
        self._device_deleted = True

    def _add_action(self, action):
        self._actions.add(action)

    def has_action(self, action):
        return action in self._actions

    def do_action(self, action):
        if action in (
            NmProfile.ACTION_SRIOV_PF,
            NmProfile.ACTION_MODIFIED,
            NmProfile.ACTION_MODIFIED_OVS_PORT,
            NmProfile.ACTION_MODIFIED_OVS_IFACE,
            NmProfile.ACTION_ACTIVATE_FIRST,
            NmProfile.ACTION_TOP_CONTROLLER,
            NmProfile.ACTION_NEW_IFACES,
            NmProfile.ACTION_OTHER_CONTROLLER,
            NmProfile.ACTION_NEW_OVS_PORT,
            NmProfile.ACTION_NEW_OVS_IFACE,
            NmProfile.ACTION_NEW_VLAN,
            NmProfile.ACTION_NEW_VXLAN,
            NmProfile.ACTION_NEW_VETH,
        ):
            self._activate()
        elif (
            action
            in (
                NmProfile.ACTION_DELETE_PROFILE,
                NmProfile.ACTION_DELETE_DEVICE,
                NmProfile.ACTION_DEACTIVATE,
                NmProfile.ACTION_DEACTIVATE_FIRST,
            )
            and not self._deactivated
        ):
            self._deactivate()
        elif action == NmProfile.ACTION_DELETE_PROFILE:
            self._delete_profile()
        elif action == NmProfile.ACTION_DELETE_DEVICE:
            self._delete_device()
        else:
            raise NmstateInternalError(
                f"BUG: NmProfile.do_action() got unknown action {action}"
            )

    def _import_current_device(self):
        """
        NetworkManager takes some time to create the device for new veth
        interface peer. In order to avoid error on activating an existing
        interface without importing the device, Nmstate is retrying up to 5
        times.
        """
        for _ in range(IMPORT_NM_DEV_TIMEOUT):
            self._nm_dev = get_nm_dev(
                self._ctx, self._iface.name, self._iface.type
            )
            if self._nm_dev:
                break
            else:
                time.sleep(IMPORT_NM_DEV_RETRY_INTERNAL)
                self._ctx.refresh()

    def import_current(self):
        self._nm_dev = get_nm_dev(
            self._ctx, self._iface.name, self._iface.type
        )
        self._nm_ac = (
            self._nm_dev.get_active_connection() if self._nm_dev else None
        )
        self._nm_profile = (
            self._nm_ac.get_connection() if self._nm_ac else None
        )

    def _import_nm_profile_by_simple_conn(self):
        for nm_profile in self._ctx.client.get_connections():
            if nm_profile.get_uuid() == self._nm_simple_conn.get_uuid():
                self._nm_profile = nm_profile
                break

    def _get_first_nm_profile(self):
        for nm_profile in self._ctx.client.get_connections():
            if nm_profile.get_interface_name() == self._iface.name and (
                self._nm_iface_type is None
                or nm_profile.get_connection_type() == self._nm_iface_type
            ):
                return nm_profile
        return None

    def delete_other_profiles(self):
        """
        Remove all profiles except the NM.RemoteConnection used by current
        NM.ActiveConnection if interface is marked as UP
        """
        if not self.has_pending_change:
            return
        if self._iface.is_down:
            return
        self.import_current()
        for nm_profile in self._ctx.client.get_connections():
            if is_multiconnect_profile(nm_profile):
                continue
            if (
                nm_profile.get_interface_name() == self._iface.name
                and (
                    self._nm_iface_type is None
                    or nm_profile.get_connection_type() == self._nm_iface_type
                )
                and (
                    self._nm_simple_conn is None
                    or nm_profile.get_uuid() != self._nm_simple_conn.get_uuid()
                )
            ):
                ProfileDelete(
                    self._ctx, self._iface.name, self._iface.type, nm_profile
                ).run()


class ProfileAdd:
    def __init__(
        self, ctx, iface_name, iface_type, nm_simple_conn, save_to_disk
    ):
        self._ctx = ctx
        self._iface_name = iface_name
        self._iface_type = iface_type
        self._nm_simple_conn = nm_simple_conn
        self._save_to_disk = save_to_disk
        self._fallback_checker = None

    def run(self):
        nm_add_conn2_flags = NM.SettingsAddConnection2Flags
        flags = nm_add_conn2_flags.BLOCK_AUTOCONNECT
        if self._save_to_disk:
            flags |= nm_add_conn2_flags.TO_DISK
        else:
            flags |= nm_add_conn2_flags.IN_MEMORY

        action = (
            f"Add profile: {self._nm_simple_conn.get_uuid()}, "
            f"iface:{self._iface_name}, type:{self._iface_type}"
        )
        self._ctx.register_async(action, fast=True)

        user_data = action
        args = None
        ignore_out_result = False  # Don't fall back to old AddConnection()
        self._ctx.client.add_connection2(
            self._nm_simple_conn.to_dbus(NM.ConnectionSerializationFlags.ALL),
            flags,
            args,
            ignore_out_result,
            self._ctx.cancellable,
            self._add_profile_callback,
            user_data,
        )
        self._fallback_checker = GLib.timeout_source_new(
            FALLBACK_CHECKER_INTERNAL * 1000
        )
        self._fallback_checker.set_callback(
            self._fallback_checker_callback, action
        )
        self._fallback_checker.attach(self._ctx.context)

    def _add_profile_callback(self, nm_client, result, user_data):
        action = user_data
        if self._ctx.is_cancelled():
            return
        try:
            nm_profile = nm_client.add_connection2_finish(result)[0]
        except GLib.Error as e:
            if e.matches(Gio.io_error_quark(), Gio.IOErrorEnum.TIMED_OUT):
                logging.debug(
                    f"{action} timeout, using fallback method to "
                    "wait profile creation"
                )
                return
            else:
                self._ctx.fail(
                    NmstateLibnmError(f"{action} failed with error: {e}")
                )
                return
        except Exception as e:
            self._ctx.fail(
                NmstateLibnmError(f"{action} failed with error: {e}")
            )
            return

        if nm_profile is None:
            self._ctx.fail(
                NmstateLibnmError(
                    f"{action} failed with error: 'None returned from "
                    "NM.Client.add_connection2_finish()'"
                )
            )
        else:
            self._clean_up()
            self._ctx.finish_async(action)

    def _clean_up(self):
        if self._fallback_checker:
            self._fallback_checker.destroy()
            self._fallback_checker = None

    def _fallback_checker_callback(self, action):
        for nm_profile in self._ctx.client.get_connections():
            if nm_profile.get_uuid() == self._nm_simple_conn.get_uuid():
                self._clean_up()
                self._ctx.finish_async(action)
                return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE


class ProfileUpdate:
    def __init__(
        self,
        ctx,
        iface_name,
        iface_type,
        nm_simple_conn,
        nm_profile,
        save_to_disk,
    ):
        self._ctx = ctx
        self._iface_name = iface_name
        self._iface_type = iface_type
        self._nm_simple_conn = nm_simple_conn
        self._nm_profile = nm_profile
        self._save_to_disk = save_to_disk

    def run(self):
        flags = NM.SettingsUpdate2Flags.BLOCK_AUTOCONNECT
        if self._save_to_disk:
            flags |= NM.SettingsUpdate2Flags.TO_DISK
        else:
            flags |= NM.SettingsUpdate2Flags.IN_MEMORY
        action = (
            f"Update profile uuid:{self._nm_profile.get_uuid()} "
            f"iface:{self._iface_name} type:{self._iface_type}"
        )
        user_data = action
        args = None

        self._ctx.register_async(action, fast=True)
        self._nm_profile.update2(
            self._nm_simple_conn.to_dbus(NM.ConnectionSerializationFlags.ALL),
            flags,
            args,
            self._ctx.cancellable,
            self._update_profile_callback,
            user_data,
        )

    def _update_profile_callback(self, nm_profile, result, user_data):
        action = user_data
        if self._ctx.is_cancelled():
            return
        try:
            ret = nm_profile.update2_finish(result)
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


class ProfileDelete:
    def __init__(self, ctx, iface_name, iface_type, nm_profile):
        self._ctx = ctx
        self._iface_name = iface_name
        self._iface_type = iface_type
        self._nm_profile = nm_profile
        self._fallback_checker = None

    def run(self):
        action = (
            f"Delete profile: uuid:{self._nm_profile.get_uuid()} "
            f"id:{self._nm_profile.get_id()} "
            f"iface:{self._iface_name} type:{self._iface_type}"
        )
        user_data = action
        self._ctx.register_async(action, fast=True)
        self._nm_profile.delete_async(
            self._ctx.cancellable,
            self._delete_profile_callback,
            user_data,
        )
        self._fallback_checker = GLib.timeout_source_new(
            FALLBACK_CHECKER_INTERNAL * 1000
        )
        self._fallback_checker.set_callback(
            self._fallback_checker_callback, action
        )
        self._fallback_checker.attach(self._ctx.context)

    def _clean_up(self):
        if self._fallback_checker:
            self._fallback_checker.destroy()
            self._fallback_checker = None

    def _delete_profile_callback(self, nm_profile, result, user_data):
        action = user_data
        if self._ctx.is_cancelled():
            return
        try:
            success = nm_profile.delete_finish(result)
        except GLib.Error as e:
            if e.matches(Gio.io_error_quark(), Gio.IOErrorEnum.TIMED_OUT):
                logging.debug(
                    f"{action} timeout, using fallback method to "
                    "wait profile deletion"
                )
                return
            else:
                self._ctx.fail(
                    NmstateLibnmError(f"{action} failed with error: {e}")
                )
                return
        except Exception as e:
            self._ctx.fail(NmstateLibnmError(f"{action} failed: error={e}"))
            return

        if success:
            self._clean_up()
            self._ctx.finish_async(action)
        else:
            self._ctx.fail(
                NmstateLibnmError(
                    f"{action} failed: error='None returned from "
                    "delete_finish'"
                )
            )

    def _fallback_checker_callback(self, action):
        for nm_profile in self._ctx.client.get_connections():
            if nm_profile.get_uuid() == self._nm_profile.get_uuid():
                return GLib.SOURCE_CONTINUE
        self._clean_up()
        self._ctx.finish_async(action)
        return GLib.SOURCE_REMOVE


def _is_memory_only(nm_profile):
    if nm_profile:
        profile_flags = nm_profile.get_flags()
        return (
            NM.SettingsConnectionFlags.UNSAVED & profile_flags
            or NM.SettingsConnectionFlags.VOLATILE & profile_flags
        )
    return False
