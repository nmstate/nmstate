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

from copy import deepcopy

from libnmstate.schema import Ethtool

from libnmstate.ifaces.base_iface import BaseIface
from ..testlib.ifacelib import gen_foo_iface_info


class TestIfaceEthtool:
    def test_pause_canonicalize_remove_rx_tx(self):
        des_info = gen_foo_iface_info()
        des_info.update(
            {
                Ethtool.CONFIG_SUBTREE: {
                    Ethtool.Pause.CONFIG_SUBTREE: {
                        Ethtool.Pause.AUTO_NEGOTIATION: True,
                        Ethtool.Pause.RX: True,
                        Ethtool.Pause.TX: True,
                    }
                }
            }
        )
        iface = BaseIface(des_info)
        iface.mark_as_desired()
        iface.pre_edit_validation_and_cleanup()

        assert iface.ethtool.pause.autoneg is True
        assert iface.ethtool.pause.rx is None
        assert iface.ethtool.pause.tx is None

    def test_pause_match_ignore_rx_tx(self):
        des_info = gen_foo_iface_info()
        des_info.update(
            {
                Ethtool.CONFIG_SUBTREE: {
                    Ethtool.Pause.CONFIG_SUBTREE: {
                        Ethtool.Pause.AUTO_NEGOTIATION: True,
                        Ethtool.Pause.RX: True,
                        Ethtool.Pause.TX: True,
                    }
                }
            }
        )
        cur_info = deepcopy(des_info)
        cur_info[Ethtool.CONFIG_SUBTREE][Ethtool.Pause.CONFIG_SUBTREE][
            Ethtool.Pause.RX
        ] = False
        cur_info[Ethtool.CONFIG_SUBTREE][Ethtool.Pause.CONFIG_SUBTREE][
            Ethtool.Pause.TX
        ] = False

        des_iface = BaseIface(des_info)
        cur_iface = BaseIface(cur_info)
        assert des_iface.match(cur_iface)
