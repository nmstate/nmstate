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
from operator import itemgetter

from libnmstate.appliers.ovs_bridge import is_ovs_running
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import Route
from libnmstate.schema import RouteRule

from . import bond as nm_bond
from . import bridge as nm_bridge
from . import connection as nm_connection
from . import device as nm_device
from . import ipv4 as nm_ipv4
from . import ipv6 as nm_ipv6
from . import ovs as nm_ovs
from . import translator as nm_translator
from . import wired as nm_wired
from . import user as nm_user
from . import vlan as nm_vlan
from . import vxlan as nm_vxlan
from . import team as nm_team
from . import dns as nm_dns
from .context import NmContext


class NetworkManagerPlugin:
    def __init__(self):
        self._ctx = NmContext()

    def unload(self):
        self._ctx.clean_up()

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
            capabilities.append(nm_ovs.CAPABILITY)
        if nm_team.has_team_capability(self.client):
            capabilities.append(nm_team.CAPABILITY)
        return capabilities

    def get_interfaces(self):
        info = []

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
            iface_info.update(nm_user.get_info(self.client, dev))
            iface_info.update(nm_vlan.get_info(dev))
            iface_info.update(nm_vxlan.get_info(dev))
            iface_info.update(nm_bridge.get_info(self.client, dev))
            iface_info.update(nm_team.get_info(dev))

            if nm_bond.is_bond_type_id(type_id):
                bondinfo = nm_bond.get_bond_info(dev)
                iface_info.update(_ifaceinfo_bond(bondinfo))
            elif nm_ovs.CAPABILITY in self.capabilities:
                if nm_ovs.is_ovs_bridge_type_id(type_id):
                    iface_info["bridge"] = nm_ovs.get_ovs_info(
                        self.client, dev, devices_info
                    )
                    iface_info = _remove_ovs_bridge_unsupported_entries(
                        iface_info
                    )
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
