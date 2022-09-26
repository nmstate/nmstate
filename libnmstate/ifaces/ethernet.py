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

from libnmstate.error import NmstateVerificationError
from libnmstate.schema import Ethernet
from libnmstate.schema import InterfaceType

from .base_iface import BaseIface


BNXT_DRIVER_PHYS_PORT_PREFIX = "p"
MULTIPORT_PCI_DEVICE_PREFIX = "n"


class EthernetIface(BaseIface):
    VF_IFACE_NAME_METADATA = "_vf_iface_name"

    def __init__(self, info, save_to_disk=True):
        super().__init__(info, save_to_disk)
        self._is_peer = False

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

    def to_dict(self):
        info = super().to_dict()
        for vf_info in (
            info.get(Ethernet.CONFIG_SUBTREE, {})
            .get(Ethernet.SRIOV_SUBTREE, {})
            .get(Ethernet.SRIOV.VFS_SUBTREE, [])
        ):
            vf_info.pop(EthernetIface.VF_IFACE_NAME_METADATA, None)
        return info


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


def verify_sriov_vf(iface, cur_ifaces):
    """
    Checking whether VF interface is been created
    """
    if not (
        iface.is_up
        and (iface.is_desired or iface.is_changed)
        and iface.type == InterfaceType.ETHERNET
        and iface.sriov_total_vfs > 0
        and iface.original_dict.get(Ethernet.CONFIG_SUBTREE, {}).get(
            Ethernet.SRIOV_SUBTREE
        )
    ):
        return
    cur_iface = cur_ifaces.get_iface(iface.name, iface.type)
    if not cur_iface:
        # Other verification will raise proper exception when current interface
        # is missing
        return
    cur_vf_names = []
    for sriov_vf in cur_iface.sriov_vfs:
        if sriov_vf.get(EthernetIface.VF_IFACE_NAME_METADATA):
            cur_vf_names.append(sriov_vf[EthernetIface.VF_IFACE_NAME_METADATA])

    if len(cur_vf_names) != iface.sriov_total_vfs:
        raise NmstateVerificationError(
            f"Found VF ports count does not match desired "
            f"{iface.sriov_total_vfs}, current is: {','.join(cur_vf_names)}"
        )
    for cur_vf_name in cur_vf_names:
        if not cur_ifaces.get_iface(cur_vf_name, InterfaceType.ETHERNET):
            raise NmstateVerificationError(
                f"VF interface {cur_vf_name} of PF {iface.name} not found"
            )
