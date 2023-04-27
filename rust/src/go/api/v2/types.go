//go:generate ./controller-gen.sh object:headerFile="boilerplate.go.txt" paths="."
package v2

import (
	"k8s.io/apimachinery/pkg/util/intstr"
)

// +k8s:deepcopy-gen=true
type LldpConfig struct {
	Enabled   bool                `json:"enabled"`
	Neighbors [][]LldpNeighborTlv `json:"neighbors,omitempty"`
}

// +k8s:deepcopy-gen=true
type LldpNeighborTlv struct {
	SystemName         string               `json:"system-name,omitempty"`
	SystemDescription  string               `json:"system-description,omitempty"`
	Description        string               `json:"_description,omitempty"`
	SystemCapabilities []intstr.IntOrString `json:"system-capabilities,omitempty"`
	Type               *int                 `json:"type,omitempty"`
	Subtype            *int                 `json:"subtype,omitempty"`
	Oui                string               `json:"oui,omitempty"`
	ChassisId          string               `json:"chassis-id,omitempty"`
	ChassisIdType      *LldpChassisIdType   `json:"chassis-id-type,omitempty"`
	PortId             string               `json:"port-id,omitempty"`
	PortIdType         *LldpPortIdType      `json:"port-id-type,omitempty"`
	Vlans              []LldpVlan           `json:"ieee-802-1-vlans,omitempty"`
	MacPhyConf         *LldpMacPhyConf      `json:"ieee-802-3-mac-phy-conf,omitempty"`
	Ppvids             []int                `json:"ieee-802-1-ppvids,omitempty"`
	MgmtAddrs          []LldpMgmtAddr       `json:"management-addresses,omitempty"`
	MaxFrameSize       int                  `json:"ieee-802-3-max-frame-size,omitempty"`
}

type LldpChassisIdType uint

const LldpChassisIdTypeReserved = 0
const LldpChassisIdTypeChassisComponent = 1
const LldpChassisIdTypeInterfaceAlias = 2
const LldpChassisIdTypePortComponent = 3
const LldpChassisIdTypeMacAddress = 4
const LldpChassisIdTypeNetworkAddress = 5
const LldpChassisIdTypeInterfaceName = 6
const LldpChassisIdTypeLocallyAssigned = 7

type LldpSystemCapability uint

const LldpSystemCapabilityOther = 1
const LldpSystemCapabilityRepeater = 2
const LldpSystemCapabilityMacBridgeComponent = 3
const LldpSystemCapabilityAccessPoint = 4
const LldpSystemCapabilityRouter = 5
const LldpSystemCapabilityTelephone = 6
const LldpSystemCapabilityDocsisCableDevice = 7
const LldpSystemCapabilityStationOnly = 8
const LldpSystemCapabilityCVlanComponent = 9
const LldpSystemCapabilitySVlanComponent = 10
const LldpSystemCapabilityTwoPortMacRelayComponent = 11

type LldpPortIdType uint

const LldpPortIdTypeReserved = 0
const LldpPortIdTypeInterfaceAlias = 1
const LldpPortIdTypePortComponent = 2
const LldpPortIdTypeMacAddress = 3
const LldpPortIdTypeNetworkAddress = 4
const LldpPortIdTypeInterfaceName = 5
const LldpPortIdTypeAgentCircuitId = 6
const LldpPortIdTypeLocallyAssigned = 7

// +k8s:deepcopy-gen=true
type LldpVlan struct {
	Name string `json:"name"`
	Vid  uint32 `json:"vid"`
}

// +k8s:deepcopy-gen=true
type LldpMacPhyConf struct {
	Autoneg            bool   `json:"autoneg"`
	OperationalMauType uint16 `json:"operational-mau-type"`
	PmdAutonegCap      uint16 `json:"pmd-autoneg-cap"`
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

// +k8s:deepcopy-gen=true
type Ieee8021XConfig struct {
	Identity           *string  `json:"identity,omitempty"`
	Eap                []string `json:"eap-methods,omitempty"`
	PrivateKey         *string  `json:"private-key,omitempty"`
	ClientCert         *string  `json:"client-cert,omitempty"`
	CaCert             *string  `json:"ca-cert,omitempty"`
	PrivateKeyPassword *string  `json:"private-key-password,omitempty"`
}

// +k8s:deepcopy-gen=true
type MptcpConfig struct {
	AddressFlags []MptcpAddressFlag `json:"address-flags"`
}

type MptcpAddressFlag string

const MptcpAddressFlagSignal = MptcpAddressFlag("signal")
const MptcpAddressFlagSubflow = MptcpAddressFlag("subflow")
const MptcpAddressFlagBackup = MptcpAddressFlag("backup")
const MptcpAddressFlagFullmesh = MptcpAddressFlag("fullmesh")

// +k8s:deepcopy-gen=true
type OvsDbGlobalConfig struct {
	ExternalIds *map[string]*intstr.IntOrString `json:"external_ids,omitempty"`
	OtherConfig *map[string]*intstr.IntOrString `json:"other_config,omitempty"`
}

// +k8s:deepcopy-gen=true
type OvsDbIfaceConfig struct {
	ExternalIds *map[string]*intstr.IntOrString `json:"external_ids,omitempty"`
	OtherConfig *map[string]*intstr.IntOrString `json:"other_config,omitempty"`
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
const InterfaceTypeMacSec = InterfaceType("macsec")
const InterfaceTypeUnknown = InterfaceType("unknown")
const InterfaceTypeOther = InterfaceType("other")

type InterfaceState string

const InterfaceStateUp = InterfaceState("up")
const InterfaceStateDown = InterfaceState("down")
const InterfaceStateAbsent = InterfaceState("absent")
const InterfaceStateUnknown = InterfaceState("unknown")
const InterfaceStateIgnore = InterfaceState("ignore")

// +k8s:deepcopy-gen=true
type BridgeOptions struct {
	*OvsBridgeOptions   `json:",omitempty"`
	*LinuxBridgeOptions `json:",omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgePortConfigMetadata struct {
	Name string                `json:"name"`
	Vlan *BridgePortVlanConfig `json:"vlan,omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgePortConfig struct {
	BridgePortConfigMetadata `json:""`
	*OvsBridgePortConfig     `json:",omitempty"`
	*LinuxBridgePortConfig   `json:",omitempty"`
}

// +k8s:deepcopy-gen=true
type OvsBridgeConfig struct {
	AllowExtraPatchPorts *bool `json:"allow-extra-patch-ports,omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgeConfig struct {
	*OvsBridgeConfig `json:",omitempty"`
	Options          *BridgeOptions      `json:"options,omitempty"`
	Ports            *[]BridgePortConfig `json:"port,omitempty"`
}

// +k8s:deepcopy-gen=true
type IpSecConfig struct {
	Right          string  `json:"right,omitempty"`
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
type Interface struct {
	BaseInterface `json:",omitempty"`
	Bond          *BondConfig       `json:"link-aggregation,omitempty"`
	Ethernet      *EthernetConfig   `json:"ethernet,omitempty"`
	Veth          *VethConfig       `json:"veth,omitempty"`
	Bridge        *BridgeConfig     `json:"bridge,omitempty"`
	OvsPatch      *OvsPatchConfig   `json:"patch,omitempty"`
	OvsDpdk       *OvsDpdkConfig    `json:"dpdk,omitempty"`
	Vlan          *VlanConfig       `json:"vlan,omitempty"`
	Vxlan         *VxlanConfig      `json:"vxlan,omitempty"`
	MacVlan       *MacVlanConfig    `json:"mac-vlan,omitempty"`
	MacVtap       *MacVtapConfig    `json:"mac-vtap,omitempty"`
	Vrf           *VrfConfig        `json:"vrf,omitempty"`
	InfiniBand    *InfiniBandConfig `json:"infiniband,omitempty"`
	MacSec        *MacSecConfig     `json:"macsec,omitempty"`
	IpSec         *IpSecConfig      `json:"libreswan,omitempty"`
}

type InterfaceIdentifier string

const InterfaceIdentifierName = InterfaceIdentifier("name")
const InterfaceIdentifierMacAddress = InterfaceIdentifier("mac-address")

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
	Running *[]Route `json:"running,omitempty"`
	Config  *[]Route `json:"config,omitempty"`
}

type RouteState string

const RouteStateAbsent = RouteState("absent")

// +k8s:deepcopy-gen=true
type Route struct {
	State        *RouteState `json:"state,omitempty"`
	RouteType    *string     `json:"route-type,omitempty"`
	Destination  *string     `json:"destination,omitempty"`
	NextHopIface *string     `json:"next-hop-interface,omitempty"`
	NextHopAddr  *string     `json:"next-hop-address,omitempty"`
	Metric       *int64      `json:"metric,omitempty"`
	TableId      *uint32     `json:"table-id,omitempty"`
	Weight       *uint16     `json:"weight,omitempty"`
}

// +k8s:deepcopy-gen=true
type RouteRules struct {
	Config *[]RouteRule `json:"config,omitempty"`
}

type RouteRuleState string

const RouteRuleStateAbsent = RouteRuleState("absent")

// +k8s:deepcopy-gen=true
type RouteRule struct {
	Family               *AddressFamily   `json:"family,omitempty"`
	State                *RouteRuleState  `json:"state,omitempty"`
	IpFrom               *string          `json:"ip-from,omitempty"`
	IpTo                 *string          `json:"ip-to,omitempty"`
	Priority             *int64           `json:"priority,omitempty"`
	TableId              *uint32          `json:"route-table,omitempty"`
	Fwmark               *uint32          `json:"fwmark,omitempty"`
	Fwmask               *uint32          `json:"fwmask,omitempty"`
	Action               *RouteRuleAction `json:"action,omitempty"`
	Iif                  *string          `json:"iif,omitempty"`
	SuppressPrefixLength *uint32          `json:"suppress-prefix-length,omitempty"`
}

type RouteRuleAction string

const RouteRuleActionBlackhole = RouteRuleAction("blackhole")
const RouteRuleActionUnreachable = RouteRuleAction("unreachable")
const RouteRuleActionProhibit = RouteRuleAction("prohibit")

// +k8s:deepcopy-gen=true
type InterfaceIp struct {
	Enabled            *bool              `json:"enabled,omitempty"`
	Dhcp               *bool              `json:"dhcp,omitempty"`
	Autoconf           *bool              `json:"autoconf,omitempty"`
	DhcpClientId       *Dhcpv4ClientId    `json:"dhcp-client-id,omitempty"`
	DhcpDuid           *Dhcpv6Duid        `json:"dhcp-duid,omitempty"`
	Addresses          *[]InterfaceIpAddr `json:"address,omitempty"`
	AutoDns            *bool              `json:"auto-dns,omitempty"`
	AutoGateway        *bool              `json:"auto-gateway,omitempty"`
	AutoRoutes         *bool              `json:"auto-routes,omitempty"`
	AutoTableId        *uint32            `json:"auto-route-table-id,omitempty"`
	AutoRouteMetric    *uint32            `json:"auto-route-metric,omitempty"`
	AddrGenMode        *Ipv6AddrGenMode   `json:"addr-gen-mode,omitempty"`
	AllowExtraAddress  *bool              `json:"allow-extra-address,omitempty"`
	Token              *string            `json:"token,omitempty"`
	DhcpSendHostname   *bool              `json:"dhcp-send-hostname,omitempty"`
	DhcpCustomHostname *string            `json:"dhcp-custom-hostname,omitempty"`
}

// +k8s:deepcopy-gen=true
type InterfaceIpAddr struct {
	Ip            string             `json:"ip"`
	PrefixLength  uint8              `json:"prefix-length"`
	MptcpFlags    []MptcpAddressFlag `json:"mptcp-flags,omitempty"`
	ValidLeft     *string            `json:"valid-left,omitempty"`
	PreferredLeft *string            `json:"preferred-left,omitempty"`
}

type Dhcpv4ClientId string

const Dhcpv4ClientIdLinkLayerAddress = Dhcpv4ClientId("link-layer-address")
const Dhcpv4ClientIdIaidPlusDuid = Dhcpv4ClientId("iaid-plus-duid")
const Dhcpv4ClientIdOther = Dhcpv4ClientId("other")

type Dhcpv6Duid string

const Dhcpv6DuidLinkLayerAddressPlusTime = Dhcpv6Duid("link-layer-address-plus-time")
const Dhcpv6DuidEnterpriseNumber = Dhcpv6Duid("enterprise-number")
const Dhcpv6DuidLinkLayerAddress = Dhcpv6Duid("link-layer-address")
const Dhcpv6DuidUuid = Dhcpv6Duid("uuid")
const Dhcpv6DuidOther = Dhcpv6Duid("other")

type Ipv6AddrGenMode string

const Ipv6AddrGenModeEui64 = Ipv6AddrGenMode("eui-64")
const Ipv6AddrGenModeStablePrivacy = Ipv6AddrGenMode("stable-privacy")
const Ipv6AddrGenModeOther = Ipv6AddrGenMode("other")

type WaitIp string

const WaitIpAny = WaitIp("any")
const WaitIpIpv4 = WaitIp("ipv4")
const WaitIpIpv6 = WaitIp("ipv6")
const WaitIpIpv4AndIpv6 = WaitIp("ipv-4-and-ipv-6")

type AddressFamily string

const AddressFamilyIPv4 = AddressFamily("ipv4")
const AddressFamilyIPv6 = AddressFamily("ipv6")
const AddressFamilyUnknown = AddressFamily("unknown")

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

// +k8s:deepcopy-gen=true
type BondPortConfig struct {
	Name     string              `json:"name,omitempty"`
	Priority *intstr.IntOrString `json:"priority,omitempty"`
	QueueId  *uint16             `json:"queue-id,omitempty"`
}

// +k8s:deepcopy-gen=true
type BondConfig struct {
	Mode        *BondMode        `json:"mode,omitempty"`
	Options     *BondOptions     `json:"options,omitempty"`
	Port        []string         `json:"port"`
	PortsConfig []BondPortConfig `json:"ports-config,omitempty"`
}

type BondAdSelect string

const BondAdSelectStable = BondAdSelect("stable")
const BondAdSelectBandwidth = BondAdSelect("bandwidth")
const BondAdSelectCount = BondAdSelect("count")

type BondLacpRate string

const BondLacpRateSlow = BondLacpRate("slow")
const BondLacpRateFast = BondLacpRate("fast")

type BondAllPortsActive string

const BondAllPortsActiveDropped = BondAllPortsActive("dropped")
const BondAllPortsActiveDelivered = BondAllPortsActive("delivered")

type BondArpAllTargets string

const BondArpAllTargetsAny = BondArpAllTargets("any")
const BondArpAllTargetsAll = BondArpAllTargets("all")

type BondArpValidate string

const BondArpValidateNone = BondArpValidate("none")
const BondArpValidateActive = BondArpValidate("active")
const BondArpValidateBackup = BondArpValidate("backup")
const BondArpValidateAll = BondArpValidate("all")
const BondArpValidateFilter = BondArpValidate("filter")
const BondArpValidateFilterActive = BondArpValidate("filter-active")
const BondArpValidateFilterBackup = BondArpValidate("filter-backup")

type BondFailOverMac string

const BondFailOverMacNone = BondFailOverMac("none")
const BondFailOverMacActive = BondFailOverMac("active")
const BondFailOverMacFollow = BondFailOverMac("follow")

type BondPrimaryReselect string

const BondPrimaryReselectAlways = BondPrimaryReselect("always")
const BondPrimaryReselectBetter = BondPrimaryReselect("better")
const BondPrimaryReselectFailure = BondPrimaryReselect("failure")

type BondXmitHashPolicy string

const BondXmitHashPolicyLayer2 = BondXmitHashPolicy("layer-2")
const BondXmitHashPolicyLayer34 = BondXmitHashPolicy("layer-34")
const BondXmitHashPolicyLayer23 = BondXmitHashPolicy("layer-23")
const BondXmitHashPolicyEncap23 = BondXmitHashPolicy("encap-23")
const BondXmitHashPolicyEncap34 = BondXmitHashPolicy("encap-34")
const BondXmitHashPolicyVlanSrcMac = BondXmitHashPolicy("vlan-src-mac")

// +k8s:deepcopy-gen=true
type BondOptions struct {
	AdActorSysPrio  *uint16              `json:"ad_actor_sys_prio,omitempty"`
	AdActorSystem   *string              `json:"ad_actor_system,omitempty"`
	AdSelect        *BondAdSelect        `json:"ad_select,omitempty"`
	AdUserPortKey   *uint16              `json:"ad_user_port_key,omitempty"`
	AllSlavesActive *BondAllPortsActive  `json:"all_slaves_active,omitempty"`
	ArpAllTargets   *BondArpAllTargets   `json:"arp_all_targets,omitempty"`
	ArpInterval     *uint32              `json:"arp_interval,omitempty"`
	ArpIpTarget     *string              `json:"arp_ip_target,omitempty"`
	ArpValidate     *BondArpValidate     `json:"arp_validate,omitempty"`
	Downdelay       *uint32              `json:"downdelay,omitempty"`
	FailOverMac     *BondFailOverMac     `json:"fail_over_mac,omitempty"`
	LacpRate        *BondLacpRate        `json:"lacp_rate,omitempty"`
	LpInterval      *uint32              `json:"lp_interval,omitempty"`
	Miimon          *intstr.IntOrString  `json:"miimon,omitempty"`
	MinLinks        *uint32              `json:"min_links,omitempty"`
	NumGratArp      *uint8               `json:"num_grat_arp,omitempty"`
	NumUnsolNa      *uint8               `json:"num_unsol_na,omitempty"`
	PacketsPerSlave *uint32              `json:"packets_per_slave,omitempty"`
	Primary         *string              `json:"primary,omitempty"`
	PrimaryReselect *BondPrimaryReselect `json:"primary_reselect,omitempty"`
	ResendIgmp      *uint32              `json:"resend_igmp,omitempty"`
	TlbDynamicLb    *bool                `json:"tlb_dynamic_lb,omitempty"`
	Updelay         *uint32              `json:"updelay,omitempty"`
	UseCarrier      *bool                `json:"use_carrier,omitempty"`
	XmitHashPolicy  *BondXmitHashPolicy  `json:"xmit_hash_policy,omitempty"`
	BalanceSlb      *bool                `json:"balance_slb,omitempty"`
	ArpMissedMax    *uint8               `json:"arp_missed_max,omitempty"`
}

// +k8s:deepcopy-gen=true
type LinuxBridgePortConfig struct {
	StpHairpinMode *bool   `json:"stp-hairpin-mode,omitempty"`
	StpPathCost    *uint32 `json:"stp-path-cost,omitempty"`
	StpPriority    *uint16 `json:"stp-priority,omitempty"`
}

// +k8s:deepcopy-gen=true
type LinuxBridgeOptions struct {
	GcTimer                        *uint64                `json:"gc-timer,omitempty"`
	GroupAddr                      *string                `json:"group-addr,omitempty"`
	GroupForwardMask               *uint16                `json:"group-forward-mask,omitempty"`
	GroupFwdMask                   *uint16                `json:"group-fwd-mask,omitempty"`
	HashMax                        *uint32                `json:"hash-max,omitempty"`
	HelloTimer                     *uint64                `json:"hello-timer,omitempty"`
	MacAgeingTime                  *uint32                `json:"mac-ageing-time,omitempty"`
	MulticastLastMemberCount       *uint32                `json:"multicast-last-member-count,omitempty"`
	MulticastLastMemberInterval    *uint64                `json:"multicast-last-member-interval,omitempty"`
	MulticastMembershipInterval    *uint64                `json:"multicast-membership-interval,omitempty"`
	MulticastQuerier               *bool                  `json:"multicast-querier,omitempty"`
	MulticastQuerierInterval       *uint64                `json:"multicast-querier-interval,omitempty"`
	MulticastQueryInterval         *uint64                `json:"multicast-query-interval,omitempty"`
	MulticastQueryResponseInterval *uint64                `json:"multicast-query-response-interval,omitempty"`
	MulticastQueryUseIfaddr        *bool                  `json:"multicast-query-use-ifaddr,omitempty"`
	MulticastRouter                *intstr.IntOrString    `json:"multicast-router,omitempty"`
	MulticastSnooping              *bool                  `json:"multicast-snooping,omitempty"`
	MulticastStartupQueryCount     *uint32                `json:"multicast-startup-query-count,omitempty"`
	MulticastStartupQueryInterval  *uint64                `json:"multicast-startup-query-interval,omitempty"`
	Stp                            *LinuxBridgeStpOptions `json:"stp,omitempty"`
	VlanProtocol                   *VlanProtocol          `json:"vlan-protocol,omitempty"`
	VlanDefaultPvid                *uint16                `json:"vlan-default-pvid,omitempty"`
}

// +k8s:deepcopy-gen=true
type LinuxBridgeStpOptions struct {
	Enabled      *bool   `json:"enabled,omitempty"`
	ForwardDelay *uint8  `json:"forward-delay,omitempty"`
	HelloTime    *uint8  `json:"hello-time,omitempty"`
	MaxAge       *uint8  `json:"max-age,omitempty"`
	Priority     *uint16 `json:"priority,omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgePortVlanConfig struct {
	EnableNative *bool                 `json:"enable-native,omitempty"`
	Mode         *BridgePortVlanMode   `json:"mode,omitempty"`
	Tag          *uint16               `json:"tag,omitempty"`
	TrunkTags    *[]BridgePortTrunkTag `json:"trunk-tags,omitempty"`
}

type BridgePortVlanMode string

const BridgePortVlanModeTrunk = BridgePortVlanMode("trunk")
const BridgePortVlanModeAccess = BridgePortVlanMode("access")

// +k8s:deepcopy-gen=true
type BridgePortTrunkTag struct {
	Id      uint16               `json:"id,omitempty"`
	IdRange *BridgePortVlanRange `json:"id-range,omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgePortVlanRange struct {
	Min uint16 `json:"min"`
	Max uint16 `json:"max"`
}

// +k8s:deepcopy-gen=true
type OvsBridgeStpOptions struct {
	Enabled       *bool `json:"enabled,omitempty"`
	marshalNested bool  `json:"-"`
}

// +k8s:deepcopy-gen=true
type OvsBridgeOptions struct {
	Rstp                *bool                `json:"rstp,omitempty"`
	McastSnoopingEnable *bool                `json:"mcast-snooping-enable,omitempty"`
	FailMode            *string              `json:"fail-mode,omitempty"`
	Datapath            *string              `json:"datapath,omitempty"`
	Stp                 *OvsBridgeStpOptions `json:"stp,omitempty"`
}

// +k8s:deepcopy-gen=true
type OvsBridgePortConfig struct {
	Bond *OvsBridgeBondConfig `json:"link-aggregation,omitempty"`
}

// +k8s:deepcopy-gen=true
type OvsBridgeBondConfig struct {
	Mode          *OvsBridgeBondMode        `json:"mode,omitempty"`
	Ports         []OvsBridgeBondPortConfig `json:"port,omitempty"`
	BondDowndelay *uint32                   `json:"bond-downdelay,omitempty"`
	BondUpdelay   *uint32                   `json:"bond-updelay,omitempty"`
	Ovsdb         *OvsDbIfaceConfig         `json:"ovs-db,omitempty"`
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

// +k8s:deepcopy-gen=true
type VxlanInterface struct {
	Vxlan *VxlanConfig `json:"vxlan,omitempty"`
}

// +k8s:deepcopy-gen=true
type VxlanConfig struct {
	BaseIface string  `json:"base-iface,omitempty"`
	Id        uint32  `json:"id"`
	Learning  *bool   `json:"learning,omitempty"`
	Local     *string `json:"local,omitempty"`
	Remote    *string `json:"remote,omitempty"`
	DstPort   *uint16 `json:"destination-port,omitempty"`
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

// +k8s:deepcopy-gen=true
type VrfInterface struct {
	Vrf *VrfConfig `json:"vrf,omitempty"`
}

// +k8s:deepcopy-gen=true
type VrfConfig struct {
	Port    []string `json:"port"`
	TableId *uint32  `json:"route-table-id"`
}

// +k8s:deepcopy-gen=true
type InfiniBandInterface struct {
	Ib *InfiniBandConfig `json:"infiniband,omitempty"`
}

type InfiniBandMode string

const InfiniBandModeDatagram = InfiniBandMode("datagram")
const InfiniBandModeConnected = InfiniBandMode("connected")

// +k8s:deepcopy-gen=true
type InfiniBandConfig struct {
	Mode      InfiniBandMode `json:"mode"`
	BaseIface *string        `json:"base-iface,omitempty"`
	Pkey      *string        `json:"pkey,omitempty"`
}

type MacSecValidate string

const (
	MacSecValidateDisabled = "disabled"
	MacSecValidateCheck    = "check"
	MacSecValidateStrict   = "strict"
)

// +k8s:deepcopy-gen=true
type MacSecConfig struct {
	Encrypt    *bool           `json:"encrypt,omitempty"`
	BaseIface  *string         `json:"base-iface,omitempty"`
	MkaCak     *string         `json:"mka-cak,omitempty"`
	MkaCkn     *string         `json:"mka-ckn,omitempty"`
	Port       *uint32         `json:"port,omitempty"`
	Validation *MacSecValidate `json:"validation,omitempty"`
	SendSci    *bool           `json:"send-sci,omitempty"`
}

// +k8s:deepcopy-gen=true
type LoopbackInterface struct {
}

// +k8s:deepcopy-gen=true
type SrIovConfig struct {
	TotalVfs *uint32         `json:"total-vfs,omitempty"`
	Vfs      []SrIovVfConfig `json:"vfs,omitempty"`
}

// +k8s:deepcopy-gen=true
type SrIovVfConfig struct {
	Id         uint32  `json:"id"`
	MacAddress *string `json:"mac-address,omitempty"`
	SpoofCheck *bool   `json:"spoof-check,omitempty"`
	Trust      *bool   `json:"trust,omitempty"`
	MinTxRate  *uint32 `json:"min-tx-rate,omitempty"`
	MaxTxRate  *uint32 `json:"max-tx-rate,omitempty"`
	VlanId     *uint32 `json:"vlan-id,omitempty"`
	Qos        *uint32 `json:"qos,omitempty"`
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
	AdaptiveRx      *bool   `json:"adaptive-rx,omitempty"`
	AdaptiveTx      *bool   `json:"adaptive-tx,omitempty"`
	PktRateHigh     *uint32 `json:"pkt-rate-high,omitempty"`
	PktRateLow      *uint32 `json:"pkt-rate-low,omitempty"`
	RxFrames        *uint32 `json:"rx-frames,omitempty"`
	RxFramesHigh    *uint32 `json:"rx-frames-high,omitempty"`
	RxFramesIrq     *uint32 `json:"rx-frames-irq,omitempty"`
	RxFramesLow     *uint32 `json:"rx-frames-low,omitempty"`
	RxUsecs         *uint32 `json:"rx-usecs,omitempty"`
	RxUsecsHigh     *uint32 `json:"rx-usecs-high,omitempty"`
	RxUsecsIrq      *uint32 `json:"rx-usecs-irq,omitempty"`
	RxUsecsLow      *uint32 `json:"rx-usecs-low,omitempty"`
	SampleInterval  *uint32 `json:"sample-interval,omitempty"`
	StatsBlockUsecs *uint32 `json:"stats-block-usecs,omitempty"`
	TxFrames        *uint32 `json:"tx-frames,omitempty"`
	TxFramesHigh    *uint32 `json:"tx-frames-high,omitempty"`
	TxFramesIrq     *uint32 `json:"tx-frames-irq,omitempty"`
	TxFramesLow     *uint32 `json:"tx-frames-low,omitempty"`
	TxUsecs         *uint32 `json:"tx-usecs,omitempty"`
	TxUsecsHigh     *uint32 `json:"tx-usecs-high,omitempty"`
	TxUsecsIrq      *uint32 `json:"tx-usecs-irq,omitempty"`
	TxUsecsLow      *uint32 `json:"tx-usecs-low,omitempty"`
}

// +k8s:deepcopy-gen=true
type EthtoolRingConfig struct {
	Rx         *uint32 `json:"rx,omitempty"`
	RxMax      *uint32 `json:"rx-max,omitempty"`
	RxJumbo    *uint32 `json:"rx-jumbo,omitempty"`
	RxJumboMax *uint32 `json:"rx-jumbo-max,omitempty"`
	RxMini     *uint32 `json:"rx-mini,omitempty"`
	RxMiniMax  *uint32 `json:"rx-mini-max,omitempty"`
	Tx         *uint32 `json:"tx,omitempty"`
	TxMax      *uint32 `json:"tx-max,omitempty"`
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
	Mtu                   *uint64             `json:"mtu,omitempty"`
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
}

// +k8s:deepcopy-gen=true
type EthernetInterface struct {
	Ethernet *EthernetConfig `json:"ethernet,omitempty"`
	Veth     *VethConfig     `json:"veth,omitempty"`
}

type EthernetDuplex string

const EthernetDuplexFull = EthernetDuplex("full")
const EthernetDuplexHalf = EthernetDuplex("half")

// +k8s:deepcopy-gen=true
type EthernetConfig struct {
	SrIov   *SrIovConfig    `json:"sr-iov,omitempty"`
	AutoNeg *bool           `json:"auto-negotiation,omitempty"`
	Speed   *uint32         `json:"speed,omitempty"`
	Duplex  *EthernetDuplex `json:"duplex,omitempty"`
}

// +k8s:deepcopy-gen=true
type VethConfig struct {
	Peer string `json:"peer"`
}

type OvnBridgeMappingState string

const OvnBridgeMappingStatePresent = OvnBridgeMappingState("present")
const OvnBridgeMappingStateAbsent = OvnBridgeMappingState("absent")

// +k8s:deepcopy-gen=true
type OvnBridgeMapping struct {
	Localnet string                `json:"localnet,omitempty"`
	State    OvnBridgeMappingState `json:"state,omitempty"`
	Bridge   string                `json:"bridge,omitempty"`
}

// +k8s:deepcopy-gen=true
type OvnConfiguration struct {
	BridgeMapping []OvnBridgeMapping `json:"bridge-mappings,omitempty"`
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
