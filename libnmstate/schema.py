#
# Copyright (c) 2018-2019 Red Hat, Inc.
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

import warnings


import pkgutil
import yaml


def load(schema_name):
    return yaml.load(
        pkgutil.get_data('libnmstate', 'schemas/' + schema_name + '.yaml'),
        Loader=yaml.SafeLoader,
    )


ifaces_schema = load('operational-state')


class Interface(object):
    KEY = 'interfaces'

    NAME = 'name'
    TYPE = 'type'
    STATE = 'state'
    DESCRIPTION = 'description'

    IPV4 = 'ipv4'
    IPV6 = 'ipv6'

    MAC = 'mac-address'
    MTU = 'mtu'


class Route(object):
    KEY = 'routes'

    RUNNING = 'running'
    CONFIG = 'config'
    STATE = 'state'
    STATE_ABSENT = 'absent'
    TABLE_ID = 'table-id'
    DESTINATION = 'destination'
    NEXT_HOP_INTERFACE = 'next-hop-interface'
    NEXT_HOP_ADDRESS = 'next-hop-address'
    METRIC = 'metric'
    USE_DEFAULT_METRIC = -1
    USE_DEFAULT_ROUTE_TABLE = 0


class RouteRule(object):
    KEY = 'route-rules'
    CONFIG = 'config'
    IP_FROM = 'ip-from'
    IP_TO = 'ip-to'
    PRIORITY = 'priority'
    ROUTE_TABLE = 'route-table'
    USE_DEFAULT_PRIORITY = -1
    USE_DEFAULT_ROUTE_TABLE = 0


class DNS(object):
    KEY = 'dns-resolver'
    RUNNING = 'running'
    CONFIG = 'config'
    SERVER = 'server'
    SEARCH = 'search'


class Constants(object):
    INTERFACES = Interface.KEY
    ROUTES = Route.KEY
    DNS = DNS.KEY


class InterfaceState(object):
    KEY = Interface.STATE

    DOWN = 'down'
    UP = 'up'
    ABSENT = 'absent'


class InterfaceType(object):
    KEY = Interface.TYPE

    BOND = 'bond'
    DUMMY = 'dummy'
    ETHERNET = 'ethernet'
    LINUX_BRIDGE = 'linux-bridge'
    OVS_BRIDGE = 'ovs-bridge'
    OVS_INTERFACE = 'ovs-interface'
    OVS_PORT = 'ovs-port'
    UNKNOWN = 'unknown'
    VLAN = 'vlan'
    VXLAN = 'vxlan'

    VIRT_TYPES = (
        BOND,
        DUMMY,
        LINUX_BRIDGE,
        OVS_BRIDGE,
        OVS_PORT,
        OVS_INTERFACE,
        VLAN,
        VXLAN,
    )


class InterfaceIP(object):
    ENABLED = 'enabled'
    ADDRESS = 'address'
    ADDRESS_IP = 'ip'
    ADDRESS_PREFIX_LENGTH = 'prefix-length'
    DHCP = 'dhcp'
    AUTO_DNS = 'auto-dns'
    AUTO_GATEWAY = 'auto-gateway'
    AUTO_ROUTES = 'auto-routes'


class InterfaceIPv4(InterfaceIP):
    pass


class InterfaceIPv6(InterfaceIP):
    AUTOCONF = 'autoconf'


class Bond(object):
    KEY = InterfaceType.BOND
    CONFIG_SUBTREE = 'link-aggregation'

    MODE = 'mode'
    SLAVES = 'slaves'
    OPTIONS_SUBTREE = 'options'


class BondMode(object):
    ROUND_ROBIN = 'balance-rr'
    ACTIVE_BACKUP = 'active-backup'
    XOR = 'balance-xor'
    BROADCAST = 'broadcast'
    LACP = '802.3ad'
    TLB = 'balance-tlb'
    ALB = 'balance-alb'


DEPRECATED_CONSTANTS = {
    'LinuxBridge.PORT_NAME': 'LinuxBridge.Port.NAME',
    'LinuxBridge.PORT_STP_HAIRPIN_MODE': 'LinuxBridge.Port.STP_HAIRPIN_MODE',
    'LinuxBridge.PORT_STP_PATH_COST': 'LinuxBridge.Port.STP_PATH_COST',
    'LinuxBridge.PORT_STP_PRIORITY': 'LinuxBridge.Port.STP_PRIORITY',
    'LinuxBridge.STP_ENABLED': 'LinuxBridge.STP.ENABLED',
    'LinuxBridge.STP_FORWARD_DELAY': 'LinuxBridge.STP.FORWARD_DELAY',
    'LinuxBridge.STP_HELLO_TIME': 'LinuxBridge.STP.HELLO_TIME',
    'LinuxBridge.STP_MAX_AGE': 'LinuxBridge.STP.MAX_AGE',
    'LinuxBridge.STP_PRIORITY': 'LinuxBridge.STP.PRIORITY',
}


class _DeprecatorType(type):
    def __getattribute__(cls, attribute):
        try:
            return super().__getattribute__(attribute)
        except AttributeError:
            deprecated_class = cls
            deprecated_classname = deprecated_class.__name__
            deprecated_name = attribute

            oldconstant = f'{deprecated_classname}.{deprecated_name}'
            newconstant = DEPRECATED_CONSTANTS.get(oldconstant)

            if newconstant:
                warnings.warn(
                    f"Using '{oldconstant}' is deprecated, "
                    f"use '{newconstant}' instead.",
                    FutureWarning,
                    stacklevel=3,
                )

                attributes = newconstant.split('.')
                new_classname = attributes.pop(0)
                new_value = globals()[new_classname]
                while attributes:
                    new_value = getattr(new_value, attributes.pop(0))

                return new_value

            raise


class LinuxBridge(metaclass=_DeprecatorType):
    TYPE = 'linux-bridge'
    CONFIG_SUBTREE = 'bridge'

    OPTIONS_SUBTREE = 'options'
    MAC_AGEING_TIME = 'mac-ageing-time'
    GROUP_FORWARD_MASK = 'group-forward-mask'
    MULTICAST_SNOOPING = 'multicast-snooping'

    STP_SUBTREE = 'stp'

    PORT_SUBTREE = 'port'

    class Port(object):
        NAME = 'name'
        STP_HAIRPIN_MODE = 'stp-hairpin-mode'
        STP_PATH_COST = 'stp-path-cost'
        STP_PRIORITY = 'stp-priority'
        VLAN_SUBTREE = 'vlan'

        class Vlan(object):
            TRUNK_TAGS = 'trunk-tags'
            TAG = 'tag'
            ENABLE_NATIVE = 'enable-native'
            TYPE = 'type'
            ACCESS_TYPE = 'access'
            TRUNK_TYPE = 'trunk'

            class TrunkTags(object):
                ID = 'id'
                ID_RANGE = 'id-range'
                MIN_RANGE = 'min'
                MAX_RANGE = 'max'

    class STP(object):
        ENABLED = 'enabled'
        FORWARD_DELAY = 'forward-delay'
        HELLO_TIME = 'hello-time'
        MAX_AGE = 'max-age'
        PRIORITY = 'priority'


class Ethernet(object):
    TYPE = InterfaceType.ETHERNET
    CONFIG_SUBTREE = 'ethernet'

    AUTO_NEGOTIATION = 'auto-negotiation'
    SPEED = 'speed'
    DUPLEX = 'duplex'

    FULL_DUPLEX = 'full'
    HALF_DUPLEX = 'half'

    SRIOV_SUBTREE = 'sr-iov'

    class SRIOV(object):
        TOTAL_VFS = 'total-vfs'


class VLAN(object):
    TYPE = InterfaceType.VLAN
    CONFIG_SUBTREE = 'vlan'

    ID = 'id'
    BASE_IFACE = 'base-iface'


class VXLAN(object):
    TYPE = InterfaceType.VXLAN
    CONFIG_SUBTREE = 'vxlan'

    ID = 'id'
    BASE_IFACE = 'base-iface'
    REMOTE = 'remote'
    DESTINATION_PORT = 'destination-port'


class OVSBridge(object):
    TYPE = 'ovs-bridge'
    CONFIG_SUBTREE = 'bridge'

    OPTIONS_SUBTREE = 'options'
    FAIL_MODE = 'fail-mode'
    MCAST_SNOOPING_ENABLED = 'mcast-snooping-enable'
    RSTP = 'rstp'
    STP = 'stp'

    PORT_SUBTREE = 'port'
    PORT_NAME = 'name'

    class Port:
        VLAN_SUBTREE = 'vlan'

        class Vlan:
            TRUNK_TAGS = 'trunk-tags'
            TAG = 'tag'
            ENABLE_NATIVE = 'enable-native'
            MODE = 'mode'

            class Mode:
                ACCESS = 'access'
                TRUNK = 'trunk'

            class TrunkTags:
                ID = 'id'
                ID_RANGE = 'id-range'
                MIN_RANGE = 'min'
                MAX_RANGE = 'max'
