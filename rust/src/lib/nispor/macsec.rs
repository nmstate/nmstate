// SPDX-License-Identifier: Apache-2.0

use crate::{
    BaseInterface, MacSecConfig, MacSecInterface, MacSecOffload, MacSecValidate,
};

impl From<nispor::MacSecValidate> for MacSecValidate {
    fn from(v: nispor::MacSecValidate) -> Self {
        match v {
            nispor::MacSecValidate::Disabled => Self::Disabled,
            nispor::MacSecValidate::Check => Self::Check,
            nispor::MacSecValidate::Strict => Self::Strict,
            _ => {
                log::warn!("Unknown MACsec validate mode {:?}", v);
                Self::default()
            }
        }
    }
}

impl From<nispor::MacSecOffload> for MacSecOffload {
    fn from(v: nispor::MacSecOffload) -> Self {
        match v {
            nispor::MacSecOffload::Off => Self::Off,
            nispor::MacSecOffload::Phy => Self::Phy,
            nispor::MacSecOffload::Mac => Self::Mac,
            _ => {
                log::warn!("Unknown MACsec offload mode {:?}", v);
                Self::default()
            }
        }
    }
}

pub(crate) fn np_macsec_to_nmstate(
    np_iface: &nispor::Iface,
    base_iface: BaseInterface,
) -> MacSecInterface {
    let macsec_conf =
        np_iface.macsec.as_ref().map(|np_macsec_info| MacSecConfig {
            encrypt: np_macsec_info.encrypt,
            port: np_macsec_info.port.into(),
            validation: np_macsec_info.validate.into(),
            send_sci: np_macsec_info.send_sci,
            base_iface: np_macsec_info.base_iface.clone().unwrap_or_default(),
            mka_cak: None,
            mka_ckn: None,
            offload: Some(np_macsec_info.offload.into()),
        });

    MacSecInterface {
        base: base_iface,
        macsec: macsec_conf,
    }
}
