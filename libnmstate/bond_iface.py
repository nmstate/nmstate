#
# Copyright 2019 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
import six

import libnmstate.nm.device as nm_device
import libnmstate.nm.nmclient as nmclient
import libnmstate.nm.bond as nm_bond
import libnmstate.nm.translator as nm_translator
from libnmstate.base_iface import BaseInterface
from libnmstate.schema import Interface
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.error import NmstateValueError


class BondInterface(BaseInterface):
    NM_DEV_TYPES = (nmclient.NM.DeviceType.BOND,)

    def __init__(self, iface_info=None, iface_name=None):
        super(BondInterface, self).__init__(
            iface_info=iface_info, iface_name=iface_name
        )
        if iface_name:
            iface_info = BondInterface._get(iface_name)
        bond_info = iface_info.get(Bond.CONFIG_SUBTREE, {})
        self.slaves = (
            sorted(set(bond_info.get(Bond.SLAVES)))
            if bond_info.get(Bond.SLAVES)
            else None
        )
        self.mode = bond_info.get(Bond.MODE)
        self.options = bond_info.get(Bond.OPTIONS_SUBTREE)
        self.nm_setting_name = nmclient.NM.SETTING_BOND_SETTING_NAME
        self.master_type = 'bond'
        self.default.update(
            {'mode': BondMode.ROUND_ROBIN, 'options': {}, 'slaves': []}
        )

    @staticmethod
    def _get(iface_name):
        dev = nm_device.get_device_by_name(iface_name)
        bond_info = nm_bond.get_bond_info(dev)
        return nm_translator.Nm2Api.get_bond_info(bond_info)

    def dump(self):
        info = super(BondInterface, self).dump()

        info[Bond.CONFIG_SUBTREE] = {
            Bond.MODE: self.mode or self.default['mode'],
            Bond.SLAVES: self.slaves or self.default['slaves'],
            Bond.OPTIONS_SUBTREE: self.options or self.default['options'],
        }
        return info

    def _dump_bond_options(self):
        bond_option = {Bond.MODE: self.mode or BondMode.ROUND_ROBIN}
        bond_option.update(self.options or {})
        return bond_option

    def generate_settings(self, base_con_profile=None):
        settings = super(BondInterface, self).generate_settings(
            base_con_profile
        )
        settings.append(nm_bond.create_setting(self._dump_bond_options()))
        return settings

    def pre_merge_validate(self, iface_state):
        super(BondInterface, self).pre_merge_validate(iface_state)

        if self.is_up and self.slaves:
            # Check slave state
            for slave_iface_name in self.slaves:
                slave_iface_obj = iface_state.get(slave_iface_name)
                if slave_iface_obj and not slave_iface_obj.is_up:
                    raise NmstateValueError(
                        "Bond slave interface %s should be in %s state",
                        slave_iface_name,
                        InterfaceState.UP,
                    )
