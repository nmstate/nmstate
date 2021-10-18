use log::{info, warn};
use nm_dbus::{NmApi, NmConnection};

use crate::{
    nm::connection::iface_type_to_nm, nm::error::nm_error_to_nmstate,
    InterfaceType, NmstateError,
};

// Found existing profile, prefer the activated one
pub(crate) fn get_exist_profile<'a>(
    exist_nm_conns: &'a [NmConnection],
    iface_name: &str,
    iface_type: &InterfaceType,
    nm_ac_uuids: &[&str],
) -> Option<&'a NmConnection> {
    let mut found_nm_conns: Vec<&NmConnection> = Vec::new();
    for exist_nm_conn in exist_nm_conns {
        if nm_connection_matches(exist_nm_conn, iface_name, iface_type) {
            if let Some(uuid) = exist_nm_conn.uuid() {
                if nm_ac_uuids.contains(&uuid) {
                    return Some(exist_nm_conn);
                }
            }
            found_nm_conns.push(exist_nm_conn);
        }
    }
    found_nm_conns.pop()
}

pub(crate) fn delete_exist_profiles(
    nm_api: &NmApi,
    exist_nm_conns: &[NmConnection],
    iface_name: &str,
    iface_type: &InterfaceType,
    excluded_uuid: &str,
) -> Result<(), NmstateError> {
    for exist_nm_conn in exist_nm_conns {
        if let Some(uuid) = exist_nm_conn.uuid() {
            if uuid != excluded_uuid
                && nm_connection_matches(exist_nm_conn, iface_name, iface_type)
            {
                info!("Deleting connection {:?}", exist_nm_conn);
                nm_api
                    .connection_delete(uuid)
                    .map_err(nm_error_to_nmstate)?;
            }
        }
    }
    Ok(())
}

fn nm_connection_matches(
    nm_conn: &NmConnection,
    iface_name: &str,
    iface_type: &InterfaceType,
) -> bool {
    // TODO Need to handle veth/ethernet
    let nm_iface_type = match iface_type_to_nm(iface_type) {
        Ok(i) => i,
        Err(e) => {
            warn!(
                "Failed to convert iface_type {:?} to network \
                manager type: {}",
                iface_type, e
            );
            return false;
        }
    };
    nm_conn.iface_name() == Some(iface_name)
        && nm_conn.iface_type() == Some(&nm_iface_type)
}
