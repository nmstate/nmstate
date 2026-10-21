// SPDX-License-Identifier: Apache-2.0

use crate::{NmstateError, nispor::error::np_error_to_nmstate};

pub(crate) async fn delete_kernel_iface(
    name: &str,
) -> Result<(), NmstateError> {
    let mut iface = nispor::IfaceConf::default();
    iface.name = name.to_string();
    iface.state = nispor::IfaceState::Absent;
    let mut net_conf = nispor::NetConf::default();
    net_conf.ifaces = Some(vec![iface]);
    net_conf.apply_async().await.map_err(np_error_to_nmstate)
}
