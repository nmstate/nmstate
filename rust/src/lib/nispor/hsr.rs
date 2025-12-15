// SPDX-License-Identifier: Apache-2.0

use crate::{BaseInterface, HsrConfig, HsrInterface, HsrProtocol};

fn protocol_from_np(
    np_protocol: nispor::HsrProtocol,
    version: u8,
) -> HsrProtocol {
    match (np_protocol, version) {
        (nispor::HsrProtocol::Hsr, 0) => HsrProtocol::Hsr,
        (nispor::HsrProtocol::Hsr, 1) => HsrProtocol::Hsr2012,
        (nispor::HsrProtocol::Prp, _) => HsrProtocol::Prp,
        _ => {
            log::warn!(
                "Unknown HSR protocol {np_protocol:?} with version {version}"
            );
            HsrProtocol::default()
        }
    }
}

pub(crate) fn np_hsr_to_nmstate(
    np_iface: &nispor::Iface,
    base_iface: BaseInterface,
) -> HsrInterface {
    let mut mutlicast_value: u8 = 0;
    if let Some(conf) = np_iface.hsr.as_ref() {
        mutlicast_value = {
            let hex_value: String = conf
                .supervision_addr
                .clone()
                .chars()
                .rev()
                .take(2)
                .collect::<String>()
                .chars()
                .rev()
                .collect();
            u8::from_str_radix(hex_value.as_str(), 16).unwrap_or_default()
        };
    }
    let hsr_conf = np_iface.hsr.as_ref().map(|np_hsr_info| HsrConfig {
        port1: np_hsr_info.port1.clone().unwrap_or_default(),
        port2: np_hsr_info.port2.clone().unwrap_or_default(),
        interlink: np_hsr_info.interlink.clone(),
        supervision_address: Some(np_hsr_info.supervision_addr.clone()),
        // Due to a kernel bug multicast_spec is always zero. Until it is fixed,
        // use the last byte of supervision_address instead.
        multicast_spec: mutlicast_value,
        protocol: protocol_from_np(np_hsr_info.protocol, np_hsr_info.version),
    });

    HsrInterface {
        base: base_iface,
        hsr: hsr_conf,
    }
}
