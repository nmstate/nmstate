// SPDX-License-Identifier: Apache-2.0

use crate::{ovsdb::db::OvsDbConnection, MergedNetworkState, NmstateError};

pub(crate) fn ovsdb_apply(
    merged_state: &MergedNetworkState,
) -> Result<(), NmstateError> {
    if merged_state.ovsdb.is_changed {
        let mut cli = OvsDbConnection::new()?;
        cli.apply_global_conf(&merged_state.ovsdb)
    } else {
        log::debug!("No OVSDB changes");
        Ok(())
    }
}
