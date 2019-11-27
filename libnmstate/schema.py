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


def _deprecate_constant(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwds):
        deprecated_class = args[0]
        deprecated_classname = args[0].__name__
        deprecated_name = f.__name__
        subclass, newname = deprecated_name.split('_', maxsplit=1)
        subclass = subclass.capitalize()
        _warn_deprecation(
            f"Using '{deprecated_classname}.{deprecated_name}' is deprecated, "
            f"use '{deprecated_classname}.{subclass}.{newname}' instead.")
        return getattr(getattr(deprecated_class, subclass), newname)
    return wrapper


class _LinuxBridge(type):
    @property
    @_deprecate_constant
    def PORT_NAME(cls):
        pass

    @property
    @_deprecate_constant
    def PORT_STP_PRIORITY(cls):
        pass

    @property
    @_deprecate_constant
    def PORT_STP_HAIRPIN_MODE(cls):
        pass

    @property
    @_deprecate_constant
    def PORT_STP_PATH_COST(cls):
        pass


class LinuxBridge(metaclass=_LinuxBridge):
    TYPE = 'linux-bridge'
    CONFIG_SUBTREE = 'bridge'

    OPTIONS_SUBTREE = 'options'
    MAC_AGEING_TIME = 'mac-ageing-time'
    GROUP_FORWARD_MASK = 'group-forward-mask'
    MULTICAST_SNOOPING = 'multicast-snooping'

    STP_SUBTREE = 'stp'
    STP_ENABLED = 'enabled'
    STP_PRIORITY = 'priority'
    STP_FORWARD_DELAY = 'forward-delay'
    STP_HELLO_TIME = 'hello-time'
    STP_MAX_AGE = 'max-age'

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
    PORT_VLAN_MODE = 'vlan-mode'
    PORT_ACCESS_TAG = 'access-tag'


def _warn_deprecation(message):
    warnings.warn(message, DeprecationWarning, stacklevel=3)
