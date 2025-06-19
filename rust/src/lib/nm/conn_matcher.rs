// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::rc::Rc;

use super::nm_dbus::{NmActiveConnection, NmConnection, NmIfaceType};
use crate::{
    BaseInterface, InterfaceIdentifier, InterfaceType, MergedInterfaces,
};

#[derive(Debug, Default)]
pub(crate) struct NmConnectionMatcher {
    saved_by_uuid: HashMap<String, Rc<NmConnection>>,
    applied_by_uuid: HashMap<String, Rc<NmConnection>>,
    acs_by_uuid: HashMap<String, Rc<NmActiveConnection>>,
    // Veth will also stored into `NmIfaceType::Ethernet`
    acs_by_name_and_type:
        HashMap<(String, NmIfaceType), Rc<NmActiveConnection>>,

    // Veth will also stored into `NmIfaceType::Ethernet`
    applied_by_name_and_type: HashMap<(String, NmIfaceType), Rc<NmConnection>>,

    saved_by_name: HashMap<String, Vec<Rc<NmConnection>>>,

    // Veth will also stored into `NmIfaceType::Ethernet`
    saved_by_name_and_type:
        HashMap<(String, NmIfaceType), Vec<Rc<NmConnection>>>,

    // (mac_upper_case, nm_iface_type) to Vec<Rc<NmConnection>> for mac
    // identifier connection.
    // Veth will also stored into `NmIfaceType::Ethernet`
    saved_by_mac: HashMap<(String, NmIfaceType), Vec<Rc<NmConnection>>>,
}

#[cfg_attr(not(feature = "query_apply"), allow(dead_code))]
impl NmConnectionMatcher {
    pub(crate) fn new(
        nm_saved_cons: Vec<NmConnection>,
        nm_applied_cons: Vec<NmConnection>,
        nm_acs: Vec<NmActiveConnection>,
        merged_ifaces: &MergedInterfaces,
    ) -> Self {
        let mut ret = Self::default();
        for nm_ac in nm_acs {
            ret.add_nm_ac(nm_ac);
        }

        for nm_conn in nm_applied_cons {
            ret.add_nm_applied_conn(nm_conn, merged_ifaces);
        }

        for nm_conn in nm_saved_cons {
            ret.add_nm_saved_conn(nm_conn, merged_ifaces);
        }

        ret
    }

    fn add_nm_ac(&mut self, nm_ac: NmActiveConnection) {
        let uuid = nm_ac.uuid.clone();
        let nm_ac = Rc::new(nm_ac);
        self.acs_by_uuid.insert(uuid, nm_ac.clone());
        if nm_ac.iface_type == NmIfaceType::Veth {
            self.acs_by_name_and_type.insert(
                (nm_ac.iface_name.clone(), NmIfaceType::Ethernet),
                nm_ac.clone(),
            );
        }
        self.acs_by_name_and_type.insert(
            (nm_ac.iface_name.clone(), nm_ac.iface_type.clone()),
            nm_ac,
        );
    }

    fn add_nm_applied_conn(
        &mut self,
        nm_conn: NmConnection,
        merged_ifaces: &MergedInterfaces,
    ) {
        let nm_conn = Rc::new(nm_conn);
        let uuid = match nm_conn.uuid().as_ref() {
            Some(u) => u.to_string(),
            None => return,
        };
        self.applied_by_uuid.insert(uuid, nm_conn.clone());

        if let (Some(name), Some(nm_iface_type)) = (
            get_nm_connection_iface_name(nm_conn.as_ref(), merged_ifaces),
            nm_conn.iface_type(),
        ) {
            if nm_iface_type == &NmIfaceType::Veth {
                self.applied_by_name_and_type.insert(
                    (name.to_string(), NmIfaceType::Ethernet),
                    nm_conn.clone(),
                );
            }
            self.applied_by_name_and_type.insert(
                (name.to_string(), nm_iface_type.clone()),
                nm_conn.clone(),
            );
        } else {
            // For all applied NmConnection, it should have existing
            // network interface defined, hence we ignore unexpected
            // NmConnection
            log::error!(
                "BUG: Ignoring the applied NmConnection due to unable to \
                 resolve network interface name: {nm_conn:?}"
            );
        }
    }

    fn add_nm_saved_conn(
        &mut self,
        nm_conn: NmConnection,
        merged_ifaces: &MergedInterfaces,
    ) {
        let nm_conn = Rc::new(nm_conn);
        let uuid = match nm_conn.uuid().as_ref() {
            Some(u) => u.to_string(),
            None => return,
        };
        self.saved_by_uuid.insert(uuid, nm_conn.clone());

        if let Some(name) =
            get_nm_connection_iface_name(nm_conn.as_ref(), merged_ifaces)
        {
            self.saved_by_name
                .entry(name.clone())
                .or_default()
                .push(nm_conn.clone());

            if let Some(nm_iface_type) = nm_conn.iface_type() {
                if nm_iface_type == &NmIfaceType::Veth {
                    self.saved_by_name_and_type
                        .entry((name.to_string(), NmIfaceType::Ethernet))
                        .or_default()
                        .push(nm_conn.clone())
                }
                self.saved_by_name_and_type
                    .entry((name, nm_iface_type.clone()))
                    .or_default()
                    .push(nm_conn.clone())
            }
        }

        if let (Some(mac), Some(nm_iface_type)) = (
            nm_conn
                .wired
                .as_ref()
                .and_then(|w| w.mac_address.as_deref()),
            nm_conn.iface_type(),
        ) {
            // For VLAN, MACVLAN and MACSEC, 802-3-ethernet.mac-address is
            // the MAC of the parent, not of the interface itself.
            if !mac.is_empty()
                && nm_conn.iface_type().map(|nm_iface_type| {
                    NM_IFACE_TYPES_USE_PARENT_MAC.contains(nm_iface_type)
                }) == Some(false)
            {
                if nm_iface_type == &NmIfaceType::Veth {
                    self.saved_by_mac
                        .entry((mac.to_uppercase(), NmIfaceType::Ethernet))
                        .or_default()
                        .push(nm_conn.clone())
                }
                self.saved_by_mac
                    .entry((mac.to_uppercase(), nm_iface_type.clone()))
                    .or_default()
                    .push(nm_conn.clone())
            }
        }
    }

    /// Activated NmConnection (including in-memory)
    pub(crate) fn get_applied(
        &self,
        base_iface: &BaseInterface,
    ) -> Option<&NmConnection> {
        self.applied_by_name_and_type
            .get(&(
                base_iface.name.to_string(),
                NmIfaceType::from(&base_iface.iface_type),
            ))
            .map(Rc::as_ref)
    }

    /// Find the best saved NmConnection in the order of:
    /// * Currently activated
    /// * Biggest `connection.autoconnect-priority`
    /// * Biggest `connection.timestamp`
    /// * Biggest `connection.uuid`
    pub(crate) fn get_prefered_saved_by_name_type<'s>(
        &'s self,
        name: &str,
        nm_iface_type: &NmIfaceType,
    ) -> Option<&'s NmConnection> {
        // Prefer the current activated NmConnection by searching
        // NmActiveConnection for specified interface, then use the UUID of
        // NmActiveConnection to search out the NmConnection.
        if let Some(nm_conn) = self
            .acs_by_name_and_type
            .get(&(name.to_string(), nm_iface_type.clone()))
            .and_then(|nm_ac| self.saved_by_uuid.get(nm_ac.uuid.as_str()))
            .map(Rc::as_ref)
        {
            return Some(nm_conn);
        }

        let nm_conns = self
            .saved_by_name_and_type
            .get(&(name.to_string(), nm_iface_type.clone()))?;

        for nm_conn in nm_conns {
            if let Some(uuid) = nm_conn.uuid() {
                if self.acs_by_uuid.contains_key(uuid) {
                    return Some(Rc::as_ref(nm_conn));
                }
            }
        }

        let mut nm_conns: Vec<&NmConnection> =
            nm_conns.iter().map(|n| n.as_ref()).collect();
        nm_conns.sort_unstable_by_key(|c| nm_conn_activation_sort_keys(c));

        nm_conns.pop()
    }

    /// Find the best saved NmConnection in the order of:
    /// * Currently activated
    /// * Biggest `connection.autoconnect-priority`
    /// * Biggest `connection.timestamp`
    /// * Biggest `connection.uuid`
    pub(crate) fn get_prefered_saved<'s>(
        &'s self,
        base_iface: &BaseInterface,
    ) -> Option<&'s NmConnection> {
        let nm_iface_type = NmIfaceType::from(&base_iface.iface_type);

        // Prefer the current activated NmConnection by searching
        // NmActiveConnection for specified interface, then use the UUID of
        // NmActiveConnection to search out the NmConnection.
        if let Some(nm_conn) = self
            .acs_by_name_and_type
            .get(&(base_iface.name.to_string(), nm_iface_type.clone()))
            .and_then(|nm_ac| self.saved_by_uuid.get(nm_ac.uuid.as_str()))
            .map(Rc::as_ref)
        {
            return Some(nm_conn);
        }

        match base_iface.identifier {
            None | Some(InterfaceIdentifier::Name) => self
                .get_prefered_saved_by_name_type(
                    base_iface.name.as_str(),
                    &nm_iface_type,
                ),
            Some(InterfaceIdentifier::MacAddress) => {
                if let Some(mac) = base_iface.mac_address.as_deref() {
                    let mut nm_conns: Vec<&NmConnection> = self
                        .saved_by_mac
                        .get(&(mac.to_string(), nm_iface_type))
                        .map(|nm_conns| {
                            nm_conns.iter().map(Rc::as_ref).collect()
                        })
                        .unwrap_or_default();
                    nm_conns.sort_unstable_by(|a, b| {
                        nm_conn_activation_sort_keys(a)
                            .cmp(&nm_conn_activation_sort_keys(b))
                    });
                    nm_conns.pop()
                } else {
                    None
                }
            }
        }
    }

    /// Get all connections can be used to activate specified interface.
    /// If interface type is unknown, all profiles with desired interface
    /// name will be included.
    pub(crate) fn get_saved(
        &self,
        base_iface: &BaseInterface,
    ) -> Vec<&NmConnection> {
        let mut ret: Vec<&NmConnection> = Vec::new();
        if base_iface.iface_type == InterfaceType::Unknown {
            if let Some(nm_conns) = self.saved_by_name.get(&base_iface.name) {
                ret.extend(nm_conns.iter().map(Rc::as_ref));
            }
        } else if let Some(nm_conns) = self.saved_by_name_and_type.get(&(
            base_iface.name.to_string(),
            NmIfaceType::from(&base_iface.iface_type),
        )) {
            ret.extend(nm_conns.iter().map(Rc::as_ref));
        }
        if base_iface.identifier == Some(InterfaceIdentifier::MacAddress) {
            if let Some(mac) = base_iface.mac_address.as_deref() {
                if let Some(nm_conns) = self.saved_by_mac.get(&(
                    mac.to_uppercase(),
                    NmIfaceType::from(&base_iface.iface_type),
                )) {
                    ret.extend(nm_conns.iter().map(Rc::as_ref));
                }
            }
        }

        ret.sort_unstable_by(|a, b| a.uuid().cmp(&b.uuid()));
        ret.dedup();
        ret
    }

    pub(crate) fn get_nm_ac(
        &self,
        iface: &BaseInterface,
    ) -> Option<&NmActiveConnection> {
        self.acs_by_name_and_type
            .get(&(
                iface.name.to_string(),
                NmIfaceType::from(&iface.iface_type),
            ))
            .map(Rc::as_ref)
    }

    pub(crate) fn saved_iter(&self) -> impl Iterator<Item = &NmConnection> {
        self.saved_by_uuid.values().map(Rc::as_ref)
    }

    pub(crate) fn is_uuid_activated(&self, uuid: &str) -> bool {
        self.acs_by_uuid.contains_key(uuid)
    }

    pub(crate) fn get_applied_by_name_type(
        &self,
        name: &str,
        iface_type: &NmIfaceType,
    ) -> Option<&NmConnection> {
        self.applied_by_name_and_type
            .get(&(name.to_string(), iface_type.clone()))
            .map(Rc::as_ref)
    }

    pub(crate) fn get_saved_by_name_type<'a>(
        &'a self,
        name: &str,
        iface_type: &NmIfaceType,
    ) -> Box<dyn Iterator<Item = &'a NmConnection> + 'a> {
        if let Some(nm_conns) = self
            .saved_by_name_and_type
            .get(&(name.to_string(), iface_type.clone()))
        {
            Box::new(nm_conns.iter().map(Rc::as_ref))
        } else {
            Box::new(std::iter::empty::<&NmConnection>())
        }
    }

    pub(crate) fn is_activated(&self, uuid: &str) -> bool {
        self.acs_by_uuid.contains_key(uuid)
    }

    pub(crate) fn get_applied_by_uuid(
        &self,
        uuid: &str,
    ) -> Option<&NmConnection> {
        self.applied_by_uuid.get(uuid).map(Rc::as_ref)
    }
}

const NM_IFACE_TYPES_USE_PARENT_MAC: [NmIfaceType; 3] =
    [NmIfaceType::Vlan, NmIfaceType::Macvlan, NmIfaceType::Macsec];

/// Find interface name for NmConnection:
///  * `connection.interface-name`
///  * For VLAN, use `vlan.id` and `vlan.parent` if `connection.interface-name`
///    is empty
///  * Resolves `802-3-ethernet.mac-address` if defined
///  * Use `connection.id` for VPN connection
fn get_nm_connection_iface_name(
    nm_conn: &NmConnection,
    merged_ifaces: &MergedInterfaces,
) -> Option<String> {
    if let Some(iface_name) = nm_conn.iface_name() {
        if !iface_name.is_empty() {
            return Some(iface_name.to_string());
        }
    }

    if let (Some(vlan_parent), Some(vlan_id)) = (
        nm_conn.vlan.as_ref().and_then(|v| v.parent.as_deref()),
        nm_conn.vlan.as_ref().and_then(|v| v.id),
    ) {
        return Some(format!("{vlan_parent}.{vlan_id}"));
    }

    // Veth and ethernet will be unified to InterfaceType::Ethernet
    let iface_type = InterfaceType::from(nm_conn.iface_type()?);

    // For VLAN, MACVLAN and MACSEC, 802-3-ethernet.mac-address is the MAC of
    // the parent, not of the interface itself.
    if nm_conn.iface_type().map(|nm_iface_type| {
        NM_IFACE_TYPES_USE_PARENT_MAC.contains(nm_iface_type)
    }) == Some(false)
    {
        if let Some(mac) = nm_conn
            .wired
            .as_ref()
            .and_then(|s| s.mac_address.as_deref())
        {
            if let Some(name) = merged_ifaces
                .kernel_ifaces
                .values()
                .filter_map(|i| i.current.as_ref())
                .find_map(|iface| {
                    let base_iface = iface.base_iface();
                    if base_iface.mac_address.as_deref() == Some(mac)
                        && (base_iface.iface_type == iface_type
                            || ([InterfaceType::Veth, InterfaceType::Ethernet]
                                .contains(&base_iface.iface_type)
                                && iface_type == InterfaceType::Ethernet))
                    {
                        Some(base_iface.name.to_string())
                    } else {
                        None
                    }
                })
            {
                return Some(name);
            }
        }
    }
    if nm_conn.vpn.is_some() {
        return nm_conn.id().map(|i| i.to_string());
    }
    None
}

const NM_SETTING_CONNECTION_AUTOCONNECT_PRIORITY_DEFAULT: i32 = 0;
const NM_SETTING_CONNECTION_TIMESTAMP_DEFAULT: u64 = 0;
const NM_SETTING_CONNECTION_UUID_DEFAULT: u128 = 0;

// Sort key for choosing NmConnection for activation:
//  (connection.autoconnect-priority, connection.timestamp, connection.uuid)
fn nm_conn_activation_sort_keys(nm_conn: &NmConnection) -> (i32, u64, u128) {
    (
        nm_conn
            .connection
            .as_ref()
            .and_then(|c| c.autoconnect_priority)
            .unwrap_or(NM_SETTING_CONNECTION_AUTOCONNECT_PRIORITY_DEFAULT),
        nm_conn
            .connection
            .as_ref()
            .and_then(|c| c.timestamp)
            .unwrap_or(NM_SETTING_CONNECTION_TIMESTAMP_DEFAULT),
        nm_conn
            .uuid()
            .and_then(|uuid_str| uuid::Uuid::parse_str(uuid_str).ok())
            .map(|u| u.as_u128())
            .unwrap_or(NM_SETTING_CONNECTION_UUID_DEFAULT),
    )
}
