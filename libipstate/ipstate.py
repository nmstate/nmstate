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
import pyroute2
from libnmstate.schema import Constants
from operator import itemgetter

INTERFACES = Constants.INTERFACES
ROUTES = Constants.ROUTES


def interfaces():
    info = []

    with pyroute2.IPRoute() as ipr:
        ipr.bind()
        state_factory = IpStateFactory(ipr)
        ip_states = state_factory.create_ip_states()
        for ip_state in ip_states:
            iface_info = {
                'name': ip_state.name,
                'device_type': ip_state.device_type,
                'link_type': ip_state.link_type,
                'mac_addr': ip_state.mac,
                'mtu': ip_state.mtu,
                'state': ip_state.state,
                'ipv4_addr': ip_state.ipv4_address,
                'ipv4_broadcast': ip_state.ipv4_broadcast,
                'ipv6_addr': ip_state.ipv6_address,
            }
            info.append(iface_info)
        info.sort(key=itemgetter('name'))
        return info


def show():
    report = {Constants.INTERFACES: interfaces()}
    return report


class IpStateFactory(object):

    def __init__(self, bound_iproute):
        super(IpStateFactory, self).__init__()
        self._ip_route = bound_iproute

    @property
    def links(self):
        return self._ip_route.get_links()
    @property
    def addresses(self):
        return self._ip_route.get_addr()

    def create_ip_states(self):
        ip_states = []
        for link in self.links:
            dev = link.get('index')
            addr_list = self._ip_route.get_addr(index=dev)
            ip_state = IpState(link, addr_list)
            ip_states.append(ip_state)
        return ip_states


class IpState(object):

    def __init__(self, iproute_link, iproute_address_list=()):
        super(IpState, self).__init__()
        self._link = iproute_link
        self._addrs = iproute_address_list

    @property
    def name(self):
        return self._link_attributes().get('IFLA_IFNAME')

    @property
    def mac(self):
        return self._link_attributes().get('IFLA_ADDRESS')

    @property
    def mtu(self):
        return self._link_attributes().get('IFLA_MTU')

    @property
    def state(self):
        return self._link_attributes().get('IFLA_OPERSTATE')

    def has_link_info(self):
        return self._link_info() is not None

    @property
    def link_type(self):
        if self.has_link_info():
            return self._link_info().get('IFLA_INFO_KIND')
        else:
            return ''

    @property
    def device_type(self):
        ifi_type = self._link.get('ifi_type')
        if ifi_type == 1:
            return 'Ethernet'
        if ifi_type == 772:
            return 'lo'
        elif ifi_type is not None :
            return (
                    'device type number is ' + str(ifi_type) +
                    '. for details see /usr/include/net/if_arp.h'
            )
        else:
            return ''

    def _link_attributes(self):
        return dict(self._link.get('attrs'))

    def _link_info(self):
        if self._link_attributes().get('IFLA_LINKINFO') is None:
            return None
        return dict(self._link_attributes().get('IFLA_LINKINFO').get('attrs'))

    @property
    def dev_index(self):
        return self._link('index')

    @property
    def ipv6_address(self):
        if self._has_ipv6_attributes():
            return self._ipv6_attributes().get('IFA_ADDRESS')
        return ''

    @property
    def ipv4_address(self):
        if self._has_ipv4_attributes():
            return self._ipv4_attributes().get('IFA_ADDRESS')
        return ''

    @property
    def ipv4_local_address(self):
        if self._has_ipv4_attributes():
            return self._ipv4_attributes().get('IFA_LOCAL')
        return ''

    @property
    def ipv4_broadcast(self):
        if self._has_ipv4_attributes():
            return self._ipv4_attributes().get('IFA_BROADCAST')
        return ''

    def _ipv4_attributes(self):
        _addr = [addr for addr in self._addrs if addr.get('family') == 2]
        if _addr:
            return dict(_addr[0].get('attrs'))
        return {}

    def _has_ipv4_attributes(self):
        return bool(self._ipv4_attributes())

    def _ipv6_attributes(self):
        _addr = [addr for addr in self._addrs if addr.get('family') == 10]
        if _addr:
            return dict(_addr[0].get('attrs'))
        return {}

    def _has_ipv6_attributes(self):
        return bool(self._ipv6_attributes())

###################################################################3
