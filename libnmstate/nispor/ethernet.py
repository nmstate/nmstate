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
from libnmstate.schema import InterfaceType

from .base_iface import NisporPluginBaseIface


class NisporPluginEthernetIface(NisporPluginBaseIface):
    @property
    def type(self):
        return InterfaceType.ETHERNET

    def to_dict(self):
        info = super().to_dict()
        if self.np_iface.sr_iov:
            vf_infos = []
            for vf in self.np_iface.sr_iov.vfs:
                vf_infos.append(
                    {
                        Ethernet.SRIOV.VFS.ID: vf.vf_id,
                        Ethernet.SRIOV.VFS.MAC_ADDRESS: vf.mac,
                        Ethernet.SRIOV.VFS.SPOOF_CHECK: vf.spoof_check,
                        Ethernet.SRIOV.VFS.TRUST: vf.trust,
                        Ethernet.SRIOV.VFS.MIN_TX_RATE: vf.min_tx_rate,
                        Ethernet.SRIOV.VFS.MAX_TX_RATE: vf.max_tx_rate,
                    }
                )

            sriov_info = {
                Ethernet.SRIOV.TOTAL_VFS: len(self.np_iface.sr_iov.vfs),
                Ethernet.SRIOV.VFS_SUBTREE: vf_infos,
            }
            info[Ethernet.CONFIG_SUBTREE] = {
                Ethernet.SRIOV_SUBTREE: sriov_info
            }

        return info
