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
from distutils.version import StrictVersion
import logging
from operator import itemgetter

from libnmstate.error import NmstateDependencyError
from libnmstate.error import NmstateValueError
from libnmstate.ifaces.ovs import is_ovs_running
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import Route
from libnmstate.plugin import NmstatePlugin


from .checkpoint import CheckPoint
from .checkpoint import get_checkpoints
from .common import NM
from .context import NmContext
from .device import get_device_common_info
from .device import list_devices
from .dns import get_running as get_dns_running
from .dns import get_running_config as get_dns_running_config
from .infiniband import get_info as get_infiniband_info
from .ipv4 import get_info as get_ipv4_info
from .ipv6 import get_info as get_ipv6_info
from .lldp import get_info as get_lldp_info
from .macvlan import get_current_macvlan_type
from .ovs import get_interface_info as get_ovs_interface_info
from .ovs import get_ovs_bridge_info
from .ovs import has_ovs_capability
from .profiles import NmProfiles
from .profiles import get_all_applied_configs
from .route import get_running_config as get_route_running_config
from .team import get_info as get_team_info
from .team import has_team_capability
from .translator import Nm2Api
from .user import get_info as get_user_info
from .wired import get_info as get_wired_info


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
            iface_info[Interface.IPV4] = get_ipv4_info(act_con, applied_config)
            iface_info[Interface.IPV6] = get_ipv6_info(act_con, applied_config)
            iface_info.update(get_wired_info(dev))
            iface_info.update(get_user_info(self.context, dev))
            iface_info.update(get_lldp_info(self.client, dev))
            iface_info.update(get_team_info(dev))
            iface_info.update(get_infiniband_info(applied_config))
            iface_info.update(get_current_macvlan_type(applied_config))

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

    def get_routes(self):
        return {Route.CONFIG: get_route_running_config(self._applied_configs)}

    def get_route_rules(self):
        """
        Nispor will provide running config of route rule from kernel.
        """
        return {}

    def get_dns_client_config(self):
        return {
            DNS.RUNNING: get_dns_running(self.client),
            DNS.CONFIG: get_dns_running_config(self._applied_configs),
        }

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
