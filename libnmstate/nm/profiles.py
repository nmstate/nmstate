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

from libnmstate.schema import InterfaceType

from .common import NM
from .device import is_externally_managed
from .device import list_devices
from .device import get_nm_dev
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

    def apply_config(self, net_state, save_to_disk):
        self._prepare_state_for_profiles(net_state)
        self._profiles = [
            NmProfile(self._ctx, iface, save_to_disk)
            for iface in net_state.ifaces.all_ifaces()
            if (iface.is_changed or iface.is_desired) and not iface.is_ignore
        ]

        for profile in self._profiles:
            profile.save_config()
        self._ctx.wait_all_finish()

        for action in NmProfile.ACTIONS:
            for profile in self._profiles:
                if profile.has_action(action):
                    profile.do_action(action)
            self._ctx.wait_all_finish()

        if save_to_disk:
            for profile in self._profiles:
                profile.delete_other_profiles()
            _delete_orphan_nm_ovs_port_profiles(self._ctx, net_state)

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
    applied_configs = {}
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
                    user_data=(iface_name, action, applied_configs, context),
                )
    context.wait_all_finish()
    return applied_configs


def _get_applied_config_callback(nm_dev, result, user_data):
    iface_name, action, applied_configs, context = user_data
    context.finish_async(action)
    try:
        remote_conn, _ = nm_dev.get_applied_connection_finish(result)
        # TODO: We should use both interface name and type as key below.
        applied_configs[nm_dev.get_iface()] = remote_conn
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


def _delete_orphan_nm_ovs_port_profiles(context, net_state):
    all_deleted_ovs_bridges = {}
    for iface in net_state.ifaces.all_user_space_ifaces:
        if iface.type == InterfaceType.OVS_BRIDGE and iface.is_absent:
            all_deleted_ovs_bridges[iface.name] = iface
    if not all_deleted_ovs_bridges:
        return
    for nm_profile in context.client.get_connections():
        if nm_profile.get_connection_type() != InterfaceType.OVS_PORT:
            continue
        conn_setting = nm_profile.get_setting_connection()
        if not conn_setting:
            continue
        ovs_port_name = nm_profile.get_interface_name()
        controller = conn_setting.get_master()
        ovs_br_iface = all_deleted_ovs_bridges.get(controller)
        need_delete = False
        if ovs_br_iface:
            if ovs_br_iface.is_absent:
                need_delete = True
            else:
                has_ovs_interface = False
                for port in ovs_br_iface.port:
                    ovs_iface = net_state.ifaces.all_kernel_ifaces.get(port)
                    if (
                        ovs_iface
                        and ovs_iface.controller == ovs_port_name
                        and ovs_iface.controller_type == InterfaceType.OVS_PORT
                    ):
                        has_ovs_interface = True
                        break
                if not has_ovs_interface:
                    need_delete = True
        if need_delete:
            ProfileDelete(
                context,
                ovs_port_name,
                InterfaceType.OVS_PORT,
                nm_profile,
            ).run()

    context.wait_all_finish()
