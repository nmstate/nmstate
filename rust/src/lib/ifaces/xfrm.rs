// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::{BaseInterface, InterfaceType};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
pub struct XfrmInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
}

impl Default for XfrmInterface {
    fn default() -> Self {
        let mut base = BaseInterface::new();
        base.iface_type = InterfaceType::Xfrm;
        Self { base }
    }
}

impl XfrmInterface {
    pub fn new() -> Self {
        Self::default()
    }
}
