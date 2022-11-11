use crate::{ovsdb::db::OvsDbConnection, NetworkState, NmstateError};

pub(crate) fn ovsdb_apply(
    desired: &NetworkState,
    current: &NetworkState,
) -> Result<(), NmstateError> {
    let mut cli = OvsDbConnection::new()?;
    let mut desired = desired.ovsdb.clone();
    desired.merge(&current.ovsdb);
    cli.apply_global_conf(&desired)
}
