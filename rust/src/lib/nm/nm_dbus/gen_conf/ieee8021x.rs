// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use super::super::{NmError, NmSetting8021X, ToKeyfile};

impl ToKeyfile for NmSetting8021X {
    fn to_keyfile(&self) -> Result<HashMap<String, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.identity {
            ret.insert("identity".to_string(), zvariant::Value::new(v));
        }
        if let Some(v) = &self.private_key {
            ret.insert(
                "private-key".to_string(),
                if let Ok(path) = Self::glib_bytes_to_file_path(v) {
                    zvariant::Value::new(path)
                } else {
                    zvariant::Value::new(v)
                },
            );
        }
        if let Some(v) = &self.eap {
            // Need NULL append at the end
            let mut new_eaps = v.clone();
            new_eaps.push("".to_string());
            ret.insert("eap".to_string(), zvariant::Value::new(new_eaps));
        }
        if let Some(v) = &self.client_cert {
            ret.insert(
                "client-cert".to_string(),
                if let Ok(path) = Self::glib_bytes_to_file_path(v) {
                    zvariant::Value::new(path)
                } else {
                    zvariant::Value::new(v)
                },
            );
        }
        if let Some(v) = &self.ca_cert {
            ret.insert(
                "ca-cert".to_string(),
                if let Ok(path) = Self::glib_bytes_to_file_path(v) {
                    zvariant::Value::new(path)
                } else {
                    zvariant::Value::new(v)
                },
            );
        }
        if let Some(v) = &self.private_key_password {
            ret.insert(
                "private-key-password".to_string(),
                zvariant::Value::new(v),
            );
        }
        if let Some(v) = &self.phase2_auth {
            ret.insert("phase2-auth".to_string(), zvariant::Value::new(v));
        }
        if let Some(v) = &self.password {
            ret.insert("password".to_string(), zvariant::Value::new(v));
        }
        Ok(ret)
    }
}
