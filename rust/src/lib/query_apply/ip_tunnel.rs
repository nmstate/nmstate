// SPDX-License-Identifier: Apache-2.0

use crate::{Ip6TunnelFlag, IpTunnelInterface};

const READONLY_IP6TUN_FLAGS: [Ip6TunnelFlag; 3] = [
    Ip6TunnelFlag::CapXmit,
    Ip6TunnelFlag::CapRcv,
    Ip6TunnelFlag::CapPerPacket,
];

impl IpTunnelInterface {
    fn sanitize_for_verify(&mut self) {
        if let Some(conf) = &mut self.ip_tunnel
            && let Some(flags) = &mut conf.ip6tun_flags
        {
            flags.dedup();
            flags.sort_unstable();

            // Remove read-only flags from state.
            flags.retain(|flag| !READONLY_IP6TUN_FLAGS.contains(flag));
        }
    }

    pub(crate) fn sanitize_desired_for_verify(&mut self) {
        self.sanitize_for_verify();
    }

    pub(crate) fn sanitize_current_for_verify(&mut self) {
        self.sanitize_for_verify();
    }
}
