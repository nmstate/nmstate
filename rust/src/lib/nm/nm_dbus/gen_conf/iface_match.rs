// SPDX-License-Identifier: Apache-2.0

use crate::nm::nm_dbus::ToDbusValue;

use super::super::{NmError, NmSettingMatch, ToKeyfile};

impl ToKeyfile for NmSettingMatch {}
