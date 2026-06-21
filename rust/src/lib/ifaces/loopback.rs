// SPDX-License-Identifier: Apache-2.0

use std::net::{Ipv4Addr, Ipv6Addr};

use serde::{Deserialize, Serialize};

use crate::{
    BaseInterface, ErrorKind, Interface, InterfaceIpAddr, InterfaceIpv4,
    InterfaceIpv6, InterfaceState, InterfaceType, MergedInterface,
    NmstateError,
};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
/// Loopback interface. Only contain information of [BaseInterface].
/// Limitations
///  * Cannot enable DHCP or autoconf.
///  * The [InterfaceState::Absent] can only restore the loopback configure back
///    to default.
///  * Cannot disable IPv4.
///  * Cannot disable IPv6 unless it is already reported disabled, so `show`
///    output round-trips (e.g. on a host booted with `ipv6.disable=1`).
///  * Even when not desired, `127.0.0.1/8` and `::1` (the latter only when IPv6
///    is enabled) are always appended to the static IP address list.
///  * Require NetworkManager 1.41+ unless in kernel only mode.
///
/// Example yaml outpuf of `[crate::NetworkState]` with loopback interface:
/// ```yml
/// interfaces:
/// - name: lo
///   type: loopback
///   state: up
///   mtu: 65535
///   ipv4:
///     enabled: true
///     address:
///     - ip: 127.0.0.1
///       prefix-length: 8
///   ipv6:
///     enabled: true
///     address:
///     - ip: ::1
///       prefix-length: 128
///   accept-all-mac-addresses: false
/// ```
pub struct LoopbackInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
}

impl Default for LoopbackInterface {
    fn default() -> Self {
        let mut base = BaseInterface::new();
        base.iface_type = InterfaceType::Loopback;
        base.name = "lo".to_string();
        base.state = InterfaceState::Up;
        base.ipv4 = Some(InterfaceIpv4 {
            enabled: true,
            enabled_defined: true,
            addresses: Some(vec![InterfaceIpAddr {
                ip: Ipv4Addr::LOCALHOST.into(),
                prefix_length: 8,
                ..Default::default()
            }]),
            ..Default::default()
        });
        base.ipv6 = Some(InterfaceIpv6 {
            enabled: true,
            enabled_defined: true,
            addresses: Some(vec![InterfaceIpAddr {
                ip: Ipv6Addr::LOCALHOST.into(),
                prefix_length: 128,
                ..Default::default()
            }]),
            ..Default::default()
        });

        Self { base }
    }
}

impl LoopbackInterface {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn sanitize(
        &self,
        is_desired: bool,
    ) -> Result<(), NmstateError> {
        if is_desired {
            if self.base.ipv4.as_ref().map(|i| i.enabled) == Some(false) {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    "Loopback interface cannot have IPv4 disabled".to_string(),
                ));
            }
            if self.base.ipv4.as_ref().map(|i| i.is_auto()) == Some(true) {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    "Loopback interface cannot have IPv4 DHCP enabled"
                        .to_string(),
                ));
            }
            if self.base.ipv6.as_ref().map(|i| i.is_auto()) == Some(true) {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    "Loopback interface cannot have IPv6 autoconf/DHCPv6 \
                     enabled"
                        .to_string(),
                ));
            }
        }
        Ok(())
    }
}

impl MergedInterface {
    // Allow disabling IPv6 on loopback only when it is already reported
    // disabled, so `nmstatectl show` output can be reapplied.
    pub(crate) fn post_inter_ifaces_process_loopback(
        &self,
    ) -> Result<(), NmstateError> {
        let apply_iface = match self.for_apply.as_ref() {
            Some(Interface::Loopback(i)) => i,
            _ => return Ok(()),
        };
        let cur_ipv6_enabled = match self.current.as_ref() {
            Some(Interface::Loopback(i)) => {
                i.base.ipv6.as_ref().map(|ip| ip.enabled)
            }
            _ => None,
        };
        if apply_iface.base.ipv6.as_ref().map(|ip| ip.enabled) == Some(false)
            && cur_ipv6_enabled != Some(false)
        {
            return Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                "Loopback interface cannot have IPv6 disabled".to_string(),
            ));
        }
        Ok(())
    }
}
