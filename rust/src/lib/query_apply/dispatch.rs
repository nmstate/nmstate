// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::{
    state::get_json_value_difference, DispatchConfig, DispatchGlobalConfig,
    DispatchInterfaceType, ErrorKind, MergedDispatchGlobalConfig, NmstateError,
};

impl DispatchConfig {
    // For current in verify, None means empty string
    pub(crate) fn sanitize_current_for_verify(&mut self) {
        if self.post_activation.is_none() {
            self.post_activation = Some(String::new());
        }
        if self.post_deactivation.is_none() {
            self.post_deactivation = Some(String::new());
        }
        if self.variables.is_none() {
            self.variables = Some(HashMap::new());
        }
    }
}

impl MergedDispatchGlobalConfig {
    pub(crate) fn verify(
        &self,
        current: &DispatchGlobalConfig,
    ) -> Result<(), NmstateError> {
        let mut current_confs: HashMap<String, &DispatchInterfaceType> =
            HashMap::new();
        if let Some(cur_confs) = current.interfaces.as_deref() {
            for cur_conf in cur_confs {
                current_confs.insert(cur_conf.kind.to_string(), cur_conf);
            }
        }

        for (des_name, des_conf) in self.desired.iter() {
            if des_conf.is_absent() {
                if current_confs.contains_key(des_name) {
                    return Err(NmstateError::new(
                        ErrorKind::VerificationError,
                        format!(
                            "Dispatch interface type {des_name} still found \
                            after `state:absent` action"
                        ),
                    ));
                }
            } else if let Some(cur_conf) = current_confs.get(des_name) {
                let desired_value = serde_json::to_value(des_conf)?;
                let current_value = serde_json::to_value(cur_conf)?;

                if let Some((reference, desire, current)) =
                    get_json_value_difference(
                        "dispatch.interfaces".to_string(),
                        &desired_value,
                        &current_value,
                    )
                {
                    return Err(NmstateError::new(
                        ErrorKind::VerificationError,
                        format!(
                            "Verification failure: {reference} \
                            desire '{desire}', current '{current}'"
                        ),
                    ));
                }
            } else {
                return Err(NmstateError::new(
                    ErrorKind::VerificationError,
                    format!(
                        "Dispatch interface type {des_name} not found \
                            after creation"
                    ),
                ));
            }
        }
        Ok(())
    }
}
