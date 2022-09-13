use serde::{Deserialize, Serialize};

use crate::{BaseInterface, ErrorKind, Interface, InterfaceType, NmstateError};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
pub struct VrfInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vrf: Option<VrfConfig>,
}

impl Default for VrfInterface {
    fn default() -> Self {
        Self {
            base: BaseInterface {
                iface_type: InterfaceType::Vrf,
                ..Default::default()
            },
            vrf: None,
        }
    }
}

impl VrfInterface {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn ports(&self) -> Option<Vec<&str>> {
        self.vrf
            .as_ref()
            .and_then(|vrf_conf| vrf_conf.port.as_ref())
            .map(|ports| ports.as_slice().iter().map(|p| p.as_str()).collect())
    }

    pub(crate) fn update_vrf(&mut self, other: &VrfInterface) {
        // TODO: this should be done by Trait
        if let Some(vrf_conf) = &mut self.vrf {
            vrf_conf.update(other.vrf.as_ref());
        } else {
            self.vrf = other.vrf.clone();
        }
    }

    // Merge table ID from current if desired table ID is 0
    pub(crate) fn pre_edit_cleanup(
        &mut self,
        current: Option<&Interface>,
    ) -> Result<(), NmstateError> {
        self.merge_table_id(current)
    }

    pub(crate) fn pre_verify_cleanup(
        &mut self,
        pre_apply_current: Option<&Interface>,
    ) {
        self.base.mac_address = None;
        if self.base.accept_all_mac_addresses == Some(false) {
            self.base.accept_all_mac_addresses = None;
        }
        if let Some(ports) = self.vrf.as_mut().and_then(|c| c.port.as_mut()) {
            ports.sort();
        }
        self.merge_table_id(pre_apply_current).ok();
    }

    fn merge_table_id(
        &mut self,
        current: Option<&Interface>,
    ) -> Result<(), NmstateError> {
        if self.vrf.as_ref().map(|v| v.table_id) == Some(0) {
            if let Some(&Interface::Vrf(VrfInterface {
                vrf:
                    Some(VrfConfig {
                        table_id: cur_table_id,
                        ..
                    }),
                ..
            })) = current
            {
                if let Some(vrf_conf) = self.vrf.as_mut() {
                    vrf_conf.table_id = cur_table_id;
                }
            } else {
                let e = NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Route table ID undefined or 0 is not allowed for \
                        new VRF interface {}",
                        self.base.name
                    ),
                );
                log::error!("{}", e);
                return Err(e);
            }
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[non_exhaustive]
#[serde(deny_unknown_fields)]
pub struct VrfConfig {
    #[serde(alias = "ports")]
    pub port: Option<Vec<String>>,
    #[serde(
        rename = "route-table-id",
        default,
        deserialize_with = "crate::deserializer::u32_or_string"
    )]
    /// Route table ID of this VRF interface.
    /// Use 0 to preserve current `table_id`.
    pub table_id: u32,
}

impl VrfConfig {
    fn update(&mut self, other: Option<&Self>) {
        if let Some(other) = other {
            self.port = other.port.clone();
            self.table_id = other.table_id;
        }
    }
}
