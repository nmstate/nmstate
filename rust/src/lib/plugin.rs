use crate::{nm::version, NmstateError};

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
