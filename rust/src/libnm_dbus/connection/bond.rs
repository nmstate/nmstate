use std::collections::HashMap;
use std::convert::TryFrom;

use serde::Deserialize;

use crate::{connection::DbusDictionary, NmError};

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingBond {
    pub mode: String,
    pub options: HashMap<String, String>,
    _other: HashMap<String, String>,
}

impl TryFrom<DbusDictionary> for NmSettingBond {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        let mut options = HashMap::<String, String>::new();
        let mut other = HashMap::<String, String>::new();

        if let Some(value) = _from_map!(v, "options", HashMap::try_from)? {
            options = value.clone();
            other = value;
        }
        Ok(Self {
            mode: String::new(),
            options,
            _other: other,
        })
    }
}

impl NmSettingBond {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn to_value(
        &self,
    ) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut merged_opts = self.options.clone();
        let mut ret = HashMap::new();

        // Do not merge existing options if the user specified empty options
        merged_opts.extend(
            self._other
                .iter()
                .filter(|(k, _)| !self.options.contains_key(*k))
                .map(|(k, v)| (k.to_string(), v.to_string())),
        );
        if let Some(arp_ip_target) = self.options.get("arp_ip_target") {
            if arp_ip_target.is_empty() {
                merged_opts.remove("arp_ip_target");
            }
        }

        if !self.mode.is_empty() {
            merged_opts.insert("mode".to_string(), self.mode.clone());
        }

        if !merged_opts.is_empty() {
            ret.insert("options", zvariant::Value::from(merged_opts.clone()));
        }
        Ok(ret)
    }

    pub fn clear_existing_opts(&mut self) {
        self._other.clear();
    }

    pub fn get_current_mode(&self) -> Option<&String> {
        self._other.get(&String::from("mode"))
    }
}
