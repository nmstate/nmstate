/*
Copyright The NMState Authors.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

package v2

import (
	"k8s.io/apimachinery/pkg/util/intstr"
)

// +kubebuilder:validation:Enum=1;2;5;6;7;8;127;
type LldpNeighborTlvType uint8

const LldpNeighborTlvTypeChassisID = LldpNeighborTlvType(1)
const LldpNeighborTlvTypePort = LldpNeighborTlvType(2)
const LldpNeighborTlvTypeSystemName = LldpNeighborTlvType(5)
const LldpNeighborTlvTypeSystemDescription = LldpNeighborTlvType(6)
const LldpNeighborTlvTypeSystemCapabilities = LldpNeighborTlvType(7)
const LldpNeighborTlvTypeManagementAddress = LldpNeighborTlvType(8)
const LldpNeighborTlvTypeOrganizationSpecific = LldpNeighborTlvType(127)

// enum LldpNeighborTlvType

// +kubebuilder:validation:Enum=3;1;2;4;
type LldpOrgSubtype uint8

const LldpOrgSubtypeVlan = LldpOrgSubtype(3)
const LldpOrgSubtypeMacPhyConf = LldpOrgSubtype(1)
const LldpOrgSubtypePpvids = LldpOrgSubtype(2)
const LldpOrgSubtypeMaxFrameSize = LldpOrgSubtype(4)

// enum LldpOrgSubtype

// +kubebuilder:validation:Enum="00:80:c2";"00:12:0f";"00:80:c2";"00:12:0f";
type LldpOrgOiu string

const LldpOrgOiuVlan = LldpOrgOiu("00:80:c2")
const LldpOrgOiuMacPhyConf = LldpOrgOiu("00:12:0f")
const LldpOrgOiuPpvids = LldpOrgOiu("00:80:c2")
const LldpOrgOiuMaxFrameSize = LldpOrgOiu("00:12:0f")

// enum LldpOrgOiu

// +k8s:deepcopy-gen=true
type LldpConfig struct {
	Enabled   bool                `json:"enabled"`
	Neighbors [][]LldpNeighborTlv `json:"neighbors,omitempty"`
}

// +k8s:deepcopy-gen=true
type LldpNeighborTlv struct {
	*LldpSystemName         `json:",omitempty"`
	*LldpSystemDescription  `json:",omitempty"`
	*LldpSystemCapabilities `json:",omitempty"`
	*LldpChassisID          `json:",omitempty"`
	*LldpPortID             `json:",omitempty"`
	*LldpVlans              `json:",omitempty"`
	*LldpMacPhy             `json:",omitempty"`
	*LldpPpvids             `json:",omitempty"`
	*LldpMgmtAddrs          `json:",omitempty"`
	*LldpMaxFrameSize       `json:",omitempty"`
}

// +k8s:deepcopy-gen=true
type LldpSystemName struct {
	Ty         *LldpNeighborTlvType `json:"type,omitempty"`
	SystemName *string              `json:"system-name,omitempty"`
}

// +k8s:deepcopy-gen=true
type LldpSystemDescription struct {
	Ty                *LldpNeighborTlvType `json:"type,omitempty"`
	SystemDescription *string              `json:"system-description,omitempty"`
}

// +k8s:deepcopy-gen=true
type LldpChassisID struct {
	Ty            *LldpNeighborTlvType `json:"type,omitempty"`
	ChassisID     *string              `json:"chassis-id,omitempty"`
	ChassisIDType *LldpChassisIDType   `json:"chassis-id-type,omitempty"`
	Description   *string              `json:"_description,omitempty"`
}

// +kubebuilder:validation:Enum=0;1;2;3;4;5;6;7;
type LldpChassisIDType uint8

const LldpChassisIDTypeReserved = LldpChassisIDType(0)
const LldpChassisIDTypeChassisComponent = LldpChassisIDType(1)
const LldpChassisIDTypeInterfaceAlias = LldpChassisIDType(2)
const LldpChassisIDTypePortComponent = LldpChassisIDType(3)
const LldpChassisIDTypeMacAddress = LldpChassisIDType(4)
const LldpChassisIDTypeNetworkAddress = LldpChassisIDType(5)
const LldpChassisIDTypeInterfaceName = LldpChassisIDType(6)
const LldpChassisIDTypeLocallyAssigned = LldpChassisIDType(7)

// enum LldpChassisIDType

// +k8s:deepcopy-gen=true
type LldpSystemCapabilities struct {
	Ty                 *LldpNeighborTlvType    `json:"type,omitempty"`
	SystemCapabilities *[]LldpSystemCapability `json:"system-capabilities,omitempty"`
}

type LldpSystemCapability string

const LldpSystemCapabilityRepeater = LldpSystemCapability("Repeater")
const LldpSystemCapabilityMacBridgeComponent = LldpSystemCapability("MAC Bridge component")
const LldpSystemCapabilityAccessPoint = LldpSystemCapability("802.11 Access Point (AP)")
const LldpSystemCapabilityRouter = LldpSystemCapability("Router")
const LldpSystemCapabilityTelephone = LldpSystemCapability("Telephone")
const LldpSystemCapabilityDocsisCableDevice = LldpSystemCapability("DOCSIS cable device")
const LldpSystemCapabilityStationOnly = LldpSystemCapability("Station Only")
const LldpSystemCapabilityCVlanComponent = LldpSystemCapability("C-VLAN component")
const LldpSystemCapabilitySVlanComponent = LldpSystemCapability("S-VLAN component")
const LldpSystemCapabilityTwoPortMacRelayComponent = LldpSystemCapability("Two-port MAC Relay component")

// enum LldpSystemCapability

// +k8s:deepcopy-gen=true
type LldpPortID struct {
	Ty          *LldpNeighborTlvType `json:"type,omitempty"`
	PortID      *string              `json:"port-id,omitempty"`
	PortIDType  *LldpPortIDType      `json:"port-id-type,omitempty"`
	Description *string              `json:"_description,omitempty"`
}

// +kubebuilder:validation:Enum=0;1;2;3;4;5;6;7;
type LldpPortIDType uint8

const LldpPortIDTypeReserved = LldpPortIDType(0)
const LldpPortIDTypeInterfaceAlias = LldpPortIDType(1)
const LldpPortIDTypePortComponent = LldpPortIDType(2)
const LldpPortIDTypeMacAddress = LldpPortIDType(3)
const LldpPortIDTypeNetworkAddress = LldpPortIDType(4)
const LldpPortIDTypeInterfaceName = LldpPortIDType(5)
const LldpPortIDTypeAgentCircuitID = LldpPortIDType(6)
const LldpPortIDTypeLocallyAssigned = LldpPortIDType(7)

// enum LldpPortIDType

// +k8s:deepcopy-gen=true
type LldpVlans struct {
	Ty            *LldpNeighborTlvType `json:"type,omitempty"`
	Ieee8021Vlans *[]LldpVlan          `json:"ieee-802-1-vlans,omitempty"`
	Oui           *LldpOrgOiu          `json:"oui,omitempty"`
	Subtype       *LldpOrgSubtype      `json:"subtype,omitempty"`
}

// +k8s:deepcopy-gen=true
type LldpVlan struct {
	Name *string `json:"name,omitempty"`
	Vid  *uint32 `json:"vid,omitempty"`
}

// +k8s:deepcopy-gen=true
type LldpMacPhy struct {
	Ty                 *LldpNeighborTlvType `json:"type,omitempty"`
	Ieee8023MacPhyConf *LldpMacPhyConf      `json:"ieee-802-3-mac-phy-conf,omitempty"`
	Oui                *LldpOrgOiu          `json:"oui,omitempty"`
	Subtype            *LldpOrgSubtype      `json:"subtype,omitempty"`
}

// +k8s:deepcopy-gen=true
type LldpMacPhyConf struct {
	Autoneg            *bool   `json:"autoneg,omitempty"`
	OperationalMauType *uint16 `json:"operational-mau-type,omitempty"`
	PmdAutonegCap      *uint16 `json:"pmd-autoneg-cap,omitempty"`
}

// +k8s:deepcopy-gen=true
type LldpPpvids struct {
	Ty             *LldpNeighborTlvType `json:"type,omitempty"`
	Ieee8021Ppvids *[]uint32            `json:"ieee-802-1-ppvids,omitempty"`
	Oui            *LldpOrgOiu          `json:"oui,omitempty"`
	Subtype        *LldpOrgSubtype      `json:"subtype,omitempty"`
}

// +k8s:deepcopy-gen=true
type LldpMgmtAddrs struct {
	Ty                  *LldpNeighborTlvType `json:"type,omitempty"`
	ManagementAddresses *[]LldpMgmtAddr      `json:"management-addresses,omitempty"`
}

// +k8s:deepcopy-gen=true
type LldpMgmtAddr struct {
	Address                *string            `json:"address,omitempty"`
	AddressSubtype         *LldpAddressFamily `json:"address-subtype,omitempty"`
	InterfaceNumber        *uint32            `json:"interface-number,omitempty"`
	InterfaceNumberSubtype *uint32            `json:"interface-number-subtype,omitempty"`
}

// +kubebuilder:validation:Enum="Unknown";"IPv4";"IPv6";"MAC";
type LldpAddressFamily string

const LldpAddressFamilyUnknown = LldpAddressFamily("Unknown")
const LldpAddressFamilyIpv4 = LldpAddressFamily("IPv4")
const LldpAddressFamilyIpv6 = LldpAddressFamily("IPv6")
const LldpAddressFamilyMac = LldpAddressFamily("MAC")

// enum LldpAddressFamily

// +k8s:deepcopy-gen=true
type LldpMaxFrameSize struct {
	Ty                   *LldpNeighborTlvType `json:"type,omitempty"`
	Ieee8023MaxFrameSize *uint32              `json:"ieee-802-3-max-frame-size,omitempty"`
	Oui                  *LldpOrgOiu          `json:"oui,omitempty"`
	Subtype              *LldpOrgSubtype      `json:"subtype,omitempty"`
}

// Ieee8021XConfig  The IEEE 802.1X authentication configuration. The example yaml output of
// [crate::NetworkState] with IEEE 802.1X authentication interface:
// ```yml
// ---
// interfaces:
//   - name: eth1
//     type: ethernet
//     state: up
//     802.1x:
//     ca-cert: /etc/pki/802-1x-test/ca.crt
//     client-cert: /etc/pki/802-1x-test/client.example.org.crt
//     eap-methods:
//   - tls
//     identity: client.example.org
//     private-key: /etc/pki/802-1x-test/client.example.org.key
//     private-key-password: password
//
// ```
// +k8s:deepcopy-gen=true
type Ieee8021XConfig struct {
	Identity *string `json:"identity,omitempty"`
	// Eap  Deserialize and serialize from/to `eap-methods`.
	Eap *[]string `json:"eap-methods,omitempty"`
	// PrivateKey  Deserialize and serialize from/to `private-key`.
	PrivateKey *string `json:"private-key,omitempty"`
	// ClientCert  Deserialize and serialize from/to `client-cert`.
	ClientCert *string `json:"client-cert,omitempty"`
	// CaCert  Deserialize and serialize from/to `ca-cert`.
	CaCert *string `json:"ca-cert,omitempty"`
	// PrivateKeyPassword  Deserialize and serialize from/to `private-key-password`.
	// Replaced to `<_password_hid_by_nmstate>` when querying.
	PrivateKeyPassword *string `json:"private-key-password,omitempty"`
}

// +k8s:deepcopy-gen=true
type MptcpConfig struct {
	// AddressFlags  Automatically assign MPTCP flags to all valid IP addresses of this
	// interface including both static and dynamic ones.
	AddressFlags *[]MptcpAddressFlag `json:"address-flags,omitempty"`
}

// +kubebuilder:validation:Enum="signal";"subflow";"backup";"fullmesh";
type MptcpAddressFlag string

// MptcpAddressFlagSignal  The endpoint will be announced/signaled to each peer via an MPTCP
// ADD_ADDR sub-option. Upon reception of an ADD_ADDR sub-option, the
// peer can try to create additional subflows. Cannot used along with
// MptcpAddressFlag::Fullmesh as Linux kernel enforced.
const MptcpAddressFlagSignal = MptcpAddressFlag("signal")

// MptcpAddressFlagSubflow  If additional subflow creation is allowed by the MPTCP limits, the
// MPTCP path manager will try to create an additional subflow using
// this endpoint as the source address after the MPTCP connection is
// established.
const MptcpAddressFlagSubflow = MptcpAddressFlag("subflow")

// MptcpAddressFlagBackup  If this is a subflow endpoint, the subflows created using this endpoint
// will have the backup flag set during the connection process. This flag
// instructs the peer to only send data on a given subflow when all
// non-backup subflows are unavailable. This does not affect outgoing
// data, where subflow priority is determined by the backup/non-backup
// flag received from the peer.
const MptcpAddressFlagBackup = MptcpAddressFlag("backup")

// MptcpAddressFlagFullmesh  If this is a subflow endpoint and additional subflow creation is
// allowed by the MPTCP limits, the MPTCP path manager will try to
// create an additional subflow for each known peer address, using
// this endpoint as the source address. This will occur after the
// MPTCP connection is established. If the peer did not announce any
// additional addresses using the MPTCP ADD_ADDR sub-option, this will
// behave the same as a plain subflow endpoint.  When the peer does
// announce addresses, each received ADD_ADDR sub-option will trigger
// creation of an additional subflow to generate a full mesh topology.
const MptcpAddressFlagFullmesh = MptcpAddressFlag("fullmesh")

// enum MptcpAddressFlag

// +k8s:deepcopy-gen=true
type OVSDBGlobalConfig struct {
	ExternalIds *map[string]*intstr.IntOrString `json:"external_ids,omitempty"`
	OtherConfig *map[string]*intstr.IntOrString `json:"other_config,omitempty"`
}

// +k8s:deepcopy-gen=true
type OVSDBIfaceConfig struct {
	ExternalIds *map[string]*intstr.IntOrString `json:"external_ids,omitempty"`
	// OtherConfig  OpenvSwitch specific `other_config`. Please refer to
	// manpage `ovs-vswitchd.conf.db(5)` for more detail.
	// When setting to None, nmstate will try to preserve current
	// `other_config`, otherwise, nmstate will override all `other_config`
	// for specified interface.
	OtherConfig *map[string]*intstr.IntOrString `json:"other_config,omitempty"`
}

// InterfaceType  Interface type
// +kubebuilder:validation:Enum="bond";"linux-bridge";"dummy";"ethernet";"hsr";"loopback";"mac-vlan";"mac-vtap";"ovs-bridge";"ovs-interface";"veth";"vlan";"vrf";"vxlan";"infiniband";"tun";"macsec";"ipsec";"xfrm";"unknown";
type InterfaceType string

// InterfaceTypeBond  [Bond interface](https://www.kernel.org/doc/Documentation/networking/bonding.txt)
// Deserialize and serialize from/to 'bond'
const InterfaceTypeBond = InterfaceType("bond")

// InterfaceTypeLinuxBridge  Bridge provided by Linux kernel.
// Deserialize and serialize from/to 'linux-bridge'.
const InterfaceTypeLinuxBridge = InterfaceType("linux-bridge")

// InterfaceTypeDummy  Dummy interface.
// Deserialize and serialize from/to 'dummy'.
const InterfaceTypeDummy = InterfaceType("dummy")

// InterfaceTypeEthernet  Ethernet interface.
// Deserialize and serialize from/to 'ethernet'.
const InterfaceTypeEthernet = InterfaceType("ethernet")

// InterfaceTypeHsr  HSR interface.
// Deserialize and serialize from/to 'hsr'.
const InterfaceTypeHsr = InterfaceType("hsr")

// InterfaceTypeLoopback  Loopback interface.
// Deserialize and serialize from/to 'loopback'.
const InterfaceTypeLoopback = InterfaceType("loopback")

// InterfaceTypeMacVlan  MAC VLAN interface.
// Deserialize and serialize from/to 'mac-vlan'.
const InterfaceTypeMacVlan = InterfaceType("mac-vlan")

// InterfaceTypeMacVtap  MAC VTAP interface.
// Deserialize and serialize from/to 'mac-vtap'.
const InterfaceTypeMacVtap = InterfaceType("mac-vtap")

// InterfaceTypeOVSBridge  OpenvSwitch bridge.
// Deserialize and serialize from/to 'ovs-bridge'.
const InterfaceTypeOVSBridge = InterfaceType("ovs-bridge")

// InterfaceTypeOVSInterface  OpenvSwitch system interface.
// Deserialize and serialize from/to 'ovs-interface'.
const InterfaceTypeOVSInterface = InterfaceType("ovs-interface")

// InterfaceTypeVeth  Virtual ethernet provide by Linux kernel.
// Deserialize and serialize from/to 'veth'.
const InterfaceTypeVeth = InterfaceType("veth")

// InterfaceTypeVlan  VLAN interface.
// Deserialize and serialize from/to 'vlan'.
const InterfaceTypeVlan = InterfaceType("vlan")

// InterfaceTypeVrf  [Virtual Routing and Forwarding interface](https://www.kernel.org/doc/html/latest/networking/vrf.html)
// Deserialize and serialize from/to 'vrf'.
const InterfaceTypeVrf = InterfaceType("vrf")

// InterfaceTypeVxlan  VxVLAN interface.
// Deserialize and serialize from/to 'vxlan'.
const InterfaceTypeVxlan = InterfaceType("vxlan")

// InterfaceTypeInfiniBand  [IP over InfiniBand interface](https://docs.kernel.org/infiniband/ipoib.html)
// Deserialize and serialize from/to 'infiniband'.
const InterfaceTypeInfiniBand = InterfaceType("infiniband")

// InterfaceTypeTun  TUN interface. Only used for query, will be ignored when applying.
// Deserialize and serialize from/to 'tun'.
const InterfaceTypeTun = InterfaceType("tun")

// InterfaceTypeMacSec  MACsec interface.
// Deserialize and serialize from/to 'macsec'
const InterfaceTypeMacSec = InterfaceType("macsec")

// InterfaceTypeIpsec  Ipsec connection.
const InterfaceTypeIpsec = InterfaceType("ipsec")

// InterfaceTypeXfrm  Linux Xfrm kernel interface
const InterfaceTypeXfrm = InterfaceType("xfrm")

// InterfaceTypeUnknown  Unknown interface.
const InterfaceTypeUnknown = InterfaceType("unknown")

// enum InterfaceType

// InterfaceState  The state of interface
// +kubebuilder:validation:Enum="up";"down";"absent";"unknown";"ignore";
type InterfaceState string

// InterfaceStateUp  Interface is up and running.
// Deserialize and serialize from/to 'up'.
const InterfaceStateUp = InterfaceState("up")

// InterfaceStateDown  For apply action, down means configuration still exist but
// deactivate. The virtual interface will be removed and other interface
// will be reverted to down state or up with IP disabled state.
// Deserialize and serialize from/to 'down'.
const InterfaceStateDown = InterfaceState("down")

// InterfaceStateAbsent  Only for apply action to remove configuration and deactivate the
// interface.
const InterfaceStateAbsent = InterfaceState("absent")

// InterfaceStateUnknown  Unknown state.
const InterfaceStateUnknown = InterfaceState("unknown")

// InterfaceStateIgnore  Interface is not managed by backend. For apply action, interface marked
// as ignore will not be changed and will not cause verification failure
// neither.
// When desired controller listed currently ignored interfaces as its
// port, nmstate will automatically convert these ignored interfaces from
// 'state: ignore' to 'state: up' only when:
//  1. This ignored port is not mentioned in desire state.
//  2. This ignored port is listed as port of a desired controller.
//  3. Controller interface is new or does not contain ignored interfaces
//     currently.
//
// Deserialize and serialize from/to 'ignore'.
const InterfaceStateIgnore = InterfaceState("ignore")

// enum InterfaceState

// UnknownInterface  Holder for interface with known interface type defined.
// During apply action, nmstate can resolve unknown interface to first
// found interface type.
// +k8s:deepcopy-gen=true
type UnknownInterface struct {
	Other string `json:"other,omitempty"`
}

// Interface  Represent a kernel or user space network interface.
// +k8s:deepcopy-gen=true
type Interface struct {
	BaseInterface        `json:",omitempty"`
	*BridgeInterface     `json:",omitempty"`
	*BondInterface       `json:",omitempty"`
	*EthernetInterface   `json:",omitempty"`
	*HsrInterface        `json:",omitempty"`
	*OVSInterface        `json:",omitempty"`
	*VlanInterface       `json:",omitempty"`
	*VxlanInterface      `json:",omitempty"`
	*MacVlanInterface    `json:",omitempty"`
	*MacVtapInterface    `json:",omitempty"`
	*VrfInterface        `json:",omitempty"`
	*InfiniBandInterface `json:",omitempty"`
	*MacSecInterface     `json:",omitempty"`
	*IpsecInterface      `json:",omitempty"`
}

// InterfaceIdentifier  Interface Identifier defines the method for network backend on matching
// network interface
// +kubebuilder:validation:Enum="name";"mac-address";
type InterfaceIdentifier string

// InterfaceIdentifierName  Use interface name to match the network interface, default value.
// Deserialize and serialize from/to 'name'.
const InterfaceIdentifierName = InterfaceIdentifier("name")

// InterfaceIdentifierMacAddress  Use interface MAC address to match the network interface.
// Deserialize and serialize from/to 'mac-address'.
const InterfaceIdentifierMacAddress = InterfaceIdentifier("mac-address")

// enum InterfaceIdentifier

// DNSState  DNS resolver state. Example partial yaml output of [NetworkState] with
// static DNS config:
// ```yaml
// ---
// dns-resolver:
//
//	running:
//	   server:
//	   - 2001:db8:1::250
//	   - 192.0.2.250
//	   search:
//	   - example.org
//	   - example.net
//	config:
//	   search:
//	   - example.org
//	   - example.net
//	   server:
//	   - 2001:db8:1::250
//	   - 192.0.2.250
//	   options:
//	   - trust-ad
//	   - rotate
//
// ```
// To purge all static DNS configuration:
// ```yml
// ---
// dns-resolver:
//
//	config: {}
//
// ```
// +k8s:deepcopy-gen=true
type DNSState struct {
	// Running  The running effective state. The DNS server might be from DHCP(IPv6
	// autoconf) or manual setup.
	// Ignored when applying state.
	Running *DNSClientState `json:"running,omitempty"`
	// Config  The static saved DNS resolver config.
	// When applying, if this not mentioned(None), current static DNS config
	// will be preserved as it was. If defined(Some), will override current
	// static DNS config.
	Config *DNSClientState `json:"config,omitempty"`
}

// DNSClientState  DNS Client state
// +k8s:deepcopy-gen=true
type DNSClientState struct {
	// Server  Name server IP address list.
	// To remove all existing servers, please use `Some(Vec::new())`.
	// If undefined(set to `None`), will preserve current config.
	Server *[]string `json:"server,omitempty"`
	// Search  Search list for host-name lookup.
	// To remove all existing search, please use `Some(Vec::new())`.
	// If undefined(set to `None`), will preserve current config.
	Search *[]string `json:"search,omitempty"`
	// Options  DNS option list.
	// To remove all existing search, please use `Some(Vec::new())`.
	// If undefined(set to `None`), will preserve current config.
	Options *[]string `json:"options,omitempty"`
}

// Routes  IP routing status
// +k8s:deepcopy-gen=true
type Routes struct {
	// Running  Running effected routes containing route from universe or link scope,
	// and only from these protocols:
	//  * boot (often used by `iproute` command)
	//  * static
	//  * ra
	//  * dhcp
	//  * mrouted
	//  * keepalived
	//  * babel
	//
	// Ignored when applying.
	Running *[]RouteEntry `json:"running,omitempty"`
	// Config  Static routes containing route from universe or link scope,
	// and only from these protocols:
	//  * boot (often used by `iproute` command)
	//  * static
	//
	// When applying, `None` means preserve current routes.
	// This property is not overriding but adding specified routes to
	// existing routes. To delete a route entry, please [RouteEntry.state] as
	// [RouteState::Absent]. Any property of absent [RouteEntry] set to
	// `None` means wildcard. For example, this [crate::NetworkState] could
	// remove all routes next hop to interface eth1(showing in yaml):
	// ```yaml
	// routes:
	//   config:
	//   - next-hop-interface: eth1
	//     state: absent
	// ```
	//
	// To change a route entry, you need to delete old one and add new one(can
	// be in single transaction).
	Config *[]RouteEntry `json:"config,omitempty"`
}

// +kubebuilder:validation:Enum="absent";
type RouteState string

// RouteStateAbsent  Mark a route entry as absent to remove it.
const RouteStateAbsent = RouteState("absent")

// enum RouteState

// RouteEntry  Route entry
// +k8s:deepcopy-gen=true
type RouteEntry struct {
	// State  Only used for delete route when applying.
	State *RouteState `json:"state,omitempty"`
	// Destination  Route destination address or network
	// Mandatory for every non-absent routes.
	Destination *string `json:"destination,omitempty"`
	// NextHopIface  Route next hop interface name.
	// Serialize and deserialize to/from `next-hop-interface`.
	// Mandatory for every non-absent routes except for route with
	// route type `Blackhole`, `Unreachable`, `Prohibit`.
	NextHopIface *string `json:"next-hop-interface,omitempty"`
	// NextHopAddr  Route next hop IP address.
	// Serialize and deserialize to/from `next-hop-address`.
	// When setting this as empty string for absent route, it will only delete
	// routes __without__ `next-hop-address`.
	NextHopAddr *string `json:"next-hop-address,omitempty"`
	// Metric  Route metric. [RouteEntry::USE_DEFAULT_METRIC] for default
	// setting of network backend.
	Metric *intstr.IntOrString `json:"metric,omitempty"`
	// TableID  Route table id. [RouteEntry::USE_DEFAULT_ROUTE_TABLE] for main
	// route table 254.
	TableID *intstr.IntOrString `json:"table-id,omitempty"`
	// Weight  ECMP(Equal-Cost Multi-Path) route weight
	// The valid range of this property is 1-256.
	Weight *intstr.IntOrString `json:"weight,omitempty"`
	// RouteType  Route type
	// Serialize and deserialize to/from `route-type`.
	RouteType *RouteType `json:"route-type,omitempty"`
}

// +kubebuilder:validation:Enum="blackhole";"unreachable";"prohibit";
type RouteType string

const RouteTypeBlackhole = RouteType("blackhole")
const RouteTypeUnreachable = RouteType("unreachable")
const RouteTypeProhibit = RouteType("prohibit")

// enum RouteType

// RouteRules  Routing rules
// +k8s:deepcopy-gen=true
type RouteRules struct {
	// Config  When applying, `None` means preserve existing route rules.
	// Nmstate is using partial editing for route rule, which means
	// desired route rules only append to existing instead of overriding.
	// To delete any route rule, please set [crate::RouteRuleEntry.state] to
	// [RouteRuleState::Absent]. Any property set to None in absent route rule
	// means wildcard. For example, this [crate::NetworkState] will delete all
	// route rule looking up route table 500:
	// ```yml
	// ---
	// route-rules:
	//   config:
	//     - state: absent
	//       route-table: 500
	// ```
	Config *[]RouteRuleEntry `json:"config,omitempty"`
}

// +kubebuilder:validation:Enum="absent";
type RouteRuleState string

// RouteRuleStateAbsent  Used for delete route rule
const RouteRuleStateAbsent = RouteRuleState("absent")

// enum RouteRuleState

// +k8s:deepcopy-gen=true
type RouteRuleEntry struct {
	// Family  Indicate the address family of the route rule.
	Family *AddressFamily `json:"family,omitempty"`
	// State  Indicate this is normal route rule or absent route rule.
	State *RouteRuleState `json:"state,omitempty"`
	// IPFrom  Source prefix to match.
	// Serialize and deserialize to/from `ip-from`.
	// When setting to empty string in absent route rule, it will only delete
	// route rule __without__ `ip-from`.
	IPFrom *string `json:"ip-from,omitempty"`
	// IPTo  Destination prefix to match.
	// Serialize and deserialize to/from `ip-to`.
	// When setting to empty string in absent route rule, it will only delete
	// route rule __without__ `ip-to`.
	IPTo *string `json:"ip-to,omitempty"`
	// Priority  Priority of this route rule.
	// Bigger number means lower priority.
	Priority *intstr.IntOrString `json:"priority,omitempty"`
	// TableID  The routing table ID to lookup if the rule selector matches.
	// Serialize and deserialize to/from `route-table`.
	TableID *intstr.IntOrString `json:"route-table,omitempty"`
	// Fwmark  Select the fwmark value to match
	Fwmark *intstr.IntOrString `json:"fwmark,omitempty"`
	// Fwmask  Select the fwmask value to match
	Fwmask *intstr.IntOrString `json:"fwmask,omitempty"`
	// Action  Actions for matching packages.
	Action *RouteRuleAction `json:"action,omitempty"`
	// Iif  Incoming interface.
	Iif *string `json:"iif,omitempty"`
	// SuppressPrefixLength  Prefix length of suppressor.
	// Can deserialize from `suppress-prefix-length` or
	// `suppress_prefixlength`.
	// Serialize into `suppress-prefix-length`.
	SuppressPrefixLength *uint32 `json:"suppress-prefix-length,omitempty"`
}

// +kubebuilder:validation:Enum="blackhole";"unreachable";"prohibit";
type RouteRuleAction string

const RouteRuleActionBlackhole = RouteRuleAction("blackhole")
const RouteRuleActionUnreachable = RouteRuleAction("unreachable")
const RouteRuleActionProhibit = RouteRuleAction("prohibit")

// enum RouteRuleAction

// +k8s:deepcopy-gen=true
type InterfaceIP struct {
	Enabled            *bool               `json:"enabled,omitempty"`
	Dhcp               *bool               `json:"dhcp,omitempty"`
	Autoconf           *bool               `json:"autoconf,omitempty"`
	DhcpClientID       *Dhcpv4ClientID     `json:"dhcp-client-id,omitempty"`
	DhcpDuid           *Dhcpv6Duid         `json:"dhcp-duid,omitempty"`
	Addresses          *[]InterfaceIPAddr  `json:"address,omitempty"`
	AutoDNS            *bool               `json:"auto-dns,omitempty"`
	AutoGateway        *bool               `json:"auto-gateway,omitempty"`
	AutoRoutes         *bool               `json:"auto-routes,omitempty"`
	AutoTableID        *intstr.IntOrString `json:"auto-route-table-id,omitempty"`
	AutoRouteMetric    *intstr.IntOrString `json:"auto-route-metric,omitempty"`
	AddrGenMode        *Ipv6AddrGenMode    `json:"addr-gen-mode,omitempty"`
	AllowExtraAddress  *bool               `json:"allow-extra-address,omitempty"`
	Token              *string             `json:"token,omitempty"`
	DhcpSendHostname   *bool               `json:"dhcp-send-hostname,omitempty"`
	DhcpCustomHostname *string             `json:"dhcp-custom-hostname,omitempty"`
}

// +k8s:deepcopy-gen=true
type InterfaceIPAddr struct {
	// IP  IP address.
	IP string `json:"ip"`
	// PrefixLength  Prefix length.
	// Serialize and deserialize to/from `prefix-length`.
	PrefixLength uint8 `json:"prefix-length"`
	// MptcpFlags  MPTCP flag on this IP address.
	// Ignored when applying as nmstate does not support support IP address
	// specific MPTCP flags. You should apply MPTCP flags at interface level
	// via [BaseInterface.mptcp].
	MptcpFlags *[]MptcpAddressFlag `json:"mptcp-flags,omitempty"`
	// ValidLifeTime  Remaining time for IP address been valid. The output format is
	// "32sec" or "forever".
	// This property is query only, it will be ignored when applying.
	// Serialize to `valid-life-time`.
	// Deserialize from `valid-life-time` or `valid-left` or `valid-lft`.
	ValidLifeTime *string `json:"valid-life-time,omitempty"`
	// PreferredLifeTime  Remaining time for IP address been preferred. The output format is
	// "32sec" or "forever".
	// This property is query only, it will be ignored when applying.
	// Serialize to `preferred-life-time`.
	// Deserialize from `preferred-life-time` or `preferred-left` or
	// `preferred-lft`.
	PreferredLifeTime *string `json:"preferred-life-time,omitempty"`
}

// Dhcpv4ClientID  DHCPv4 client ID
type Dhcpv4ClientID string

// Dhcpv4ClientIDLinkLayerAddress  Use link layer address as DHCPv4 client ID.
// Serialize and deserialize to/from `ll`.
const Dhcpv4ClientIDLinkLayerAddress = Dhcpv4ClientID("ll")

// Dhcpv4ClientIDIaidPlusDuid  RFC 4361 type 255, 32 bits IAID followed by DUID.
// Serialize and deserialize to/from `iaid+duid`.
const Dhcpv4ClientIDIaidPlusDuid = Dhcpv4ClientID("iaid+duid")

// enum Dhcpv4ClientID

// Dhcpv6Duid  DHCPv6 Unique Identifier
type Dhcpv6Duid string

// Dhcpv6DuidLinkLayerAddressPlusTime  DUID Based on Link-Layer Address Plus Time
// Serialize and deserialize to/from `llt`.
const Dhcpv6DuidLinkLayerAddressPlusTime = Dhcpv6Duid("llt")

// Dhcpv6DuidEnterpriseNumber  DUID Assigned by Vendor Based on Enterprise Number
// Serialize and deserialize to/from `en`.
const Dhcpv6DuidEnterpriseNumber = Dhcpv6Duid("en")

// Dhcpv6DuidLinkLayerAddress  DUID Assigned by Vendor Based on Enterprise Number
// Serialize and deserialize to/from `ll`.
const Dhcpv6DuidLinkLayerAddress = Dhcpv6Duid("ll")

// Dhcpv6DuidUUID  DUID Based on Universally Unique Identifier
// Serialize and deserialize to/from `uuid`.
const Dhcpv6DuidUUID = Dhcpv6Duid("uuid")

// enum Dhcpv6Duid

// Ipv6AddrGenMode  IPv6 address generation mode
type Ipv6AddrGenMode string

// Ipv6AddrGenModeEui64  EUI-64 format defined by RFC 4862
// Serialize and deserialize to/from `eui64`.
const Ipv6AddrGenModeEui64 = Ipv6AddrGenMode("eui64")

// Ipv6AddrGenModeStablePrivacy  Semantically Opaque Interface Identifiers defined by RFC 7217
// Serialize and deserialize to/from `stable-privacy`.
const Ipv6AddrGenModeStablePrivacy = Ipv6AddrGenMode("stable-privacy")

// enum Ipv6AddrGenMode

// WaitIP  Which IP stack should network backend wait before considering the interface
// activation finished.
// +kubebuilder:validation:Enum="any";"ipv4";"ipv6";"ipv4+ipv6";
type WaitIP string

// WaitIPAny  The activation is considered done once IPv4 stack or IPv6 stack is
// configure
// Serialize and deserialize to/from `any`.
const WaitIPAny = WaitIP("any")

// WaitIPIpv4  The activation is considered done once IPv4 stack is configured.
// Serialize and deserialize to/from `ipv4`.
const WaitIPIpv4 = WaitIP("ipv4")

// WaitIPIpv6  The activation is considered done once IPv6 stack is configured.
// Serialize and deserialize to/from `ipv6`.
const WaitIPIpv6 = WaitIP("ipv6")

// WaitIPIpv4AndIpv6  The activation is considered done once both IPv4 and IPv6 stack are
// configured.
// Serialize and deserialize to/from `ipv4+ipv6`.
const WaitIPIpv4AndIpv6 = WaitIP("ipv4+ipv6")

// enum WaitIP

// +kubebuilder:validation:Enum="ipv4";"ipv6";"unknown";
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

// BondInterface  Bond interface. When serializing or deserializing, the [BaseInterface] will
// be flatted and [BondConfig] stored as `link-aggregation` section. The yaml
// output [crate::NetworkState] containing an example bond interface:
// ```yml
// interfaces:
//   - name: bond99
//     type: bond
//     state: up
//     mac-address: 1A:24:D5:CA:76:54
//     mtu: 1500
//     min-mtu: 68
//     max-mtu: 65535
//     wait-ip: any
//     ipv4:
//     enabled: false
//     ipv6:
//     enabled: false
//     accept-all-mac-addresses: false
//     link-aggregation:
//     mode: balance-rr
//     options:
//     all_slaves_active: dropped
//     arp_all_targets: any
//     arp_interval: 0
//     arp_validate: none
//     downdelay: 0
//     lp_interval: 1
//     miimon: 100
//     min_links: 0
//     packets_per_slave: 1
//     primary_reselect: always
//     resend_igmp: 1
//     updelay: 0
//     use_carrier: true
//     port:
//   - eth1
//   - eth2
//
// ```
// +k8s:deepcopy-gen=true
type BondInterface struct {
	// Bond  Bond specific settings.
	Bond *BondConfig `json:"link-aggregation,omitempty"`
}

// BondMode  Bond mode
// +kubebuilder:validation:Enum="balance-rr";"0";"active-backup";"1";"balance-xor";"2";"broadcast";"3";"802.3ad";"4";"balance-tlb";"5";"balance-alb";"6";"unknown";
type BondMode string

// BondModeRoundRobin  Deserialize and serialize from/to `balance-rr`.
// You can use integer 0 for deserializing to this mode.
const BondModeRoundRobin = BondMode("balance-rr")

// BondModeActiveBackup  Deserialize and serialize from/to `active-backup`.
// You can use integer 1 for deserializing to this mode.
const BondModeActiveBackup = BondMode("active-backup")

// BondModeXor  Deserialize and serialize from/to `balance-xor`.
// You can use integer 2 for deserializing to this mode.
const BondModeXor = BondMode("balance-xor")

// BondModeBroadcast  Deserialize and serialize from/to `broadcast`.
// You can use integer 3 for deserializing to this mode.
const BondModeBroadcast = BondMode("broadcast")

// BondModeLacp  Deserialize and serialize from/to `802.3ad`.
// You can use integer 4 for deserializing to this mode.
const BondModeLacp = BondMode("802.3ad")

// BondModeTlb  Deserialize and serialize from/to `balance-tlb`.
// You can use integer 5 for deserializing to this mode.
const BondModeTlb = BondMode("balance-tlb")

// BondModeAlb  Deserialize and serialize from/to `balance-alb`.
// You can use integer 6 for deserializing to this mode.
const BondModeAlb = BondMode("balance-alb")
const BondModeUnknown = BondMode("unknown")

// enum BondMode

// +k8s:deepcopy-gen=true
type BondConfig struct {
	// Mode  Mode is mandatory when create new bond interface.
	Mode *BondMode `json:"mode,omitempty"`
	// Options  When applying, if defined, it will override current port list.
	// The verification will not fail on bond options miss-match but an
	// warning message.
	// Please refer to [kernel documentation](https://www.kernel.org/doc/Documentation/networking/bonding.txt) for detail
	Options *BondOptions `json:"options,omitempty"`
	// Port  Deserialize and serialize from/to `port`.
	// You can also use `ports` or `slaves`(deprecated) for deserializing.
	// When applying, if defined, it will override current port list.
	Port *[]string `json:"port,omitempty"`
	// PortsConfig  Deserialize and serialize from/to `ports-config`.
	// When applying, if defined, it will override current ports
	// configuration. Note that `port` is not required to set with
	// `ports-config`. An error will be raised during apply when the port
	// names specified in `port` and `ports-config` conflict with each
	// other.
	PortsConfig *[]BondPortConfig `json:"ports-config,omitempty"`
}

// BondAdSelect  Specifies the 802.3ad aggregation selection logic to use.
// +kubebuilder:validation:Enum="stable";"0";"bandwidth";"1";"count";"2";
type BondAdSelect string

// BondAdSelectStable  Deserialize and serialize from/to `stable`.
const BondAdSelectStable = BondAdSelect("stable")

// BondAdSelectBandwidth  Deserialize and serialize from/to `bandwidth`.
const BondAdSelectBandwidth = BondAdSelect("bandwidth")

// BondAdSelectCount  Deserialize and serialize from/to `count`.
const BondAdSelectCount = BondAdSelect("count")

// enum BondAdSelect

// BondLacpRate  Option specifying the rate in which we'll ask our link partner to transmit
// LACPDU packets in 802.3ad mode
// +kubebuilder:validation:Enum="slow";"0";"fast";"1";
type BondLacpRate string

// BondLacpRateSlow  Request partner to transmit LACPDUs every 30 seconds.
// Serialize to `slow`.
// Deserialize from 0 or `slow`.
const BondLacpRateSlow = BondLacpRate("slow")

// BondLacpRateFast  Request partner to transmit LACPDUs every 1 second
// Serialize to `fast`.
// Deserialize from 1 or `fast`.
const BondLacpRateFast = BondLacpRate("fast")

// enum BondLacpRate

// BondAllPortsActive  Equal to kernel `all_slaves_active` option.
// Specifies that duplicate frames (received on inactive ports) should be
// dropped (0) or delivered (1).
// +kubebuilder:validation:Enum="dropped";"0";"delivered";"1";
type BondAllPortsActive string

// BondAllPortsActiveDropped  Drop the duplicate frames
// Serialize to `dropped`.
// Deserialize from 0 or `dropped`.
const BondAllPortsActiveDropped = BondAllPortsActive("dropped")

// BondAllPortsActiveDelivered  Deliver the duplicate frames
// Serialize to `delivered`.
// Deserialize from 1 or `delivered`.
const BondAllPortsActiveDelivered = BondAllPortsActive("delivered")

// enum BondAllPortsActive

// BondArpAllTargets  The `arp_all_targets` kernel bond option: Specifies the quantity of
// arp_ip_targets that must be reachable in order for the ARP monitor to
// consider a port as being up. This option affects only active-backup mode
// for ports with arp_validation enabled.
// +kubebuilder:validation:Enum="any";"0";"all";"1";
type BondArpAllTargets string

// BondArpAllTargetsAny  consider the port up only when any of the `arp_ip_targets` is reachable
const BondArpAllTargetsAny = BondArpAllTargets("any")

// BondArpAllTargetsAll  consider the port up only when all of the `arp_ip_targets` are
// reachable
const BondArpAllTargetsAll = BondArpAllTargets("all")

// enum BondArpAllTargets

// BondArpValidate  The `arp_validate` kernel bond option: Specifies whether or not ARP probes
// and replies should be validated in any mode that supports arp monitoring, or
// whether non-ARP traffic should be filtered (disregarded) for link monitoring
// purposes.
// +kubebuilder:validation:Enum="none";"0";"active";"1";"backup";"2";"all";"3";"filter";"4";"filter_active";"5";"filter_backup";"6";
type BondArpValidate string

// BondArpValidateNone  No validation or filtering is performed.
// Serialize to `none`.
// Deserialize from 0 or `none`.
const BondArpValidateNone = BondArpValidate("none")

// BondArpValidateActive  Validation is performed only for the active port.
// Serialize to `active`.
// Deserialize from 1 or `active`.
const BondArpValidateActive = BondArpValidate("active")

// BondArpValidateBackup  Validation is performed only for backup ports.
// Serialize to `backup`.
// Deserialize from 2 or `backup`.
const BondArpValidateBackup = BondArpValidate("backup")

// BondArpValidateAll  Validation is performed for all ports.
// Serialize to `all`.
// Deserialize from 3 or `all`.
const BondArpValidateAll = BondArpValidate("all")

// BondArpValidateFilter  Filtering is applied to all ports. No validation is performed.
// Serialize to `filter`.
// Deserialize from 4 or `filter`.
const BondArpValidateFilter = BondArpValidate("filter")

// BondArpValidateFilterActive  Filtering is applied to all ports, validation is performed only for
// the active port.
// Serialize to `filter_active`.
// Deserialize from 5 or `filter-active`.
const BondArpValidateFilterActive = BondArpValidate("filter_active")

// BondArpValidateFilterBackup  Filtering is applied to all ports, validation is performed only for
// backup port.
// Serialize to `filter_backup`.
// Deserialize from 6 or `filter_backup`.
const BondArpValidateFilterBackup = BondArpValidate("filter_backup")

// enum BondArpValidate

// BondFailOverMac  The `fail_over_mac` kernel bond option: Specifies whether active-backup mode
// should set all ports to the same MAC address at port attachment (the
// traditional behavior), or, when enabled, perform special handling of the
// bond's MAC address in accordance with the selected policy.
// +kubebuilder:validation:Enum="none";"0";"active";"1";"follow";"2";
type BondFailOverMac string

// BondFailOverMacNone  This setting disables fail_over_mac, and causes bonding to set all
// ports of an active-backup bond to the same MAC address at attachment
// time.
// Serialize to `none`.
// Deserialize from 0 or `none`.
const BondFailOverMacNone = BondFailOverMac("none")

// BondFailOverMacActive  The "active" fail_over_mac policy indicates that the MAC address of the
// bond should always be the MAC address of the currently active port.
// The MAC address of the ports is not changed; instead, the MAC address
// of the bond changes during a failover.
// Serialize to `active`.
// Deserialize from 1 or `active`.
const BondFailOverMacActive = BondFailOverMac("active")

// BondFailOverMacFollow  The "follow" fail_over_mac policy causes the MAC address of the bond to
// be selected normally (normally the MAC address of the first port added
// to the bond). However, the second and subsequent ports are not set to
// this MAC address while they are in a backup role; a port is programmed
// with the bond's MAC address at failover time (and the formerly active
// port receives the newly active port's MAC address).
// Serialize to `follow`.
// Deserialize from 2 or `follow`.
const BondFailOverMacFollow = BondFailOverMac("follow")

// enum BondFailOverMac

// BondPrimaryReselect  The `primary_reselect` kernel bond option: Specifies the reselection policy
// for the primary port. This affects how the primary port is chosen to
// become the active port when failure of the active port or recovery of the
// primary port occurs. This option is designed to prevent flip-flopping
// between the primary port and other ports.
// +kubebuilder:validation:Enum="always";"0";"better";"1";"failure";"2";
type BondPrimaryReselect string

// BondPrimaryReselectAlways The primary port becomes the active port whenever it comes back up.
// Serialize to `always`.
// Deserialize from 0 or `always`.
const BondPrimaryReselectAlways = BondPrimaryReselect("always")

// BondPrimaryReselectBetter  The primary port becomes the active port when it comes back up, if the
// speed and duplex of the primary port is better than the speed and
// duplex of the current active port.
// Serialize to `better`.
// Deserialize from 1 or `better`.
const BondPrimaryReselectBetter = BondPrimaryReselect("better")

// BondPrimaryReselectFailure  The primary port becomes the active port only if the current active
// port fails and the primary port is up.
// Serialize to `failure`.
// Deserialize from 2 or `failure`.
const BondPrimaryReselectFailure = BondPrimaryReselect("failure")

// enum BondPrimaryReselect

// BondXmitHashPolicy  The `xmit_hash_policy` kernel bond option: Selects the transmit hash policy
// to use for port selection in balance-xor, 802.3ad, and tlb modes.
// +kubebuilder:validation:Enum="layer2";"0";"layer3+4";"1";"layer2+3";"2";"encap2+3";"3";"encap3+4";"4";"vlan+srcmac";"5";
type BondXmitHashPolicy string

// BondXmitHashPolicyLayer2  Serialize to `layer2`.
// Deserialize from 0 or `layer2`.
const BondXmitHashPolicyLayer2 = BondXmitHashPolicy("layer2")

// BondXmitHashPolicyLayer34  Serialize to `layer3+4`.
// Deserialize from 1 or `layer3+4`.
const BondXmitHashPolicyLayer34 = BondXmitHashPolicy("layer3+4")

// BondXmitHashPolicyLayer23  Serialize to `layer2+3`.
// Deserialize from 2 or `layer2+3`.
const BondXmitHashPolicyLayer23 = BondXmitHashPolicy("layer2+3")

// BondXmitHashPolicyEncap23  Serialize to `encap2+3`.
// Deserialize from 3 or `encap2+3`.
const BondXmitHashPolicyEncap23 = BondXmitHashPolicy("encap2+3")

// BondXmitHashPolicyEncap34  Serialize to `encap3+4`.
// Deserialize from 4 or `encap3+4`.
const BondXmitHashPolicyEncap34 = BondXmitHashPolicy("encap3+4")

// BondXmitHashPolicyVlanSrcMac  Serialize to `vlan+srcmac`.
// Deserialize from 5 or `vlan+srcmac`.
const BondXmitHashPolicyVlanSrcMac = BondXmitHashPolicy("vlan+srcmac")

// enum BondXmitHashPolicy

// +k8s:deepcopy-gen=true
type BondOptions struct {
	// AdActorSysPrio  In an AD system, this specifies the system priority. The allowed range
	// is 1 - 65535.
	AdActorSysPrio *intstr.IntOrString `json:"ad_actor_sys_prio,omitempty"`
	// AdActorSystem  In an AD system, this specifies the mac-address for the actor in
	// protocol packet exchanges (LACPDUs). The value cannot be NULL or
	// multicast. It is preferred to have the local-admin bit set for this mac
	// but driver does not enforce it. If the value is not given then system
	// defaults to using the controller's mac address as actors' system
	// address.
	AdActorSystem *string `json:"ad_actor_system,omitempty"`
	// AdSelect  Specifies the 802.3ad aggregation selection logic to use. The
	// possible values and their effects are:
	AdSelect *BondAdSelect `json:"ad_select,omitempty"`
	// AdUserPortKey  In an AD system, the port-key has three parts as shown below -
	//
	// ```text
	// Bits   Use
	// 00     Duplex
	// 01-05  Speed
	// 06-15  User-defined
	// ```
	//
	// This defines the upper 10 bits of the port key. The values can be from
	// 0
	// - 1023. If not given, the system defaults to 0.
	//
	// This parameter has effect only in 802.3ad mode.
	AdUserPortKey *intstr.IntOrString `json:"ad_user_port_key,omitempty"`
	// AllSlavesActive  Specifies that duplicate frames (received on inactive ports) should be
	// dropped (0) or delivered (1).
	//
	// Normally, bonding will drop duplicate frames (received on inactive
	// ports), which is desirable for most users. But there are some times it
	// is nice to allow duplicate frames to be delivered.
	AllSlavesActive *BondAllPortsActive `json:"all_slaves_active,omitempty"`
	// ArpAllTargets  Specifies the quantity of arp_ip_targets that must be reachable in
	// order for the ARP monitor to consider a port as being up. This
	// option affects only active-backup mode for ports with
	// arp_validation enabled.
	ArpAllTargets *BondArpAllTargets `json:"arp_all_targets,omitempty"`
	// ArpInterval  Specifies the ARP link monitoring frequency in milliseconds.
	//
	// The ARP monitor works by periodically checking the port devices to
	// determine whether they have sent or received traffic recently (the
	// precise criteria depends upon the bonding mode, and the state of the
	// port). Regular traffic is generated via ARP probes issued for the
	// addresses specified by the arp_ip_target option.
	//
	// This behavior can be modified by the arp_validate option,
	// below.
	//
	// If ARP monitoring is used in an etherchannel compatible mode (modes 0
	// and 2), the switch should be configured in a mode that evenly
	// distributes packets across all links. If the switch is configured to
	// distribute the packets in an XOR fashion, all replies from the ARP
	// targets will be received on the same link which could cause the other
	// team members to fail. ARP monitoring should not be used in conjunction
	// with miimon. A value of 0 disables ARP monitoring. The default value
	// is 0.
	ArpInterval *intstr.IntOrString `json:"arp_interval,omitempty"`
	// ArpIPTarget  Specifies the IP addresses to use as ARP monitoring peers when
	// arp_interval is > 0. These are the targets of the ARP request sent to
	// determine the health of the link to the targets. Specify these values
	// in ddd.ddd.ddd.ddd format. Multiple IP addresses must be separated by a
	// comma. At least one IP address must be given for ARP monitoring to
	// function. The maximum number of targets that can be specified is 16.
	// The default value is no IP addresses.
	ArpIPTarget *string `json:"arp_ip_target,omitempty"`
	// ArpValidate  Specifies whether or not ARP probes and replies should be validated in
	// any mode that supports arp monitoring, or whether non-ARP traffic
	// should be filtered (disregarded) for link monitoring purposes.
	ArpValidate *BondArpValidate `json:"arp_validate,omitempty"`
	// Downdelay  Specifies the time, in milliseconds, to wait before disabling a port
	// after a link failure has been detected. This option is only valid for
	// the miimon link monitor. The downdelay value should be a multiple of
	// the miimon value; if not, it will be rounded down to the nearest
	// multiple. The default value is 0.
	Downdelay *intstr.IntOrString `json:"downdelay,omitempty"`
	// FailOverMac  Specifies whether active-backup mode should set all ports to the same
	// MAC address at enportment (the traditional behavior), or, when enabled,
	// perform special handling of the bond's MAC address in accordance with
	// the selected policy.
	FailOverMac *BondFailOverMac `json:"fail_over_mac,omitempty"`
	// LacpRate  Option specifying the rate in which we'll ask our link partner to
	// transmit LACPDU packets in 802.3ad mode.
	LacpRate *BondLacpRate `json:"lacp_rate,omitempty"`
	// LpInterval  Specifies the number of seconds between instances where the bonding
	// driver sends learning packets to each slaves peer switch.
	//
	// The valid range is 1 - 0x7fffffff; the default value is 1. This Option
	// has effect only in balance-tlb and balance-alb modes.
	LpInterval *intstr.IntOrString `json:"lp_interval,omitempty"`
	// Miimon  Specifies the MII link monitoring frequency in milliseconds.
	// This determines how often the link state of each port is
	// inspected for link failures. A value of zero disables MII
	// link monitoring. A value of 100 is a good starting point.
	// The use_carrier option, below, affects how the link state is
	// determined. See the High Availability section for additional
	// information. The default value is 0.
	Miimon *intstr.IntOrString `json:"miimon,omitempty"`
	// MinLinks  Specifies the minimum number of links that must be active before
	// asserting carrier. It is similar to the Cisco EtherChannel min-links
	// feature. This allows setting the minimum number of member ports that
	// must be up (link-up state) before marking the bond device as up
	// (carrier on). This is useful for situations where higher level services
	// such as clustering want to ensure a minimum number of low bandwidth
	// links are active before switchover. This option only affect 802.3ad
	// mode.
	//
	// The default value is 0. This will cause carrier to be asserted (for
	// 802.3ad mode) whenever there is an active aggregator, regardless of the
	// number of available links in that aggregator. Note that, because an
	// aggregator cannot be active without at least one available link,
	// setting this option to 0 or to 1 has the exact same effect.
	MinLinks *intstr.IntOrString `json:"min_links,omitempty"`
	// NumGratArp  Specify the number of peer notifications (gratuitous ARPs and
	// unsolicited IPv6 Neighbor Advertisements) to be issued after a
	// failover event. As soon as the link is up on the new port
	// (possibly immediately) a peer notification is sent on the
	// bonding device and each VLAN sub-device. This is repeated at
	// the rate specified by peer_notif_delay if the number is
	// greater than 1.
	//
	// The valid range is 0 - 255; the default value is 1. These options
	// affect only the active-backup mode. These options were added for
	// bonding versions 3.3.0 and 3.4.0 respectively.
	//
	// From Linux 3.0 and bonding version 3.7.1, these notifications are
	// generated by the ipv4 and ipv6 code and the numbers of repetitions
	// cannot be set independently.
	NumGratArp *intstr.IntOrString `json:"num_grat_arp,omitempty"`
	// NumUnsolNa  Identical to [BondOptions.num_grat_arp]
	NumUnsolNa *intstr.IntOrString `json:"num_unsol_na,omitempty"`
	// PacketsPerSlave  Specify the number of packets to transmit through a port before moving
	// to the next one. When set to 0 then a port is chosen at random.
	//
	// The valid range is 0 - 65535; the default value is 1. This option has
	// effect only in balance-rr mode.
	PacketsPerSlave *intstr.IntOrString `json:"packets_per_slave,omitempty"`
	// Primary  A string (eth0, eth2, etc) specifying which slave is the primary
	// device. The specified device will always be the active slave while
	// it is available. Only when the primary is off-line will alternate
	// devices be used. This is useful when one slave is preferred over
	// another, e.g., when one slave has higher throughput than another.
	//
	// The primary option is only valid for active-backup(1), balance-tlb (5)
	// and balance-alb (6) mode.
	Primary *string `json:"primary,omitempty"`
	// PrimaryReselect  Specifies the reselection policy for the primary port. This affects
	// how the primary port is chosen to become the active port when failure
	// of the active port or recovery of the primary port occurs. This
	// option is designed to prevent flip-flopping between the primary port
	// and other ports.
	PrimaryReselect *BondPrimaryReselect `json:"primary_reselect,omitempty"`
	// ResendIgmp  Specifies the number of IGMP membership reports to be issued after
	// a failover event. One membership report is issued immediately after
	// the failover, subsequent packets are sent in each 200ms interval.
	//
	// The valid range is 0 - 255; the default value is 1. A value of 0
	// prevents the IGMP membership report from being issued in response
	// to the failover event.
	//
	// This option is useful for bonding modes balance-rr (0), active-backup
	// (1), balance-tlb (5) and balance-alb (6), in which a failover can
	// switch the IGMP traffic from one port to another. Therefore a
	// fresh IGMP report must be issued to cause the switch to forward the
	// incoming IGMP traffic over the newly selected port.
	ResendIgmp *intstr.IntOrString `json:"resend_igmp,omitempty"`
	// TlbDynamicLb  Specifies if dynamic shuffling of flows is enabled in tlb mode. The
	// value has no effect on any other modes.
	//
	// The default behavior of tlb mode is to shuffle active flows across
	// ports based on the load in that interval. This gives nice lb
	// characteristics but can cause packet reordering. If re-ordering is a
	// concern use this variable to disable flow shuffling and rely on load
	// balancing provided solely by the hash distribution. xmit-hash-policy
	// can be used to select the appropriate hashing for the setup.
	//
	// The sysfs entry can be used to change the setting per bond device and
	// the initial value is derived from the module parameter. The sysfs entry
	// is allowed to be changed only if the bond device is down.
	//
	// The default value is "1" that enables flow shuffling while value "0"
	// disables it. This option was added in bonding driver 3.7.1
	TlbDynamicLb *bool `json:"tlb_dynamic_lb,omitempty"`
	// Updelay  Specifies the time, in milliseconds, to wait before enabling a port
	// after a link recovery has been detected. This option is only valid for
	// the miimon link monitor. The updelay value should be a multiple of the
	// miimon value; if not, it will be rounded down to the nearest multiple.
	// The default value is 0.
	Updelay *intstr.IntOrString `json:"updelay,omitempty"`
	// UseCarrier  Specifies whether or not miimon should use MII or ETHTOOL
	// ioctls vs. netif_carrier_ok() to determine the link
	// status. The MII or ETHTOOL ioctls are less efficient and
	// utilize a deprecated calling sequence within the kernel.  The
	// netif_carrier_ok() relies on the device driver to maintain its
	// state with netif_carrier_on/off; at this writing, most, but
	// not all, device drivers support this facility.
	//
	// If bonding insists that the link is up when it should not be,
	// it may be that your network device driver does not support
	// netif_carrier_on/off.  The default state for netif_carrier is
	// "carrier on," so if a driver does not support netif_carrier,
	// it will appear as if the link is always up.  In this case,
	// setting use_carrier to 0 will cause bonding to revert to the
	// MII / ETHTOOL ioctl method to determine the link state.
	//
	// A value of 1 enables the use of netif_carrier_ok(), a value of
	// 0 will use the deprecated MII / ETHTOOL ioctls.  The default
	// value is 1.
	UseCarrier *bool `json:"use_carrier,omitempty"`
	// XmitHashPolicy  Selects the transmit hash policy to use for slave selection in
	// balance-xor, 802.3ad, and tlb modes.
	XmitHashPolicy *BondXmitHashPolicy `json:"xmit_hash_policy,omitempty"`
	BalanceSlb     *bool               `json:"balance_slb,omitempty"`
	ArpMissedMax   *intstr.IntOrString `json:"arp_missed_max,omitempty"`
}

// +k8s:deepcopy-gen=true
type BondPortConfig struct {
	// Name  name is mandatory when specifying the ports configuration.
	Name string `json:"name"`
	// Priority  Deserialize and serialize from/to `priority`.
	// When applying, if defined, it will override the current bond port
	// priority. The verification will fail if bonding mode is not
	// active-backup(1) or balance-tlb (5) or balance-alb (6).
	Priority *intstr.IntOrString `json:"priority,omitempty"`
	// QueueID  Deserialize and serialize from/to `queue-id`.
	QueueID *intstr.IntOrString `json:"queue-id,omitempty"`
}

// DummyInterface  Dummy interface. Only contain information of [BaseInterface].
// Example yaml outpuf of `[crate::NetworkState]` with dummy interface:
// ```yml
// interfaces:
//   - name: dummy1
//     type: dummy
//     state: up
//     mac-address: BE:25:F0:6D:55:64
//     mtu: 1500
//     wait-ip: any
//     ipv4:
//     enabled: false
//     ipv6:
//     enabled: false
//     accept-all-mac-addresses: false
//     lldp:
//     enabled: false
//     ethtool:
//     feature:
//     tx-checksum-ip-generic: true
//     tx-ipxip6-segmentation: true
//     rx-gro: true
//     tx-generic-segmentation: true
//     tx-udp-segmentation: true
//     tx-udp_tnl-csum-segmentation: true
//     rx-udp-gro-forwarding: false
//     tx-tcp-segmentation: true
//     tx-sctp-segmentation: true
//     tx-ipxip4-segmentation: true
//     tx-nocache-copy: false
//     tx-gre-csum-segmentation: true
//     tx-udp_tnl-segmentation: true
//     tx-tcp-mangleid-segmentation: true
//     rx-gro-list: false
//     tx-scatter-gather-fraglist: true
//     tx-gre-segmentation: true
//     tx-tcp-ecn-segmentation: true
//     tx-gso-list: true
//     highdma: true
//     tx-tcp6-segmentation: true
//
// ```
// +k8s:deepcopy-gen=true
type DummyInterface struct {
}

// LinuxBridgeConfig  Linux bridge specific configuration.
// +k8s:deepcopy-gen=true
type LinuxBridgeConfig struct {
	// Options  Linux bridge options. When applying, existing options will merged into
	// desired.
	Options *LinuxBridgeOptions `json:"options,omitempty"`
	// Port  Linux bridge ports. When applying, desired port list will __override__
	// current port list.
	// Serialize to 'port'. Deserialize from `port` or `ports`.
	Port *[]LinuxBridgePortConfig `json:"port,omitempty"`
}

// +k8s:deepcopy-gen=true
type LinuxBridgePortConfig struct {
	// StpHairpinMode  Controls whether traffic may be send back out of the port on which it
	// was received.
	StpHairpinMode *bool `json:"stp-hairpin-mode,omitempty"`
	// StpPathCost  The STP path cost of the specified port.
	StpPathCost *intstr.IntOrString `json:"stp-path-cost,omitempty"`
	// StpPriority  The STP port priority. The priority value is an unsigned 8-bit quantity
	// (number between 0 and 255). This metric is used in the designated port
	// an droot port selec‐ tion algorithms.
	StpPriority *intstr.IntOrString `json:"stp-priority,omitempty"`
}

// +k8s:deepcopy-gen=true
type LinuxBridgeOptions struct {
	GcTimer   *uint64 `json:"gc-timer,omitempty"`
	GroupAddr *string `json:"group-addr,omitempty"`
	// GroupForwardMask  Alias of [LinuxBridgeOptions.group_fwd_mask], not preferred, please
	// use [LinuxBridgeOptions.group_fwd_mask] instead.
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
	// Enabled  If disabled during applying, the remaining STP options will be discard.
	Enabled      *bool               `json:"enabled,omitempty"`
	ForwardDelay *intstr.IntOrString `json:"forward-delay,omitempty"`
	HelloTime    *intstr.IntOrString `json:"hello-time,omitempty"`
	MaxAge       *intstr.IntOrString `json:"max-age,omitempty"`
	Priority     *intstr.IntOrString `json:"priority,omitempty"`
}

// +kubebuilder:validation:XIntOrString
// +kubebuilder:validation:Enum=1;"auto";0;"disabled";2;"enabled";
type LinuxBridgeMulticastRouterType intstr.IntOrString

func (o LinuxBridgeMulticastRouterType) MarshalJSON() ([]byte, error) {
	return intstr.IntOrString(o).MarshalJSON()
}

func (o *LinuxBridgeMulticastRouterType) UnmarshalJSON(data []byte) error {
	oi := intstr.IntOrString(*o)
	if err := oi.UnmarshalJSON(data); err != nil {
		return err
	}
	*o = LinuxBridgeMulticastRouterType(oi)
	return nil
}

var LinuxBridgeMulticastRouterTypeAuto = LinuxBridgeMulticastRouterType(intstr.FromString("auto"))
var LinuxBridgeMulticastRouterTypeDisabled = LinuxBridgeMulticastRouterType(intstr.FromString("disabled"))
var LinuxBridgeMulticastRouterTypeEnabled = LinuxBridgeMulticastRouterType(intstr.FromString("enabled"))

// enum LinuxBridgeMulticastRouterType

// BridgePortVlanConfig  Bridge VLAN filtering configuration
// +k8s:deepcopy-gen=true
type BridgePortVlanConfig struct {
	// EnableNative  Enable native VLAN.
	// Deserialize and serialize from/to `enable-native`.
	EnableNative *bool `json:"enable-native,omitempty"`
	// Mode  Bridge VLAN filtering mode
	Mode *BridgePortVlanMode `json:"mode,omitempty"`
	// Tag  VLAN Tag for native VLAN.
	Tag *intstr.IntOrString `json:"tag,omitempty"`
	// TrunkTags  Trunk tags.
	// Deserialize and serialize from/to `trunk-tags`.
	TrunkTags *[]BridgePortTrunkTag `json:"trunk-tags,omitempty"`
}

// +kubebuilder:validation:Enum="trunk";"access";
type BridgePortVlanMode string

// BridgePortVlanModeTrunk  Trunk mode
const BridgePortVlanModeTrunk = BridgePortVlanMode("trunk")

// BridgePortVlanModeAccess  Access mode
const BridgePortVlanModeAccess = BridgePortVlanMode("access")

// enum BridgePortVlanMode

// +k8s:deepcopy-gen=true
type BridgePortTrunkTag struct {
	// ID  Single VLAN trunk ID
	ID *uint16 `json:"id,omitempty"`
	// IDRange  VLAN trunk ID range
	IDRange *BridgePortVlanRange `json:"id-range,omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgePortVlanRange struct {
	// Min  Minimum VLAN ID(included).
	Min uint16 `json:"min"`
	// Max  Maximum VLAN ID(included).
	Max uint16 `json:"max"`
}

// +k8s:deepcopy-gen=true
type OVSBridgeConfig struct {
	// AllowExtraPatchPorts  Only validate for applying, when set to `true`, extra OVS patch ports
	// will not fail the verification. Default is false.
	// This property will not be persisted, every time you modify
	// ports of specified OVS bridge, you need to explicitly define this
	// property if not using default value.
	// Deserialize from `allow-extra-patch-ports`.
	AllowExtraPatchPorts *bool `json:"allow-extra-patch-ports,omitempty"`
}

// +k8s:deepcopy-gen=true
type OVSBridgeOptions struct {
	Stp  *OVSBridgeStpOptions `json:"stp,omitempty"`
	Rstp *bool                `json:"rstp,omitempty"`
	// McastSnoopingEnable  Deserialize and serialize from/to `mcast-snooping-enable`.
	McastSnoopingEnable *bool `json:"mcast-snooping-enable,omitempty"`
	// FailMode  Deserialize and serialize from/to `fail-mode`.
	FailMode *string `json:"fail-mode,omitempty"`
	// Datapath  Set to `netdev` for DPDK.
	// Deserialize and serialize from/to `datapath`.
	Datapath *string `json:"datapath,omitempty"`
}

// +k8s:deepcopy-gen=true
type OVSBridgePortConfig struct {
	Bond *OVSBridgeBondConfig `json:"link-aggregation,omitempty"`
}

// OVSInterface  OpenvSwitch internal interface. Example yaml output of [crate::NetworkState]
// with an DPDK enabled OVS interface:
// ```yml
// ---
// interfaces:
//   - name: ovs0
//     type: ovs-interface
//     state: up
//     dpdk:
//     devargs: "0000:af:00.1"
//     rx-queue: 100
//   - name: br0
//     type: ovs-bridge
//     state: up
//     bridge:
//     options:
//     datapath: "netdev"
//     port:
//   - name: ovs0
//
// ovs-db:
//
//	other_config:
//	  dpdk-init: "true"
//
// ```
//
// The yaml example of OVS pathing:
// ```yml
// ---
// interfaces:
//   - name: patch0
//     type: ovs-interface
//     state: up
//     patch:
//     peer: patch1
//   - name: ovs-br0
//     type: ovs-bridge
//     state: up
//     bridge:
//     port:
//   - name: patch0
//   - name: patch1
//     type: ovs-interface
//     state: up
//     patch:
//     peer: patch0
//   - name: ovs-br1
//     type: ovs-bridge
//     state: up
//     bridge:
//     port:
//   - name: patch1
//
// ```
// +k8s:deepcopy-gen=true
type OVSInterface struct {
	Patch *OVSPatchConfig `json:"patch,omitempty"`
	Dpdk  *OVSDpdkConfig  `json:"dpdk,omitempty"`
}

// OVSBridgeBondConfig  The example yaml output of OVS bond:
// ```yml
// ---
// interfaces:
//   - name: eth1
//     type: ethernet
//     state: up
//   - name: eth2
//     type: ethernet
//     state: up
//   - name: br0
//     type: ovs-bridge
//     state: up
//     bridge:
//     port:
//   - name: veth1
//   - name: ovs0
//   - name: bond1
//     link-aggregation:
//     mode: balance-slb
//     port:
//   - name: eth2
//   - name: eth1
//
// ```
// +k8s:deepcopy-gen=true
type OVSBridgeBondConfig struct {
	Mode *OVSBridgeBondMode `json:"mode,omitempty"`
	// Ports  Serialize to 'port'. Deserialize from `port` or `ports`.
	Ports *[]OVSBridgeBondPortConfig `json:"port,omitempty"`
	// BondDowndelay  Deserialize and serialize from/to `bond-downdelay`.
	BondDowndelay *intstr.IntOrString `json:"bond-downdelay,omitempty"`
	// BondUpdelay  Deserialize and serialize from/to `bond-updelay`.
	BondUpdelay *intstr.IntOrString `json:"bond-updelay,omitempty"`
	// Ovsdb  OpenvSwitch specific `other_config` for OVS bond. Please refer to
	// manpage `ovs-vswitchd.conf.db(5)` for more detail.
	// When setting to None, nmstate will try to preserve current
	// `other_config`, otherwise, nmstate will override all `other_config`
	// for specified OVS bond.
	Ovsdb *OVSDBIfaceConfig `json:"ovs-db,omitempty"`
}

// +k8s:deepcopy-gen=true
type OVSBridgeBondPortConfig struct {
	Name string `json:"name"`
}

// +kubebuilder:validation:Enum="active-backup";"balance-slb";"balance-tcp";"lacp";
type OVSBridgeBondMode string

// OVSBridgeBondModeActiveBackup  Deserialize and serialize from/to `active-backup`.
const OVSBridgeBondModeActiveBackup = OVSBridgeBondMode("active-backup")

// OVSBridgeBondModeBalanceSlb  Deserialize and serialize from/to `balance-slb`.
const OVSBridgeBondModeBalanceSlb = OVSBridgeBondMode("balance-slb")

// OVSBridgeBondModeBalanceTCP  Deserialize and serialize from/to `balance-tcp`.
const OVSBridgeBondModeBalanceTCP = OVSBridgeBondMode("balance-tcp")

// OVSBridgeBondModeLacp  Deserialize and serialize from/to `lacp`.
const OVSBridgeBondModeLacp = OVSBridgeBondMode("lacp")

// enum OVSBridgeBondMode

// +k8s:deepcopy-gen=true
type OVSPatchConfig struct {
	Peer string `json:"peer,omitempty"`
}

// +k8s:deepcopy-gen=true
type OVSDpdkConfig struct {
	Devargs string `json:"devargs"`
	// RxQueue  Deserialize and serialize from/to `rx-queue`. You may also use
	// OVS terminology `n_rxq` for this property.
	RxQueue *uint32 `json:"rx-queue,omitempty"`
	// NRxqDesc  Specifies  the  rx  queue  size (number rx descriptors) for dpdk ports.
	// Must be power of 2 in the range of 1 to 4096.
	// Setting to 0 means remove this setting from OVS database.
	NRxqDesc *uint32 `json:"n_rxq_desc,omitempty"`
	// NTxqDesc  Specifies  the  tx  queue  size (number tx descriptors) for dpdk ports.
	// Must be power of 2 in the range of 1 to 4096.
	// Setting to 0 means remove this setting from OVS database.
	NTxqDesc *uint32 `json:"n_txq_desc,omitempty"`
}

// VlanInterface  Linux kernel VLAN interface. The example yaml output of
// [crate::NetworkState] with a VLAN interface would be:
// ```yaml
// interfaces:
//   - name: eth1.101
//     type: vlan
//     state: up
//     mac-address: BE:E8:17:8F:D2:70
//     mtu: 1500
//     max-mtu: 65535
//     wait-ip: any
//     ipv4:
//     enabled: false
//     ipv6:
//     enabled: false
//     accept-all-mac-addresses: false
//     vlan:
//     base-iface: eth1
//     id: 101
//
// ```
// +k8s:deepcopy-gen=true
type VlanInterface struct {
	Vlan *VlanConfig `json:"vlan,omitempty"`
}

// +k8s:deepcopy-gen=true
type VlanConfig struct {
	BaseIface string `json:"base-iface"`
	ID        uint16 `json:"id"`
	// Protocol  Could be `802.1q` or `802.1ad`. Default to `802.1q` if not defined.
	Protocol *VlanProtocol `json:"protocol,omitempty"`
	// RegistrationProtocol  Could be `gvrp`, `mvrp` or `none`. Default to none if not defined.
	RegistrationProtocol *VlanRegistrationProtocol `json:"registration-protocol,omitempty"`
	// ReorderHeaders  reordering of output packet headers
	ReorderHeaders *bool `json:"reorder-headers,omitempty"`
	// LooseBinding  loose binding of the interface to its master device's operating state
	LooseBinding *bool `json:"loose-binding,omitempty"`
}

// +kubebuilder:validation:Enum="802.1q";"802.1ad";
type VlanProtocol string

// VlanProtocolIeee8021Q  Deserialize and serialize from/to `802.1q`.
const VlanProtocolIeee8021Q = VlanProtocol("802.1q")

// VlanProtocolIeee8021Ad  Deserialize and serialize from/to `802.1ad`.
const VlanProtocolIeee8021Ad = VlanProtocol("802.1ad")

// enum VlanProtocol

// +kubebuilder:validation:Enum="gvrp";"mvrp";"none";
type VlanRegistrationProtocol string

// VlanRegistrationProtocolGvrp  GARP VLAN Registration Protocol
const VlanRegistrationProtocolGvrp = VlanRegistrationProtocol("gvrp")

// VlanRegistrationProtocolMvrp  Multiple VLAN Registration Protocol
const VlanRegistrationProtocolMvrp = VlanRegistrationProtocol("mvrp")

// VlanRegistrationProtocolNone  No Registration Protocol
const VlanRegistrationProtocolNone = VlanRegistrationProtocol("none")

// enum VlanRegistrationProtocol

// VxlanInterface  Linux kernel VxLAN interface. The example yaml output of
// [crate::NetworkState] with a VxLAN interface would be:
// ```yml
// interfaces:
//   - name: eth1.102
//     type: vxlan
//     state: up
//     mac-address: 0E:00:95:53:19:55
//     mtu: 1450
//     min-mtu: 68
//     max-mtu: 65535
//     vxlan:
//     base-iface: eth1
//     id: 102
//     remote: 239.1.1.1
//     destination-port: 1235
//
// ```
// +k8s:deepcopy-gen=true
type VxlanInterface struct {
	Vxlan *VxlanConfig `json:"vxlan,omitempty"`
}

// +k8s:deepcopy-gen=true
type VxlanConfig struct {
	BaseIface string  `json:"base-iface,omitempty"`
	ID        uint32  `json:"id"`
	Learning  *bool   `json:"learning,omitempty"`
	Local     *string `json:"local,omitempty"`
	Remote    *string `json:"remote,omitempty"`
	// DstPort  Deserialize and serialize from/to `destination-port`.
	DstPort *intstr.IntOrString `json:"destination-port,omitempty"`
}

// MacVlanInterface  Linux kernel MAC VLAN interface. The example yaml output of
// [crate::NetworkState] with a mac vlan interface would be:
// ```yaml
// ---
// interfaces:
//   - name: mac0
//     type: mac-vlan
//     state: up
//     mac-vlan:
//     base-iface: eth1
//     mode: vepa
//     promiscuous: true
//
// ```
// +k8s:deepcopy-gen=true
type MacVlanInterface struct {
	// MacVlan  Deserialize and serialize from/to `mac-vlan`.
	MacVlan *MacVlanConfig `json:"mac-vlan,omitempty"`
}

// +k8s:deepcopy-gen=true
type MacVlanConfig struct {
	BaseIface string      `json:"base-iface"`
	Mode      MacVlanMode `json:"mode"`
	// AcceptAllMac  Serialize to `promiscuous`.
	// Deserialize from `promiscuous` or `accept-all-mac`.
	AcceptAllMac *bool `json:"promiscuous,omitempty"`
}

// +kubebuilder:validation:Enum="vepa";"bridge";"private";"passthru";"source";"unknown";
type MacVlanMode string

// MacVlanModeVepa  Deserialize and serialize from/to `vepa`.
const MacVlanModeVepa = MacVlanMode("vepa")

// MacVlanModeBridge  Deserialize and serialize from/to `bridge`.
const MacVlanModeBridge = MacVlanMode("bridge")

// MacVlanModePrivate  Deserialize and serialize from/to `private`.
const MacVlanModePrivate = MacVlanMode("private")

// MacVlanModePassthru  Deserialize and serialize from/to `passthru`.
const MacVlanModePassthru = MacVlanMode("passthru")

// MacVlanModeSource  Deserialize and serialize from/to `source`.
const MacVlanModeSource = MacVlanMode("source")
const MacVlanModeUnknown = MacVlanMode("unknown")

// enum MacVlanMode

// MacVtapInterface  Linux kernel MAC VTAP interface. The example output of [crate::NetworkState]
// with a mac vtap interface would be:
// ```yml
// ---
// interfaces:
//   - name: mac0
//     type: mac-vtap
//     state: up
//     mac-vtap:
//     base-iface: eth1
//     mode: passthru
//     promiscuous: true
//
// ```
// +k8s:deepcopy-gen=true
type MacVtapInterface struct {
	// MacVtap  Deserialize and serialize from/to `mac-vtap`.
	MacVtap *MacVtapConfig `json:"mac-vtap,omitempty"`
}

// +k8s:deepcopy-gen=true
type MacVtapConfig struct {
	BaseIface string      `json:"base-iface"`
	Mode      MacVtapMode `json:"mode"`
	// AcceptAllMac  Serialize to `promiscuous`.
	// Deserialize from `promiscuous` or `accept-all-mac`.
	AcceptAllMac *bool `json:"promiscuous,omitempty"`
}

// +kubebuilder:validation:Enum="vepa";"bridge";"private";"passthru";"source";"unknown";
type MacVtapMode string

// MacVtapModeVepa  Deserialize and serialize from/to `vepa`.
const MacVtapModeVepa = MacVtapMode("vepa")

// MacVtapModeBridge  Deserialize and serialize from/to `bridge`.
const MacVtapModeBridge = MacVtapMode("bridge")

// MacVtapModePrivate  Deserialize and serialize from/to `private`.
const MacVtapModePrivate = MacVtapMode("private")

// MacVtapModePassthru  Deserialize and serialize from/to `passthru`.
const MacVtapModePassthru = MacVtapMode("passthru")

// MacVtapModeSource  Deserialize and serialize from/to `source`.
const MacVtapModeSource = MacVtapMode("source")
const MacVtapModeUnknown = MacVtapMode("unknown")

// enum MacVtapMode

// VrfInterface  Linux kernel Virtual Routing and Forwarding(VRF) interface. The example
// yaml output of a [crate::NetworkState] with a VRF interface would be:
// ```yml
// interfaces:
//   - name: vrf0
//     type: vrf
//     state: up
//     mac-address: 42:6C:4A:0B:A3:C0
//     mtu: 65575
//     min-mtu: 1280
//     max-mtu: 65575
//     wait-ip: any
//     ipv4:
//     enabled: false
//     ipv6:
//     enabled: false
//     accept-all-mac-addresses: false
//     vrf:
//     port:
//   - eth1
//   - eth2
//     route-table-id: 100
//
// ```
// +k8s:deepcopy-gen=true
type VrfInterface struct {
	Vrf *VrfConfig `json:"vrf,omitempty"`
}

// +k8s:deepcopy-gen=true
type VrfConfig struct {
	// Port  Port list.
	// Deserialize and serialize from/to `port`.
	// Also deserialize from `ports`.
	Port *[]string `json:"port"`
	// TableID  Route table ID of this VRF interface.
	// Use 0 to preserve current `table_id`.
	// Deserialize and serialize from/to `route-table-id`.
	TableID uint32 `json:"route-table-id,omitempty"`
}

// InfiniBandInterface  IP over InfiniBand interface. The example yaml output of a
// [crate::NetworkState] with an infiniband interface would be:
// ```yaml
// ---
// interfaces:
//   - name: ib2.8001
//     type: infiniband
//     state: up
//     mtu: 1280
//     infiniband:
//     pkey: "0x8001"
//     mode: "connected"
//     base-iface: "ib2"
//
// ```
// +k8s:deepcopy-gen=true
type InfiniBandInterface struct {
	Ib *InfiniBandConfig `json:"infiniband,omitempty"`
}

// +kubebuilder:validation:Enum="datagram";"connected";
type InfiniBandMode string

// InfiniBandModeDatagram  Deserialize and serialize from/to `datagram`.
const InfiniBandModeDatagram = InfiniBandMode("datagram")

// InfiniBandModeConnected  Deserialize and serialize from/to `connected`.
const InfiniBandModeConnected = InfiniBandMode("connected")

// enum InfiniBandMode

// +k8s:deepcopy-gen=true
type InfiniBandConfig struct {
	// Mode  Mode of InfiniBand interface.
	Mode InfiniBandMode `json:"mode"`
	// BaseIface  For pkey sub-interface only. Empty for base interface.
	BaseIface *string `json:"base-iface,omitempty"`
	// Pkey  P-key of sub-interface.
	// Serialize in hex string format(lower case).
	// For base interface, it is set to None.
	// The `0xffff` value also indicate this is a InfiniBand base interface.
	Pkey *intstr.IntOrString `json:"pkey,omitempty"`
}

// LoopbackInterface  Loopback interface. Only contain information of [BaseInterface].
// Limitations
//   - Cannot enable DHCP or autoconf.
//   - The [InterfaceState::Absent] can only restore the loopback configure back
//     to default.
//   - Ignore the request of disable IPv4 or IPv6.
//   - Even not desired, the `127.0.0.1/8` and `::1` are always appended to
//     static IP address list.
//   - Require NetworkManager 1.41+ unless in kernel only mode.
//
// Example yaml outpuf of `[crate::NetworkState]` with loopback interface:
// ```yml
// interfaces:
//   - name: lo
//     type: loopback
//     state: up
//     mtu: 65535
//     ipv4:
//     enabled: true
//     address:
//   - ip: 127.0.0.1
//     prefix-length: 8
//     ipv6:
//     enabled: true
//     address:
//   - ip: ::1
//     prefix-length: 128
//     accept-all-mac-addresses: false
//
// ```
// +k8s:deepcopy-gen=true
type LoopbackInterface struct {
}

// SrIovConfig  Single Root I/O Virtualization(SRIOV) configuration. The example yaml output
// of [crate::NetworkState] with SR-IOV enabled ethernet interface would be:
// ```yml
// interfaces:
//   - name: ens1f1
//     type: ethernet
//     state: up
//     mac-address: 00:11:22:33:44:55
//     mtu: 1500
//     min-mtu: 68
//     max-mtu: 9702
//     ethernet:
//     sr-iov:
//     total-vfs: 2
//     vfs:
//   - id: 0
//     mac-address: 00:11:22:33:00:ff
//     spoof-check: true
//     trust: false
//     min-tx-rate: 0
//     max-tx-rate: 0
//     vlan-id: 0
//     qos: 0
//   - id: 1
//     mac-address: 00:11:22:33:00:ef
//     spoof-check: true
//     trust: false
//     min-tx-rate: 0
//     max-tx-rate: 0
//     vlan-id: 0
//     qos: 0
//
// ```
// +k8s:deepcopy-gen=true
type SrIovConfig struct {
	// TotalVfs  The number of VFs enabled on PF.
	// Deserialize and serialize from/to `total-vfs`.
	TotalVfs *intstr.IntOrString `json:"total-vfs,omitempty"`
	// Vfs  VF specific configurations.
	// * Setting to `Some(Vec::new())` will revert all VF configurations back
	//   to defaults.
	// * If not empty, missing [SrIovVfConfig] will use current configuration.
	Vfs *[]SrIovVfConfig `json:"vfs,omitempty"`
}

// +k8s:deepcopy-gen=true
type SrIovVfConfig struct {
	ID uint32 `json:"id"`
	// IfaceName  Interface name for this VF, only for querying, will be ignored
	// when applying network state.
	IfaceName string `json:"iface-name,omitempty"`
	// MacAddress  Deserialize and serialize from/to `mac-address`.
	MacAddress *string `json:"mac-address,omitempty"`
	// SpoofCheck  Deserialize and serialize from/to `spoof-check`.
	SpoofCheck *bool `json:"spoof-check,omitempty"`
	Trust      *bool `json:"trust,omitempty"`
	// MinTxRate  Deserialize and serialize from/to `min_tx_rate`.
	MinTxRate *intstr.IntOrString `json:"min-tx-rate,omitempty"`
	// MaxTxRate  Deserialize and serialize from/to `max-tx-rate`.
	MaxTxRate *intstr.IntOrString `json:"max-tx-rate,omitempty"`
	// VlanID  Deserialize and serialize from/to `vlan-id`.
	VlanID    *intstr.IntOrString `json:"vlan-id,omitempty"`
	Qos       *intstr.IntOrString `json:"qos,omitempty"`
	VlanProto *VlanProtocol       `json:"vlan-proto,omitempty"`
}

// +k8s:deepcopy-gen=true
type EthtoolFeatureConfig struct {
	Data map[string]bool `json:"data"`
}

// EthtoolConfig  The ethtool configurations.
// The yaml output of [crate::NetworkState] containing ethtool information of
// an ethernet interface would be:
// ```yml
// interfaces:
//   - name: ens3
//     type: ethernet
//     state: up
//     ethtool:
//     feature:
//     tx-tcp-ecn-segmentation: true
//     tx-tcp-mangleid-segmentation: false
//     tx-tcp6-segmentation: true
//     tx-tcp-segmentation: true
//     rx-gro-list: false
//     rx-udp-gro-forwarding: false
//     rx-gro-hw: true
//     tx-checksum-ip-generic: true
//     tx-generic-segmentation: true
//     rx-gro: true
//     tx-nocache-copy: false
//     coalesce:
//     rx-frames: 1
//     tx-frames: 1
//     ring:
//     rx: 256
//     rx-max: 256
//     tx: 256
//     tx-max: 256
//
// ```
// +k8s:deepcopy-gen=true
type EthtoolConfig struct {
	// Pause  The pause parameters of the specified Ethernet device.
	Pause *EthtoolPauseConfig `json:"pause,omitempty"`
	// Feature  The protocol offload and other features of specified network device.
	// Only changeable features are included when querying.
	Feature map[string]bool `json:"feature,omitempty"`
	// Coalesce  The coalescing settings of the specified network device.
	Coalesce *EthtoolCoalesceConfig `json:"coalesce,omitempty"`
	// Ring  The rx/tx ring parameters of the specified network device.
	Ring *EthtoolRingConfig `json:"ring,omitempty"`
}

// +k8s:deepcopy-gen=true
type EthtoolPauseConfig struct {
	Rx      *bool `json:"rx,omitempty"`
	Tx      *bool `json:"tx,omitempty"`
	Autoneg *bool `json:"autoneg,omitempty"`
}

// +k8s:deepcopy-gen=true
type EthtoolCoalesceConfig struct {
	// AdaptiveRx  Deserialize and serialize from/to `adaptive-rx`.
	AdaptiveRx *bool `json:"adaptive-rx,omitempty"`
	// AdaptiveTx  Deserialize and serialize from/to `adaptive-tx`.
	AdaptiveTx *bool `json:"adaptive-tx,omitempty"`
	// PktRateHigh  Deserialize and serialize from/to `pkt-rate-high`.
	PktRateHigh *intstr.IntOrString `json:"pkt-rate-high,omitempty"`
	// PktRateLow  Deserialize and serialize from/to `pkt-rate-low`.
	PktRateLow *intstr.IntOrString `json:"pkt-rate-low,omitempty"`
	// RxFrames  Deserialize and serialize from/to `rx-frames`.
	RxFrames *intstr.IntOrString `json:"rx-frames,omitempty"`
	// RxFramesHigh  Deserialize and serialize from/to `rx-frames-high`.
	RxFramesHigh *intstr.IntOrString `json:"rx-frames-high,omitempty"`
	// RxFramesIrq  Deserialize and serialize from/to `rx-frames-irq`.
	RxFramesIrq *intstr.IntOrString `json:"rx-frames-irq,omitempty"`
	// RxFramesLow  Deserialize and serialize from/to `rx-frames-low`.
	RxFramesLow *intstr.IntOrString `json:"rx-frames-low,omitempty"`
	// RxUsecs  Deserialize and serialize from/to `rx-usecs`.
	RxUsecs *intstr.IntOrString `json:"rx-usecs,omitempty"`
	// RxUsecsHigh  Deserialize and serialize from/to `rx-usecs-high`.
	RxUsecsHigh *intstr.IntOrString `json:"rx-usecs-high,omitempty"`
	// RxUsecsIrq  Deserialize and serialize from/to `rx-usecs-irq`.
	RxUsecsIrq *intstr.IntOrString `json:"rx-usecs-irq,omitempty"`
	// RxUsecsLow  Deserialize and serialize from/to `rx-usecs-low`.
	RxUsecsLow *intstr.IntOrString `json:"rx-usecs-low,omitempty"`
	// SampleInterval  Deserialize and serialize from/to `sample-interval`.
	SampleInterval *intstr.IntOrString `json:"sample-interval,omitempty"`
	// StatsBlockUsecs  Deserialize and serialize from/to `stats-block-usecs`.
	StatsBlockUsecs *intstr.IntOrString `json:"stats-block-usecs,omitempty"`
	// TxFrames  Deserialize and serialize from/to `tx-frames`.
	TxFrames *intstr.IntOrString `json:"tx-frames,omitempty"`
	// TxFramesHigh  Deserialize and serialize from/to `tx-frames-high`.
	TxFramesHigh *intstr.IntOrString `json:"tx-frames-high,omitempty"`
	// TxFramesIrq  Deserialize and serialize from/to `tx-frames-irq`.
	TxFramesIrq *intstr.IntOrString `json:"tx-frames-irq,omitempty"`
	// TxFramesLow  Deserialize and serialize from/to `tx-frames-low`.
	TxFramesLow *intstr.IntOrString `json:"tx-frames-low,omitempty"`
	// TxUsecs  Deserialize and serialize from/to `tx-usecs`.
	TxUsecs *intstr.IntOrString `json:"tx-usecs,omitempty"`
	// TxUsecsHigh  Deserialize and serialize from/to `tx-usecs-high`.
	TxUsecsHigh *intstr.IntOrString `json:"tx-usecs-high,omitempty"`
	// TxUsecsIrq  Deserialize and serialize from/to `tx-usecs-irq`.
	TxUsecsIrq *intstr.IntOrString `json:"tx-usecs-irq,omitempty"`
	// TxUsecsLow  Deserialize and serialize from/to `tx-usecs-low`.
	TxUsecsLow *intstr.IntOrString `json:"tx-usecs-low,omitempty"`
}

// +k8s:deepcopy-gen=true
type EthtoolRingConfig struct {
	Rx *intstr.IntOrString `json:"rx,omitempty"`
	// RxMax  Deserialize and serialize from/to `rx-max`.
	RxMax *intstr.IntOrString `json:"rx-max,omitempty"`
	// RxJumbo  Deserialize and serialize from/to `rx-jumbo`.
	RxJumbo *intstr.IntOrString `json:"rx-jumbo,omitempty"`
	// RxJumboMax  Deserialize and serialize from/to `rx-jumbo-max`.
	RxJumboMax *intstr.IntOrString `json:"rx-jumbo-max,omitempty"`
	// RxMini  Deserialize and serialize from/to `rx-mini`.
	RxMini *intstr.IntOrString `json:"rx-mini,omitempty"`
	// RxMiniMax  Deserialize and serialize from/to `rx-mini-max`.
	RxMiniMax *intstr.IntOrString `json:"rx-mini-max,omitempty"`
	Tx        *intstr.IntOrString `json:"tx,omitempty"`
	// TxMax  Deserialize and serialize from/to `tx-max`.
	TxMax *intstr.IntOrString `json:"tx-max,omitempty"`
}

// BaseInterface  Information shared among all interface types
// +k8s:deepcopy-gen=true
type BaseInterface struct {
	// Name  Interface name, when applying with `InterfaceIdentifier::MacAddress`,
	// if `profile_name` not defined, this will be used as profile name.
	Name        string  `json:"name"`
	ProfileName *string `json:"profile-name,omitempty"`
	// Description  Interface description stored in network backend. Not available for
	// kernel only mode.
	Description *string `json:"description,omitempty"`
	// Type  Interface type. Serialize and deserialize to/from `type`
	Type InterfaceType `json:"type,omitempty"`
	// State  Interface state. Default to [InterfaceState::Up] when applying.
	State InterfaceState `json:"state,omitempty"`
	// Identifier  Define network backend matching method on choosing network interface.
	// Default to [InterfaceIdentifier::Name].
	Identifier *InterfaceIdentifier `json:"identifier,omitempty"`
	// MacAddress  When applying with `[InterfaceIdentifier::MacAddress]`,
	// nmstate will store original desired interface name as `profile_name`
	// here and store the real interface name as `name` property.
	// For [InterfaceIdentifier::Name] (default), this property will change
	// the interface MAC address to desired one when applying.
	// For [InterfaceIdentifier::MacAddress], this property will be used
	// for searching interface on desired MAC address when applying.
	// MAC address in the format: upper case hex string separated by `:` on
	// every two characters. Case insensitive when applying.
	// Serialize and deserialize to/from `mac-address`.
	MacAddress *string `json:"mac-address,omitempty"`
	// Mtu  Maximum transmission unit.
	Mtu *intstr.IntOrString `json:"mtu,omitempty"`
	// MinMtu  Minimum MTU allowed. Ignored during apply.
	// Serialize and deserialize to/from `min-mtu`.
	MinMtu *uint64 `json:"min-mtu,omitempty"`
	// MaxMtu  Maximum MTU allowed. Ignored during apply.
	// Serialize and deserialize to/from `max-mtu`.
	MaxMtu *uint64 `json:"max-mtu,omitempty"`
	// WaitIP  Whether system should wait certain IP stack before considering
	// network interface activated.
	// Serialize and deserialize to/from `wait-ip`.
	WaitIP *WaitIP `json:"wait-ip,omitempty"`
	// Ipv4  IPv4 information.
	// Hided if interface is not allowed to hold IP information(e.g. port of
	// bond is not allowed to hold IP information).
	Ipv4 *InterfaceIP `json:"ipv4,omitempty"`
	// Ipv6  IPv4 information.
	// Hided if interface is not allowed to hold IP information(e.g. port of
	// bond is not allowed to hold IP information).
	Ipv6 *InterfaceIP `json:"ipv6,omitempty"`
	// Mptcp  Interface wide MPTCP flags.
	// Nmstate will apply these flags to all valid IP addresses(both static
	// and dynamic).
	Mptcp *MptcpConfig `json:"mptcp,omitempty"`
	// Controller  Controller of the specified interface.
	// Only valid for applying, `None` means no change, empty string means
	// detach from current controller, please be advise, an error will trigger
	// if this property conflict with ports list of bridge/bond/etc.
	// Been always set to `None` by [crate::NetworkState::retrieve()].
	Controller *string `json:"controller,omitempty"`
	// AcceptAllMacAddresses  Whether kernel should skip check on package targeting MAC address and
	// accept all packages, also known as promiscuous mode.
	// Serialize and deserialize to/from `accpet-all-mac-addresses`.
	AcceptAllMacAddresses *bool `json:"accept-all-mac-addresses,omitempty"`
	// CopyMacFrom  Copy the MAC address from specified interface.
	// Ignored during serializing.
	// Deserialize from `copy-mac-from`.
	CopyMacFrom *string `json:"copy-mac-from,omitempty"`
	// Ovsdb  Interface specific OpenvSwitch database configurations.
	Ovsdb *OVSDBIfaceConfig `json:"ovs-db,omitempty"`
	// Ieee8021X  IEEE 802.1X authentication configurations.
	// Serialize and deserialize to/from `802.1x`.
	Ieee8021X *Ieee8021XConfig `json:"802.1x,omitempty"`
	// Lldp  Link Layer Discovery Protocol configurations.
	Lldp *LldpConfig `json:"lldp,omitempty"`
	// Ethtool  Ethtool configurations
	Ethtool *EthtoolConfig `json:"ethtool,omitempty"`
	// Dispatch  Dispatch script configurations
	Dispatch *DispatchConfig `json:"dispatch,omitempty"`
}

// EthernetInterface  Ethernet(IEEE 802.3) interface.
// Besides [BaseInterface], optionally could hold [EthernetConfig] and/or
// [VethConfig].
// The yaml output of [crate::NetworkState] containing ethernet interface would
// be:
// ```yml
// interfaces:
//   - name: ens3
//     type: ethernet
//     state: up
//     mac-address: 00:11:22:33:44:FF
//     mtu: 1500
//     min-mtu: 68
//     max-mtu: 65535
//     wait-ip: ipv4
//     ipv4:
//     enabled: true
//     dhcp: false
//     address:
//   - ip: 192.0.2.9
//     prefix-length: 24
//     ipv6:
//     enabled: false
//     mptcp:
//     address-flags: []
//     accept-all-mac-addresses: false
//     lldp:
//     enabled: false
//     ethtool:
//     feature:
//     tx-tcp-ecn-segmentation: true
//     tx-tcp-mangleid-segmentation: false
//     tx-tcp6-segmentation: true
//     tx-tcp-segmentation: true
//     rx-gro-list: false
//     rx-udp-gro-forwarding: false
//     rx-gro-hw: true
//     tx-checksum-ip-generic: true
//     tx-generic-segmentation: true
//     rx-gro: true
//     tx-nocache-copy: false
//     coalesce:
//     rx-frames: 1
//     tx-frames: 1
//     ring:
//     rx: 256
//     rx-max: 256
//     tx: 256
//     tx-max: 256
//     ethernet:
//     auto-negotiation: false
//
// ```
// +k8s:deepcopy-gen=true
type EthernetInterface struct {
	Ethernet *EthernetConfig `json:"ethernet,omitempty"`
	// Veth  When applying, the [VethConfig] is only valid when
	// [BaseInterface.iface_type] is set to [InterfaceType::Veth] explicitly.
	Veth *VethConfig `json:"veth,omitempty"`
}

// +kubebuilder:validation:Enum="full";"half";
type EthernetDuplex string

// EthernetDuplexFull  Deserialize and serialize from/to `full`.
const EthernetDuplexFull = EthernetDuplex("full")

// EthernetDuplexHalf  Deserialize and serialize from/to `half`.
const EthernetDuplexHalf = EthernetDuplex("half")

// enum EthernetDuplex

// +k8s:deepcopy-gen=true
type EthernetConfig struct {
	// SrIov  Single Root I/O Virtualization(SRIOV) configuration.
	// Deserialize and serialize from/to `sr-iov`.
	SrIov *SrIovConfig `json:"sr-iov,omitempty"`
	// AutoNeg  Deserialize and serialize from/to `auto-negotiation`.
	AutoNeg *bool               `json:"auto-negotiation,omitempty"`
	Speed   *intstr.IntOrString `json:"speed,omitempty"`
	Duplex  *EthernetDuplex     `json:"duplex,omitempty"`
}

// +k8s:deepcopy-gen=true
type VethConfig struct {
	// Peer  The name of veth peer.
	Peer string `json:"peer,omitempty"`
}

// MacSecInterface  MACsec interface. The example YAML output of a
// [crate::NetworkState] with an MACsec interface would be:
// ```yaml
// ---
// interfaces:
//   - name: macsec0
//     type: macsec
//     state: up
//     macsec:
//     encrypt: true
//     base-iface: eth1
//     mka-cak: 50b71a8ef0bd5751ea76de6d6c98c03a
//     mka-ckn: f2b4297d39da7330910a74abc0449feb45b5c0b9fc23df1430e1898fcf1c4550
//     port: 0
//     validation: strict
//     send-sci: true
//
// ```
// +k8s:deepcopy-gen=true
type MacSecInterface struct {
	// Macsec  Deserialize and serialize to `macsec`.
	Macsec *MacSecConfig `json:"macsec,omitempty"`
}

// +k8s:deepcopy-gen=true
type MacSecConfig struct {
	// Encrypt  Wether the transmitted traffic must be encrypted.
	Encrypt bool `json:"encrypt"`
	// BaseIface  The parent interface used by the MACsec interface.
	BaseIface string `json:"base-iface"`
	// MkaCak  The pre-shared CAK (Connectivity Association Key) for MACsec Key
	// Agreement. Must be a string of 32 hexadecimal characters.
	MkaCak *string `json:"mka-cak,omitempty"`
	// MkaCkn  The pre-shared CKN (Connectivity-association Key Name) for MACsec Key
	// Agreement. Must be a string of hexadecimal characters with a even
	// length between 2 and 64.
	MkaCkn *string `json:"mka-ckn,omitempty"`
	// Port  The port component of the SCI (Secure Channel Identifier), between 1
	// and 65534.
	Port uint32 `json:"port"`
	// Validation  Specifies the validation mode for incoming frames.
	Validation MacSecValidate `json:"validation"`
	// SendSci  Specifies whether the SCI (Secure Channel Identifier) is included in
	// every packet.
	SendSci bool `json:"send-sci"`
}

// +kubebuilder:validation:Enum="disabled";"check";"strict";
type MacSecValidate string

const MacSecValidateDisabled = MacSecValidate("disabled")
const MacSecValidateCheck = MacSecValidate("check")
const MacSecValidateStrict = MacSecValidate("strict")

// enum MacSecValidate

// IpsecInterface  The libreswan Ipsec interface. This interface does not exist in kernel
// space but only exist in user space tools.
// This is the example yaml output of [crate::NetworkState] with a libreswan
// ipsec connection:
// ```yaml
// ---
// interfaces:
//   - name: hosta_conn
//     type: ipsec
//     ipv4:
//     enabled: true
//     dhcp: true
//     libreswan:
//     right: 192.0.2.252
//     rightid: '@hostb.example.org'
//     left: 192.0.2.251
//     leftid: '%fromcert'
//     leftcert: hosta.example.org
//     ikev2: insist
//
// ```
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
	// Psk  PSK authentication, if not defined, will use X.509 PKI authentication
	Psk               *string                  `json:"psk,omitempty"`
	Ikelifetime       *string                  `json:"ikelifetime,omitempty"`
	Salifetime        *string                  `json:"salifetime,omitempty"`
	Ike               *string                  `json:"ike,omitempty"`
	Esp               *string                  `json:"esp,omitempty"`
	Dpddelay          *intstr.IntOrString      `json:"dpddelay,omitempty"`
	Dpdtimeout        *intstr.IntOrString      `json:"dpdtimeout,omitempty"`
	Dpdaction         *string                  `json:"dpdaction,omitempty"`
	IpsecInterface    *intstr.IntOrString      `json:"ipsec-interface,omitempty"`
	Authby            *string                  `json:"authby,omitempty"`
	Rightsubnet       *string                  `json:"rightsubnet,omitempty"`
	Leftmodecfgclient *bool                    `json:"leftmodecfgclient,omitempty"`
	Kind              *LibreswanConnectionType `json:"type,omitempty"`
	Hostaddrfamily    *LibreswanAddressFamily  `json:"hostaddrfamily,omitempty"`
	Clientaddrfamily  *LibreswanAddressFamily  `json:"clientaddrfamily,omitempty"`
}

// +kubebuilder:validation:Enum="tunnel";"transport";
type LibreswanConnectionType string

const LibreswanConnectionTypeTunnel = LibreswanConnectionType("tunnel")
const LibreswanConnectionTypeTransport = LibreswanConnectionType("transport")

// enum LibreswanConnectionType

// +kubebuilder:validation:Enum="ipv4";"ipv6";
type LibreswanAddressFamily string

const LibreswanAddressFamilyIpv4 = LibreswanAddressFamily("ipv4")
const LibreswanAddressFamilyIpv6 = LibreswanAddressFamily("ipv6")

// enum LibreswanAddressFamily

// HsrInterface  HSR interface. The example YAML output of a
// [crate::NetworkState] with an HSR interface would be:
// ```yaml
// ---
// interfaces:
//   - name: hsr0
//     type: hsr
//     state: up
//     hsr:
//     port1: eth1
//     port2: eth2
//     multicast-spec: 40
//     protocol: prp
//
// ```
// +k8s:deepcopy-gen=true
type HsrInterface struct {
	// Hsr  Deserialize and serialize to `hsr`.
	Hsr *HsrConfig `json:"hsr,omitempty"`
}

// +k8s:deepcopy-gen=true
type HsrConfig struct {
	// Port1  The port1 interface name.
	Port1 string `json:"port1"`
	// Port2  The port2 interface name.
	Port2 string `json:"port2"`
	// SupervisionAddress  The MAC address used for the supervision frames. This property is
	// read-only.
	SupervisionAddress *string `json:"supervision-address,omitempty"`
	// MulticastSpec  The last byte of the supervision address.
	MulticastSpec uint8 `json:"multicast-spec"`
	// Protocol  Protocol to be used.
	Protocol HsrProtocol `json:"protocol"`
}

// +kubebuilder:validation:Enum="hsr";"prp";
type HsrProtocol string

const HsrProtocolHsr = HsrProtocol("hsr")
const HsrProtocolPrp = HsrProtocol("prp")

// enum HsrProtocol

// NetworkState  The [NetworkState] represents the whole network state including both
// kernel status and configurations provides by backends(NetworkManager,
// OpenvSwitch databas, and etc).
//
// Example yaml(many lines omitted) serialized NetworkState would be:
//
// ```yaml
// hostname:
//
//	running: host.example.org
//	config: host.example.org
//
// dns-resolver:
//
//	config:
//	  server:
//	  - 2001:db8:1::
//	  - 192.0.2.1
//	  search: []
//
// route-rules:
//
//	config:
//	- ip-from: 2001:db8:b::/64
//	  priority: 30000
//	  route-table: 200
//	- ip-from: 192.0.2.2/32
//	  priority: 30000
//	  route-table: 200
//
// routes:
//
//	config:
//	- destination: 2001:db8:a::/64
//	  next-hop-interface: eth1
//	  next-hop-address: 2001:db8:1::2
//	  metric: 108
//	  table-id: 200
//	- destination: 192.168.2.0/24
//	  next-hop-interface: eth1
//	  next-hop-address: 192.168.1.3
//	  metric: 108
//	  table-id: 200
//
// interfaces:
//   - name: eth1
//     type: ethernet
//     state: up
//     mac-address: 0E:F9:2B:28:42:D9
//     mtu: 1500
//     ipv4:
//     enabled: true
//     dhcp: false
//     address:
//   - ip: 192.168.1.3
//     prefix-length: 24
//     ipv6:
//     enabled: true
//     dhcp: false
//     autoconf: false
//     address:
//   - ip: 2001:db8:1::1
//     prefix-length: 64
//
// ovs-db:
//
//	external_ids:
//	  hostname: host.example.org
//	  rundir: /var/run/openvswitch
//	  system-id: 176866c7-6dc8-400f-98ac-c658509ec09f
//	other_config: {}
//
// ```
// +k8s:deepcopy-gen=true
type NetworkState struct {
	// Hostname  Hostname of current host.
	Hostname *HostNameState `json:"hostname,omitempty"`
	// DNS  DNS resolver status, deserialize and serialize from/to `dns-resolver`.
	DNS *DNSState `json:"dns-resolver,omitempty"`
	// Rules  Route rule, deserialize and serialize from/to `route-rules`.
	Rules *RouteRules `json:"route-rules,omitempty"`
	// Routes  Route
	Routes *Routes `json:"routes,omitempty"`
	// Interfaces  Network interfaces
	Interfaces []Interface `json:"interfaces,omitempty"`
	// Ovsdb  The global configurations of OpenvSwitach daemon
	Ovsdb *OVSDBGlobalConfig `json:"ovs-db,omitempty"`
	// OVN  The OVN configuration in the system
	OVN *OVNConfiguration `json:"ovn,omitempty"`
}

// OVNConfiguration  Global OVN bridge mapping configuration. Example yaml output of
// [crate::NetworkState]:
// ```yml
// ---
// ovn:
//
//	bridge-mappings:
//	- localnet: tenantblue
//	  bridge: ovsbr1
//	  state: present
//	- localnet: tenantred
//	  bridge: ovsbr1
//	  state: absent
//
// ```
// +k8s:deepcopy-gen=true
type OVNConfiguration struct {
	BridgeMappings *[]OVNBridgeMapping `json:"bridge-mappings,omitempty"`
}

// +k8s:deepcopy-gen=true
type OVNBridgeMapping struct {
	Localnet string `json:"localnet"`
	// State  When set to `state: absent`, will delete the existing
	// `localnet` mapping.
	State  *OVNBridgeMappingState `json:"state,omitempty"`
	Bridge *string                `json:"bridge,omitempty"`
}

// +kubebuilder:validation:Enum="present";"absent";
type OVNBridgeMappingState string

const OVNBridgeMappingStatePresent = OVNBridgeMappingState("present")
const OVNBridgeMappingStateAbsent = OVNBridgeMappingState("absent")

// enum OVNBridgeMappingState

// +k8s:deepcopy-gen=true
type DispatchConfig struct {
	// PostActivation  Dispatch bash script content to be invoked after interface activation
	// finished by network backend. Nmstate will append additional lines
	// to make sure this script is only invoked for specified interface when
	// backend interface activation finished.
	// Setting to empty string will remove the dispatch script
	PostActivation *string `json:"post-activation,omitempty"`
	// PostDeactivation  Dispatch bash script content to be invoked after interface deactivation
	// finished by network backend. Nmstate will append additional lines
	// to make sure this script is only invoked for specified interface when
	// backend interface deactivation finished.
	// Setting to empty string will remove the dispatch script
	PostDeactivation *string `json:"post-deactivation,omitempty"`
}

// +k8s:deepcopy-gen=true
type OVSBridgeStpOptions struct {
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
	*OVSBridgePortConfig     `json:",omitempty"`
	*LinuxBridgePortConfig   `json:",omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgeOptions struct {
	*LinuxBridgeOptions `json:",omitempty"`
	*OVSBridgeOptions   `json:",omitempty"`
}

// BridgeConfig Linux or OVS bridge configuration
//
// Linux bridge:   Bridge interface provided by linux kernel.
// When serializing or deserializing, the [BaseInterface] will
// be flatted and [LinuxBridgeConfig] stored as `bridge` section. The yaml
// output [crate::NetworkState] containing an example linux bridge interface:
// ```yml
// interfaces:
//   - name: br0
//     type: linux-bridge
//     state: up
//     mac-address: 9A:91:53:6C:67:DA
//     mtu: 1500
//     min-mtu: 68
//     max-mtu: 65535
//     wait-ip: any
//     ipv4:
//     enabled: false
//     ipv6:
//     enabled: false
//     bridge:
//     options:
//     gc-timer: 29594
//     group-addr: 01:80:C2:00:00:00
//     group-forward-mask: 0
//     group-fwd-mask: 0
//     hash-max: 4096
//     hello-timer: 46
//     mac-ageing-time: 300
//     multicast-last-member-count: 2
//     multicast-last-member-interval: 100
//     multicast-membership-interval: 26000
//     multicast-querier: false
//     multicast-querier-interval: 25500
//     multicast-query-interval: 12500
//     multicast-query-response-interval: 1000
//     multicast-query-use-ifaddr: false
//     multicast-router: auto
//     multicast-snooping: true
//     multicast-startup-query-count: 2
//     multicast-startup-query-interval: 3125
//     stp:
//     enabled: true
//     forward-delay: 15
//     hello-time: 2
//     max-age: 20
//     priority: 32768
//     vlan-protocol: 802.1q
//     port:
//   - name: eth1
//     stp-hairpin-mode: false
//     stp-path-cost: 100
//     stp-priority: 32
//   - name: eth2
//     stp-hairpin-mode: false
//     stp-path-cost: 100
//     stp-priority: 32
//
// ```
//
// OVS bridge:   OpenvSwitch bridge interface. Example yaml output of [crate::NetworkState]
// with an OVS bridge:
// ```yaml
// ---
// interfaces:
//   - name: br0
//     type: ovs-interface
//     state: up
//     ipv4:
//     address:
//   - ip: 192.0.2.252
//     prefix-length: 24
//   - ip: 192.0.2.251
//     prefix-length: 24
//     dhcp: false
//     enabled: true
//     ipv6:
//     address:
//   - ip: 2001:db8:2::1
//     prefix-length: 64
//   - ip: 2001:db8:1::1
//     prefix-length: 64
//     autoconf: false
//     dhcp: false
//     enabled: true
//   - name: br0
//     type: ovs-bridge
//     state: up
//     bridge:
//     port:
//   - name: br0
//   - name: eth1
//
// ```
// +k8s:deepcopy-gen=true
type BridgeConfig struct {
	*OVSBridgeConfig `json:",omitempty"`
	Options          *BridgeOptions      `json:"options,omitempty"`
	Ports            *[]BridgePortConfig `json:"port,omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgeInterface struct {
	*BridgeConfig `json:"bridge,omitempty"`
}
