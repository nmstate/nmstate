// SPDX-License-Identifier: Apache-2.0

#[cfg(test)]
use std::collections::HashMap;
use std::net::IpAddr;
#[cfg(target_os = "linux")]
use std::{num::NonZeroI32, time::Duration};

#[cfg(test)]
use crate::nm::nm_dbus::NmSettingIp;
use crate::nm::nm_dbus::{
    NmApi, NmConnection, NmSettingIpMethod, NmSettingVpn,
};

#[cfg(target_os = "linux")]
const NM_DEVICE_WAIT_ATTEMPTS: usize = 20;
#[cfg(target_os = "linux")]
const NM_DEVICE_WAIT_INTERVAL: Duration = Duration::from_millis(50);
// Linux `EEXIST`.
#[cfg(target_os = "linux")]
const EEXIST: i32 = 17;

#[cfg_attr(not(target_os = "linux"), allow(dead_code))]
struct XfrmPrecreate {
    if_id: u32,
    name: String,
    left: IpAddr,
}

/// Create the libreswan XFRM interface and wait until NetworkManager has a
/// device for it.
///
/// NetworkManager main hits `nm_assert(device)` in
/// `nm_vpn_connection_check_complete()` when `ipv4.method` is not `auto`.
/// The generic config callback schedules the device-added idle, then the
/// following IPv4 config callback calls the same function again while the
/// device is still missing and aborts. That restart drops the checkpoint.
/// Realizing `ipsecN` before activation closes that window. Failure here is
/// logged and activation continues.
pub(crate) async fn prepare_ipsec_xfrm_for_nm(
    nm_api: &mut NmApi<'_>,
    nm_conn: &NmConnection,
) {
    #[cfg(target_os = "linux")]
    if let Some(target) = xfrm_precreate_target(nm_conn)
        && let Err(err) = prepare_linux(nm_api, &target).await
    {
        log::warn!(
            "Could not prepare XFRM interface {} before IPSec activation: \
             {err}",
            target.name
        );
    }
    #[cfg(not(target_os = "linux"))]
    {
        let _ = (nm_api, nm_conn);
    }
}

#[cfg_attr(not(target_os = "linux"), allow(dead_code))]
fn xfrm_precreate_target(nm_conn: &NmConnection) -> Option<XfrmPrecreate> {
    let vpn = nm_conn.vpn.as_ref()?;
    if vpn.service_type.as_deref() != Some(NmSettingVpn::SERVICE_TYPE_LIBRESWAN)
    {
        return None;
    }
    // `method_auto` is set only for ipv4.method=auto. That path waits for
    // IP config before the first check-complete, so it does not double-call.
    if nm_conn.ipv4.as_ref().and_then(|ip| ip.method.as_ref())
        == Some(&NmSettingIpMethod::Auto)
    {
        return None;
    }
    let data = vpn.data.as_ref()?;
    let if_id: u32 = data.get("ipsec-interface")?.parse().ok()?;
    // if_id 0 is remapped by libreswan and is not named `ipsec0`'s if_id.
    if if_id == 0 {
        return None;
    }
    let left: IpAddr = data.get("left")?.parse().ok()?;
    Some(XfrmPrecreate {
        if_id,
        name: format!("ipsec{if_id}"),
        left,
    })
}

#[cfg(target_os = "linux")]
async fn prepare_linux(
    nm_api: &mut NmApi<'_>,
    target: &XfrmPrecreate,
) -> Result<(), String> {
    let mut iface_filter = nispor::NetStateIfaceFilter::minimum();
    iface_filter.include_ip_address = true;
    let mut filter = nispor::NetStateFilter::minimum();
    filter.iface = Some(iface_filter);
    let state = nispor::NetState::retrieve_with_filter_async(&filter)
        .await
        .map_err(|err| err.to_string())?;

    if !state.ifaces.contains_key(&target.name) {
        let parent_index = parent_index_for_left(&state, target.left)
            .ok_or_else(|| {
                format!(
                    "no interface holds left address {} for {}",
                    target.left, target.name
                )
            })?;
        create_xfrm_iface(&target.name, parent_index, target.if_id).await?;
        log::info!(
            "Created XFRM interface {} (if_id {}) on ifindex {parent_index} \
             before IPSec activation",
            target.name,
            target.if_id
        );
    }
    wait_for_nm_device(nm_api, &target.name).await;
    Ok(())
}

#[cfg(target_os = "linux")]
fn parent_index_for_left(
    state: &nispor::NetState,
    left: IpAddr,
) -> Option<u32> {
    state.ifaces.values().find_map(|iface| {
        (iface.index != 0 && iface_has_address(iface, left))
            .then_some(iface.index)
    })
}

#[cfg(target_os = "linux")]
fn iface_has_address(iface: &nispor::Iface, left: IpAddr) -> bool {
    let ipv4_match = iface.ipv4.as_ref().is_some_and(|ipv4| {
        ipv4.addresses
            .iter()
            .any(|addr| addr.address.parse::<IpAddr>() == Ok(left))
    });
    let ipv6_match = iface.ipv6.as_ref().is_some_and(|ipv6| {
        ipv6.addresses
            .iter()
            .any(|addr| addr.address.parse::<IpAddr>() == Ok(left))
    });
    ipv4_match || ipv6_match
}

#[cfg(target_os = "linux")]
async fn create_xfrm_iface(
    name: &str,
    parent_index: u32,
    if_id: u32,
) -> Result<(), String> {
    let (connection, handle, _) =
        rtnetlink::new_connection().map_err(|err| err.to_string())?;
    let task = tokio::spawn(connection);
    let result = handle
        .link()
        .add(
            rtnetlink::LinkXfrm::new(name, parent_index, if_id)
                .up()
                .build(),
        )
        .execute()
        .await;
    task.abort();
    match result {
        Ok(()) => Ok(()),
        Err(err) if netlink_eexist(&err) => Ok(()),
        Err(err) => Err(err.to_string()),
    }
}

#[cfg(target_os = "linux")]
fn netlink_eexist(err: &rtnetlink::Error) -> bool {
    matches!(
        err,
        rtnetlink::Error::NetlinkError(msg)
            if msg.code == NonZeroI32::new(-EEXIST)
    )
}

#[cfg(target_os = "linux")]
async fn wait_for_nm_device(nm_api: &mut NmApi<'_>, name: &str) {
    for attempt in 0..NM_DEVICE_WAIT_ATTEMPTS {
        match nm_api.devices_get().await {
            Ok(devices) if devices.iter().any(|dev| dev.name == name) => {
                log::debug!(
                    "NetworkManager registered XFRM device {name} before \
                     IPSec activation"
                );
                return;
            }
            Ok(_) => {}
            Err(err) => {
                log::warn!(
                    "Failed to list NetworkManager devices while preparing \
                     XFRM device {name}: {err}"
                );
                return;
            }
        }
        if attempt + 1 != NM_DEVICE_WAIT_ATTEMPTS {
            tokio::time::sleep(NM_DEVICE_WAIT_INTERVAL).await;
        }
    }
    log::warn!(
        "NetworkManager did not register XFRM device {name} before IPSec \
         activation"
    );
}

#[cfg(test)]
fn vpn_conn(
    method: NmSettingIpMethod,
    ipsec_interface: &str,
    left: &str,
) -> NmConnection {
    let mut data = HashMap::new();
    data.insert("ipsec-interface".to_string(), ipsec_interface.to_string());
    data.insert("left".to_string(), left.to_string());
    let mut ipv4 = NmSettingIp::default();
    ipv4.method = Some(method);
    let mut vpn = NmSettingVpn::default();
    vpn.service_type = Some(NmSettingVpn::SERVICE_TYPE_LIBRESWAN.to_string());
    vpn.data = Some(data);
    let mut nm_conn = NmConnection::default();
    nm_conn.ipv4 = Some(ipv4);
    nm_conn.vpn = Some(vpn);
    nm_conn
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn disabled_ipv4_with_numeric_ipsec_interface_is_prepared() {
        let nm_conn = vpn_conn(NmSettingIpMethod::Disabled, "97", "192.0.2.2");
        let target = xfrm_precreate_target(&nm_conn).unwrap();
        assert_eq!(target.if_id, 97);
        assert_eq!(target.name, "ipsec97");
        assert_eq!(target.left, "192.0.2.2".parse::<IpAddr>().unwrap());
    }

    #[test]
    fn auto_ipv4_does_not_need_precreate() {
        let nm_conn = vpn_conn(NmSettingIpMethod::Auto, "97", "192.0.2.2");
        assert!(xfrm_precreate_target(&nm_conn).is_none());
    }

    #[test]
    fn non_numeric_or_zero_ipsec_interface_is_skipped() {
        assert!(
            xfrm_precreate_target(&vpn_conn(
                NmSettingIpMethod::Disabled,
                "yes",
                "192.0.2.2"
            ))
            .is_none()
        );
        assert!(
            xfrm_precreate_target(&vpn_conn(
                NmSettingIpMethod::Disabled,
                "0",
                "192.0.2.2"
            ))
            .is_none()
        );
    }

    #[test]
    fn left_must_be_an_address() {
        let nm_conn =
            vpn_conn(NmSettingIpMethod::Disabled, "97", "%defaultroute");
        assert!(xfrm_precreate_target(&nm_conn).is_none());
    }
}
