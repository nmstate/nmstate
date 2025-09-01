// SPDX-License-Identifier: Apache-2.0

use crate::Interface;

impl Interface {
    pub(crate) fn alt_name_pre_verify(&self, current: &mut Self) {
        if let Some(des_alt_names) = self.base_iface().alt_names.as_ref() {
            let cur_alt_names =
                current.base_iface_mut().alt_names.get_or_insert(Vec::new());

            for des_alt_name in des_alt_names {
                if des_alt_name.is_absent() {
                    // Add `state: absent` entry, so follow up verification
                    // process can pass
                    if !cur_alt_names
                        .iter()
                        .any(|c| c.name == des_alt_name.name)
                    {
                        cur_alt_names.push(des_alt_name.clone())
                    }
                }
            }
            // In order to pass the verification, we need to remove extra
            // alt name not desired
            cur_alt_names
                .retain(|cur_alt_name| des_alt_names.contains(cur_alt_name));

            cur_alt_names.sort_unstable();
        }
    }
}
