// SPDX-License-Identifier: Apache-2.0

#[cfg(not(feature = "gen_conf"))]
use std::collections::HashMap;

use serde::{Deserialize, Deserializer, Serialize};

use crate::ovn::{
    MergedOvnConfiguration, OvnConfiguration, OVN_BRIDGE_MAPPINGS,
};
use crate::{
    DnsState, ErrorKind, HostNameState, Interface, Interfaces, MergedDnsState,
    MergedHostNameState, MergedInterfaces, MergedOvsDbGlobalConfig,
    MergedRouteRules, MergedRoutes, NmstateError, OvsDbGlobalConfig,
    RouteRules, Routes,
};

#[derive(Clone, Debug, Serialize, Default, PartialEq, Eq)]
#[non_exhaustive]
/// The [NetworkState] represents the whole network state including both
/// kernel status and configurations provides by backends(NetworkManager,
/// OpenvSwitch databas, and etc).
///
/// Example yaml(many lines omitted) serialized NetworkState would be:
///
/// ```yaml
/// hostname:
///   running: host.example.org
///   config: host.example.org
/// dns-resolver:
///   config:
///     server:
///     - 2001:db8:1::
///     - 192.0.2.1
///     search: []
/// route-rules:
///   config:
///   - ip-from: 2001:db8:b::/64
///     priority: 30000
///     route-table: 200
///   - ip-from: 192.0.2.2/32
///     priority: 30000
///     route-table: 200
/// routes:
///   config:
///   - destination: 2001:db8:a::/64
///     next-hop-interface: eth1
///     next-hop-address: 2001:db8:1::2
///     metric: 108
///     table-id: 200
///   - destination: 192.168.2.0/24
///     next-hop-interface: eth1
///     next-hop-address: 192.168.1.3
///     metric: 108
///     table-id: 200
/// interfaces:
/// - name: eth1
///   type: ethernet
///   state: up
///   mac-address: 0E:F9:2B:28:42:D9
///   mtu: 1500
///   ipv4:
///     enabled: true
///     dhcp: false
///     address:
///     - ip: 192.168.1.3
///       prefix-length: 24
///   ipv6:
///     enabled: true
///     dhcp: false
///     autoconf: false
///     address:
///     - ip: 2001:db8:1::1
///       prefix-length: 64
/// ovs-db:
///   external_ids:
///     hostname: host.example.org
///     rundir: /var/run/openvswitch
///     system-id: 176866c7-6dc8-400f-98ac-c658509ec09f
///   other_config: {}
/// ```
pub struct NetworkState {
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Hostname of current host.
    pub hostname: Option<HostNameState>,
    #[serde(rename = "dns-resolver", default)]
    /// DNS resolver status, deserialize and serialize from/to `dns-resolver`.
    pub dns: DnsState,
    #[serde(rename = "route-rules", default)]
    /// Route rule, deserialize and serialize from/to `route-rules`.
    pub rules: RouteRules,
    #[serde(default)]
    /// Route
    pub routes: Routes,
    #[serde(default)]
    /// Network interfaces
    pub interfaces: Interfaces,
    #[serde(
        default,
        rename = "ovs-db",
        skip_serializing_if = "OvsDbGlobalConfig::is_none"
    )]
    /// The global configurations of OpenvSwitach daemon
    pub ovsdb: OvsDbGlobalConfig,
    #[serde(default, skip_serializing_if = "OvnConfiguration::is_none")]
    /// The OVN configuration in the system
    pub ovn: OvnConfiguration,
    #[serde(skip)]
    // Contain a list of struct member name which is defined explicitly in
    // desire state instead of generated.
    /// Only for internal use. TODO: should changed to pub(crate)
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
        let mut v = serde_json::Value::deserialize(deserializer)?;
        let v = match v.as_object_mut() {
            Some(v) => v,
            None => {
                return Err(serde::de::Error::custom(format!(
                    "Expecting a HashMap/Object/Dictionary, but got {v}"
                )));
            }
        };
        if let Some(ifaces_value) = v.remove("interfaces") {
            net_state.prop_list.push("interfaces");
            net_state.interfaces = Interfaces::deserialize(ifaces_value)
                .map_err(serde::de::Error::custom)?;
        }
        if let Some(dns_value) = v.remove("dns-resolver") {
            net_state.prop_list.push("dns");
            net_state.dns = DnsState::deserialize(dns_value)
                .map_err(serde::de::Error::custom)?;
        }
        if let Some(route_value) = v.remove("routes") {
            net_state.prop_list.push("routes");
            net_state.routes = Routes::deserialize(route_value)
                .map_err(serde::de::Error::custom)?;
        }
        if let Some(rule_value) = v.remove("route-rules") {
            net_state.prop_list.push("rules");
            net_state.rules = RouteRules::deserialize(rule_value)
                .map_err(serde::de::Error::custom)?;
        }
        if let Some(ovsdb_value) = v.remove("ovs-db") {
            net_state.prop_list.push("ovsdb");
            net_state.ovsdb = OvsDbGlobalConfig::deserialize(ovsdb_value)
                .map_err(serde::de::Error::custom)?;
        }
        if let Some(ovn_value) = v.remove("ovn") {
            net_state.prop_list.push("ovn");
            net_state.ovn = OvnConfiguration::deserialize(ovn_value)
                .map_err(serde::de::Error::custom)?;
        }
        if let Some(hostname_value) = v.remove("hostname") {
            net_state.prop_list.push("hostname");
            net_state.hostname = Some(
                HostNameState::deserialize(hostname_value)
                    .map_err(serde::de::Error::custom)?,
            );
        }
        if !v.is_empty() {
            Err(serde::de::Error::custom(format!(
                "Unsupported keys found: {:?}",
                v.keys().collect::<Vec<&String>>()
            )))
        } else {
            Ok(net_state)
        }
    }
}

impl NetworkState {
    pub fn is_empty(&self) -> bool {
        self.hostname.is_none()
            && self.dns.is_empty()
            && self.rules.is_empty()
            && self.routes.is_empty()
            && self.interfaces.is_empty()
            && self.ovsdb.is_none()
            && self.ovn.is_none()
    }

    pub(crate) const PASSWORD_HID_BY_NMSTATE: &'static str =
        "<_password_hid_by_nmstate>";

    /// Whether to perform kernel actions(also known as `kernel only` mode
    /// through the document this project) only or not.
    /// When set to false, nmstate will contact NetworkManager plugin for
    /// querying/applying the network state.
    /// Default is false.
    pub fn set_kernel_only(&mut self, value: bool) -> &mut Self {
        self.kernel_only = value;
        self
    }

    /// By default(true), When nmstate applying the network state, after applied
    /// the network state, nmstate will verify whether the outcome network
    /// configuration matches with desired, if not, will rollback to state
    /// before apply(only when [NetworkState::set_kernel_only()] set to false.
    /// When set to false, no verification will be performed.
    pub fn set_verify_change(&mut self, value: bool) -> &mut Self {
        self.no_verify = !value;
        self
    }

    /// Only available when [NetworkState::set_kernel_only()] set to false.
    /// When set to false, the network configuration will not commit
    /// persistently, and will rollback after timeout defined by
    /// [NetworkState::set_timeout()].  Default to true for making the network
    /// state persistent.
    pub fn set_commit(&mut self, value: bool) -> &mut Self {
        self.no_commit = !value;
        self
    }

    /// Only available when [NetworkState::set_commit()] set to false.
    /// The time to wait before rolling back the network state to the state
    /// before [NetworkState::apply()` invoked.
    pub fn set_timeout(&mut self, value: u32) -> &mut Self {
        self.timeout = Some(value);
        self
    }

    /// Whether to include secrets(like password) in [NetworkState::retrieve()]
    /// Default is false.
    pub fn set_include_secrets(&mut self, value: bool) -> &mut Self {
        self.include_secrets = value;
        self
    }

    /// Deprecated. No use at all.
    pub fn set_include_status_data(&mut self, value: bool) -> &mut Self {
        self.include_status_data = value;
        self
    }

    /// Query activated/running network configuration excluding:
    /// * IP address retrieved by DHCP or IPv6 auto configuration.
    /// * DNS client resolver retrieved by DHCP or IPv6 auto configuration.
    /// * Routes retrieved by DHCPv4 or IPv6 router advertisement.
    /// * LLDP neighbor information.
    pub fn set_running_config_only(&mut self, value: bool) -> &mut Self {
        self.running_config_only = value;
        self
    }

    /// When set to true, the network state be applied and only stored in memory
    /// which will be purged after system reboot.
    pub fn set_memory_only(&mut self, value: bool) -> &mut Self {
        self.memory_only = value;
        self
    }

    /// Create empty [NetworkState]
    pub fn new() -> Self {
        Default::default()
    }

    /// Wrapping function of [serde_json::from_str()] with error mapped to
    /// [NmstateError].
    pub fn new_from_json(net_state_json: &str) -> Result<Self, NmstateError> {
        match serde_json::from_str(net_state_json) {
            Ok(s) => Ok(s),
            Err(e) => Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!("Invalid JSON string: {e}"),
            )),
        }
    }

    /// Wrapping function of [serde_yaml::from_str()] with error mapped to
    /// [NmstateError].
    pub fn new_from_yaml(net_state_yaml: &str) -> Result<Self, NmstateError> {
        match serde_yaml::from_str(net_state_yaml) {
            Ok(s) => Ok(s),
            Err(e) => Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!("Invalid YAML string: {e}"),
            )),
        }
    }

    /// Append [Interface] into [NetworkState]
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

    /// Replace secret string with `<_password_hid_by_nmstate>`
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
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub(crate) struct MergedNetworkState {
    pub(crate) hostname: MergedHostNameState,
    pub(crate) dns: MergedDnsState,
    pub(crate) interfaces: MergedInterfaces,
    pub(crate) ovsdb: MergedOvsDbGlobalConfig,
    pub(crate) ovn: MergedOvnConfiguration,
    pub(crate) routes: MergedRoutes,
    pub(crate) rules: MergedRouteRules,
    pub(crate) memory_only: bool,
    pub(crate) prop_list: Vec<&'static str>,
}

impl MergedNetworkState {
    pub(crate) fn new(
        desired: NetworkState,
        current: NetworkState,
        gen_conf_mode: bool,
        memory_only: bool,
    ) -> Result<Self, NmstateError> {
        let interfaces = MergedInterfaces::new(
            desired.interfaces,
            current.interfaces,
            gen_conf_mode,
            memory_only,
        )?;
        let ignored_ifaces = interfaces.ignored_ifaces.as_slice();

        let mut routes =
            MergedRoutes::new(desired.routes, current.routes, &interfaces)?;
        routes.remove_routes_to_ignored_ifaces(ignored_ifaces);

        let mut rules = MergedRouteRules::new(desired.rules, current.rules)?;
        rules.remove_rules_to_ignored_ifaces(ignored_ifaces);

        let hostname =
            MergedHostNameState::new(desired.hostname, current.hostname);

        let mut ovsdb = MergedOvsDbGlobalConfig::new(
            desired.ovsdb,
            current.ovsdb,
            current.ovn.clone().bridge_mappings,
        )?;
        let ovn_config = MergedOvnConfiguration::new(desired.ovn, current.ovn)?;
        if let Some(updated_mapping_value) =
            ovn_config.clone().mappings_ext_id_value
        {
            if updated_mapping_value.is_empty() {
                ovsdb.external_ids.remove(OVN_BRIDGE_MAPPINGS);
            } else {
                ovsdb
                    .external_ids
                    .entry(OVN_BRIDGE_MAPPINGS.to_string())
                    .and_modify(|m| *m = Some(updated_mapping_value.clone()))
                    .or_insert(Some(updated_mapping_value.clone()));
            }
        }
        let ret = Self {
            interfaces,
            routes,
            rules,
            dns: MergedDnsState::new(desired.dns, current.dns)?,
            ovsdb,
            ovn: ovn_config,
            hostname,
            memory_only,
            prop_list: desired.prop_list,
        };
        ret.validate_ipv6_link_local_address_dns_srv()?;

        Ok(ret)
    }
}
