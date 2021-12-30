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
#   * Actions required the knownldege of multiple NmProfile

import logging
from operator import attrgetter

from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType

from .common import NM
from .device import is_externally_managed
from .device import list_devices
from .device import get_iface_type
from .device import get_nm_dev
from .device import is_kernel_iface
from .dns import get_dns_config_iface_names
from .ipv4 import acs_and_ip_profiles as acs_and_ip4_profiles
from .ipv6 import acs_and_ip_profiles as acs_and_ip6_profiles
from .ovs import create_iface_for_nm_ovs_port
from .profile import NmProfile
from .profile import ProfileDelete
from .veth import create_iface_for_nm_veth_peer
from .veth import is_nm_veth_supported


class NmProfiles:
    def __init__(self, context):
        self._ctx = context

    def generate_config_strings(self, net_state):
        _append_nm_ovs_port_iface(net_state)
        all_profiles = []
        for iface in net_state.ifaces.all_ifaces():
            if iface.is_up:
                profile = NmProfile(self._ctx, iface)
                profile.prepare_config(save_to_disk=False, gen_conf_mode=True)
                all_profiles.append(profile)

        return [
            (profile.config_file_name, profile.to_key_file_string())
            for profile in all_profiles
        ]

    def apply_config(self, net_state, save_to_disk):
        self._prepare_state_for_profiles(net_state)
        # The activation order on bridge/bond ports determins their controler's
        # MAC address. The default NetworkManager is using alphabet order on
        # boot. So we should to the same here.
        all_profiles = [
            NmProfile(self._ctx, iface)
            for iface in sorted(
                list(net_state.ifaces.all_ifaces()), key=attrgetter("name")
            )
        ]

        for profile in all_profiles:
            profile.import_current()
            profile.prepare_config(save_to_disk, gen_conf_mode=False)
        _use_uuid_as_controller_and_parent(all_profiles)

        changed_ovs_bridges_and_ifaces = {}
        for profile in all_profiles:
            if (
                profile.iface.type
                in (InterfaceType.OVS_BRIDGE, InterfaceType.OVS_INTERFACE)
                and profile.has_pending_change
            ):
                changed_ovs_bridges_and_ifaces[profile.uuid] = profile

        for profile in all_profiles:
            if profile.has_pending_change:
                profile.save_config(save_to_disk)
        self._ctx.wait_all_finish()

        for action in NmProfile.ACTIONS:
            for profile in all_profiles:
                if profile.has_action(action):
                    profile.do_action(action)
            self._ctx.wait_all_finish()

        if save_to_disk:
            for profile in all_profiles:
                if profile.has_pending_change:
                    profile.delete_other_profiles()

            _delete_orphan_nm_ovs_port_profiles(
                self._ctx, changed_ovs_bridges_and_ifaces, net_state
            )

    def _prepare_state_for_profiles(self, net_state):
        _preapply_dns_fix_for_profiles(self._ctx, net_state)
        _mark_nm_external_subordinate_changed(self._ctx, net_state)
        _mark_mode_changed_bond_child_interface_as_changed(net_state)
        _append_nm_ovs_port_iface(net_state)
        _consider_not_supported_veth_as_ethernet(net_state)
        _create_veth_iface_for_missing_peers(net_state)


def _append_nm_ovs_port_iface(net_state):
    """
    In NM OVS, each OVS internal/system/ interface should be
    subordinate of NM OVS port profile which is port of the OVS bridge
    profile.
    We need to create/delete this NM OVS port profile accordingly.
    """
    nm_ovs_port_ifaces = {}

    for iface in net_state.ifaces.all_kernel_ifaces.values():
        if iface.controller_type == InterfaceType.OVS_BRIDGE:
            nm_ovs_port_iface = create_iface_for_nm_ovs_port(iface)
            iface.set_controller(
                nm_ovs_port_iface.name, InterfaceType.OVS_PORT
            )
            if iface.is_desired or iface.is_changed:
                nm_ovs_port_iface.mark_as_changed()
            nm_ovs_port_ifaces[nm_ovs_port_iface.name] = nm_ovs_port_iface

    net_state.ifaces.add_ifaces(nm_ovs_port_ifaces.values())


def get_all_applied_configs(context):
    """
    Return two dictionaries.
    First one for kernel interface with interface name as key.
    Second one for user space interface with interface name and type as key.
    """
    kernel_nic_applied_configs = {}
    userspace_nic_applid_configs = {}
    for nm_dev in list_devices(context.client):
        if (
            nm_dev.get_state()
            in (
                NM.DeviceState.ACTIVATED,
                NM.DeviceState.IP_CONFIG,
            )
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
                    callback=_get_applied_config_callback,
                    user_data=(
                        iface_name,
                        action,
                        kernel_nic_applied_configs,
                        userspace_nic_applid_configs,
                        context,
                    ),
                )
    context.wait_all_finish()
    return kernel_nic_applied_configs, userspace_nic_applid_configs


def _get_applied_config_callback(nm_dev, result, user_data):
    (
        iface_name,
        action,
        kernel_nic_applied_configs,
        userspace_nic_applid_configs,
        context,
    ) = user_data
    context.finish_async(action)
    try:
        iface_name = nm_dev.get_iface()
        remote_conn, _ = nm_dev.get_applied_connection_finish(result)
        if is_kernel_iface(nm_dev):
            kernel_nic_applied_configs[iface_name] = remote_conn
        else:
            iface_type = get_iface_type(nm_dev)
            userspace_nic_applid_configs[
                f"{iface_name}{iface_type}"
            ] = remote_conn
    except Exception as e:
        logging.warning(
            "Failed to retrieve applied config for device "
            f"{iface_name}: {e}"
        )


def _preapply_dns_fix_for_profiles(context, net_state):
    """
    * When DNS configuration does not changed and old interface hold DNS
      configuration is not included in `ifaces_desired_state`, preserve
      the old DNS configure by removing DNS metadata from
      `ifaces_desired_state`.
    * When DNS configuration changed, include old interface which is holding
      DNS configuration, so it's DNS configure could be removed.
    """
    cur_dns_iface_names = get_dns_config_iface_names(
        acs_and_ip4_profiles(context.client),
        acs_and_ip6_profiles(context.client),
    )

    # Whether to mark interface as changed which is used for holding old DNS
    # configurations
    remove_existing_dns_config = False
    # Whether to preserve old DNS config by DNS metadata to be removed from
    # desired state
    preserve_old_dns_config = False
    if net_state.dns.config == net_state.dns.current_config:
        for cur_dns_iface_name in cur_dns_iface_names:
            iface = net_state.ifaces.all_kernel_ifaces[cur_dns_iface_name]
            if iface.is_changed or iface.is_desired:
                remove_existing_dns_config = True
        if not remove_existing_dns_config:
            preserve_old_dns_config = True
    else:
        remove_existing_dns_config = True

    if remove_existing_dns_config:
        for cur_dns_iface_name in cur_dns_iface_names:
            iface = net_state.ifaces.all_kernel_ifaces[cur_dns_iface_name]
            iface.mark_as_changed()

    if preserve_old_dns_config:
        for iface in net_state.ifaces.all_kernel_ifaces.values():
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
    for iface in net_state.ifaces.all_ifaces():
        if (
            iface.is_controller
            and iface.is_up
            and (iface.is_changed or iface.is_desired)
        ):
            for subordinate in iface.port:
                port_iface = net_state.ifaces.all_kernel_ifaces.get(
                    subordinate
                )
                if port_iface:
                    nmdev = get_nm_dev(context, subordinate, port_iface.type)
                    if nmdev:
                        if is_externally_managed(nmdev):
                            port_iface.mark_as_changed()


def _mark_mode_changed_bond_child_interface_as_changed(net_state):
    """
    When bond mode changed, due to NetworkManager bug
    https://bugzilla.redhat.com/show_bug.cgi?id=1881318
    the bond child will be deactivated.
    This is workaround would be manually activate the childs.
    """
    for iface in net_state.ifaces.all_kernel_ifaces.values():
        if not iface.parent:
            continue
        parent_iface = net_state.ifaces.get_iface(
            iface.parent, InterfaceType.BOND
        )
        if (
            parent_iface
            and parent_iface.is_up
            and parent_iface.is_bond_mode_changed
        ):
            iface.mark_as_changed()


def _consider_not_supported_veth_as_ethernet(net_state):
    for iface in net_state.ifaces.all_kernel_ifaces.values():
        if iface.type == InterfaceType.VETH and not is_nm_veth_supported():
            iface.raw[InterfaceType.KEY] = InterfaceType.ETHERNET


def _create_veth_iface_for_missing_peers(net_state):
    new_peers = []
    for iface in net_state.ifaces.all_kernel_ifaces.values():
        # Nmstate should check if there is a current interface with the same
        # name and type veth or ethernet.
        if (
            iface.type == InterfaceType.VETH
            and iface.is_up
            and iface.is_desired
            and not net_state.ifaces.get_cur_iface(iface.name, iface.type)
            and not net_state.ifaces.get_cur_iface(iface.peer, iface.type)
            and not net_state.ifaces.all_kernel_ifaces.get(iface.peer)
        ):
            peer = create_iface_for_nm_veth_peer(iface)
            peer.mark_as_peer()
            if not net_state.ifaces.get_cur_iface(
                iface.name, InterfaceType.ETHERNET
            ):
                peer.mark_as_changed()
            new_peers.append(peer)

    net_state.ifaces.add_ifaces(new_peers)


def _delete_orphan_nm_ovs_port_profiles(
    context, changed_ovs_bridges_and_ifaces, net_state
):
    """
    * When OVS port's master is gone, remove it.
    * When OVS port's child is empty, remove it.
    """
    if not changed_ovs_bridges_and_ifaces:
        return

    ovs_bridge_named_to_profile = {
        profile.iface.name: profile
        for profile in changed_ovs_bridges_and_ifaces.values()
    }

    for nm_profile in context.client.get_connections():
        if nm_profile.get_connection_type() != InterfaceType.OVS_PORT:
            continue
        conn_setting = nm_profile.get_setting_connection()
        if not conn_setting:
            continue
        ovs_port_name = nm_profile.get_interface_name()
        controller = conn_setting.get_master()
        ovs_bridge_profile = changed_ovs_bridges_and_ifaces.get(
            controller, ovs_bridge_named_to_profile.get(controller)
        )

        # When OVS bridge is deleted, so its ovs ports.
        if ovs_bridge_profile:
            if ovs_bridge_profile.iface.is_absent:
                ProfileDelete(
                    context,
                    ovs_port_name,
                    InterfaceType.OVS_PORT,
                    nm_profile,
                ).run()
                continue
            # When OVS port has no child, delete it
            ovs_bridge_iface = ovs_bridge_profile.iface
            if not _nm_ovs_port_has_child_or_is_ignored(
                nm_profile, ovs_bridge_iface, net_state
            ):
                ProfileDelete(
                    context,
                    ovs_port_name,
                    InterfaceType.OVS_PORT,
                    nm_profile,
                ).run()
                continue

    context.wait_all_finish()


def _use_uuid_as_controller_and_parent(nm_profiles):
    iface_to_uuid = {}
    kernel_iface_to_uuid = {}

    for nm_profile in nm_profiles:
        iface_to_uuid[
            f"{nm_profile.iface.name}/{nm_profile.iface.type}"
        ] = nm_profile.uuid
        if not nm_profile.iface.is_user_space_only:
            kernel_iface_to_uuid[nm_profile.iface.name] = nm_profile.uuid

    for nm_profile in nm_profiles:
        iface = nm_profile.iface
        if not iface.is_up:
            continue
        if (
            iface.controller
            and (iface.is_changed or iface.is_desired)
            and not iface.is_ignore
        ):
            uuid = iface_to_uuid.get(
                f"{iface.controller}/{iface.controller_type}"
            )
            if uuid:
                nm_profile.update_controller(uuid)
        if iface.need_parent:
            uuid = kernel_iface_to_uuid.get(iface.parent)
            if uuid:
                nm_profile.update_parent(uuid)


def _nm_ovs_port_has_child_or_is_ignored(
    nm_profile, ovs_bridge_iface, net_state
):
    ovs_port_uuid = nm_profile.get_uuid()
    ovs_port_name = nm_profile.get_interface_name()
    for ovs_iface_name in ovs_bridge_iface.port:
        ovs_iface = net_state.ifaces.all_kernel_ifaces.get(ovs_iface_name)
        if (
            ovs_iface
            and ovs_iface.controller in (ovs_port_name, ovs_port_uuid)
            and ovs_iface.controller_type == InterfaceType.OVS_PORT
        ):
            return True
    # Gather the ovs bridge interface from the current state in order to check
    # if any port is ignored in the original desired state.
    current_ovs_bridge = net_state.ifaces.get_cur_iface(
        ovs_bridge_iface.name, InterfaceType.OVS_BRIDGE
    )
    if current_ovs_bridge:
        for port_name in current_ovs_bridge.port:
            port_iface = net_state.ifaces.all_kernel_ifaces.get(port_name)
            if (
                port_iface
                and port_iface.original_desire_dict.get(Interface.STATE)
                == InterfaceState.IGNORE
            ):
                return True
    return False
