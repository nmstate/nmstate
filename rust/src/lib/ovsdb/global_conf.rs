use serde_json::{Map, Value};

use crate::{ovsdb::db::parse_str_map, OvsDbGlobalConfig};

impl From<&Map<std::string::String, Value>> for OvsDbGlobalConfig {
    fn from(m: &Map<std::string::String, Value>) -> Self {
        let mut ret = Self::default();
        if let (Some(Value::Array(ids)), Some(Value::Array(other_cfg))) =
            (m.get("external_ids"), m.get("other_config"))
        {
            ret.external_ids = Some(parse_str_map(ids));
            ret.other_config = Some(parse_str_map(other_cfg));
        }
        ret
    }
}
