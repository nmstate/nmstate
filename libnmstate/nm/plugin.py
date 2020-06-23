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

from libnmstate.error import NmstateValueError
from libnmstate.ifaces.ovs import is_ovs_running
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import Route
from libnmstate.schema import RouteRule
from libnmstate.plugin import NmstatePlugin

from . import bond as nm_bond
from . import bridge as nm_bridge
from . import connection as nm_connection
from . import device as nm_device
from . import ipv4 as nm_ipv4
from . import ipv6 as nm_ipv6
from . import lldp as nm_lldp
from . import ovs as nm_ovs
from . import translator as nm_translator
from . import wired as nm_wired
from . import user as nm_user
from . import vlan as nm_vlan
from . import vxlan as nm_vxlan
from . import team as nm_team
from . import dns as nm_dns
from . import applier as nm_applier
from .checkpoint import CheckPoint
from .checkpoint import get_checkpoints
from .common import NM
from .context import NmContext


class NetworkManagerPlugin(NmstatePlugin):
    def __init__(self):
        self._ctx = NmContext()
        self._checkpoint = None
        self._check_version_mismatch()

    @property
    def name(self):
        return "NetworkManager"

    def unload(self):
        if self._ctx:
            self._ctx.clean_up()
            self._ctx = None

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
        if nm_ovs.has_ovs_capability(self.client) and is_ovs_running():
            capabilities.append(NmstatePlugin.OVS_CAPABILITY)
        if nm_team.has_team_capability(self.client):
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
        capabilities = self.capabilities

        devices_info = [
            (dev, nm_device.get_device_common_info(dev))
            for dev in nm_device.list_devices(self.client)
        ]

        for dev, devinfo in devices_info:
            type_id = devinfo["type_id"]

            iface_info = nm_translator.Nm2Api.get_common_device_info(devinfo)

            act_con = nm_connection.get_device_active_connection(dev)
            iface_info[Interface.IPV4] = nm_ipv4.get_info(act_con)
            iface_info[Interface.IPV6] = nm_ipv6.get_info(act_con)
            iface_info.update(nm_wired.get_info(dev))
            iface_info.update(nm_user.get_info(self.context, dev))
            iface_info.update(nm_lldp.get_info(self.client, dev))
            iface_info.update(nm_vlan.get_info(dev))
            iface_info.update(nm_vxlan.get_info(dev))
            iface_info.update(nm_bridge.get_info(self.context, dev))
            iface_info.update(nm_team.get_info(dev))

            if nm_bond.is_bond_type_id(type_id):
                bondinfo = nm_bond.get_bond_info(dev)
                iface_info.update(_ifaceinfo_bond(bondinfo))
            elif NmstatePlugin.OVS_CAPABILITY in capabilities:
                if nm_ovs.is_ovs_bridge_type_id(type_id):
                    iface_info["bridge"] = nm_ovs.get_ovs_info(
                        self.context, dev, devices_info
                    )
                    iface_info = _remove_ovs_bridge_unsupported_entries(
                        iface_info
                    )
                elif nm_ovs.is_ovs_interface_type_id(type_id):
                    iface_info.update(nm_ovs.get_interface_info(act_con))
                elif nm_ovs.is_ovs_port_type_id(type_id):
                    continue

            info.append(iface_info)

        info.sort(key=itemgetter("name"))

        return info

    def get_routes(self):
        return {
            Route.RUNNING: (
                nm_ipv4.get_route_running(self.client)
                + nm_ipv6.get_route_running(self.client)
            ),
            Route.CONFIG: (
                nm_ipv4.get_route_config(self.client)
                + nm_ipv6.get_route_config(self.client)
            ),
        }

    def get_route_rules(self):
        return {
            RouteRule.CONFIG: (
                nm_ipv4.get_routing_rule_config(self.client)
                + nm_ipv6.get_routing_rule_config(self.client)
            )
        }

    def get_dns_client_config(self):
        return {
            DNS.RUNNING: nm_dns.get_running(self.client),
            DNS.CONFIG: nm_dns.get_config(
                nm_ipv4.acs_and_ip_profiles(self.client),
                nm_ipv6.acs_and_ip_profiles(self.client),
            ),
        }

    def refresh_content(self):
        self._ctx.refresh_content()

    def apply_changes(self, net_state, save_to_disk):
        nm_applier.apply_changes(self.context, net_state, save_to_disk)

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
            logging.warning("NetworkManager is not running")
        elif StrictVersion(nm_client_version) != StrictVersion(
            nm_utils_version
        ):
            logging.warning(
                "libnm version %s mismatches NetworkManager version %s",
                nm_utils_version,
                nm_client_version,
            )


def _ifaceinfo_bond(devinfo):
    # TODO: What about unmanaged devices?
    bondinfo = nm_translator.Nm2Api.get_bond_info(devinfo)
    if "link-aggregation" in bondinfo:
        return bondinfo
    return {}


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
