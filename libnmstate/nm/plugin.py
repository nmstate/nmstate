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

from collections import defaultdict
from distutils.version import StrictVersion
import logging
from operator import itemgetter

from libnmstate.error import NmstateDependencyError
from libnmstate.error import NmstateValueError
from libnmstate.ifaces.base_iface import BaseIface
from libnmstate.ifaces.ovs import is_ovs_running
from libnmstate.plugin import NmstatePlugin
from libnmstate.schema import Bond
from libnmstate.schema import DNS
from libnmstate.schema import Ethernet
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import LLDP
from libnmstate.schema import LinuxBridge
from libnmstate.schema import MacVlan
from libnmstate.schema import MacVtap
from libnmstate.schema import OVSBridge
from libnmstate.schema import OVSInterface
from libnmstate.schema import Route
from libnmstate.schema import Team
from libnmstate.schema import VLAN
from libnmstate.schema import VRF
from libnmstate.schema import VXLAN
from libnmstate.schema import Veth


from .bond import get_bond_config
from .bridge import get_linux_bridge_config
from .checkpoint import CheckPoint
from .checkpoint import get_checkpoints
from .common import NM
from .context import NmContext
from .device import get_device_common_info
from .device import list_devices
from .dns import get_running as get_dns_running
from .dns import get_dns_config_from_nm_profiles
from .infiniband import get_infiniband_config
from .ipv4 import get_ipv4_config
from .ipv6 import get_ipv6_config
from .lldp import get_lldp_config
from .macvlan import get_current_macvlan_type
from .macvlan import get_macvtap_config
from .ovs import get_interface_info as get_ovs_interface_info
from .ovs import get_ovs_bridge_config
from .ovs import get_ovs_bridge_info
from .ovs import get_ovs_patch_iface_config
from .ovs import has_ovs_capability
from .profile import get_basic_iface_info
from .profiles import NmProfiles
from .profiles import get_all_applied_configs
from .route import get_routes_from_nm_profiles
from .route import get_route_rules_from_nm_profiles
from .sriov import get_sriov_config
from .team import get_info as get_team_info
from .team import get_team_config
from .team import has_team_capability
from .translator import Nm2Api
from .user import get_user_config
from .veth import get_current_veth_type
from .veth import get_veth_config
from .vlan import get_vlan_config
from .vrf import get_vrf_config
from .vxlan import get_vxlan_config
from .wired import get_info as get_wired_info
from .wired import get_wired_config

_METADATA_PROFILE_PRIORITY = "_priority"
_METADATA_PROFILE_TIMESTAMP = "_timestamp"
_METADATA_NM_PROFILE = "_nm_profile"


class NetworkManagerPlugin(NmstatePlugin):
    def __init__(self):
        self._ctx = NmContext()
        self._checkpoint = None
        self._check_version_mismatch()
        self.__applied_configs = None

    @property
    def priority(self):
        return NmstatePlugin.DEFAULT_PRIORITY

    @property
    def name(self):
        return "NetworkManager"

    def unload(self):
        if self._ctx:
            self._ctx.clean_up()
            self._ctx = None

    @property
    def _applied_configs(self):
        if self.__applied_configs is None:
            self.__applied_configs = get_all_applied_configs(self.context)
        return self.__applied_configs

    @property
    def checkpoint(self):
        return self._checkpoint

    @property
    def client(self):
        return self._ctx.client if self._ctx else None

    @property
    def context(self):
        return self._ctx

    @property
    def capabilities(self):
        capabilities = []
        if has_ovs_capability(self.client) and is_ovs_running():
            capabilities.append(NmstatePlugin.OVS_CAPABILITY)
        if has_team_capability(self.client):
            capabilities.append(NmstatePlugin.TEAM_CAPABILITY)
        return capabilities

    @property
    def plugin_capabilities(self):
        return [
            NmstatePlugin.PLUGIN_CAPABILITY_IFACE,
            NmstatePlugin.PLUGIN_CAPABILITY_ROUTE,
            NmstatePlugin.PLUGIN_CAPABILITY_ROUTE_RULE,
            NmstatePlugin.PLUGIN_CAPABILITY_DNS,
        ]

    def get_interfaces(self):
        info = []

        applied_configs = self._applied_configs

        devices_info = [
            (dev, get_device_common_info(dev))
            for dev in list_devices(self.client)
        ]

        for dev, devinfo in devices_info:
            if not dev.get_managed():
                # Skip unmanaged interface
                continue

            iface_info = Nm2Api.get_common_device_info(devinfo)
            applied_config = applied_configs.get(iface_info[Interface.NAME])

            act_con = dev.get_active_connection()
            iface_info[Interface.IPV4] = get_ipv4_config(applied_config)
            iface_info[Interface.IPV6] = get_ipv6_config(applied_config)
            iface_info.update(get_wired_info(dev))
            iface_info.update(get_user_config(applied_config))
            iface_info[LLDP.CONFIG_SUBTREE] = get_lldp_config(
                applied_config, nmdev=dev
            )
            iface_info.update(get_team_info(dev))
            iface_info.update(get_infiniband_config(applied_config))
            iface_info.update(get_current_macvlan_type(applied_config))
            iface_info.update(get_current_veth_type(applied_config))

            if iface_info[Interface.TYPE] == InterfaceType.OVS_BRIDGE:
                iface_info.update(get_ovs_bridge_info(dev))
                iface_info = _remove_ovs_bridge_unsupported_entries(iface_info)
            elif iface_info[Interface.TYPE] == InterfaceType.OVS_INTERFACE:
                iface_info.update(get_ovs_interface_info(act_con))
            elif iface_info[Interface.TYPE] == InterfaceType.OVS_PORT:
                continue

            info.append(iface_info)

        info.sort(key=itemgetter("name"))

        return info

    def get_running_config_interfaces(self):
        iface_infos = self.get_interfaces()
        # Remove LLDP neighber information
        for iface_info in iface_infos:
            if LLDP.CONFIG_SUBTREE in iface_info:
                iface_info[LLDP.CONFIG_SUBTREE].pop(
                    LLDP.NEIGHBORS_SUBTREE, None
                )
        return iface_infos

    def _get_iface_info_from_saved_profiles(self):
        iface_infos = {}
        for nm_profile in self.client.get_connections():
            profile_flags = nm_profile.get_flags()
            if (
                NM.SettingsConnectionFlags.UNSAVED & profile_flags
                or NM.SettingsConnectionFlags.VOLATILE & profile_flags
            ):
                continue
            iface_info = get_basic_iface_info(nm_profile)
            iface_type = iface_info[Interface.TYPE]
            iface_name = iface_info[Interface.NAME]
            nm_conn_setting = nm_profile.get_setting_connection()
            if not nm_conn_setting:
                continue
            iface_info[
                _METADATA_PROFILE_PRIORITY
            ] = nm_conn_setting.get_autoconnect_priority()
            iface_info[
                _METADATA_PROFILE_TIMESTAMP
            ] = nm_conn_setting.get_timestamp()
            if not iface_name or iface_type == InterfaceType.UNKNOWN:
                # TODO: Support matching interface via MAC
                continue
            iface_index = iface_info[Interface.NAME]
            if iface_type in (
                InterfaceType.OVS_BRIDGE,
                InterfaceType.OVS_PORT,
            ):
                iface_index = f"{iface_type} {iface_name}"
            cur_iface_info = iface_infos.get(iface_index)
            should_save = False
            if not cur_iface_info:
                should_save = True
            else:
                cur_priority = cur_iface_info[_METADATA_PROFILE_PRIORITY]
                new_priority = iface_infos[_METADATA_PROFILE_PRIORITY]
                if new_priority > cur_priority:
                    should_save = True
                elif new_priority == cur_priority:
                    cur_timestamp = cur_iface_info[_METADATA_PROFILE_TIMESTAMP]
                    new_timestamp = iface_info[_METADATA_PROFILE_TIMESTAMP]
                    if new_timestamp > cur_timestamp:
                        should_save = True

            if should_save:
                iface_info[_METADATA_NM_PROFILE] = nm_profile
                iface_name = iface_info[Interface.NAME]
                iface_type = iface_info[Interface.TYPE]
                if iface_type in (
                    InterfaceType.OVS_BRIDGE,
                    InterfaceType.OVS_PORT,
                ):
                    iface_infos[f"{iface_type} {iface_name}"] = iface_info
                else:
                    iface_infos[iface_name] = iface_info
        return iface_infos

    def get_saved_config_interfaces(self):
        iface_infos = self._get_iface_info_from_saved_profiles()

        _fill_interface_specific_info(iface_infos)

        for iface_info in iface_infos.values():
            metadata_keys = [
                key for key in iface_info.keys() if key.startswith("_")
            ]
            for key in metadata_keys:
                iface_info.pop(key)

        return sorted(
            [
                iface_info
                for iface_info in iface_infos.values()
                if iface_info[Interface.TYPE] != InterfaceType.OVS_PORT
            ],
            key=itemgetter(Interface.NAME),
        )

    def get_routes(self):
        return {
            Route.CONFIG: get_routes_from_nm_profiles(self._applied_configs)
        }

    def get_saved_routes(self):
        iface_infos = self._get_iface_info_from_saved_profiles()
        return get_routes_from_nm_profiles(
            {
                iface_info[Interface.NAME]: iface_info[_METADATA_NM_PROFILE]
                for iface_info in iface_infos.values()
            }
        )

    def get_route_rules(self):
        """
        Nispor will provide running config of route rule from kernel.
        """
        return {}

    def get_saved_route_rules(self):
        iface_infos = self._get_iface_info_from_saved_profiles()
        return get_route_rules_from_nm_profiles(
            [
                iface_info[_METADATA_NM_PROFILE]
                for iface_info in iface_infos.values()
            ]
        )

    def get_dns_client_config(self):
        return {
            DNS.RUNNING: get_dns_running(self.client),
            DNS.CONFIG: get_dns_config_from_nm_profiles(self._applied_configs),
        }

    def get_saved_dns_client_config(self):
        iface_infos = self._get_iface_info_from_saved_profiles()
        return get_dns_config_from_nm_profiles(
            {
                iface_index: iface_info[_METADATA_NM_PROFILE]
                for iface_index, iface_info in iface_infos.items()
            }
        )

    def refresh_content(self):
        self.__applied_configs = None
        self._ctx.refresh_content()

    def apply_changes(self, net_state, save_to_disk):
        NmProfiles(self.context).apply_config(net_state, save_to_disk)

    def _load_checkpoint(self, checkpoint_path):
        if checkpoint_path:
            if self._checkpoint:
                # Old checkpoint might timeout, hence it's legal to load
                # another one.
                self._checkpoint.clean_up()
            candidates = get_checkpoints(self._ctx.client)
            if checkpoint_path in candidates:
                self._checkpoint = CheckPoint(
                    nm_context=self._ctx, dbuspath=checkpoint_path
                )
            else:
                raise NmstateValueError("No checkpoint specified or found")
        else:
            if not self._checkpoint:
                # Get latest one
                candidates = get_checkpoints(self._ctx.client)
                if candidates:
                    self._checkpoint = CheckPoint(
                        nm_context=self._ctx, dbuspath=candidates[0]
                    )
                else:
                    raise NmstateValueError("No checkpoint specified or found")

    def create_checkpoint(self, timeout=60):
        self._checkpoint = CheckPoint.create(self._ctx, timeout)
        return str(self._checkpoint)

    def rollback_checkpoint(self, checkpoint=None):
        self._load_checkpoint(checkpoint)
        self._checkpoint.rollback()
        self._checkpoint = None

    def destroy_checkpoint(self, checkpoint=None):
        self._load_checkpoint(checkpoint)
        self._checkpoint.destroy()
        self._checkpoint = None

    def _check_version_mismatch(self):
        nm_client_version = self._ctx.client.get_version()
        nm_utils_version = _nm_utils_decode_version()

        if nm_client_version is None:
            raise NmstateDependencyError(
                "NetworkManager daemon is not running which is required for "
                "NetworkManager plugin"
            )
        elif StrictVersion(nm_client_version) != StrictVersion(
            nm_utils_version
        ):
            logging.warning(
                "libnm version %s mismatches NetworkManager version %s",
                nm_utils_version,
                nm_client_version,
            )


def _remove_ovs_bridge_unsupported_entries(iface_info):
    """
    OVS bridges are not supporting several common interface key entries.
    These entries are removed explicitly.
    """
    iface_info.pop(Interface.IPV4, None)
    iface_info.pop(Interface.IPV6, None)
    iface_info.pop(Interface.MTU, None)

    return iface_info


def _nm_utils_decode_version():
    return f"{NM.MAJOR_VERSION}.{NM.MINOR_VERSION}.{NM.MICRO_VERSION}"


def _fill_interface_specific_info(iface_infos):
    for iface_index, iface_info in iface_infos.items():
        iface_name = iface_info[Interface.NAME]
        nm_profile = iface_info[_METADATA_NM_PROFILE]
        subordinate_nm_profiles = [
            tmp_iface_info[_METADATA_NM_PROFILE]
            for tmp_iface_info in iface_infos.values()
            if tmp_iface_info[BaseIface.CONTROLLER_METADATA] == iface_name
            and tmp_iface_info[BaseIface.CONTROLLER_TYPE_METADATA]
            == nm_profile.get_connection_type()
        ]
        iface_info[Interface.IPV4] = get_ipv4_config(
            nm_profile, full_config=True
        )
        iface_info[Interface.IPV6] = get_ipv6_config(
            nm_profile, full_config=True
        )
        iface_info.update(get_wired_config(nm_profile))
        iface_info.update(get_user_config(nm_profile))
        iface_info[LLDP.CONFIG_SUBTREE] = get_lldp_config(
            nm_profile, config_only=True
        )
        sriov_config = get_sriov_config(nm_profile)
        if sriov_config:
            iface_info[Ethernet.SRIOV_SUBTREE] = sriov_config

        iface_type = iface_info[Interface.TYPE]
        if iface_type == InterfaceType.TEAM:
            iface_info[Team.CONFIG_SUBTREE] = get_team_config(
                nm_profile, subordinate_nm_profiles
            )
        elif iface_type == InterfaceType.INFINIBAND:
            iface_info.update(get_infiniband_config(nm_profile))
        elif iface_type == InterfaceType.OVS_BRIDGE:
            _fill_ovs_bridge_iface_info(
                iface_info, iface_infos, subordinate_nm_profiles
            )
        elif iface_type == InterfaceType.OVS_INTERFACE:
            ovs_patch_info = get_ovs_patch_iface_config(nm_profile)
            if ovs_patch_info:
                iface_info[OVSInterface.PATCH_CONFIG_SUBTREE] = ovs_patch_info
        elif iface_type == InterfaceType.BOND:
            iface_info[Bond.CONFIG_SUBTREE] = get_bond_config(
                nm_profile, subordinate_nm_profiles
            )
        elif iface_type == InterfaceType.VLAN:
            iface_info[VLAN.CONFIG_SUBTREE] = get_vlan_config(nm_profile)
        elif iface_type == InterfaceType.VXLAN:
            iface_info[VXLAN.CONFIG_SUBTREE] = get_vxlan_config(nm_profile)
        elif iface_type == InterfaceType.LINUX_BRIDGE:
            iface_info[LinuxBridge.CONFIG_SUBTREE] = get_linux_bridge_config(
                nm_profile, subordinate_nm_profiles
            )
        elif iface_type == InterfaceType.MAC_VTAP:
            iface_info[MacVtap.CONFIG_SUBTREE] = get_macvtap_config(nm_profile)
        elif iface_type == InterfaceType.MAC_VLAN:
            iface_info[MacVlan.CONFIG_SUBTREE] = get_macvtap_config(nm_profile)
        elif iface_type == InterfaceType.VRF:
            iface_info[VRF.CONFIG_SUBTREE] = get_vrf_config(
                nm_profile, subordinate_nm_profiles
            )
        elif iface_type == InterfaceType.VETH:
            iface_info[Veth.CONFIG_SUBTREE] = get_veth_config(nm_profile)


def _fill_ovs_bridge_iface_info(iface_info, iface_infos, ovs_port_nm_profiles):
    nm_profile = iface_info[_METADATA_NM_PROFILE]
    ovs_iface_nm_profiles = defaultdict(list)
    for nm_ovs_port_profile in ovs_port_nm_profiles:
        ovs_port_name = nm_ovs_port_profile.get_interface_name()
        for tmp_iface_info in iface_infos.values():
            if (
                tmp_iface_info[BaseIface.CONTROLLER_METADATA] == ovs_port_name
                and tmp_iface_info[BaseIface.CONTROLLER_TYPE_METADATA]
                == InterfaceType.OVS_PORT
            ):
                ovs_iface_nm_profiles[ovs_port_name].append(
                    tmp_iface_info[_METADATA_NM_PROFILE]
                )

    iface_info[OVSBridge.CONFIG_SUBTREE] = get_ovs_bridge_config(
        nm_profile, ovs_port_nm_profiles, ovs_iface_nm_profiles
    )
    _remove_ovs_bridge_unsupported_entries(iface_info)
