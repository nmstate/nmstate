// SPDX-License-Identifier: Apache-2.0

use crate::nm::nm_dbus::{NmConnection, NmSettingMacSec};

use crate::{MacSecInterface, MacSecOffload};

pub(crate) fn gen_nm_macsec_setting(
    iface: &MacSecInterface,
    nm_conn: &mut NmConnection,
) {
    let mut nm_macsec_set =
        nm_conn.macsec.as_ref().cloned().unwrap_or_default();
    if let Some(macsec_conf) = iface.macsec.as_ref() {
        nm_macsec_set.parent = Some(macsec_conf.base_iface.clone());
        nm_macsec_set.encrypt = Some(macsec_conf.encrypt);
        nm_macsec_set.mka_cak = macsec_conf.mka_cak.clone();
        nm_macsec_set.mka_ckn = macsec_conf.mka_ckn.clone();
        nm_macsec_set.port = Some(macsec_conf.port as i32);
        nm_macsec_set.validation = Some(macsec_conf.validation.into());
        nm_macsec_set.send_sci = Some(macsec_conf.send_sci);
        if let Some(v) = macsec_conf.offload.as_ref() {
            nm_macsec_set.offload = Some(match v {
                MacSecOffload::Off => NmSettingMacSec::OFFLOAD_OFF,
                MacSecOffload::Phy => NmSettingMacSec::OFFLOAD_PHY,
                MacSecOffload::Mac => NmSettingMacSec::OFFLOAD_MAC,
            });
        }
    }
    nm_conn.macsec = Some(nm_macsec_set)
}
