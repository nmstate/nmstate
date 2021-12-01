use nm_dbus::{NmConnection, NmSettingBond};

use crate::{BondConfig, BondInterface, BondMode, BondOptions};

pub(crate) fn gen_nm_bond_setting(
    bond_iface: &BondInterface,
    nm_conn: &mut NmConnection,
) {
    let mut nm_bond_setting =
        nm_conn.bond.as_ref().cloned().unwrap_or_default();

    if let Some(bond_conf) = bond_iface.bond.as_ref() {
        apply_bond_config(&mut nm_bond_setting, bond_conf);
        if let Some(bond_opts) = bond_conf.options.as_ref() {
            nm_bond_setting.options.clear();
            apply_bond_options(&mut nm_bond_setting, bond_opts);
            if nm_bond_setting.options.is_empty() {
                nm_bond_setting.clear_existing_opts();
            }
        }
    }

    nm_conn.bond = Some(nm_bond_setting);
}

fn apply_bond_config(nm_bond_set: &mut NmSettingBond, bond_conf: &BondConfig) {
    if let Some(mode) = &bond_conf.mode {
        if bond_mode_changed(nm_bond_set, mode) {
            nm_bond_set.clear_existing_opts();
        }
        nm_bond_set.mode = mode.to_string();
    }
}

fn bond_mode_changed(nm_bond_set: &mut NmSettingBond, mode: &BondMode) -> bool {
    if let Some(current_mode) = nm_bond_set.get_current_mode() {
        return !current_mode.eq(&mode.to_string());
    }
    false
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
            .insert("ad_select".to_string(), v.to_u8().to_string());
    }
    if let Some(v) = bond_opts.ad_user_port_key.as_ref() {
        nm_bond_set
            .options
            .insert("ad_user_port_key".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.all_slaves_active.as_ref() {
        nm_bond_set
            .options
            .insert("all_slaves_active".to_string(), v.to_u8().to_string());
    }
    if let Some(v) = bond_opts.arp_all_targets.as_ref() {
        nm_bond_set
            .options
            .insert("arp_all_targets".to_string(), v.to_u32().to_string());
    }
    if let Some(v) = bond_opts.arp_interval.as_ref() {
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
            .insert("arp_validate".to_string(), v.to_u32().to_string());
    }
    if let Some(v) = bond_opts.downdelay.as_ref() {
        nm_bond_set
            .options
            .insert("downdelay".to_string(), v.to_string());
    }
    if let Some(v) = bond_opts.fail_over_mac.as_ref() {
        nm_bond_set
            .options
            .insert("fail_over_mac".to_string(), v.to_u8().to_string());
    }
    if let Some(v) = bond_opts.lacp_rate.as_ref() {
        nm_bond_set
            .options
            .insert("lacp_rate".to_string(), v.to_u8().to_string());
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
            .insert("primary_reselect".to_string(), v.to_u8().to_string());
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
            .insert("xmit_hash_policy".to_string(), v.to_u8().to_string());
    }
}
