# SPDX-License-Identifier: LGPL-2.1-or-later


class Interface:
    KEY = "interfaces"

    NAME = "name"
    TYPE = "type"
    STATE = "state"
    DESCRIPTION = "description"

    IPV4 = "ipv4"
    IPV6 = "ipv6"
    MPTCP = "mptcp"

    MAC = "mac-address"
    MTU = "mtu"
    MIN_MTU = "min-mtu"
    MAX_MTU = "max-mtu"
    COPY_MAC_FROM = "copy-mac-from"
    ACCEPT_ALL_MAC_ADDRESSES = "accept-all-mac-addresses"
    WAIT_IP = "wait-ip"
    CONTROLLER = "controller"


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
    WEIGHT = "weight"
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
    FWMARK = "fwmark"
    FWMASK = "fwmask"
    FAMILY = "family"
    FAMILY_IPV4 = "ipv4"
    FAMILY_IPV6 = "ipv6"
    IIF = "iif"
    ACTION = "action"
    ACTION_BLACKHOLE = "blackhole"
    ACTION_UNREACHABLE = "unreachable"
    ACTION_PROHIBIT = "prohibit"


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
    VRF = "vrf"
    INFINIBAND = "infiniband"
    VETH = "veth"
    OTHER = "other"
    LOOPBACK = "loopback"

    VIRT_TYPES = (
        BOND,
        DUMMY,
        LINUX_BRIDGE,
        OVS_BRIDGE,
        OVS_PORT,
        OVS_INTERFACE,
        VETH,
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
    AUTO_ROUTE_METRIC = "auto-route-metric"
    MPTCP_FLAGS = "mptcp-flags"
    ALLOW_EXTRA_ADDRESS = "allow-extra-address"


class InterfaceIPv4(InterfaceIP):
    DHCP_CLIENT_ID = "dhcp-client-id"


class InterfaceIPv6(InterfaceIP):
    AUTOCONF = "autoconf"
    DHCP_DUID = "dhcp-duid"
    ADDR_GEN_MODE = "addr-gen-mode"
    ADDR_GEN_MODE_EUI64 = "eui64"
    ADDR_GEN_MODE_STABLE_PRIVACY = "stable-privacy"
    TOKEN = "token"


class Bond:
    KEY = InterfaceType.BOND
    CONFIG_SUBTREE = "link-aggregation"

    MODE = "mode"
    PORT = "port"
    PORTS = "ports"
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
    PORTS_SUBTREE = "ports"

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
        VLAN_PROTOCOL = "vlan-protocol"

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
            VLAN_ID = "vlan-id"
            QOS = "qos"


class Veth:
    TYPE = InterfaceType.VETH
    CONFIG_SUBTREE = "veth"

    PEER = "peer"


class VLAN:
    TYPE = InterfaceType.VLAN
    CONFIG_SUBTREE = "vlan"

    ID = "id"
    BASE_IFACE = "base-iface"
    PROTOCOL = "protocol"
    PROTOCOL_802_1AD = "802.1ad"
    PROTOCOL_802_1Q = "802.1q"


class VXLAN:
    TYPE = InterfaceType.VXLAN
    CONFIG_SUBTREE = "vxlan"

    ID = "id"
    BASE_IFACE = "base-iface"
    REMOTE = "remote"
    DESTINATION_PORT = "destination-port"


class OvsDB:
    KEY = "ovs-db"
    OVS_DB_SUBTREE = "ovs-db"
    # Don't use hypen as this is OVS data base entry
    EXTERNAL_IDS = "external_ids"
    OTHER_CONFIG = "other_config"


class OVSInterface(OvsDB):
    TYPE = InterfaceType.OVS_INTERFACE
    PATCH_CONFIG_SUBTREE = "patch"
    DPDK_CONFIG_SUBTREE = "dpdk"

    class Patch:
        PEER = "peer"

    class Dpdk:
        DEVARGS = "devargs"
        RX_QUEUE = "rx-queue"
        N_RXQ_DESC = "n_rxq_desc"
        N_TXQ_DESC = "n_txq_desc"


class OVSBridge(Bridge, OvsDB):
    TYPE = "ovs-bridge"

    class Options:
        FAIL_MODE = "fail-mode"
        MCAST_SNOOPING_ENABLED = "mcast-snooping-enable"
        RSTP = "rstp"
        STP = "stp"
        DATAPATH = "datapath"

    class Port(Bridge.Port):
        LINK_AGGREGATION_SUBTREE = "link-aggregation"

        class LinkAggregation:
            MODE = "mode"
            PORT_SUBTREE = "port"
            OVS_DB_SUBTREE = "ovs-db"

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


class Ieee8021X:
    CONFIG_SUBTREE = "802.1x"
    IDENTITY = "identity"
    EAP_METHODS = "eap-methods"
    PRIVATE_KEY = "private-key"
    PRIVATE_KEY_PASSWORD = "private-key-password"
    CLIENT_CERT = "client-cert"
    CA_CERT = "ca-cert"


class Ethtool:
    CONFIG_SUBTREE = "ethtool"

    class Pause:
        CONFIG_SUBTREE = "pause"
        AUTO_NEGOTIATION = "autoneg"
        RX = "rx"
        TX = "tx"

    class Feature:
        CONFIG_SUBTREE = "feature"

    class Ring:
        CONFIG_SUBTREE = "ring"
        RX = "rx"
        RX_JUMBO = "rx-jumbo"
        RX_MINI = "rx-mini"
        TX = "tx"

    class Coalesce:
        CONFIG_SUBTREE = "coalesce"
        ADAPTIVE_RX = "adaptive-rx"
        ADAPTIVE_TX = "adaptive-tx"
        PKT_RATE_HIGH = "pkt-rate-high"
        PKT_RATE_LOW = "pkt-rate-low"
        RX_FRAMES = "rx-frames"
        RX_FRAMES_HIGH = "rx-frames-high"
        RX_FRAMES_IRQ = "rx-frames-irq"
        RX_FRAMES_LOW = "rx-frames-low"
        RX_USECS = "rx-usecs"
        RX_USECS_HIGH = "rx-usecs-high"
        RX_USECS_IRQ = "rx-usecs-irq"
        RX_USECS_LOW = "rx-usecs-low"
        SAMPLE_INTERVAL = "sample-interval"
        STATS_BLOCK_USECS = "stats-block-usecs"
        TX_FRAMES = "tx-frames"
        TX_FRAMES_HIGH = "tx-frames-high"
        TX_FRAMES_IRQ = "tx-frames-irq"
        TX_FRAMES_LOW = "tx-frames-low"
        TX_USECS = "tx-usecs"
        TX_USECS_HIGH = "tx-usecs-high"
        TX_USECS_IRQ = "tx-usecs-irq"
        TX_USECS_LOW = "tx-usecs-low"


class HostNameState:
    KEY = "hostname"
    CONFIG = "config"
    RUNNING = "running"


class Mptcp:
    ADDRESS_FLAGS = "address-flags"
    FLAG_SIGNAL = "signal"
    FLAG_SUBFLOW = "subflow"
    FLAG_BACKUP = "backup"
    FLAG_FULLMESH = "fullmesh"
