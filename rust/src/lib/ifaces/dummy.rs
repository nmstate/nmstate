use serde::{Deserialize, Serialize};

use crate::{BaseInterface, InterfaceType};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
/// Dummy interface. Only contain information of [BaseInterface].
/// Example yaml outpuf of `[crate::NetworkState]` with dummy interface:
/// ```yml
/// interfaces:
/// - name: dummy1
///   type: dummy
///   state: up
///   mac-address: BE:25:F0:6D:55:64
///   mtu: 1500
///   wait-ip: any
///   ipv4:
///     enabled: false
///   ipv6:
///     enabled: false
///   accept-all-mac-addresses: false
///   lldp:
///     enabled: false
///   ethtool:
///     feature:
///       tx-checksum-ip-generic: true
///       tx-ipxip6-segmentation: true
///       rx-gro: true
///       tx-generic-segmentation: true
///       tx-udp-segmentation: true
///       tx-udp_tnl-csum-segmentation: true
///       rx-udp-gro-forwarding: false
///       tx-tcp-segmentation: true
///       tx-sctp-segmentation: true
///       tx-ipxip4-segmentation: true
///       tx-nocache-copy: false
///       tx-gre-csum-segmentation: true
///       tx-udp_tnl-segmentation: true
///       tx-tcp-mangleid-segmentation: true
///       rx-gro-list: false
///       tx-scatter-gather-fraglist: true
///       tx-gre-segmentation: true
///       tx-tcp-ecn-segmentation: true
///       tx-gso-list: true
///       highdma: true
///       tx-tcp6-segmentation: true
/// ```
pub struct DummyInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
}

impl Default for DummyInterface {
    fn default() -> Self {
        let mut base = BaseInterface::new();
        base.iface_type = InterfaceType::Dummy;
        Self { base }
    }
}

impl DummyInterface {
    pub fn new() -> Self {
        Self::default()
    }
}
