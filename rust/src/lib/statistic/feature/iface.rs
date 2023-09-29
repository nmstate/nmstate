// SPDX-License-Identifier: Apache-2.0

use crate::{
    BaseInterface, Interface, InterfaceIdentifier, MergedInterface,
    NmstateFeature,
};

impl MergedInterface {
    pub(crate) fn get_features(&self) -> Vec<NmstateFeature> {
        let mut ret: Vec<NmstateFeature> = Vec::new();
        if self.merged.base_iface().identifier
            == InterfaceIdentifier::MacAddress
        {
            ret.push(NmstateFeature::MacBasedIdentifier);
        }

        if let Some(iface) = self.for_apply.as_ref() {
            ret.append(&mut iface.base_iface().get_features());
            match iface {
                Interface::OvsBridge(iface) => {
                    ret.append(&mut iface.get_features());
                }
                Interface::OvsInterface(iface) => {
                    ret.append(&mut iface.get_features());
                }
                Interface::Ethernet(iface) => {
                    ret.append(&mut iface.get_features());
                }
                _ => (),
            }
        }
        ret
    }
}

impl BaseInterface {
    pub(crate) fn get_features(&self) -> Vec<NmstateFeature> {
        let mut ret = Vec::new();
        if self.ovsdb.as_ref().map(|o| !o.is_empty()) == Some(true) {
            ret.push(NmstateFeature::OvsDbInterface);
        }
        ret
    }
}
