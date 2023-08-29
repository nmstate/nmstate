// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::NmSettingIp;

use crate::DnsClientState;

pub(crate) fn apply_nm_dns_setting(
    nm_ip_setting: &mut NmSettingIp,
    dns_conf: &DnsClientState,
) {
    nm_ip_setting.dns = dns_conf.server.clone();
    nm_ip_setting.dns_search = dns_conf.search.clone();
    nm_ip_setting.dns_priority = dns_conf.priority;
    nm_ip_setting.dns_options = dns_conf.options.clone();
}
