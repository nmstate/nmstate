package v2

import (
	"k8s.io/apimachinery/pkg/util/intstr"
)

// +k8s:deepcopy-gen=true
type LldpConfig struct {
	Enabled   bool                `json:"enabled"`
	Neighbors [][]LldpNeighborTlv `json:"neighbors,omitempty"`
}

type LldpNeighborTlv string

const LldpNeighborTlvSystemName = LldpNeighborTlv("system-name")
const LldpNeighborTlvSystemDescription = LldpNeighborTlv("system-description")
const LldpNeighborTlvSystemCapabilities = LldpNeighborTlv("system-capabilities")
const LldpNeighborTlvChassisId = LldpNeighborTlv("chassis-id")
const LldpNeighborTlvPortId = LldpNeighborTlv("port-id")
const LldpNeighborTlvIeee8021Vlans = LldpNeighborTlv("ieee-8021-vlans")
const LldpNeighborTlvIeee8023MacPhyConf = LldpNeighborTlv("ieee-8023-mac-phy-conf")
const LldpNeighborTlvIeee8021Ppvids = LldpNeighborTlv("ieee-8021-ppvids")
const LldpNeighborTlvManagementAddresses = LldpNeighborTlv("management-addresses")
const LldpNeighborTlvIeee8023MaxFrameSize = LldpNeighborTlv("ieee-8023-max-frame-size")

// enum LldpNeighborTlv

// +k8s:deepcopy-gen=true
type LldpSystemName struct {
}

// +k8s:deepcopy-gen=true
type LldpSystemDescription struct {
}

// +k8s:deepcopy-gen=true
type LldpChassisId struct {
	Id     string            `json:"id"`
	IdType LldpChassisIdType `json:"id_type"`
}

type LldpChassisIdType string

const LldpChassisIdTypeReserved = LldpChassisIdType("reserved")
const LldpChassisIdTypeChassisComponent = LldpChassisIdType("chassis-component")
const LldpChassisIdTypeInterfaceAlias = LldpChassisIdType("interface-alias")
const LldpChassisIdTypePortComponent = LldpChassisIdType("port-component")
const LldpChassisIdTypeMacAddress = LldpChassisIdType("mac-address")
const LldpChassisIdTypeNetworkAddress = LldpChassisIdType("network-address")
const LldpChassisIdTypeInterfaceName = LldpChassisIdType("interface-name")
const LldpChassisIdTypeLocallyAssigned = LldpChassisIdType("locally-assigned")

// enum LldpChassisIdType

// +k8s:deepcopy-gen=true
type LldpSystemCapabilities struct {
}

type LldpSystemCapability string

const LldpSystemCapabilityOther = LldpSystemCapability("other")
const LldpSystemCapabilityRepeater = LldpSystemCapability("repeater")
const LldpSystemCapabilityMacBridgeComponent = LldpSystemCapability("mac-bridge-component")
const LldpSystemCapabilityAccessPoint = LldpSystemCapability("access-point")
const LldpSystemCapabilityRouter = LldpSystemCapability("router")
const LldpSystemCapabilityTelephone = LldpSystemCapability("telephone")
const LldpSystemCapabilityDocsisCableDevice = LldpSystemCapability("docsis-cable-device")
const LldpSystemCapabilityStationOnly = LldpSystemCapability("station-only")
const LldpSystemCapabilityCVlanComponent = LldpSystemCapability("c-vlan-component")
const LldpSystemCapabilitySVlanComponent = LldpSystemCapability("s-vlan-component")
const LldpSystemCapabilityTwoPortMacRelayComponent = LldpSystemCapability("two-port-mac-relay-component")

// enum LldpSystemCapability

// +k8s:deepcopy-gen=true
type LldpPortId struct {
	Id     string         `json:"id"`
	IdType LldpPortIdType `json:"id_type"`
}

type LldpPortIdType string

const LldpPortIdTypeReserved = LldpPortIdType("reserved")
const LldpPortIdTypeInterfaceAlias = LldpPortIdType("interface-alias")
const LldpPortIdTypePortComponent = LldpPortIdType("port-component")
const LldpPortIdTypeMacAddress = LldpPortIdType("mac-address")
const LldpPortIdTypeNetworkAddress = LldpPortIdType("network-address")
const LldpPortIdTypeInterfaceName = LldpPortIdType("interface-name")
const LldpPortIdTypeAgentCircuitId = LldpPortIdType("agent-circuit-id")
const LldpPortIdTypeLocallyAssigned = LldpPortIdType("locally-assigned")

// enum LldpPortIdType

// +k8s:deepcopy-gen=true
type LldpVlans struct {
}

// +k8s:deepcopy-gen=true
type LldpVlan struct {
	Name string `json:"name"`
	Vid  uint32 `json:"vid"`
}

// +k8s:deepcopy-gen=true
type LldpMacPhyConf struct {
	Autoneg            bool   `json:"autoneg"`
	OperationalMauType uint16 `json:"operational_mau_type"`
	PmdAutonegCap      uint16 `json:"pmd_autoneg_cap"`
}

// +k8s:deepcopy-gen=true
type _LldpMacPhyConf struct {
	Autoneg            bool   `json:"autoneg"`
	OperationalMauType uint16 `json:"operational-mau-type"`
	PmdAutonegCap      uint16 `json:"pmd-autoneg-cap"`
}

// +k8s:deepcopy-gen=true
type LldpPpvids struct {
}

// +k8s:deepcopy-gen=true
type LldpMgmtAddrs struct {
}

// +k8s:deepcopy-gen=true
type LldpMgmtAddr struct {
	Address                string            `json:"address"`
	AddressSubtype         LldpAddressFamily `json:"address-subtype"`
	InterfaceNumber        uint32            `json:"interface-number"`
	InterfaceNumberSubtype uint32            `json:"interface-number-subtype"`
}

type LldpAddressFamily string

const LldpAddressFamilyUnknown = LldpAddressFamily("unknown")
const LldpAddressFamilyIpv4 = LldpAddressFamily("ipv4")
const LldpAddressFamilyIpv6 = LldpAddressFamily("ipv6")
const LldpAddressFamilyMac = LldpAddressFamily("mac")

// enum LldpAddressFamily

// +k8s:deepcopy-gen=true
type LldpMaxFrameSize struct {
}

// +k8s:deepcopy-gen=true
type Ieee8021XConfig struct {
	Identity           *string   `json:"identity,omitempty"`
	Eap                *[]string `json:"eap-methods,omitempty"`
	PrivateKey         *string   `json:"private-key,omitempty"`
	ClientCert         *string   `json:"client-cert,omitempty"`
	CaCert             *string   `json:"ca-cert,omitempty"`
	PrivateKeyPassword *string   `json:"private-key-password,omitempty"`
}

// +k8s:deepcopy-gen=true
type MptcpConfig struct {
	AddressFlags *[]MptcpAddressFlag `json:"address-flags,omitempty"`
}

type MptcpAddressFlag string

const MptcpAddressFlagSignal = MptcpAddressFlag("signal")
const MptcpAddressFlagSubflow = MptcpAddressFlag("subflow")
const MptcpAddressFlagBackup = MptcpAddressFlag("backup")
const MptcpAddressFlagFullmesh = MptcpAddressFlag("fullmesh")

// enum MptcpAddressFlag

// +k8s:deepcopy-gen=true
type OvsDbGlobalConfig struct {
	ExternalIds *map[string]*string `json:"external_ids,omitempty"`
	OtherConfig *map[string]*string `json:"other_config,omitempty"`
}

// +k8s:deepcopy-gen=true
type OvsDbIfaceConfig struct {
	ExternalIds *map[string]*string `json:"external_ids,omitempty"`
	OtherConfig *map[string]*string `json:"other_config,omitempty"`
}

type InterfaceType string

const InterfaceTypeBond = InterfaceType("bond")
const InterfaceTypeLinuxBridge = InterfaceType("linux-bridge")
const InterfaceTypeDummy = InterfaceType("dummy")
const InterfaceTypeEthernet = InterfaceType("ethernet")
const InterfaceTypeLoopback = InterfaceType("loopback")
const InterfaceTypeMacVlan = InterfaceType("mac-vlan")
const InterfaceTypeMacVtap = InterfaceType("mac-vtap")
const InterfaceTypeOvsBridge = InterfaceType("ovs-bridge")
const InterfaceTypeOvsInterface = InterfaceType("ovs-interface")
const InterfaceTypeVeth = InterfaceType("veth")
const InterfaceTypeVlan = InterfaceType("vlan")
const InterfaceTypeVrf = InterfaceType("vrf")
const InterfaceTypeVxlan = InterfaceType("vxlan")
const InterfaceTypeInfiniBand = InterfaceType("infiniband")
const InterfaceTypeTun = InterfaceType("tun")
const InterfaceTypeMacSec = InterfaceType("mac-sec")
const InterfaceTypeIpsec = InterfaceType("ipsec")
const InterfaceTypeUnknown = InterfaceType("unknown")
const InterfaceTypeOther = InterfaceType("other")

// enum InterfaceType

type InterfaceState string

const InterfaceStateUp = InterfaceState("up")
const InterfaceStateDown = InterfaceState("down")
const InterfaceStateAbsent = InterfaceState("absent")
const InterfaceStateUnknown = InterfaceState("unknown")
const InterfaceStateIgnore = InterfaceState("ignore")

// enum InterfaceState

// +k8s:deepcopy-gen=true
type UnknownInterface struct {
	Other string `json:"other,omitempty"`
}

// +k8s:deepcopy-gen=true
type OvsBridgeStpOptions struct {
	Enabled *bool `json:"enabled,omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgePortConfigMetaData struct {
	Name string                `json:"name"`
	Vlan *BridgePortVlanConfig `json:"vlan,omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgePortConfig struct {
	BridgePortConfigMetaData `json:""`
	*OvsBridgePortConfig     `json:",omitempty"`
	*LinuxBridgePortConfig   `json:",omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgeOptions struct {
	*LinuxBridgeOptions `json:",omitempty"`
	*OvsBridgeOptions   `json:",omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgeConfig struct {
	*OvsBridgeConfig `json:",omitempty"`
	Options          *BridgeOptions      `json:"options,omitempty"`
	Ports            *[]BridgePortConfig `json:"port,omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgeInterface struct {
	*BridgeConfig `json:"bridge,omitempty"`
}

// +k8s:deepcopy-gen=true
type Interface struct {
	BaseInterface        `json:",omitempty"`
	*BridgeInterface     `json:",omitempty"`
	*BondInterface       `json:",omitempty"`
	*EthernetInterface   `json:",omitempty"`
	*OvsInterface        `json:",omitempty"`
	*VlanInterface       `json:",omitempty"`
	*VxlanInterface      `json:",omitempty"`
	*MacVlanInterface    `json:",omitempty"`
	*MacVtapInterface    `json:",omitempty"`
	*VrfInterface        `json:",omitempty"`
	*InfiniBandInterface `json:",omitempty"`
	*MacSecInterface     `json:",omitempty"`
	*IpsecInterface      `json:",omitempty"`
}

type InterfaceIdentifier string

const InterfaceIdentifierName = InterfaceIdentifier("name")
const InterfaceIdentifierMacAddress = InterfaceIdentifier("mac-address")

// enum InterfaceIdentifier

// +k8s:deepcopy-gen=true
type DnsState struct {
	Running *DnsClientState `json:"running,omitempty"`
	Config  *DnsClientState `json:"config,omitempty"`
}

// +k8s:deepcopy-gen=true
type DnsClientState struct {
	Server  *[]string `json:"server,omitempty"`
	Search  *[]string `json:"search,omitempty"`
	Options *[]string `json:"options,omitempty"`
}

// +k8s:deepcopy-gen=true
type Routes struct {
	Running *[]RouteEntry `json:"running,omitempty"`
	Config  *[]RouteEntry `json:"config,omitempty"`
}

type RouteState string

const RouteStateAbsent = RouteState("absent")

// enum RouteState

// +k8s:deepcopy-gen=true
type RouteEntry struct {
	State        *RouteState         `json:"state,omitempty"`
	Destination  *string             `json:"destination,omitempty"`
	NextHopIface *string             `json:"next-hop-interface,omitempty"`
	NextHopAddr  *string             `json:"next-hop-address,omitempty"`
	Metric       *intstr.IntOrString `json:"metric,omitempty"`
	TableId      *intstr.IntOrString `json:"table-id,omitempty"`
	Weight       *intstr.IntOrString `json:"weight,omitempty"`
	RouteType    *RouteType          `json:"route-type,omitempty"`
}

type RouteType string

const RouteTypeBlackhole = RouteType("blackhole")
const RouteTypeUnreachable = RouteType("unreachable")
const RouteTypeProhibit = RouteType("prohibit")

// enum RouteType

// +k8s:deepcopy-gen=true
type RouteRules struct {
	Config *[]RouteRuleEntry `json:"config,omitempty"`
}

type RouteRuleState string

const RouteRuleStateAbsent = RouteRuleState("absent")

// enum RouteRuleState

// +k8s:deepcopy-gen=true
type RouteRuleEntry struct {
	Family               *AddressFamily      `json:"family,omitempty"`
	State                *RouteRuleState     `json:"state,omitempty"`
	IpFrom               *string             `json:"ip-from,omitempty"`
	IpTo                 *string             `json:"ip-to,omitempty"`
	Priority             *intstr.IntOrString `json:"priority,omitempty"`
	TableId              *intstr.IntOrString `json:"route-table,omitempty"`
	Fwmark               *intstr.IntOrString `json:"fwmark,omitempty"`
	Fwmask               *intstr.IntOrString `json:"fwmask,omitempty"`
	Action               *RouteRuleAction    `json:"action,omitempty"`
	Iif                  *string             `json:"iif,omitempty"`
	SuppressPrefixLength *uint32             `json:"suppress-prefix-length,omitempty"`
}

type RouteRuleAction string

const RouteRuleActionBlackhole = RouteRuleAction("blackhole")
const RouteRuleActionUnreachable = RouteRuleAction("unreachable")
const RouteRuleActionProhibit = RouteRuleAction("prohibit")

// enum RouteRuleAction

// +k8s:deepcopy-gen=true
type InterfaceIp struct {
	Enabled            *bool               `json:"enabled,omitempty"`
	Dhcp               *bool               `json:"dhcp,omitempty"`
	Autoconf           *bool               `json:"autoconf,omitempty"`
	DhcpClientId       *Dhcpv4ClientId     `json:"dhcp-client-id,omitempty"`
	DhcpDuid           *Dhcpv6Duid         `json:"dhcp-duid,omitempty"`
	Addresses          *[]InterfaceIpAddr  `json:"address,omitempty"`
	AutoDns            *bool               `json:"auto-dns,omitempty"`
	AutoGateway        *bool               `json:"auto-gateway,omitempty"`
	AutoRoutes         *bool               `json:"auto-routes,omitempty"`
	AutoTableId        *intstr.IntOrString `json:"auto-route-table-id,omitempty"`
	AutoRouteMetric    *intstr.IntOrString `json:"auto-route-metric,omitempty"`
	AddrGenMode        *Ipv6AddrGenMode    `json:"addr-gen-mode,omitempty"`
	AllowExtraAddress  *bool               `json:"allow-extra-address,omitempty"`
	Token              *string             `json:"token,omitempty"`
	DhcpSendHostname   *bool               `json:"dhcp-send-hostname,omitempty"`
	DhcpCustomHostname *string             `json:"dhcp-custom-hostname,omitempty"`
}

// +k8s:deepcopy-gen=true
type InterfaceIpAddr struct {
	Ip            string              `json:"ip"`
	PrefixLength  uint8               `json:"prefix-length"`
	MptcpFlags    *[]MptcpAddressFlag `json:"mptcp-flags,omitempty"`
	ValidLeft     *string             `json:"valid-left,omitempty"`
	PreferredLeft *string             `json:"preferred-left,omitempty"`
}

type Dhcpv4ClientId string

const Dhcpv4ClientIdLinkLayerAddress = Dhcpv4ClientId("link-layer-address")
const Dhcpv4ClientIdIaidPlusDuid = Dhcpv4ClientId("iaid-plus-duid")
const Dhcpv4ClientIdOther = Dhcpv4ClientId("other")

// enum Dhcpv4ClientId

type Dhcpv6Duid string

const Dhcpv6DuidLinkLayerAddressPlusTime = Dhcpv6Duid("link-layer-address-plus-time")
const Dhcpv6DuidEnterpriseNumber = Dhcpv6Duid("enterprise-number")
const Dhcpv6DuidLinkLayerAddress = Dhcpv6Duid("link-layer-address")
const Dhcpv6DuidUuid = Dhcpv6Duid("uuid")
const Dhcpv6DuidOther = Dhcpv6Duid("other")

// enum Dhcpv6Duid

type Ipv6AddrGenMode string

const Ipv6AddrGenModeEui64 = Ipv6AddrGenMode("eui-64")
const Ipv6AddrGenModeStablePrivacy = Ipv6AddrGenMode("stable-privacy")
const Ipv6AddrGenModeOther = Ipv6AddrGenMode("other")

// enum Ipv6AddrGenMode

type WaitIp string

const WaitIpAny = WaitIp("any")
const WaitIpIpv4 = WaitIp("ipv4")
const WaitIpIpv6 = WaitIp("ipv6")
const WaitIpIpv4AndIpv6 = WaitIp("ipv-4-and-ipv-6")

// enum WaitIp

type AddressFamily string

const AddressFamilyIPv4 = AddressFamily("ipv4")
const AddressFamilyIPv6 = AddressFamily("ipv6")
const AddressFamilyUnknown = AddressFamily("unknown")

// enum AddressFamily

// +k8s:deepcopy-gen=true
type HostNameState struct {
	Running *string `json:"running,omitempty"`
	Config  *string `json:"config,omitempty"`
}

// +k8s:deepcopy-gen=true
type BondInterface struct {
	Bond *BondConfig `json:"link-aggregation,omitempty"`
}

type BondMode string

const BondModeRoundRobin = BondMode("round-robin")
const BondModeActiveBackup = BondMode("active-backup")
const BondModeXOR = BondMode("xor")
const BondModeBroadcast = BondMode("broadcast")
const BondModeLACP = BondMode("lacp")
const BondModeTLB = BondMode("tlb")
const BondModeALB = BondMode("alb")
const BondModeUnknown = BondMode("unknown")

// enum BondMode

// +k8s:deepcopy-gen=true
type BondConfig struct {
	Mode        *BondMode         `json:"mode,omitempty"`
	Options     *BondOptions      `json:"options,omitempty"`
	Port        *[]string         `json:"port,omitempty"`
	PortsConfig *[]BondPortConfig `json:"ports-config,omitempty"`
}

type BondAdSelect string

const BondAdSelectStable = BondAdSelect("stable")
const BondAdSelectBandwidth = BondAdSelect("bandwidth")
const BondAdSelectCount = BondAdSelect("count")

// enum BondAdSelect

type BondLacpRate string

const BondLacpRateSlow = BondLacpRate("slow")
const BondLacpRateFast = BondLacpRate("fast")

// enum BondLacpRate

type BondAllPortsActive string

const BondAllPortsActiveDropped = BondAllPortsActive("dropped")
const BondAllPortsActiveDelivered = BondAllPortsActive("delivered")

// enum BondAllPortsActive

type BondArpAllTargets string

const BondArpAllTargetsAny = BondArpAllTargets("any")
const BondArpAllTargetsAll = BondArpAllTargets("all")

// enum BondArpAllTargets

type BondArpValidate string

const BondArpValidateNone = BondArpValidate("none")
const BondArpValidateActive = BondArpValidate("active")
const BondArpValidateBackup = BondArpValidate("backup")
const BondArpValidateAll = BondArpValidate("all")
const BondArpValidateFilter = BondArpValidate("filter")
const BondArpValidateFilterActive = BondArpValidate("filter-active")
const BondArpValidateFilterBackup = BondArpValidate("filter-backup")

// enum BondArpValidate

type BondFailOverMac string

const BondFailOverMacNone = BondFailOverMac("none")
const BondFailOverMacActive = BondFailOverMac("active")
const BondFailOverMacFollow = BondFailOverMac("follow")

// enum BondFailOverMac

type BondPrimaryReselect string

const BondPrimaryReselectAlways = BondPrimaryReselect("always")
const BondPrimaryReselectBetter = BondPrimaryReselect("better")
const BondPrimaryReselectFailure = BondPrimaryReselect("failure")

// enum BondPrimaryReselect

type BondXmitHashPolicy string

const BondXmitHashPolicyLayer2 = BondXmitHashPolicy("layer-2")
const BondXmitHashPolicyLayer34 = BondXmitHashPolicy("layer-34")
const BondXmitHashPolicyLayer23 = BondXmitHashPolicy("layer-23")
const BondXmitHashPolicyEncap23 = BondXmitHashPolicy("encap-23")
const BondXmitHashPolicyEncap34 = BondXmitHashPolicy("encap-34")
const BondXmitHashPolicyVlanSrcMac = BondXmitHashPolicy("vlan-src-mac")

// enum BondXmitHashPolicy

// +k8s:deepcopy-gen=true
type BondOptions struct {
	AdActorSysPrio  *intstr.IntOrString  `json:"ad_actor_sys_prio,omitempty"`
	AdActorSystem   *string              `json:"ad_actor_system,omitempty"`
	AdSelect        *BondAdSelect        `json:"ad_select,omitempty"`
	AdUserPortKey   *intstr.IntOrString  `json:"ad_user_port_key,omitempty"`
	AllSlavesActive *BondAllPortsActive  `json:"all_slaves_active,omitempty"`
	ArpAllTargets   *BondArpAllTargets   `json:"arp_all_targets,omitempty"`
	ArpInterval     *intstr.IntOrString  `json:"arp_interval,omitempty"`
	ArpIpTarget     *string              `json:"arp_ip_target,omitempty"`
	ArpValidate     *BondArpValidate     `json:"arp_validate,omitempty"`
	Downdelay       *intstr.IntOrString  `json:"downdelay,omitempty"`
	FailOverMac     *BondFailOverMac     `json:"fail_over_mac,omitempty"`
	LacpRate        *BondLacpRate        `json:"lacp_rate,omitempty"`
	LpInterval      *intstr.IntOrString  `json:"lp_interval,omitempty"`
	Miimon          *intstr.IntOrString  `json:"miimon,omitempty"`
	MinLinks        *intstr.IntOrString  `json:"min_links,omitempty"`
	NumGratArp      *intstr.IntOrString  `json:"num_grat_arp,omitempty"`
	NumUnsolNa      *intstr.IntOrString  `json:"num_unsol_na,omitempty"`
	PacketsPerSlave *intstr.IntOrString  `json:"packets_per_slave,omitempty"`
	Primary         *string              `json:"primary,omitempty"`
	PrimaryReselect *BondPrimaryReselect `json:"primary_reselect,omitempty"`
	ResendIgmp      *intstr.IntOrString  `json:"resend_igmp,omitempty"`
	TlbDynamicLb    *bool                `json:"tlb_dynamic_lb,omitempty"`
	Updelay         *intstr.IntOrString  `json:"updelay,omitempty"`
	UseCarrier      *bool                `json:"use_carrier,omitempty"`
	XmitHashPolicy  *BondXmitHashPolicy  `json:"xmit_hash_policy,omitempty"`
	BalanceSlb      *bool                `json:"balance_slb,omitempty"`
	ArpMissedMax    *intstr.IntOrString  `json:"arp_missed_max,omitempty"`
}

// +k8s:deepcopy-gen=true
type BondPortConfig struct {
	Name     string              `json:"name"`
	Priority *intstr.IntOrString `json:"priority,omitempty"`
	QueueId  *intstr.IntOrString `json:"queue-id,omitempty"`
}

// +k8s:deepcopy-gen=true
type DummyInterface struct {
}

// +k8s:deepcopy-gen=true
type LinuxBridgeConfig struct {
	Options *LinuxBridgeOptions      `json:"options,omitempty"`
	Port    *[]LinuxBridgePortConfig `json:"port,omitempty"`
}

// +k8s:deepcopy-gen=true
type LinuxBridgePortConfig struct {
	StpHairpinMode *bool               `json:"stp-hairpin-mode,omitempty"`
	StpPathCost    *intstr.IntOrString `json:"stp-path-cost,omitempty"`
	StpPriority    *intstr.IntOrString `json:"stp-priority,omitempty"`
}

// +k8s:deepcopy-gen=true
type LinuxBridgeOptions struct {
	GcTimer                        *uint64                         `json:"gc-timer,omitempty"`
	GroupAddr                      *string                         `json:"group-addr,omitempty"`
	GroupForwardMask               *intstr.IntOrString             `json:"group-forward-mask,omitempty"`
	GroupFwdMask                   *intstr.IntOrString             `json:"group-fwd-mask,omitempty"`
	HashMax                        *intstr.IntOrString             `json:"hash-max,omitempty"`
	HelloTimer                     *uint64                         `json:"hello-timer,omitempty"`
	MacAgeingTime                  *intstr.IntOrString             `json:"mac-ageing-time,omitempty"`
	MulticastLastMemberCount       *intstr.IntOrString             `json:"multicast-last-member-count,omitempty"`
	MulticastLastMemberInterval    *intstr.IntOrString             `json:"multicast-last-member-interval,omitempty"`
	MulticastMembershipInterval    *intstr.IntOrString             `json:"multicast-membership-interval,omitempty"`
	MulticastQuerier               *bool                           `json:"multicast-querier,omitempty"`
	MulticastQuerierInterval       *intstr.IntOrString             `json:"multicast-querier-interval,omitempty"`
	MulticastQueryInterval         *intstr.IntOrString             `json:"multicast-query-interval,omitempty"`
	MulticastQueryResponseInterval *intstr.IntOrString             `json:"multicast-query-response-interval,omitempty"`
	MulticastQueryUseIfaddr        *bool                           `json:"multicast-query-use-ifaddr,omitempty"`
	MulticastRouter                *LinuxBridgeMulticastRouterType `json:"multicast-router,omitempty"`
	MulticastSnooping              *bool                           `json:"multicast-snooping,omitempty"`
	MulticastStartupQueryCount     *intstr.IntOrString             `json:"multicast-startup-query-count,omitempty"`
	MulticastStartupQueryInterval  *intstr.IntOrString             `json:"multicast-startup-query-interval,omitempty"`
	Stp                            *LinuxBridgeStpOptions          `json:"stp,omitempty"`
	VlanProtocol                   *VlanProtocol                   `json:"vlan-protocol,omitempty"`
	VlanDefaultPvid                *uint16                         `json:"vlan-default-pvid,omitempty"`
}

// +k8s:deepcopy-gen=true
type LinuxBridgeStpOptions struct {
	Enabled      *bool               `json:"enabled,omitempty"`
	ForwardDelay *intstr.IntOrString `json:"forward-delay,omitempty"`
	HelloTime    *intstr.IntOrString `json:"hello-time,omitempty"`
	MaxAge       *intstr.IntOrString `json:"max-age,omitempty"`
	Priority     *intstr.IntOrString `json:"priority,omitempty"`
}

type LinuxBridgeMulticastRouterType string

const LinuxBridgeMulticastRouterTypeAuto = LinuxBridgeMulticastRouterType("auto")
const LinuxBridgeMulticastRouterTypeDisabled = LinuxBridgeMulticastRouterType("disabled")
const LinuxBridgeMulticastRouterTypeEnabled = LinuxBridgeMulticastRouterType("enabled")

// enum LinuxBridgeMulticastRouterType

// +k8s:deepcopy-gen=true
type BridgePortVlanConfig struct {
	EnableNative *bool                 `json:"enable-native,omitempty"`
	Mode         *BridgePortVlanMode   `json:"mode,omitempty"`
	Tag          *intstr.IntOrString   `json:"tag,omitempty"`
	TrunkTags    *[]BridgePortTrunkTag `json:"trunk-tags,omitempty"`
}

type BridgePortVlanMode string

const BridgePortVlanModeTrunk = BridgePortVlanMode("trunk")
const BridgePortVlanModeAccess = BridgePortVlanMode("access")

// enum BridgePortVlanMode

// +k8s:deepcopy-gen=true
type BridgePortTrunkTag struct {
	Id      *uint16              `json:"id,omitempty"`
	IdRange *BridgePortVlanRange `json:"id-range,omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgePortVlanRange struct {
	Min uint16 `json:"min"`
	Max uint16 `json:"max"`
}

// +k8s:deepcopy-gen=true
type OvsBridgeConfig struct {
	AllowExtraPatchPorts *bool `json:"allow-extra-patch-ports,omitempty"`
}

// +k8s:deepcopy-gen=true
type OvsBridgeOptions struct {
	Stp                 *OvsBridgeStpOptions `json:"stp,omitempty"`
	Rstp                *bool                `json:"rstp,omitempty"`
	McastSnoopingEnable *bool                `json:"mcast-snooping-enable,omitempty"`
	FailMode            *string              `json:"fail-mode,omitempty"`
	Datapath            *string              `json:"datapath,omitempty"`
}

// +k8s:deepcopy-gen=true
type OvsBridgePortConfig struct {
	Bond *OvsBridgeBondConfig `json:"link-aggregation,omitempty"`
}

// +k8s:deepcopy-gen=true
type OvsInterface struct {
	Patch *OvsPatchConfig `json:"patch,omitempty"`
	Dpdk  *OvsDpdkConfig  `json:"dpdk,omitempty"`
}

// +k8s:deepcopy-gen=true
type OvsBridgeBondConfig struct {
	Mode          *OvsBridgeBondMode         `json:"mode,omitempty"`
	Ports         *[]OvsBridgeBondPortConfig `json:"port,omitempty"`
	BondDowndelay *intstr.IntOrString        `json:"bond-downdelay,omitempty"`
	BondUpdelay   *intstr.IntOrString        `json:"bond-updelay,omitempty"`
	Ovsdb         *OvsDbIfaceConfig          `json:"ovs-db,omitempty"`
}

// +k8s:deepcopy-gen=true
type OvsBridgeBondPortConfig struct {
	Name string `json:"name"`
}

type OvsBridgeBondMode string

const OvsBridgeBondModeActiveBackup = OvsBridgeBondMode("active-backup")
const OvsBridgeBondModeBalanceSlb = OvsBridgeBondMode("balance-slb")
const OvsBridgeBondModeBalanceTcp = OvsBridgeBondMode("balance-tcp")
const OvsBridgeBondModeLacp = OvsBridgeBondMode("lacp")

// enum OvsBridgeBondMode

// +k8s:deepcopy-gen=true
type OvsPatchConfig struct {
	Peer string `json:"peer"`
}

// +k8s:deepcopy-gen=true
type OvsDpdkConfig struct {
	Devargs  string  `json:"devargs"`
	RxQueue  *uint32 `json:"rx-queue,omitempty"`
	NRxqDesc *uint32 `json:"n_rxq_desc,omitempty"`
	NTxqDesc *uint32 `json:"n_txq_desc,omitempty"`
}

// +k8s:deepcopy-gen=true
type VlanInterface struct {
	Vlan *VlanConfig `json:"vlan,omitempty"`
}

// +k8s:deepcopy-gen=true
type VlanConfig struct {
	BaseIface string        `json:"base-iface"`
	Id        uint16        `json:"id"`
	Protocol  *VlanProtocol `json:"protocol,omitempty"`
}

type VlanProtocol string

const VlanProtocolIeee8021Q = VlanProtocol("ieee-8021-q")
const VlanProtocolIeee8021Ad = VlanProtocol("ieee-8021-ad")

// enum VlanProtocol

// +k8s:deepcopy-gen=true
type VxlanInterface struct {
	Vxlan *VxlanConfig `json:"vxlan,omitempty"`
}

// +k8s:deepcopy-gen=true
type VxlanConfig struct {
	BaseIface string              `json:"base-iface,omitempty"`
	Id        uint32              `json:"id"`
	Learning  *bool               `json:"learning,omitempty"`
	Local     *string             `json:"local,omitempty"`
	Remote    *string             `json:"remote,omitempty"`
	DstPort   *intstr.IntOrString `json:"destination-port,omitempty"`
}

// +k8s:deepcopy-gen=true
type MacVlanInterface struct {
	MacVlan *MacVlanConfig `json:"mac-vlan,omitempty"`
}

// +k8s:deepcopy-gen=true
type MacVlanConfig struct {
	BaseIface    string      `json:"base-iface"`
	Mode         MacVlanMode `json:"mode"`
	AcceptAllMac *bool       `json:"promiscuous,omitempty"`
}

type MacVlanMode string

const MacVlanModeVepa = MacVlanMode("vepa")
const MacVlanModeBridge = MacVlanMode("bridge")
const MacVlanModePrivate = MacVlanMode("private")
const MacVlanModePassthru = MacVlanMode("passthru")
const MacVlanModeSource = MacVlanMode("source")
const MacVlanModeUnknown = MacVlanMode("unknown")

// enum MacVlanMode

// +k8s:deepcopy-gen=true
type MacVtapInterface struct {
	MacVtap *MacVtapConfig `json:"mac-vtap,omitempty"`
}

// +k8s:deepcopy-gen=true
type MacVtapConfig struct {
	BaseIface    string      `json:"base-iface"`
	Mode         MacVtapMode `json:"mode"`
	AcceptAllMac *bool       `json:"promiscuous,omitempty"`
}

type MacVtapMode string

const MacVtapModeVepa = MacVtapMode("vepa")
const MacVtapModeBridge = MacVtapMode("bridge")
const MacVtapModePrivate = MacVtapMode("private")
const MacVtapModePassthru = MacVtapMode("passthru")
const MacVtapModeSource = MacVtapMode("source")
const MacVtapModeUnknown = MacVtapMode("unknown")

// enum MacVtapMode

// +k8s:deepcopy-gen=true
type VrfInterface struct {
	Vrf *VrfConfig `json:"vrf,omitempty"`
}

// +k8s:deepcopy-gen=true
type VrfConfig struct {
	Port    *[]string `json:"port"`
	TableId uint32    `json:"route-table-id"`
}

// +k8s:deepcopy-gen=true
type InfiniBandInterface struct {
	Ib *InfiniBandConfig `json:"infiniband,omitempty"`
}

type InfiniBandMode string

const InfiniBandModeDatagram = InfiniBandMode("datagram")
const InfiniBandModeConnected = InfiniBandMode("connected")

// enum InfiniBandMode

// +k8s:deepcopy-gen=true
type InfiniBandConfig struct {
	Mode      InfiniBandMode      `json:"mode"`
	BaseIface *string             `json:"base-iface,omitempty"`
	Pkey      *intstr.IntOrString `json:"pkey,omitempty"`
}

// +k8s:deepcopy-gen=true
type LoopbackInterface struct {
}

// +k8s:deepcopy-gen=true
type SrIovConfig struct {
	TotalVfs *intstr.IntOrString `json:"total-vfs,omitempty"`
	Vfs      *[]SrIovVfConfig    `json:"vfs,omitempty"`
}

// +k8s:deepcopy-gen=true
type SrIovVfConfig struct {
	Id         uint32              `json:"id"`
	IfaceName  string              `json:"iface-name,omitempty"`
	MacAddress *string             `json:"mac-address,omitempty"`
	SpoofCheck *bool               `json:"spoof-check,omitempty"`
	Trust      *bool               `json:"trust,omitempty"`
	MinTxRate  *intstr.IntOrString `json:"min-tx-rate,omitempty"`
	MaxTxRate  *intstr.IntOrString `json:"max-tx-rate,omitempty"`
	VlanId     *intstr.IntOrString `json:"vlan-id,omitempty"`
	Qos        *intstr.IntOrString `json:"qos,omitempty"`
}

// +k8s:deepcopy-gen=true
type EthtoolFeatureConfig struct {
	Data map[string]bool `json:"data"`
}

// +k8s:deepcopy-gen=true
type EthtoolConfig struct {
	Pause    *EthtoolPauseConfig    `json:"pause,omitempty"`
	Feature  map[string]bool        `json:"feature,omitempty"`
	Coalesce *EthtoolCoalesceConfig `json:"coalesce,omitempty"`
	Ring     *EthtoolRingConfig     `json:"ring,omitempty"`
}

// +k8s:deepcopy-gen=true
type EthtoolPauseConfig struct {
	Rx      *bool `json:"rx,omitempty"`
	Tx      *bool `json:"tx,omitempty"`
	Autoneg *bool `json:"autoneg,omitempty"`
}

// +k8s:deepcopy-gen=true
type EthtoolCoalesceConfig struct {
	AdaptiveRx      *bool               `json:"adaptive-rx,omitempty"`
	AdaptiveTx      *bool               `json:"adaptive-tx,omitempty"`
	PktRateHigh     *intstr.IntOrString `json:"pkt-rate-high,omitempty"`
	PktRateLow      *intstr.IntOrString `json:"pkt-rate-low,omitempty"`
	RxFrames        *intstr.IntOrString `json:"rx-frames,omitempty"`
	RxFramesHigh    *intstr.IntOrString `json:"rx-frames-high,omitempty"`
	RxFramesIrq     *intstr.IntOrString `json:"rx-frames-irq,omitempty"`
	RxFramesLow     *intstr.IntOrString `json:"rx-frames-low,omitempty"`
	RxUsecs         *intstr.IntOrString `json:"rx-usecs,omitempty"`
	RxUsecsHigh     *intstr.IntOrString `json:"rx-usecs-high,omitempty"`
	RxUsecsIrq      *intstr.IntOrString `json:"rx-usecs-irq,omitempty"`
	RxUsecsLow      *intstr.IntOrString `json:"rx-usecs-low,omitempty"`
	SampleInterval  *intstr.IntOrString `json:"sample-interval,omitempty"`
	StatsBlockUsecs *intstr.IntOrString `json:"stats-block-usecs,omitempty"`
	TxFrames        *intstr.IntOrString `json:"tx-frames,omitempty"`
	TxFramesHigh    *intstr.IntOrString `json:"tx-frames-high,omitempty"`
	TxFramesIrq     *intstr.IntOrString `json:"tx-frames-irq,omitempty"`
	TxFramesLow     *intstr.IntOrString `json:"tx-frames-low,omitempty"`
	TxUsecs         *intstr.IntOrString `json:"tx-usecs,omitempty"`
	TxUsecsHigh     *intstr.IntOrString `json:"tx-usecs-high,omitempty"`
	TxUsecsIrq      *intstr.IntOrString `json:"tx-usecs-irq,omitempty"`
	TxUsecsLow      *intstr.IntOrString `json:"tx-usecs-low,omitempty"`
}

// +k8s:deepcopy-gen=true
type EthtoolRingConfig struct {
	Rx         *intstr.IntOrString `json:"rx,omitempty"`
	RxMax      *intstr.IntOrString `json:"rx-max,omitempty"`
	RxJumbo    *intstr.IntOrString `json:"rx-jumbo,omitempty"`
	RxJumboMax *intstr.IntOrString `json:"rx-jumbo-max,omitempty"`
	RxMini     *intstr.IntOrString `json:"rx-mini,omitempty"`
	RxMiniMax  *intstr.IntOrString `json:"rx-mini-max,omitempty"`
	Tx         *intstr.IntOrString `json:"tx,omitempty"`
	TxMax      *intstr.IntOrString `json:"tx-max,omitempty"`
}

// +k8s:deepcopy-gen=true
type BaseInterface struct {
	Name                  string              `json:"name"`
	ProfileName           *string             `json:"profile-name,omitempty"`
	Description           *string             `json:"description,omitempty"`
	Type                  InterfaceType       `json:"type,omitempty"`
	State                 InterfaceState      `json:"state,omitempty"`
	Identifier            InterfaceIdentifier `json:"identifier,omitempty"`
	MacAddress            *string             `json:"mac-address,omitempty"`
	Mtu                   *intstr.IntOrString `json:"mtu,omitempty"`
	MinMtu                *uint64             `json:"min-mtu,omitempty"`
	MaxMtu                *uint64             `json:"max-mtu,omitempty"`
	WaitIp                *WaitIp             `json:"wait-ip,omitempty"`
	Ipv4                  *InterfaceIp        `json:"ipv4,omitempty"`
	Ipv6                  *InterfaceIp        `json:"ipv6,omitempty"`
	Mptcp                 *MptcpConfig        `json:"mptcp,omitempty"`
	Controller            *string             `json:"controller,omitempty"`
	AcceptAllMacAddresses *bool               `json:"accept-all-mac-addresses,omitempty"`
	CopyMacFrom           *string             `json:"copy-mac-from,omitempty"`
	Ovsdb                 *OvsDbIfaceConfig   `json:"ovs-db,omitempty"`
	Ieee8021X             *Ieee8021XConfig    `json:"802.1x,omitempty"`
	Lldp                  *LldpConfig         `json:"lldp,omitempty"`
	Ethtool               *EthtoolConfig      `json:"ethtool,omitempty"`
	Dispatch              *DispatchConfig     `json:"dispatch,omitempty"`
}

// +k8s:deepcopy-gen=true
type EthernetInterface struct {
	Ethernet *EthernetConfig `json:"ethernet,omitempty"`
	Veth     *VethConfig     `json:"veth,omitempty"`
}

type EthernetDuplex string

const EthernetDuplexFull = EthernetDuplex("full")
const EthernetDuplexHalf = EthernetDuplex("half")

// enum EthernetDuplex

// +k8s:deepcopy-gen=true
type EthernetConfig struct {
	SrIov   *SrIovConfig        `json:"sr-iov,omitempty"`
	AutoNeg *bool               `json:"auto-negotiation,omitempty"`
	Speed   *intstr.IntOrString `json:"speed,omitempty"`
	Duplex  *EthernetDuplex     `json:"duplex,omitempty"`
}

// +k8s:deepcopy-gen=true
type VethConfig struct {
	Peer string `json:"peer"`
}

// +k8s:deepcopy-gen=true
type MacSecInterface struct {
	Macsec *MacSecConfig `json:"macsec,omitempty"`
}

// +k8s:deepcopy-gen=true
type MacSecConfig struct {
	Encrypt    bool           `json:"encrypt"`
	BaseIface  string         `json:"base-iface"`
	MkaCak     *string        `json:"mka-cak,omitempty"`
	MkaCkn     *string        `json:"mka-ckn,omitempty"`
	Port       uint32         `json:"port"`
	Validation MacSecValidate `json:"validation"`
	SendSci    bool           `json:"send-sci"`
}

type MacSecValidate string

const MacSecValidateDisabled = MacSecValidate("disabled")
const MacSecValidateCheck = MacSecValidate("check")
const MacSecValidateStrict = MacSecValidate("strict")

// enum MacSecValidate

// +k8s:deepcopy-gen=true
type IpsecInterface struct {
	Libreswan *LibreswanConfig `json:"libreswan,omitempty"`
}

// +k8s:deepcopy-gen=true
type LibreswanConfig struct {
	Right          string  `json:"right"`
	Rightid        *string `json:"rightid,omitempty"`
	Rightrsasigkey *string `json:"rightrsasigkey,omitempty"`
	Left           *string `json:"left,omitempty"`
	Leftid         *string `json:"leftid,omitempty"`
	Leftrsasigkey  *string `json:"leftrsasigkey,omitempty"`
	Leftcert       *string `json:"leftcert,omitempty"`
	Ikev2          *string `json:"ikev2,omitempty"`
	Psk            *string `json:"psk,omitempty"`
	Ikelifetime    *string `json:"ikelifetime,omitempty"`
	Salifetime     *string `json:"salifetime,omitempty"`
	Ike            *string `json:"ike,omitempty"`
	Esp            *string `json:"esp,omitempty"`
}

// +k8s:deepcopy-gen=true
type NetworkState struct {
	Hostname   *HostNameState     `json:"hostname,omitempty"`
	Dns        *DnsState          `json:"dns-resolver,omitempty"`
	Rules      *RouteRules        `json:"route-rules,omitempty"`
	Routes     *Routes            `json:"routes,omitempty"`
	Interfaces []Interface        `json:"interfaces,omitempty"`
	Ovsdb      *OvsDbGlobalConfig `json:"ovs-db,omitempty"`
	Ovn        *OvnConfiguration  `json:"ovn,omitempty"`
}

// +k8s:deepcopy-gen=true
type OvnConfiguration struct {
	BridgeMappings *[]OvnBridgeMapping `json:"bridge-mappings,omitempty"`
}

// +k8s:deepcopy-gen=true
type OvnBridgeMapping struct {
	Localnet string                 `json:"localnet"`
	State    *OvnBridgeMappingState `json:"state,omitempty"`
	Bridge   *string                `json:"bridge,omitempty"`
}

type OvnBridgeMappingState string

const OvnBridgeMappingStatePresent = OvnBridgeMappingState("present")
const OvnBridgeMappingStateAbsent = OvnBridgeMappingState("absent")

// enum OvnBridgeMappingState

// +k8s:deepcopy-gen=true
type DispatchConfig struct {
	PostActivation   *string `json:"post-activation,omitempty"`
	PostDeactivation *string `json:"post-deactivation,omitempty"`
}
