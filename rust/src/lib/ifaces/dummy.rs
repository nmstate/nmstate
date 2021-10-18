use serde::{Deserialize, Serialize};

use crate::{BaseInterface, InterfaceType};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DummyInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
}

impl Default for DummyInterface {
    fn default() -> Self {
        Self {
            base: BaseInterface {
                iface_type: InterfaceType::Dummy,
                ..Default::default()
            },
        }
    }
}

impl DummyInterface {
    pub fn new(base: BaseInterface) -> Self {
        Self { base }
    }
}
