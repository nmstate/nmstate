// SPDX-License-Identifier: Apache-2.0

#[cfg(not(feature = "gen_conf"))]
use std::collections::HashMap;

use serde::{Deserialize, Deserializer, Serialize};

use crate::{
    dns::{
        get_cur_dns_ifaces, is_dns_changed, purge_dns_config,
        reselect_dns_ifaces,
    },
    DnsState, ErrorKind, HostNameState, Interface, InterfaceType, Interfaces,
    NmstateError, OvsDbGlobalConfig, RouteRules, Routes,
};

#[derive(Clone, Debug, Serialize, Default, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
#[non_exhaustive]
pub struct NetworkState {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hostname: Option<HostNameState>,
    #[serde(rename = "dns-resolver", default)]
    pub dns: DnsState,
    #[serde(rename = "route-rules", default)]
    pub rules: RouteRules,
    #[serde(default)]
    pub routes: Routes,
    #[serde(default)]
    pub interfaces: Interfaces,
    #[serde(
        default,
        rename = "ovs-db",
        skip_serializing_if = "OvsDbGlobalConfig::is_none"
    )]
    pub ovsdb: OvsDbGlobalConfig,
    #[serde(skip)]
    // Contain a list of struct member name which is defined explicitly in
    // desire state instead of generated.
    pub prop_list: Vec<&'static str>,
    #[serde(skip)]
    // TODO: Hide user space only info when serialize
    pub(crate) kernel_only: bool,
    #[serde(skip)]
    pub(crate) no_verify: bool,
    #[serde(skip)]
    pub(crate) no_commit: bool,
    #[serde(skip)]
    pub(crate) timeout: Option<u32>,
    #[serde(skip)]
    pub(crate) include_secrets: bool,
    #[serde(skip)]
    pub(crate) include_status_data: bool,
    #[serde(skip)]
    pub(crate) running_config_only: bool,
    #[serde(skip)]
    pub(crate) memory_only: bool,
}

impl<'de> Deserialize<'de> for NetworkState {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let mut net_state = NetworkState::new();
        let v = serde_json::Value::deserialize(deserializer)?;
        if let Some(ifaces_value) = v.get("interfaces") {
            net_state.prop_list.push("interfaces");
            net_state.interfaces = Interfaces::deserialize(ifaces_value)
                .map_err(serde::de::Error::custom)?;
        }
        if let Some(dns_value) = v.get("dns-resolver") {
            net_state.prop_list.push("dns");
            net_state.dns = DnsState::deserialize(dns_value)
                .map_err(serde::de::Error::custom)?;
        }
        if let Some(route_value) = v.get("routes") {
            net_state.prop_list.push("routes");
            net_state.routes = Routes::deserialize(route_value)
                .map_err(serde::de::Error::custom)?;
        }
        if let Some(rule_value) = v.get("route-rules") {
            net_state.prop_list.push("rules");
            net_state.rules = RouteRules::deserialize(rule_value)
                .map_err(serde::de::Error::custom)?;
        }
        if let Some(ovsdb_value) = v.get("ovs-db") {
            net_state.prop_list.push("ovsdb");
            net_state.ovsdb = OvsDbGlobalConfig::deserialize(ovsdb_value)
                .map_err(serde::de::Error::custom)?;
        }
        if let Some(hostname_value) = v.get("hostname") {
            net_state.prop_list.push("hostname");
            net_state.hostname = Some(
                HostNameState::deserialize(hostname_value)
                    .map_err(serde::de::Error::custom)?,
            );
        }
        Ok(net_state)
    }
}

impl NetworkState {
    pub(crate) const PASSWORD_HID_BY_NMSTATE: &'static str =
        "<_password_hid_by_nmstate>";

    pub fn set_kernel_only(&mut self, value: bool) -> &mut Self {
        self.kernel_only = value;
        self
    }

    pub fn set_verify_change(&mut self, value: bool) -> &mut Self {
        self.no_verify = !value;
        self
    }

    pub fn set_commit(&mut self, value: bool) -> &mut Self {
        self.no_commit = !value;
        self
    }

    pub fn set_timeout(&mut self, value: u32) -> &mut Self {
        self.timeout = Some(value);
        self
    }

    pub fn set_include_secrets(&mut self, value: bool) -> &mut Self {
        self.include_secrets = value;
        self
    }

    pub fn set_include_status_data(&mut self, value: bool) -> &mut Self {
        self.include_status_data = value;
        self
    }

    // Query activated/running network configuration excluding:
    // * IP address retrieved by DHCP or IPv6 auto configuration.
    // * DNS client resolver retrieved by DHCP or IPv6 auto configuration.
    // * Routes retrieved by DHCPv4 or IPv6 router advertisement.
    // * LLDP neighbor information.
    pub fn set_running_config_only(&mut self, value: bool) -> &mut Self {
        self.running_config_only = value;
        self
    }

    pub fn set_memory_only(&mut self, value: bool) -> &mut Self {
        self.memory_only = value;
        self
    }

    pub fn new() -> Self {
        Default::default()
    }

    // We provide this instead asking use to do serde_json::from_str(), so that
    // we could provide better error NmstateError instead of serde_json one.
    pub fn new_from_json(net_state_json: &str) -> Result<Self, NmstateError> {
        match serde_json::from_str(net_state_json) {
            Ok(s) => Ok(s),
            Err(e) => Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!("Invalid json string: {}", e),
            )),
        }
    }

    pub fn append_interface_data(&mut self, iface: Interface) {
        self.interfaces.push(iface);
    }

    #[cfg(not(feature = "query_apply"))]
    pub fn retrieve(&mut self) -> Result<&mut Self, NmstateError> {
        Err(NmstateError::new(
            ErrorKind::DependencyError,
            "NetworkState::retrieve() need `query_apply` feature enabled"
                .into(),
        ))
    }

    pub fn hide_secrets(&mut self) {
        self.interfaces.hide_secrets();
    }

    #[cfg(not(feature = "query_apply"))]
    pub fn apply(&mut self) -> Result<(), NmstateError> {
        Err(NmstateError::new(
            ErrorKind::DependencyError,
            "NetworkState::apply() need `query_apply` feature enabled".into(),
        ))
    }

    #[cfg(not(feature = "gen_conf"))]
    pub fn gen_conf(
        &self,
    ) -> Result<HashMap<String, Vec<(String, String)>>, NmstateError> {
        Err(NmstateError::new(
            ErrorKind::DependencyError,
            "NetworkState::gen_conf() need `genconf` feature enabled".into(),
        ))
    }

    // Return three NetworkState:
    //  * State for addition.
    //  * State for change.
    //  * State for deletion.
    // This function is the entry point for decision making which
    // expanding complex desire network layout to flat network layout.
    pub(crate) fn gen_state_for_apply(
        &self,
        current: &Self,
    ) -> Result<(Self, Self, Self), NmstateError> {
        self.routes.validate()?;
        self.rules.validate()?;
        self.dns.validate()?;

        let mut add_net_state = NetworkState::new();
        let mut chg_net_state = NetworkState::new();
        let mut del_net_state = NetworkState::new();

        let mut ifaces = self.interfaces.clone();

        let (add_ifaces, chg_ifaces, del_ifaces) = ifaces
            .gen_state_for_apply(&current.interfaces, self.memory_only)?;

        add_net_state.interfaces = add_ifaces;
        add_net_state.hostname = self.hostname.clone();
        chg_net_state.interfaces = chg_ifaces;
        del_net_state.interfaces = del_ifaces;

        self.include_route_changes(
            &mut add_net_state,
            &mut chg_net_state,
            &del_net_state,
            current,
        )?;

        self.include_rule_changes(
            &mut add_net_state,
            &mut chg_net_state,
            &del_net_state,
            current,
        )?;

        self.include_dns_changes(
            &mut add_net_state,
            &mut chg_net_state,
            current,
        )?;

        Ok((add_net_state, chg_net_state, del_net_state))
    }

    fn include_route_changes(
        &self,
        add_net_state: &mut Self,
        chg_net_state: &mut Self,
        del_net_state: &Self,
        current: &Self,
    ) -> Result<(), NmstateError> {
        let mut changed_iface_routes =
            self.routes.gen_changed_ifaces_and_routes(&current.routes)?;

        for (iface_name, routes) in changed_iface_routes.drain() {
            let cur_iface = current
                .interfaces
                .get_iface(&iface_name, InterfaceType::Unknown);
            if del_net_state
                .interfaces
                .kernel_ifaces
                .get(&iface_name)
                .is_some()
            {
                // Ignore routes on absent interfaces.
                continue;
            }

            if let Some(iface) =
                add_net_state.interfaces.kernel_ifaces.get_mut(&iface_name)
            {
                // Desire interface might not have IP information defined
                // in that case, we copy from current
                iface.base_iface_mut().routes = Some(routes);
                if let Some(cur_iface) = cur_iface {
                    iface
                        .base_iface_mut()
                        .copy_ip_config_if_none(cur_iface.base_iface());
                }
            } else if let Some(iface) =
                chg_net_state.interfaces.kernel_ifaces.get_mut(&iface_name)
            {
                iface.base_iface_mut().routes = Some(routes);
                if let Some(cur_iface) = cur_iface {
                    iface
                        .base_iface_mut()
                        .copy_ip_config_if_none(cur_iface.base_iface());
                }
            } else if let Some(cur_iface) = cur_iface {
                // Interface not mentioned in desire state but impacted by
                // wildcard absent route
                let mut new_iface = cur_iface.clone_name_type_only();
                new_iface
                    .base_iface_mut()
                    .copy_ip_config_if_none(cur_iface.base_iface());
                new_iface.base_iface_mut().routes = Some(routes);
                chg_net_state.append_interface_data(new_iface);
            } else {
                log::warn!(
                    "The next hop interface of desired routes {:?} \
                    does not exist",
                    routes
                );
            }
        }
        Ok(())
    }

    fn include_rule_changes(
        &self,
        add_net_state: &mut Self,
        chg_net_state: &mut Self,
        del_net_state: &Self,
        current: &Self,
    ) -> Result<(), NmstateError> {
        let mut changed_rules =
            self.rules.gen_rule_changed_table_ids(&current.rules)?;

        // Convert table id to interface name
        for (table_id, rules) in changed_rules.drain() {
            // We does not differentiate the IPv4 and IPv6 route table ID.
            // The verification process will find out the error.
            // We did not head any use case been limited by this.
            let iface_name =
                self.get_iface_name_for_route_table(current, table_id)?;
            let cur_iface = current
                .interfaces
                .get_iface(&iface_name, InterfaceType::Unknown);
            if del_net_state
                .interfaces
                .kernel_ifaces
                .get(&iface_name)
                .is_some()
            {
                // Ignore rules on absent interfaces.
                continue;
            }
            if let Some(iface) =
                add_net_state.interfaces.kernel_ifaces.get_mut(&iface_name)
            {
                if let Some(ex_rules) = iface.base_iface_mut().rules.as_mut() {
                    ex_rules.extend(rules);
                    ex_rules.sort_unstable();
                    ex_rules.dedup();
                } else {
                    iface.base_iface_mut().rules = Some(rules);
                }
                if let Some(cur_iface) = cur_iface {
                    iface
                        .base_iface_mut()
                        .copy_ip_config_if_none(cur_iface.base_iface());
                }
            } else if let Some(iface) =
                chg_net_state.interfaces.kernel_ifaces.get_mut(&iface_name)
            {
                if let Some(ex_rules) = iface.base_iface_mut().rules.as_mut() {
                    ex_rules.extend(rules);
                    ex_rules.sort_unstable();
                    ex_rules.dedup();
                } else {
                    iface.base_iface_mut().rules = Some(rules);
                }
                if let Some(cur_iface) = cur_iface {
                    iface
                        .base_iface_mut()
                        .copy_ip_config_if_none(cur_iface.base_iface());
                }
            } else if let Some(cur_iface) = cur_iface {
                // Interface not mentioned in desire state but impacted by
                // wildcard absent route rule
                let mut new_iface = cur_iface.clone_name_type_only();
                new_iface
                    .base_iface_mut()
                    .copy_ip_config_if_none(cur_iface.base_iface());
                new_iface.base_iface_mut().rules = Some(rules);
                chg_net_state.append_interface_data(new_iface);
            } else {
                let e = NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                    "Failed to find a interface for desired routes rules {:?} ",
                    rules
                ),
                );
                log::error!("{}", e);
                return Err(e);
            }
        }
        Ok(())
    }

    // The whole design of this DNS setting is matching NetworkManager
    // design where DNS information is saved into each interface.
    // When different network control backend nmstate supported, we need to
    // move these code to NetworkManager plugin. Currently, we keep it
    // here for consistency with route/route rule.
    fn include_dns_changes(
        &self,
        add_net_state: &mut Self,
        chg_net_state: &mut Self,
        current: &Self,
    ) -> Result<(), NmstateError> {
        let mut self_clone = self.clone();
        self_clone.dns.merge_current(&current.dns);

        if is_dns_changed(&self_clone, current) {
            let (v4_iface_name, v6_iface_name) =
                reselect_dns_ifaces(&self_clone, current);
            let (cur_v4_ifaces, cur_v6_ifaces) =
                get_cur_dns_ifaces(&current.interfaces);
            if let Some(dns_conf) = &self_clone.dns.config {
                if dns_conf.is_purge() {
                    purge_dns_config(
                        false,
                        cur_v4_ifaces.as_slice(),
                        self,
                        chg_net_state,
                        current,
                    );
                    purge_dns_config(
                        true,
                        cur_v6_ifaces.as_slice(),
                        self,
                        chg_net_state,
                        current,
                    );
                } else {
                    purge_dns_config(
                        false,
                        &cur_v4_ifaces,
                        self,
                        chg_net_state,
                        current,
                    );
                    purge_dns_config(
                        true,
                        &cur_v6_ifaces,
                        self,
                        chg_net_state,
                        current,
                    );
                    dns_conf.save_dns_to_iface(
                        &v4_iface_name,
                        &v6_iface_name,
                        add_net_state,
                        chg_net_state,
                        current,
                    )?;
                }
            }
        } else {
            log::debug!("DNS configuration unchanged");
        }
        Ok(())
    }

    fn _get_iface_name_for_route_table(&self, table_id: u32) -> Option<String> {
        if let Some(routes) = self.routes.config.as_ref() {
            for route in routes {
                if route.table_id == Some(table_id) {
                    if let Some(iface_name) = route.next_hop_iface.as_ref() {
                        return Some(iface_name.to_string());
                    }
                }
            }
        }
        // We need to differentiate IPv4 and IPv6 auto route table ID when
        // user case shows up. Currently, we just assume user does not
        // mix up the table number for IPv4 and IPv6 between interfaces.
        for iface in self.interfaces.kernel_ifaces.values() {
            if iface
                .base_iface()
                .ipv6
                .as_ref()
                .and_then(|c| c.auto_table_id)
                .or_else(|| {
                    iface
                        .base_iface()
                        .ipv4
                        .as_ref()
                        .and_then(|c| c.auto_table_id)
                })
                == Some(table_id)
            {
                return Some(iface.name().to_string());
            }
        }
        None
    }

    // * Find desired interface with static route to given table ID.
    // * Find desired interface with dynamic route to given table ID.
    // * Find current interface with static route to given table ID.
    // * Find current interface with dynamic route to given table ID.
    fn get_iface_name_for_route_table(
        &self,
        current: &Self,
        table_id: u32,
    ) -> Result<String, NmstateError> {
        match self
            ._get_iface_name_for_route_table(table_id)
            .or_else(|| current._get_iface_name_for_route_table(table_id))
        {
            Some(iface_name) => Ok(iface_name),
            None => {
                let e = NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Route table {} for route rule is not defined by \
                        any routes",
                        table_id
                    ),
                );
                log::error!("{}", e);
                Err(e)
            }
        }
    }

    #[cfg(not(feature = "query_apply"))]
    pub fn checkpoint_rollback(_checkpoint: &str) -> Result<(), NmstateError> {
        Err(NmstateError::new(
            ErrorKind::DependencyError,
            "NetworkState::checkpoint_rollback() need `query_apply` \
            feature enabled"
                .into(),
        ))
    }

    #[cfg(not(feature = "query_apply"))]
    pub fn checkpoint_commit(_checkpoint: &str) -> Result<(), NmstateError> {
        Err(NmstateError::new(
            ErrorKind::DependencyError,
            "NetworkState::checkpoint_commit() need `query_apply` \
            feature enabled"
                .into(),
        ))
    }

    pub(crate) fn get_kernel_iface_with_route(
        &self,
        iface_name: &str,
    ) -> Option<Interface> {
        if let Some(iface) = self.interfaces.kernel_ifaces.get(iface_name) {
            let mut ret = iface.clone();
            ret.base_iface_mut().routes =
                self.routes.get_config_routes_of_iface(iface_name);
            Some(ret)
        } else {
            None
        }
    }
}
