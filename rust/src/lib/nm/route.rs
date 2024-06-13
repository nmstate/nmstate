// SPDX-License-Identifier: Apache-2.0

use crate::{MergedNetworkState, NmstateError};

pub(crate) fn store_route_config(
    merged_state: &mut MergedNetworkState,
) -> Result<(), NmstateError> {
    if merged_state.routes.is_changed() {
        let empty_rts = Vec::new();
        for iface_name in merged_state.routes.route_changed_ifaces.as_slice() {
            let rts =
                if let Some(rts) = merged_state.routes.merged.get(iface_name) {
                    rts
                } else {
                    &empty_rts
                };
            if let Some(iface) =
                merged_state.interfaces.kernel_ifaces.get_mut(iface_name)
            {
                if !iface.is_changed() {
                    iface.mark_as_changed();
                }
                if let Some(apply_iface) = iface.for_apply.as_mut() {
                    if apply_iface.base_iface_mut().ipv4.is_none() {
                        apply_iface
                            .base_iface_mut()
                            .ipv4
                            .clone_from(&iface.merged.base_iface_mut().ipv4);
                    }
                    if apply_iface.base_iface_mut().ipv6.is_none() {
                        apply_iface
                            .base_iface_mut()
                            .ipv6
                            .clone_from(&iface.merged.base_iface_mut().ipv6);
                    }
                    apply_iface.base_iface_mut().routes = Some(rts.clone());
                }
            }
        }
    }
    Ok(())
}
