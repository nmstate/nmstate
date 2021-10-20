use serde::{Deserialize, Serialize};

use crate::{BaseInterface, InterfaceType};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DummyInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
}

impl Default for DummyInterface {
    fn default() -> Self {
        let mut base = BaseInterface::new();
        base.iface_type = InterfaceType::Dummy;
        Self { base }
    }
}

impl DummyInterface {
    pub fn new(base: BaseInterface) -> Self {
        Self { base }
    }
}
