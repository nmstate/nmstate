use std::collections::HashMap;

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct OvsDbGlobalConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub external_ids: Option<HashMap<String, String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub other_config: Option<HashMap<String, String>>,
}

#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct OvsDbIfaceConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub external_ids: Option<HashMap<String, String>>,
}
