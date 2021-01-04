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

from libnmstate.schema import Ethernet
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState

from .base_iface import BaseIface


class EthernetIface(BaseIface):
    def merge(self, other):
        """
        Given the other_state, update the ethernet interfaces state base on
        the other_state ethernet interfaces data.
        Usually the other_state represents the current state.
        If auto-negotiation, speed and duplex settings are not provided,
        but exist in the current state, they need to be set to None
        to not override them with the values from the current settings
        since the current settings are read from the device state and not
        from the actual configuration.  This makes it possible to distinguish
        whether a user specified these values in the later configuration step.
        """
        eth_conf = self._info.setdefault(Ethernet.CONFIG_SUBTREE, {})
        eth_conf.setdefault(Ethernet.AUTO_NEGOTIATION, None)
        eth_conf.setdefault(Ethernet.SPEED, None)
        eth_conf.setdefault(Ethernet.DUPLEX, None)
        super().merge(other)

    def state_for_verify(self):
        state = super().state_for_verify()
        _capitalize_sriov_vf_mac(state)
        return state

    @property
    def sriov_total_vfs(self):
        return (
            self.raw.get(Ethernet.CONFIG_SUBTREE, {})
            .get(Ethernet.SRIOV_SUBTREE, {})
            .get(Ethernet.SRIOV.TOTAL_VFS, 0)
        )

    def create_sriov_vf_ifaces(self):
        return [
            EthernetIface(
                {
                    # According to manpage of systemd.net-naming-scheme(7),
                    # SRIOV VF interface will have v{slot} in device name.
                    # Currently, nmstate has no intention to support
                    # user-defined udev rule on SRIOV interface naming policy.
                    Interface.NAME: f"{self.name}v{i}",
                    Interface.TYPE: InterfaceType.ETHERNET,
                    # VF will be in DOWN state initialy.
                    Interface.STATE: InterfaceState.DOWN,
                }
            )
            for i in range(0, self.sriov_total_vfs)
        ]


def _capitalize_sriov_vf_mac(state):
    vfs = (
        state.get(Ethernet.CONFIG_SUBTREE, {})
        .get(Ethernet.SRIOV_SUBTREE, {})
        .get(Ethernet.SRIOV.VFS_SUBTREE, [])
    )
    for vf in vfs:
        vf_mac = vf.get(Ethernet.SRIOV.VFS.MAC_ADDRESS)
        if vf_mac:
            vf[Ethernet.SRIOV.VFS.MAC_ADDRESS] = vf_mac.upper()
