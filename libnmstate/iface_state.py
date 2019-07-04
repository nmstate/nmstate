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
import copy

import libnmstate.nm.nmclient as nmclient
import libnmstate.nm.connection as nm_connection
import libnmstate.nm.applier as nm_applier
import libnmstate.nm.device as nm_device
from libnmstate.eth_iface import EthernetInterface
from libnmstate.base_iface import BaseInterface
from libnmstate.bond_iface import BondInterface
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType


class IfaceState(object):
    def __init__(self, ifaces=None):
        iface_objs = []
        if ifaces is None:
            iface_objs = IfaceState._get()
        else:
            for iface in ifaces:
                iface_type = iface[Interface.TYPE]
                if iface_type == InterfaceType.ETHERNET:
                    iface_objs.append(EthernetInterface(iface))
                elif iface_type == InterfaceType.BOND:
                    iface_objs.append(BondInterface(iface))
                else:
                    print(
                        "Unknown dev type ", iface[Interface.NAME], iface_type
                    )
                    iface_objs.append(BaseInterface(iface))

        self._iface_obj_dict = {}
        for iface_obj in iface_objs:
            self._iface_obj_dict[iface_obj.name] = iface_obj
        if ifaces is None:
            self.sanitize()

    def update_slave_ifaces(self):
        # Remove all existing master/slave information
        for iface_obj in self:
            iface_obj.master_name = None
            iface_obj.slave_type = None
        # Fill in the master/slave information
        for iface_obj in self:
            if iface_obj.is_up:
                for slave in iface_obj.slaves:
                    self[slave].master_name = iface_obj.name
                    self[slave].slave_type = iface_obj.master_type

    def __str__(self):
        return "{}: {}".format(
            type(self).__name__,
            list(iface_obj.__str__() for iface_obj in self),
        )

    def __getitem__(self, iface_name):
        return self._iface_obj_dict.get(iface_name)

    def __delitem__(self, iface_name):
        del self._iface_obj_dict[iface_name]

    def get(self, iface_name):
        return self._iface_obj_dict.get(iface_name)

    def items(self):
        return self._iface_obj_dict.items()

    def keys(self):
        return self._iface_obj_dict.keys()

    def values(self):
        return self._iface_obj_dict.values()

    def __iter__(self):
        for iface_obj in self._iface_obj_dict.values():
            yield iface_obj

    @staticmethod
    def _get():
        iface_objs = []
        nmclient.client(refresh=True)
        iface_names = sorted(
            [dev.get_iface() for dev in nm_device.list_devices()]
        )
        for dev in nm_device.list_devices():
            iface_name = dev.get_iface()
            dev_type = dev.get_device_type()
            if dev_type in EthernetInterface.NM_DEV_TYPES:
                iface_objs.append(EthernetInterface(iface_name=iface_name))
            elif dev_type in BondInterface.NM_DEV_TYPES:
                iface_objs.append(BondInterface(iface_name=iface_name))
            else:
                print("Unknown dev type ", iface_name, dev_type)
                iface_objs.append(BaseInterface(iface_name=iface_name))

        return iface_objs

    def dump(self):
        return [iface_obj.dump() for iface_obj in self]

    def merge_config(self, current_state):
        current = current_state.iface_state
        for iface_name, iface_obj in current.items():
            if iface_name not in self.keys():
                self._iface_obj_dict[iface_obj.name] = copy.deepcopy(iface_obj)

        for iface_name, iface_obj in self.items():
            current_iface_obj = current.get(iface_name)
            if current_iface_obj:
                iface_obj.merge_config(current_iface_obj)

    def generate_metadata(self):
        for iface_obj in self.values():
            iface_obj.generate_metadata()

    def remove_unchanged_iface(self, current_state):
        current = current_state.iface_state
        unchanged_iface_names = []
        for iface_name, iface_obj in self.items():
            if iface_obj == current.get(iface_name):
                print('Interface %s is not changed' % iface_name)
                unchanged_iface_names.append(iface_name)
            else:
                print('Changed interface, current: ', current.get(iface_name))
                print('Changed interface, desired: ', iface_obj)
        for iface_name in unchanged_iface_names:
            del self[iface_name]

    def apply(self):
        profiles = []
        for iface_name, iface_obj in self.items():
            cur_profile = nm_connection.ConnectionProfile()
            nmdev = nm_device.get_device_by_name(iface_name)
            cur_profile.import_by_device(nmdev)
            new_profile = nm_connection.ConnectionProfile()
            if not cur_profile.profile:
                # No profile exists for this device
                settings = iface_obj.generate_settings()
                new_profile.create(settings)
                profiles.append(new_profile)
            else:
                settings = iface_obj.generate_settings(cur_profile)
                new_profile.create(settings)
                cur_profile.update(new_profile)
                profiles.append(cur_profile)

        nm_applier.edit_existing_ifaces(profiles)
        nm_applier.set_ifaces_admin_state(self.dump(), profiles)

    def verify(self, current):
        pass

    def pre_merge_validate(self):
        for iface_obj in self:
            iface_obj.pre_merge_validate(self)

    def post_merge_validate(self):
        pass

    def sanitize(self):
        for iface_obj in self:
            iface_obj.sanitize()
        # Change slave state to UP
        for iface_obj in self:
            if iface_obj.is_up:
                for slave in iface_obj.slaves:
                    self[slave].state = InterfaceState.UP
