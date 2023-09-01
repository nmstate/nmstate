// SPDX-License-Identifier: Apache-2.0

use crate::{MacSecConfig, MacSecInterface};

impl MacSecInterface {
    pub(crate) fn update_macsec(&mut self, other: &MacSecInterface) {
        if let Some(macsec_conf) = &mut self.macsec {
            macsec_conf.update(other.macsec.as_ref());
        } else {
            self.macsec = other.macsec.clone();
        }
    }
}

impl MacSecConfig {
    // Only allow update `mka_cak` and `mka_ckn` as other values should be
    // provided by nispor netlink code.
    fn update(&mut self, other: Option<&Self>) {
        if let Some(other) = other {
            self.mka_cak = other.mka_cak.clone();
            self.mka_ckn = other.mka_ckn.clone();
        }
    }
}
