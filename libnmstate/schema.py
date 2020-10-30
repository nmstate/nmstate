#
# Copyright (c) 2018-2020 Red Hat, Inc.
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
        pkgutil.get_data("libnmstate", "schemas/" + schema_name + ".yaml"),
        Loader=yaml.SafeLoader,
    )


ifaces_schema = load("operational-state")


class Interface:
    KEY = "interfaces"

    NAME = "name"
    TYPE = "type"
    STATE = "state"
    DESCRIPTION = "description"

    IPV4 = "ipv4"
    IPV6 = "ipv6"

    MAC = "mac-address"
    MTU = "mtu"


class Route:
    KEY = "routes"

    RUNNING = "running"
    CONFIG = "config"
    STATE = "state"
    STATE_ABSENT = "absent"
    TABLE_ID = "table-id"
    DESTINATION = "destination"
    NEXT_HOP_INTERFACE = "next-hop-interface"
    NEXT_HOP_ADDRESS = "next-hop-address"
    METRIC = "metric"
    USE_DEFAULT_METRIC = -1
    USE_DEFAULT_ROUTE_TABLE = 0


class RouteRule:
    KEY = "route-rules"
    CONFIG = "config"
    IP_FROM = "ip-from"
    IP_TO = "ip-to"
    PRIORITY = "priority"
    ROUTE_TABLE = "route-table"
    USE_DEFAULT_PRIORITY = -1
    USE_DEFAULT_ROUTE_TABLE = 0
    STATE = "state"
    STATE_ABSENT = "absent"


class DNS:
    KEY = "dns-resolver"
    RUNNING = "running"
    CONFIG = "config"
    SERVER = "server"
    SEARCH = "search"


class Constants:
    INTERFACES = Interface.KEY
    ROUTES = Route.KEY
    DNS = DNS.KEY


class InterfaceState:
    KEY = Interface.STATE

    DOWN = "down"
    UP = "up"
    ABSENT = "absent"
    IGNORE = "ignore"


class InterfaceType:
    KEY = Interface.TYPE

    BOND = "bond"
    DUMMY = "dummy"
    ETHERNET = "ethernet"
    LINUX_BRIDGE = "linux-bridge"
    MAC_VLAN = "mac-vlan"
    MAC_VTAP = "mac-vtap"
    OVS_BRIDGE = "ovs-bridge"
    OVS_INTERFACE = "ovs-interface"
    OVS_PORT = "ovs-port"
    UNKNOWN = "unknown"
    VLAN = "vlan"
    VXLAN = "vxlan"
    TEAM = "team"
    VRF = "vrf"
    INFINIBAND = "infiniband"
    OTHER = "other"

    VIRT_TYPES = (
        BOND,
        DUMMY,
        LINUX_BRIDGE,
        OVS_BRIDGE,
        OVS_PORT,
        OVS_INTERFACE,
        TEAM,
        VLAN,
        VXLAN,
    )


class InterfaceIP:
    ENABLED = "enabled"
    ADDRESS = "address"
    ADDRESS_IP = "ip"
    ADDRESS_PREFIX_LENGTH = "prefix-length"
    DHCP = "dhcp"
    AUTO_DNS = "auto-dns"
    AUTO_GATEWAY = "auto-gateway"
    AUTO_ROUTES = "auto-routes"
    AUTO_ROUTE_TABLE_ID = "auto-route-table-id"


class InterfaceIPv4(InterfaceIP):
    pass


class InterfaceIPv6(InterfaceIP):
    AUTOCONF = "autoconf"


OVS_BRIDGE = "OVSBridge.Port.LinkAggregation"


DEPRECATED_CONSTANTS = {
    "Bond.SLAVES": "Bond.PORT",
    "LinkAggregation.SLAVES_SUBTREE": f"{OVS_BRIDGE}.PORT_SUBTREE",
    "LinkAggregation.Slave": f"{OVS_BRIDGE}.Port",
}


class _DeprecatorType(type):
    def __getattribute__(cls, attribute):
        try:
            return super().__getattribute__(attribute)
        except AttributeError:
            deprecated_class = cls
            deprecated_classname = deprecated_class.__name__
            deprecated_name = attribute

            oldconstant = f"{deprecated_classname}.{deprecated_name}"
            newconstant = DEPRECATED_CONSTANTS.get(oldconstant)

            if newconstant:
                warnings.warn(
                    f"Using '{oldconstant}' is deprecated, "
                    f"use '{newconstant}' instead.",
                    FutureWarning,
                    stacklevel=3,
                )

                attributes = newconstant.split(".")
                new_classname = attributes.pop(0)
                new_value = globals()[new_classname]
                while attributes:
                    new_value = getattr(new_value, attributes.pop(0))

                return new_value

            raise


class Bond(metaclass=_DeprecatorType):
    KEY = InterfaceType.BOND
    CONFIG_SUBTREE = "link-aggregation"

    MODE = "mode"
    PORT = "port"
    OPTIONS_SUBTREE = "options"


class BondMode:
    ROUND_ROBIN = "balance-rr"
    ACTIVE_BACKUP = "active-backup"
    XOR = "balance-xor"
    BROADCAST = "broadcast"
    LACP = "802.3ad"
    TLB = "balance-tlb"
    ALB = "balance-alb"


class Bridge:
    CONFIG_SUBTREE = "bridge"
    OPTIONS_SUBTREE = "options"
    PORT_SUBTREE = "port"

    class Port:
        NAME = "name"
        VLAN_SUBTREE = "vlan"

        class Vlan:
            ENABLE_NATIVE = "enable-native"
            TRUNK_TAGS = "trunk-tags"
            MODE = "mode"
            TAG = "tag"

            class Mode:
                ACCESS = "access"
                TRUNK = "trunk"
                UNKNOWN = "unknown"

            class TrunkTags:
                ID = "id"
                ID_RANGE = "id-range"
                MIN_RANGE = "min"
                MAX_RANGE = "max"


class LinuxBridge(Bridge):
    TYPE = "linux-bridge"
    STP_SUBTREE = "stp"
    MULTICAST_SUBTREE = "multicast"

    class Options:
        GROUP_FORWARD_MASK = "group-forward-mask"
        MAC_AGEING_TIME = "mac-ageing-time"
        MULTICAST_SNOOPING = "multicast-snooping"
        GROUP_ADDR = "group-addr"
        GROUP_FWD_MASK = "group-fwd-mask"
        HASH_ELASTICITY = "hash-elasticity"
        HASH_MAX = "hash-max"
        MULTICAST_ROUTER = "multicast-router"
        MULTICAST_LAST_MEMBER_COUNT = "multicast-last-member-count"
        MULTICAST_LAST_MEMBER_INTERVAL = "multicast-last-member-interval"
        MULTICAST_MEMBERSHIP_INTERVAL = "multicast-membership-interval"
        MULTICAST_QUERIER = "multicast-querier"
        MULTICAST_QUERIER_INTERVAL = "multicast-querier-interval"
        MULTICAST_QUERY_USE_IFADDR = "multicast-query-use-ifaddr"
        MULTICAST_QUERY_INTERVAL = "multicast-query-interval"
        MULTICAST_QUERY_RESPONSE_INTERVAL = "multicast-query-response-interval"
        MULTICAST_STARTUP_QUERY_COUNT = "multicast-startup-query-count"
        MULTICAST_STARTUP_QUERY_INTERVAL = "multicast-startup-query-interval"

        # Read only properties begin
        HELLO_TIMER = "hello-timer"
        GC_TIMER = "gc-timer"
        # Read only properties end

    class Port(Bridge.Port):
        STP_HAIRPIN_MODE = "stp-hairpin-mode"
        STP_PATH_COST = "stp-path-cost"
        STP_PRIORITY = "stp-priority"

    class STP:
        ENABLED = "enabled"
        FORWARD_DELAY = "forward-delay"
        HELLO_TIME = "hello-time"
        MAX_AGE = "max-age"
        PRIORITY = "priority"


class Ethernet:
    TYPE = InterfaceType.ETHERNET
    CONFIG_SUBTREE = "ethernet"

    AUTO_NEGOTIATION = "auto-negotiation"
    SPEED = "speed"
    DUPLEX = "duplex"

    FULL_DUPLEX = "full"
    HALF_DUPLEX = "half"

    SRIOV_SUBTREE = "sr-iov"

    class SRIOV:
        TOTAL_VFS = "total-vfs"
        VFS_SUBTREE = "vfs"

        class VFS:
            ID = "id"
            MAC_ADDRESS = "mac-address"
            SPOOF_CHECK = "spoof-check"
            TRUST = "trust"
            MIN_TX_RATE = "min-tx-rate"
            MAX_TX_RATE = "max-tx-rate"


class VLAN:
    TYPE = InterfaceType.VLAN
    CONFIG_SUBTREE = "vlan"

    ID = "id"
    BASE_IFACE = "base-iface"


class VXLAN:
    TYPE = InterfaceType.VXLAN
    CONFIG_SUBTREE = "vxlan"

    ID = "id"
    BASE_IFACE = "base-iface"
    REMOTE = "remote"
    DESTINATION_PORT = "destination-port"


class OvsDB:
    OVS_DB_SUBTREE = "ovs-db"
    # Don't use hypen as this is OVS data base entry
    EXTERNAL_IDS = "external_ids"


class OVSInterface(OvsDB):
    TYPE = InterfaceType.OVS_INTERFACE
    PATCH_CONFIG_SUBTREE = "patch"

    class Patch:
        PEER = "peer"


class OVSBridge(Bridge, OvsDB):
    TYPE = "ovs-bridge"

    class Options:
        FAIL_MODE = "fail-mode"
        MCAST_SNOOPING_ENABLED = "mcast-snooping-enable"
        RSTP = "rstp"
        STP = "stp"

    class Port(Bridge.Port):
        LINK_AGGREGATION_SUBTREE = "link-aggregation"

        class LinkAggregation(metaclass=_DeprecatorType):
            MODE = "mode"
            PORT_SUBTREE = "port"

            class Port:
                NAME = "name"

            class Options:
                DOWN_DELAY = "bond-downdelay"
                UP_DELAY = "bond-updelay"

            class Mode:
                ACTIVE_BACKUP = "active-backup"
                BALANCE_SLB = "balance-slb"
                BALANCE_TCP = "balance-tcp"
                LACP = "lacp"


class Team:
    TYPE = InterfaceType.TEAM
    CONFIG_SUBTREE = InterfaceType.TEAM

    PORT_SUBTREE = "port"
    RUNNER_SUBTREE = "runner"

    class Port:
        NAME = "name"

    class Runner:
        NAME = "name"

        class RunnerMode:
            LOAD_BALANCE = "loadbalance"


class LLDP:
    CONFIG_SUBTREE = "lldp"
    ENABLED = "enabled"
    NEIGHBORS_SUBTREE = "neighbors"

    class Neighbors:
        DESCRIPTION = "_description"
        TLV_TYPE = "type"
        TLV_SUBTYPE = "subtype"
        ORGANIZATION_CODE = "oui"


class VRF:
    CONFIG_SUBTREE = "vrf"
    PORT_SUBTREE = "port"
    ROUTE_TABLE_ID = "route-table-id"


class InfiniBand:
    CONFIG_SUBTREE = "infiniband"
    PKEY = "pkey"
    MODE = "mode"
    BASE_IFACE = "base-iface"
    DEFAULT_PKEY = 0xFFFF

    class Mode:
        DATAGRAM = "datagram"
        CONNECTED = "connected"


class MacVlan:
    TYPE = InterfaceType.MAC_VLAN
    CONFIG_SUBTREE = "mac-vlan"
    BASE_IFACE = "base-iface"
    MODE = "mode"
    PROMISCUOUS = "promiscuous"

    class Mode:
        UNKNOWN = "unknown"
        VEPA = "vepa"
        BRIDGE = "bridge"
        PRIVATE = "private"
        PASSTHRU = "passthru"
        SOURCE = "source"


class MacVtap(MacVlan):
    TYPE = InterfaceType.MAC_VTAP
    CONFIG_SUBTREE = "mac-vtap"
