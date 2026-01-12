// SPDX-License-Identifier: Apache-2.0

use super::super::{NmError, NmSettingMatch, ToKeyfile};
use crate::nm::nm_dbus::ToDbusValue;

impl ToKeyfile for NmSettingMatch {}
