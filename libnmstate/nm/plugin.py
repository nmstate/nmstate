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

from libnmstate.error import NmstateConflictError
from libnmstate.error import NmstateInternalError
from libnmstate.error import NmstateValueError
from libnmstate.schema import Interface

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
from .checkpoint import CheckPoint
from .checkpoint import get_checkpoints
from .ovs import NmOvsIfacePlugin
from .team import NmTeamIfacePlugin
from .context import NmContext


class NetworkManagerPlugin:
    def __init__(self):
        self._ctx = NmContext()
        self._iface_plugins = [
            NmOvsIfacePlugin(self.context),
            NmTeamIfacePlugin(self.context),
        ]
        self._capabilites = []
        self._quiting = False
        self._checkpoint = None
        for iface_plugins in self._iface_plugins:
            self._capabilites.extend(iface_plugins.capabilities)

    @property
    def client(self):
        return self._ctx.client if self._ctx else None

    @property
    def context(self):
        return self._ctx

    @property
    def capabilities(self):
        return self._capabilites

    def __del__(self):
        if self._checkpoint:
            self.destroy_checkpoint()
        self._checkpoint = None
        self._iface_plugins = []
        self._ctx = None

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
            iface_info.update(nm_user.get_info(self.context, dev))
            iface_info.update(nm_vlan.get_info(dev))
            iface_info.update(nm_vxlan.get_info(dev))
            iface_info.update(nm_bridge.get_info(self.context, dev))
            iface_info.update(nm_team.get_info(dev))

            if nm_bond.is_bond_type_id(type_id):
                bondinfo = nm_bond.get_bond_info(dev)
                iface_info.update(_ifaceinfo_bond(bondinfo))
            elif nm_ovs.CAPABILITY in self.capabilities:
                if nm_ovs.is_ovs_bridge_type_id(type_id):
                    iface_info["bridge"] = nm_ovs.get_ovs_info(
                        self.context, dev, devices_info
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
        return {}
        pass

    def get_route_rules(self):
        return {}

    def get_dns_client_config(self):
        return {}

    def get_checkpoint(self):
        return str(self._checkpoint.dbuspath) if self._checkpoint else None

    def _load_checkpoint(self, checkpoint_path):
        all_checkpoint_paths = get_checkpoints(self.client)
        if not all_checkpoint_paths or (
            checkpoint_path and checkpoint_path not in all_checkpoint_paths
        ):
            raise NmstateValueError(
                "Specified checkpoint {checkpoint_path} does not exists"
            )
        self._checkpoint = CheckPoint(
            self.client,
            dbuspath=checkpoint_path
            if checkpoint_path
            else all_checkpoint_paths[0],
        )

    def create_checkpoint(self, rollback_timeout=60, autodestroy=True):
        if self._checkpoint:
            raise NmstateConflictError("Only single checkpoint is allowed")
        self._checkpoint = CheckPoint(
            self.client, timeout=rollback_timeout, autodestroy=autodestroy
        )
        self._checkpoint.create()
        return self.get_checkpoint()

    def rollback_checkpoint(self, checkpoint_path=None):
        if checkpoint_path:
            self._load_checkpoint(checkpoint_path)
        if not self._checkpoint:
            raise NmstateInternalError("No checkpoint in NetworkManagerPlugin")
        self._checkpoint.rollback()
        self._checkpoint = None

    def destroy_checkpoint(self, checkpoint_path=None):
        if checkpoint_path:
            self._load_checkpoint(checkpoint_path)
        if not self._checkpoint:
            raise NmstateInternalError("No checkpoint in NetworkManagerPlugin")
        self._checkpoint.destroy()
        self._checkpoint = None


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
