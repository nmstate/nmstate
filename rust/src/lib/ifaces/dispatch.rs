// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::{BaseInterface, InterfaceType};

/// Interface created by dispatch scripts.
///
/// Example yaml outpuf of `[crate::NetworkState]` with interface created by
/// dispatch scripts.
/// ```yml
/// dispatch:
///   interfaces:
///   - type: vxcan
///     activation: |
///       ip link add $name type vxcan peer $peer
///     deactivation: |
///       ip link del $name
/// interfaces:
/// - name: vxcan0
///   type: dispatch
///   state: up
///   ipv4:
///     enabled: false
///   ipv6:
///     enabled: false
///   dispatch:
///     type: vxcan
///     variables:
///       peer: vxcan0-ep
/// ```
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case")]
pub struct DispatchInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
}

impl Default for DispatchInterface {
    fn default() -> Self {
        let mut base = BaseInterface::new();
        base.iface_type = InterfaceType::Dispatch;
        Self { base }
    }
}
