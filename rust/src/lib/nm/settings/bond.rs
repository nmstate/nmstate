// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::nm::nm_dbus::{NmConnection, NmSettingBond};

use crate::{BondConfig, BondInterface, BondOptions};

const DEFAULT_ARP_MISSED_MAX: u8 = 2;

#[cfg(feature = "query_apply")]
pub(crate) fn get_bond_balance_slb(nm_conn: &NmConnection) -> Option<bool> {
    if let Some(nm_bond_setting) = nm_conn.bond.as_ref() {
        match nm_bond_setting
            .options
            .get("balance-slb")
            .map(|s| s.as_str())
        {
            Some("1") => Some(true),
            Some("0") => Some(false),
            Some(i) => {
                log::warn!("Unknown value for bond balance-slb {}", i);
                None
            }
            None => None,
        }
    } else {
        None
    }
}

pub(crate) fn gen_nm_bond_setting(
    bond_iface: &BondInterface,
    nm_conn: &mut NmConnection,
) {
    let mut nm_bond_setting =
        nm_conn.bond.as_ref().cloned().unwrap_or_default();

    if bond_iface.is_options_reset() {
        nm_bond_setting.options.retain(|k, _| k == "mode");
    }

    if let Some(bond_conf) = bond_iface.bond.as_ref() {
        apply_bond_mode(&mut nm_bond_setting, bond_conf);
        if let Some(bond_opts) = bond_conf.options.as_ref() {
            apply_bond_options(&mut nm_bond_setting, bond_opts);
        }
    }

    nm_conn.bond = Some(nm_bond_setting);
}

fn apply_bond_mode(nm_bond_set: &mut NmSettingBond, bond_conf: &BondConfig) {
    if let Some(mode) = bond_conf.mode {
        if Some(&mode.to_string()) != nm_bond_set.options.get("mode") {
            nm_bond_set.options = HashMap::new();
        }
        nm_bond_set
            .options
            .insert("mode".to_string(), mode.to_string());
    }
}

fn apply_bond_options(
    nm_bond_set: &mut NmSettingBond,
    bond_opts: &BondOptions,
) {
    if let Some(v) = bond_opts.ad_actor_sys_prio.as_ref() {
        nm_bond_set
            .options
            .insert("ad_actor_sys_prio".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.ad_actor_system.as_ref() {
        nm_bond_set
            .options
            .insert("ad_actor_system".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.ad_select.as_ref() {
        nm_bond_set
            .options
            .insert("ad_select".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.ad_user_port_key.as_ref() {
        nm_bond_set
            .options
            .insert("ad_user_port_key".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.all_slaves_active.as_ref() {
        nm_bond_set
            .options
            .insert("all_slaves_active".to_string(), u8::from(*v).to_string());
    }
    if let Some(v) = bond_opts.arp_all_targets.as_ref() {
        nm_bond_set
            .options
            .insert("arp_all_targets".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.arp_interval.as_ref() {
        if *v == 0 {
            nm_bond_set
                .options
                .insert("arp_ip_target".to_string(), String::new());
        }
        nm_bond_set
            .options
            .insert("arp_interval".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.arp_ip_target.as_ref() {
        nm_bond_set
            .options
            .insert("arp_ip_target".to_string(), v.clone());
    }
    if let Some(v) = bond_opts.arp_validate.as_ref() {
        nm_bond_set
            .options
            .insert("arp_validate".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.downdelay.as_ref() {
        nm_bond_set
            .options
            .insert("downdelay".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.fail_over_mac.as_ref() {
        nm_bond_set
            .options
            .insert("fail_over_mac".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.lacp_rate.as_ref() {
        nm_bond_set
            .options
            .insert("lacp_rate".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.lp_interval.as_ref() {
        nm_bond_set
            .options
            .insert("lp_interval".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.miimon.as_ref() {
        nm_bond_set
            .options
            .insert("miimon".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.min_links.as_ref() {
        nm_bond_set
            .options
            .insert("min_links".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.num_grat_arp.as_ref() {
        nm_bond_set
            .options
            .insert("num_grat_arp".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.num_unsol_na.as_ref() {
        nm_bond_set
            .options
            .insert("num_unsol_na".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.packets_per_slave.as_ref() {
        nm_bond_set
            .options
            .insert("packets_per_slave".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.primary.as_ref() {
        nm_bond_set.options.insert("primary".to_string(), v.clone());
    }
    if let Some(v) = bond_opts.primary_reselect.as_ref() {
        nm_bond_set
            .options
            .insert("primary_reselect".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.resend_igmp.as_ref() {
        nm_bond_set
            .options
            .insert("resend_igmp".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.tlb_dynamic_lb.as_ref() {
        let v_parsed: u8 = (*v).into();
        nm_bond_set
            .options
            .insert("tlb_dynamic_lb".to_string(), v_parsed.to_string());
    }
    if let Some(v) = bond_opts.updelay.as_ref() {
        nm_bond_set
            .options
            .insert("updelay".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.use_carrier.as_ref() {
        let v_parsed: u8 = (*v).into();
        nm_bond_set
            .options
            .insert("use_carrier".to_string(), v_parsed.to_string());
    }
    if let Some(v) = bond_opts.xmit_hash_policy.as_ref() {
        nm_bond_set
            .options
            .insert("xmit_hash_policy".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.balance_slb.as_ref() {
        nm_bond_set.options.insert(
            "balance-slb".to_string(),
            if *v { "1".to_string() } else { "0".to_string() },
        );
    }
    if let Some(v) = bond_opts.arp_missed_max.as_ref() {
        // The `arp_missed_max` is only supported by NM 1.42+, when using
        // default value, we do not set it in NM configure in case user are
        // applying whatever they got from `NetworkState::retrieve()`.
        if nm_bond_set.options.contains_key("arp_missed_max")
            || *v != DEFAULT_ARP_MISSED_MAX
        {
            nm_bond_set
                .options
                .insert("arp_missed_max".to_string(), v.to_string());
        }
    }

    // Remove all empty string option
    nm_bond_set.options.retain(|_, v| !v.is_empty());
}

pub(crate) fn gen_nm_bond_port_setting(
    bond_iface: &BondInterface,
    nm_conn: &mut NmConnection,
) {
    let mut nm_set = nm_conn.bond_port.as_ref().cloned().unwrap_or_default();
    let bond_port_conf = if let Some(i) = nm_conn
        .iface_name()
        .and_then(|iface_name| bond_iface.get_port_conf(iface_name))
    {
        i
    } else {
        return;
    };

    if let Some(v) = bond_port_conf.priority {
        nm_set.priority = Some(v);
    }

    if let Some(v) = bond_port_conf.queue_id {
        nm_set.queue_id = Some(v.into());
    }

    nm_conn.bond_port = Some(nm_set);
}
