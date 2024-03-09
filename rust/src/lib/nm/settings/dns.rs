// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::NmSettingIp;

use crate::DnsClientState;

pub(crate) fn apply_nm_dns_setting(
    nm_ip_setting: &mut NmSettingIp,
    dns_conf: &DnsClientState,
) {
    nm_ip_setting.dns.clone_from(&dns_conf.server);
    nm_ip_setting.dns_search.clone_from(&dns_conf.search);
    nm_ip_setting.dns_priority = dns_conf.priority;
    nm_ip_setting.dns_options.clone_from(&dns_conf.options);
}
