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

import libnmstate.nm.device as nm_device
import libnmstate.nm.connection as nm_connection
import libnmstate.nm.ipv4 as nm_ipv4
import libnmstate.nm.ipv6 as nm_ipv6
import libnmstate.nm.nmclient as nmclient
from libnmstate.nm.translator import Nm2Api
import libnmstate.nm.wired as nm_wired
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPV4
from libnmstate.schema import InterfaceIPV6
from libnmstate.schema import InterfaceState
import libnmstate.iplib as iplib


class BaseStateObject(object):
    def __init__(self):
        self.default = {}
        self.name = None

    def set_default(self):
        for key, default_value in self.default.items():
            if getattr(self, key) is None:
                setattr(self, key, default_value)

    def merge_config(self, other):
        for key in self.default.keys():
            other_value = getattr(other, key)
            self_value = getattr(self, key)
            if self_value is None and other_value is not None:
                setattr(self, key, other_value)


class BaseInterface(BaseStateObject):
    def __init__(self, iface_info=None, iface_name=None):
        if iface_name:
            iface_info = BaseInterface._get(iface_name)

        self.name = iface_info[Interface.NAME]
        self.type = iface_info.get(Interface.TYPE)
        self.state = iface_info.get(Interface.STATE)
        ipv4_info = iface_info.get(Interface.IPV4)
        self.ipv4 = BaseInterfaceIPV4(ipv4_info) if ipv4_info else None
        ipv6_info = iface_info.get(Interface.IPV6)
        self.ipv6 = BaseInterfaceIPV6(ipv6_info) if ipv6_info else None
        self.mtu = iface_info.get(Interface.MTU)
        self.mac = iface_info.get(Interface.MAC)
        self.verify_skip_mac = False
        self.master_name = None
        self.slave_type = None
        self.master_type = None
        self.nm_setting_name = None
        self.slaves = []
        ipv4_default = BaseInterfaceIPV4({})
        ipv4_default.set_default()
        ipv6_default = BaseInterfaceIPV6({})
        ipv6_default.set_default()
        self.default = {
            'name': 'unknown',
            'type': 'unknown',
            'state': InterfaceState.UP,
            'mtu': -1,
            'mac': '00:00:00:00:00:00',
            'ipv4': ipv4_default,
            'ipv6': ipv6_default,
            'master_name': None,
            'slave_type': None,
        }
        self.merge_keys = ['name', 'type', 'state', 'mtu', 'mac']

    @staticmethod
    def _get(iface_name):
        dev = nm_device.get_device_by_name(iface_name)
        devinfo = nm_device.get_device_common_info(dev)
        iface_info = Nm2Api.get_common_device_info(devinfo)
        active_connection = nm_connection.get_device_active_connection(dev)
        iface_info[Interface.IPV4] = nm_ipv4.get_info(active_connection)
        iface_info[Interface.IPV6] = nm_ipv6.get_info(active_connection)
        nm_dev = nm_device.get_device_by_name(iface_name)
        wire_info = nm_wired.get_info(nm_dev)
        iface_info[Interface.MTU] = wire_info.get(Interface.MTU)
        iface_info[Interface.MAC] = wire_info.get(Interface.MAC)
        return iface_info

    def dump(self):
        return {
            Interface.NAME: self.name,
            Interface.TYPE: self.type or self.default['type'],
            Interface.STATE: self.state or self.default['state'],
            Interface.MTU: self.mtu or self.default['mtu'],
            Interface.MAC: self.mac or self.default['mac'],
            Interface.IPV4: self.ipv4.dump() if self.ipv4 else {},
            Interface.IPV6: self.ipv6.dump() if self.ipv6 else {},
        }

    @property
    def metadata(self):
        return (
            {'master': self.master_name, 'slave_type': self.slave_type}
            if self.master_name
            else {}
        )

    @property
    def is_up(self):
        return self.state == InterfaceState.UP

    @property
    def is_down(self):
        return self.state == InterfaceState.DOWN

    @property
    def is_absent(self):
        return self.state == InterfaceState.ABSENT

    def __str__(self):
        return "{}: {} {}".format(
            type(self).__name__, self.dump().__str__(), self.metadata
        )

    @property
    def _verify_keys(self):
        # TODO: handle state absent vs down
        keys = [self.name, self.type, self.state]
        if self.is_up:
            keys.extend(
                [
                    self.mtu,
                    self.ipv4.verify_keys,
                    self.ipv6.verify_keys,
                    self.master_name,
                    self.slave_type,
                ]
            )

        if not self.verify_skip_mac:
            keys.append(self.mac)
        return keys

    def __eq__(self, other):
        if other is None:
            return False

        return self._verify_keys == other._verify_keys

    def generate_metadata(self):
        pass

    def merge_config(self, other):
        super(BaseInterface, self).merge_config(other)
        self.ipv4.merge_config(other.ipv4)
        self.ipv6.merge_config(other.ipv6)

    def generate_settings(self, base_con_profile=None):
        con_setting = nm_connection.ConnectionSetting()
        if base_con_profile and base_con_profile.profile:
            con_setting.import_by_profile(base_con_profile)
        else:
            con_setting.create(
                con_name=self.name,
                iface_name=self.name,
                iface_type=self.nm_setting_name,
            )
        if self.master_name:
            con_setting.set_master(self.master_name, self.slave_type)

        profile = base_con_profile.profile if base_con_profile else None

        return [
            con_setting.setting,
            nm_ipv4.create_setting(self.ipv4.dump(), profile),
            nm_ipv6.create_setting(self.ipv6.dump(), profile),
        ]

    def pre_merge_validate(self, iface_state):
        pass

    def sanitize(self):
        self.set_default()
        self.ipv4.sanitize()
        self.ipv6.sanitize()


class IPAddr(object):
    def __init__(self, addr):
        self.ip = addr[InterfaceIP.ADDRESS_IP]
        self.prefix_length = addr[InterfaceIP.ADDRESS_PREFIX_LENGTH]

    @property
    def verify_keys(self):
        return (self.ip, self.prefix_length)

    def dump(self):
        return {
            InterfaceIP.ADDRESS_IP: self.ip,
            InterfaceIP.ADDRESS_PREFIX_LENGTH: self.prefix_length,
        }

    def __hash__(self):
        return hash(self.verify_keys)

    def __eq__(self, other):
        return self.verify_keys == other.verify_keys

    def __lt__(self, other):
        return self.verify_keys < other.verify_keys

    @property
    def is_ipv6(self):
        return iplib.is_ipv6_address(self.ip)

    @property
    def is_ipv6_link_local(self):
        return self.is_ipv6 and iplib.is_ipv6_link_local_addr(
            self.ip, self.prefix_length
        )


class BaseInterfaceIP(BaseStateObject):
    def __init__(self, ip_info):
        super(BaseInterfaceIP, self).__init__()
        self.enabled = ip_info.get(InterfaceIP.ENABLED)
        self.address = (
            sorted(
                set(
                    [
                        IPAddr(addr)
                        for addr in ip_info.get(InterfaceIP.ADDRESS, [])
                    ]
                )
            )
            if InterfaceIP.ADDRESS
            else None
        )
        self.dhcp = ip_info.get(InterfaceIP.DHCP)
        self.auto_dns = ip_info.get(InterfaceIP.AUTO_DNS)
        self.auto_gateway = ip_info.get(InterfaceIP.AUTO_GATEWAY)
        self.auto_routes = ip_info.get(InterfaceIP.AUTO_ROUTES)
        self.default = {
            'enabled': False,
            'address': [],
            'dhcp': False,
            'auto_dns': True,
            'auto_gateway': True,
            'auto_routes': True,
        }

    def __str__(self):
        return "{}: {}".format(type(self).__name__, self.dump().__str__())

    def dump(self, skip_ipv6_link_local=False):
        tmp = copy.deepcopy(self)
        tmp.set_default()

        if not tmp.enabled:
            return {InterfaceIP.ENABLED: False}

        info = {InterfaceIP.ENABLED: True}

        info[InterfaceIP.DHCP] = tmp.dhcp
        if tmp.dhcp:
            info[InterfaceIP.AUTO_DNS] = tmp.auto_dns
            info[InterfaceIP.AUTO_GATEWAY] = tmp.auto_gateway
            info[InterfaceIP.AUTO_ROUTES] = tmp.auto_routes

        info[InterfaceIP.ADDRESS] = [
            addr.dump()
            for addr in tmp.address
            if not (skip_ipv6_link_local and addr.is_ipv6_link_local)
        ]

        return info

    @property
    def verify_keys(self):
        return self.dump(skip_ipv6_link_local=True)

    def sanitize(self):
        self.set_default()
        if self.dhcp:
            self.address = []


class BaseInterfaceIPV4(BaseInterfaceIP):
    def __init__(self, ip_info):
        super(BaseInterfaceIPV4, self).__init__(ip_info)


class BaseInterfaceIPV6(BaseInterfaceIP):
    def __init__(self, ip_info):
        super(BaseInterfaceIPV6, self).__init__(ip_info)
        self.autoconf = ip_info.get(InterfaceIPV6.AUTOCONF)
        self.default['autoconf'] = False

    def dump(self, skip_ipv6_link_local=False):
        info = super(BaseInterfaceIPV6, self).dump(skip_ipv6_link_local)
        tmp = copy.deepcopy(self)
        tmp.set_default()
        if tmp.enabled:
            info[InterfaceIPV6.AUTOCONF] = tmp.autoconf
            if tmp.autoconf:
                info[InterfaceIP.AUTO_DNS] = tmp.auto_dns
                info[InterfaceIP.AUTO_GATEWAY] = tmp.auto_gateway
                info[InterfaceIP.AUTO_ROUTES] = tmp.auto_routes
        return info

    def sanitize(self):
        super(BaseInterfaceIPV6, self).sanitize()
        self.set_default()
        if self.autoconf:
            self.address = []
        self.address = [
            addr for addr in self.address if not addr.is_ipv6_link_local
        ]
