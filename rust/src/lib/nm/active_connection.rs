use std::collections::HashMap;

use nm_dbus::NmActiveConnection;

pub(crate) fn create_index_for_nm_acs_by_name_type(
    nm_acs: &[NmActiveConnection],
) -> HashMap<(&str, &str), &NmActiveConnection> {
    let mut ret = HashMap::new();
    for nm_ac in nm_acs {
        ret.insert(
            (nm_ac.iface_name.as_str(), nm_ac.iface_type.as_str()),
            nm_ac,
        );
    }
    ret
}
