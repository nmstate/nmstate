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

from libnmstate.schema import Ethernet
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState

from .base_iface import BaseIface


BNXT_DRIVER_PHYS_PORT_PREFIX = "p"
MULTIPORT_PCI_DEVICE_PREFIX = "n"
IS_GENERATED_VF_METADATA = "_is_generated_vf"


class EthernetIface(BaseIface):
    def __init__(self, info, save_to_disk=True):
        super().__init__(info, save_to_disk)
        self._is_peer = False

    def merge(self, other):
        super().merge(other)
        EthernetIface._canonicalize(self._info)

    @staticmethod
    def _canonicalize(state):
        """
        * AUTO_NEGOTIATION: true: Remove speed and duplex
        * AUTO_NEGOTIATION: false: copy speed/duplex from other if not defined
        """
        if state.get(Ethernet.CONFIG_SUBTREE, {}).get(
            Ethernet.AUTO_NEGOTIATION
        ):
            state.get(Ethernet.CONFIG_SUBTREE, {}).pop(Ethernet.SPEED, None)
            state.get(Ethernet.CONFIG_SUBTREE, {}).pop(Ethernet.DUPLEX, None)

    def state_for_verify(self):
        state = super().state_for_verify()
        _capitalize_sriov_vf_mac(state)
        EthernetIface._canonicalize(state)
        return state

    @property
    def sriov_total_vfs(self):
        return (
            self.raw.get(Ethernet.CONFIG_SUBTREE, {})
            .get(Ethernet.SRIOV_SUBTREE, {})
            .get(Ethernet.SRIOV.TOTAL_VFS, 0)
        )

    @property
    def sriov_vfs(self):
        return (
            self.raw.get(Ethernet.CONFIG_SUBTREE, {})
            .get(Ethernet.SRIOV_SUBTREE, {})
            .get(Ethernet.SRIOV.VFS_SUBTREE, [])
        )

    @property
    def is_peer(self):
        return self._is_peer

    @property
    def is_sriov(self):
        return self.raw.get(Ethernet.CONFIG_SUBTREE, {}).get(
            Ethernet.SRIOV_SUBTREE
        )

    @property
    def speed(self):
        return self.raw.get(Ethernet.CONFIG_SUBTREE, {}).get(Ethernet.SPEED)

    @property
    def auto_negotiation(self):
        return self.raw.get(Ethernet.CONFIG_SUBTREE, {}).get(
            Ethernet.AUTO_NEGOTIATION
        )

    @property
    def duplex(self):
        return self.raw.get(Ethernet.CONFIG_SUBTREE, {}).get(Ethernet.DUPLEX)

    def create_sriov_vf_ifaces(self):
        # Currently there is not a way to see the relation between a SR-IOV PF
        # and its VFs. Broadcom BCM57416 follows a different name pattern for
        # PF and VF, therefore it needs to be parsed if present.
        #
        # PF name: ens2f0np0
        # VF name: ens2f0v0
        #
        # The different name pattern is due to:
        #  1. The `n` is for `multi-port PCI device` support.
        #  2. The `p*` is `phys_port_name` provided by the BCM driver
        #  `bnxt_en`.
        #
        # If the NIC is following the standard pattern "pfname+v+vfid", this
        # split will not touch it and the vf_pattern will be the PF name.
        # Ref: https://bugzilla.redhat.com/1959679
        vf_pattern = self.name
        multiport_pattern = (
            MULTIPORT_PCI_DEVICE_PREFIX + BNXT_DRIVER_PHYS_PORT_PREFIX
        )
        if len(self.name.split(multiport_pattern)) == 2:
            vf_pattern = self.name.split(multiport_pattern)[0]

        vf_ifaces = [
            EthernetIface(
                {
                    # According to manpage of systemd.net-naming-scheme(7),
                    # SRIOV VF interface will have v{slot} in device name.
                    # Currently, nmstate has no intention to support
                    # user-defined udev rule on SRIOV interface naming policy.
                    Interface.NAME: f"{vf_pattern}v{i}",
                    Interface.TYPE: InterfaceType.ETHERNET,
                    # VF will be in DOWN state initialy
                    Interface.STATE: InterfaceState.DOWN,
                }
            )
            for i in range(0, self.sriov_total_vfs)
        ]
        # The generated vf metadata cannot be part of the original dict.
        for vf in vf_ifaces:
            vf._info[IS_GENERATED_VF_METADATA] = True

        return vf_ifaces

    def remove_vfs_entry_when_total_vfs_decreased(self):
        vfs_count = len(
            self._info[Ethernet.CONFIG_SUBTREE]
            .get(Ethernet.SRIOV_SUBTREE, {})
            .get(Ethernet.SRIOV.VFS_SUBTREE, [])
        )
        if vfs_count > self.sriov_total_vfs:
            [
                self._info[Ethernet.CONFIG_SUBTREE][Ethernet.SRIOV_SUBTREE][
                    Ethernet.SRIOV.VFS_SUBTREE
                ].pop()
                for _ in range(self.sriov_total_vfs, vfs_count)
            ]

    def get_delete_vf_interface_names(self, old_sriov_total_vfs):
        return [
            f"{self.name}v{i}"
            for i in range(self.sriov_total_vfs, old_sriov_total_vfs)
        ]

    def check_total_vfs_matches_vf_list(self, total_vfs):
        return total_vfs == len(self.sriov_vfs)


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
