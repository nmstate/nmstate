// SPDX-License-Identifier: Apache-2.0

use crate::{ErrorKind, InterfaceType, MergedInterfaces, NmstateError};

/// NetworkManager always brings an OVS internal interface link up on
/// activation and offers no way to keep it administratively down while the
/// connection stays active (the only "down" it has detaches the port from the
/// bridge). To support `state: down` on OVS internal interfaces — keeping them
/// attached to the bridge with the link DOWN, like `ovs-vsctl add-br` — we set
/// the kernel link state directly via nispor after the NetworkManager apply.
/// See NMT-2268.
pub(crate) async fn enforce_ovs_internal_link_state(
    merged_ifaces: &MergedInterfaces,
) -> Result<(), NmstateError> {
    let np_ifaces: Vec<nispor::IfaceConf> = merged_ifaces
        .kernel_ifaces
        .values()
        .filter_map(|i| {
            let iface = i.for_apply.as_ref()?;
            if !i.is_desired()
                || iface.iface_type() != InterfaceType::OvsInterface
            {
                return None;
            }
            let state = if iface.is_down() {
                nispor::IfaceState::Down
            } else if iface.is_up() {
                nispor::IfaceState::Up
            } else {
                return None;
            };
            let mut np_iface = nispor::IfaceConf::default();
            np_iface.name = iface.name().to_string();
            np_iface.iface_type = Some(nispor::IfaceType::OpenvSwitch);
            np_iface.state = state;
            Some(np_iface)
        })
        .collect();

    if np_ifaces.is_empty() {
        return Ok(());
    }

    let mut net_conf = nispor::NetConf::default();
    net_conf.ifaces = Some(np_ifaces);

    // The OVS internal kernel link may not be ready immediately after the
    // NetworkManager activation returns, so retry a few times.
    let mut last_err = None;
    for _ in 0..5 {
        match net_conf.apply_async().await {
            Ok(()) => return Ok(()),
            Err(e) => {
                last_err = Some(e);
                tokio::time::sleep(std::time::Duration::from_millis(200)).await;
            }
        }
    }
    if let Some(e) = last_err {
        return Err(NmstateError::new(
            ErrorKind::PluginFailure,
            format!(
                "Failed to set OVS internal interface link state: {} {}",
                e.kind, e.msg
            ),
        ));
    }
    Ok(())
}
