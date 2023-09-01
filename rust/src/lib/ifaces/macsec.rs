// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::{
    BaseInterface, ErrorKind, InterfaceType, NetworkState, NmstateError,
};

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
/// MACsec interface. The example YAML output of a
/// [crate::NetworkState] with an MACsec interface would be:
/// ```yaml
/// ---
/// interfaces:
///   - name: macsec0
///     type: macsec
///     state: up
///     macsec:
///       encrypt: true
///       parent: eth1
///       mka-cak: 50b71a8ef0bd5751ea76de6d6c98c03a
///       mka-ckn: f2b4297d39da7330910a74abc0449feb45b5c0b9fc23df1430e1898fcf1c4550
///       port: 0
///       validation: strict
///       send-sci: true
/// ```
pub struct MacSecInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Deserialize and serialize to `macsec`.
    pub macsec: Option<MacSecConfig>,
}

impl Default for MacSecInterface {
    fn default() -> Self {
        Self {
            base: BaseInterface {
                iface_type: InterfaceType::MacSec,
                ..Default::default()
            },
            macsec: None,
        }
    }
}

impl MacSecInterface {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn sanitize(
        &self,
        is_desired: bool,
    ) -> Result<(), NmstateError> {
        if is_desired {
            if let Some(conf) = &self.macsec {
                if conf.mka_cak.is_none() ^ conf.mka_ckn.is_none() {
                    let e = NmstateError::new(
                        ErrorKind::InvalidArgument,
                        "The mka_cak and mka_cnk must be all missing or present.".to_string(),
                    );
                    log::error!("{}", e);
                    return Err(e);
                }
                if let Some(mka_cak) = &conf.mka_cak {
                    if mka_cak.len() != 32 {
                        let e = NmstateError::new(
                            ErrorKind::InvalidArgument,
                            "The mka_cak must be a string of 32 characters"
                                .to_string(),
                        );
                        log::error!("{}", e);
                        return Err(e);
                    }
                }
                if let Some(mka_ckn) = &conf.mka_ckn {
                    if mka_ckn.len() > 64
                        || mka_ckn.len() < 2
                        || mka_ckn.len() % 2 == 1
                    {
                        let e = NmstateError::new(ErrorKind::InvalidArgument,
                        "The mka_ckn must be a string of even size between 2 and 64 characters".to_string());
                        log::error!("{}", e);
                        return Err(e);
                    }
                }
            }
        }
        Ok(())
    }

    pub(crate) fn parent(&self) -> Option<&str> {
        self.macsec.as_ref().map(|cfg| cfg.parent.as_str())
    }
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
#[derive(Default)]
pub struct MacSecConfig {
    /// Wether the transmitted traffic must be encrypted.
    pub encrypt: bool,
    /// The parent interface used by the MACsec interface.
    pub parent: String,
    /// The pre-shared CAK (Connectivity Association Key) for MACsec Key
    /// Agreement. Must be a string of 32 hexadecimal characters.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mka_cak: Option<String>,
    /// The pre-shared CKN (Connectivity-association Key Name) for MACsec Key
    /// Agreement. Must be a string of hexadecimal characters with a even
    /// length between 2 and 64.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mka_ckn: Option<String>,
    /// The port component of the SCI (Secure Channel Identifier), between 1
    /// and 65534.
    pub port: u32,
    /// Specifies the validation mode for incoming frames.
    pub validation: MacSecValidate,
    /// Specifies whether the SCI (Secure Channel Identifier) is included in
    /// every packet.
    pub send_sci: bool,
}

impl MacSecConfig {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn hide_secrets(&mut self) {
        if self.mka_cak.is_some() {
            self.mka_cak =
                Some(NetworkState::PASSWORD_HID_BY_NMSTATE.to_string());
        }
    }
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone, Copy)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum MacSecValidate {
    Disabled,
    Check,
    Strict,
}

impl Default for MacSecValidate {
    fn default() -> Self {
        Self::Disabled
    }
}

impl From<MacSecValidate> for u32 {
    fn from(v: MacSecValidate) -> u32 {
        match v {
            MacSecValidate::Disabled => 0,
            MacSecValidate::Check => 1,
            MacSecValidate::Strict => 2,
        }
    }
}

impl From<MacSecValidate> for i32 {
    fn from(v: MacSecValidate) -> i32 {
        match v {
            MacSecValidate::Disabled => 0,
            MacSecValidate::Check => 1,
            MacSecValidate::Strict => 2,
        }
    }
}
