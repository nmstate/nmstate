// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use crate::{
    BaseInterface, ErrorKind, Interface, InterfaceState, InterfaceType,
    Interfaces, MergedUserDefinedData, NmstateError,
};

/// User defined interface
/// Example yaml outpuf of `[crate::NetworkState]` with user defined interface
/// ```yml
/// interface-types:
/// - name: vxcan
///   # This is NetworkManager specific handler script
///   handler-script: |
///     ifname=$1
///     action=$2
///
///     if [ "$action" = "device-add" ]; then
///         peer=$CONNECTION_USER_VXAN__PEER
///
///         if [ -z "$peer" ]; then
///             echo "ERROR=Missing peer name"
///             exit 1
///         fi
///
///         if ! err=$(ip link add "$ifname" type vxcan peer "$peer" 2>&1); then
///             echo "ERROR=Failed creating the interface: $err"
///             exit 2
///         fi
///
///         echo IFINDEX="$(cat /sys/class/net/"$ifname"/ifindex)"
///         exit 0
///     elif [ "$action" = "device-delete" ]; then
///         # Delete the interface created by "device-add" here.
///         ip link del "$ifname"
///         exit 0
///     fi
/// interfaces:
/// - name: vxcan0
///   type: vxcan
///   state: up
///   ipv4:
///     enabled: false
///   ipv6:
///     enabled: false
///   user-defined:
///     peer: vxcan0-ep
/// ```
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case")]
pub struct UserDefinedInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user_defined: Option<HashMap<String, String>>,
}

impl Default for UserDefinedInterface {
    fn default() -> Self {
        let mut base = BaseInterface::new();
        base.iface_type = InterfaceType::Other("undefined".to_string());
        Self {
            base,
            user_defined: None,
        }
    }
}

impl UserDefinedInterface {
    pub fn new(iface_name: &str, iface_type: &str) -> Self {
        Self {
            base: BaseInterface {
                name: iface_name.to_string(),
                iface_type: InterfaceType::UserDefined(iface_type.to_string()),
                ..Default::default()
            },
            ..Default::default()
        }
    }
}

impl Interfaces {
    // * Make sure user defined interface type exist and not deleting
    // * Convert `InterfaceType::Other` to InterfaceType::UserDefined` when
    //   possible
    pub(crate) fn sanitize_user_defined_iface_type(
        &mut self,
        user_defined: &MergedUserDefinedData,
    ) -> Result<(), NmstateError> {
        for iface in self.user_ifaces.values_mut().filter_map(|i| {
            if let Interface::UserDefined(i) = i {
                Some(i)
            } else {
                None
            }
        }) {
            if let InterfaceType::Other(kind) = &iface.base.iface_type {
                match user_defined.get_iface_type(kind) {
                    None => {
                        if iface.base.state == InterfaceState::Up {
                            return Err(NmstateError::new(
                                ErrorKind::InvalidArgument,
                                format!(
                                    "Interface type {kind} is \
                                not native supported or defined in \
                                user-defined section"
                                ),
                            ));
                        }
                    }
                    Some(t)
                        if t.is_absent()
                            && iface.base.state == InterfaceState::Up =>
                    {
                        return Err(NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "Interface {} is holding user defined type \
                                {kind}, but that interface type is \
                                removing by this desire state",
                                iface.base.name
                            ),
                        ));
                    }
                    Some(_) => {
                        iface.base.iface_type =
                            InterfaceType::UserDefined(kind.to_string());
                    }
                }
            }
        }
        Ok(())
    }
}
