// SPDX-License-Identifier: Apache-2.0

use crate::{mptcp::remove_per_addr_mptcp_flags, BaseInterface};

pub(crate) fn mptcp_pre_verify_cleanup(iface: &mut BaseInterface) {
    remove_per_addr_mptcp_flags(iface);
    if let Some(addrs) =
        iface.mptcp.as_mut().and_then(|m| m.address_flags.as_mut())
    {
        addrs.sort_unstable();
    }
}
