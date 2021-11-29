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
from libnmstate.validator import validate_boolean
from libnmstate.validator import validate_integer
from libnmstate.validator import validate_string

from .base_iface import BaseIface

BNXT_DRIVER_PHYS_PORT_PREFIX = "p"
MULTIPORT_PCI_DEVICE_PREFIX = "n"

DUPLEX_VALID_VALUES = ["full", "half"]


class EthernetIface(BaseIface):
    VF_IFACE_NAME_METADATA = "_vf_iface_name"

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

    def pre_edit_validation_and_cleanup(self):
        self._validate_ethernet_properties()
        super().pre_edit_validation_and_cleanup()

    def _validate_ethernet_properties(self):
        validate_boolean(self.auto_negotiation, Ethernet.AUTO_NEGOTIATION)
        validate_string(self.duplex, Ethernet.DUPLEX, DUPLEX_VALID_VALUES)
        validate_integer(self.speed, Ethernet.SPEED, minimum=0)
        validate_integer(
            self.sriov_total_vfs, Ethernet.SRIOV.TOTAL_VFS, minimum=0
        )
        for vf in self.sriov_vfs:
            validate_integer(
                vf.get(Ethernet.SRIOV.VFS.ID), Ethernet.SRIOV.VFS.ID, minimum=0
            )
            validate_string(
                vf.get(Ethernet.SRIOV.VFS.MAC_ADDRESS),
                Ethernet.SRIOV.VFS.MAC_ADDRESS,
                pattern="^([a-fA-F0-9]{2}:){3,31}[a-fA-F0-9]{2}$",
            )
            validate_boolean(
                vf.get(Ethernet.SRIOV.VFS.SPOOF_CHECK),
                Ethernet.SRIOV.VFS.SPOOF_CHECK,
            )
            validate_boolean(
                vf.get(Ethernet.SRIOV.VFS.TRUST), Ethernet.SRIOV.VFS.TRUST
            )
            validate_integer(
                vf.get(Ethernet.SRIOV.VFS.MAX_TX_RATE),
                Ethernet.SRIOV.VFS.MAX_TX_RATE,
                minimum=0,
            )
            validate_integer(
                vf.get(Ethernet.SRIOV.VFS.MIN_TX_RATE),
                Ethernet.SRIOV.VFS.MIN_TX_RATE,
                minimum=0,
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
