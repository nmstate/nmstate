use crate::{nm::version, NmstateError};

use serde::Serialize;

#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize)]
pub struct Plugin {
    name: String,
    version: String,
}

pub(crate) fn list_plugins() -> Result<Vec<Plugin>, NmstateError> {
    Ok(vec![Plugin {
        name: "NetworkManager".to_string(),
        version: version::nm_version().unwrap(),
    }])
}
