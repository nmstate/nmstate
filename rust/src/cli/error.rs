use nmstate::NmstateError;

pub(crate) struct CliError {
    pub(crate) msg: String,
}

impl std::fmt::Display for CliError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.msg)
    }
}

impl From<std::io::Error> for CliError {
    fn from(e: std::io::Error) -> Self {
        Self {
            msg: format!("std::io::Error: {}", e),
        }
    }
}

impl From<NmstateError> for CliError {
    fn from(e: NmstateError) -> Self {
        Self {
            msg: format!("NmstateError: {}", e),
        }
    }
}

impl From<serde_yaml::Error> for CliError {
    fn from(e: serde_yaml::Error) -> Self {
        Self {
            msg: format!("serde_yaml::Error: {}", e),
        }
    }
}

impl From<clap::Error> for CliError {
    fn from(e: clap::Error) -> Self {
        Self {
            msg: format!("clap::Error {}", e),
        }
    }
}
