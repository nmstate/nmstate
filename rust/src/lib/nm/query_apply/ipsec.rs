// SPDX-License-Identifier: Apache-2.0

#[cfg(test)]
use std::collections::HashMap;
use std::net::IpAddr;
#[cfg(target_os = "linux")]
use std::{num::NonZeroI32, time::Duration};

#[cfg(target_os = "linux")]
use crate::ErrorKind;
#[cfg(test)]
use crate::nm::nm_dbus::{NmIfaceType, NmSettingConnection, NmSettingIp};
use crate::{
    NmstateError,
    nm::nm_dbus::{NmApi, NmConnection, NmSettingIpMethod, NmSettingVpn},
};

#[cfg(target_os = "linux")]
const NM_DEVICE_WAIT_ATTEMPTS: usize = 20;
#[cfg(target_os = "linux")]
const NM_DEVICE_WAIT_INTERVAL: Duration = Duration::from_millis(50);
// Linux `EEXIST`.
#[cfg(target_os = "linux")]
const EEXIST: i32 = 17;

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
/// Realizing `ipsecN` before activation closes that window. An error here
/// must skip activation; continuing would take the same assertion path.
pub(crate) async fn prepare_ipsec_xfrm_for_nm(
    nm_api: &mut NmApi<'_>,
    nm_conn: &NmConnection,
) -> Result<(), NmstateError> {
    #[cfg(target_os = "linux")]
    if let Some(target) = xfrm_precreate_target(nm_conn) {
        prepare_linux(nm_api, &target).await?;
    }
    #[cfg(not(target_os = "linux"))]
    {
        let _ = (nm_api, nm_conn);
    }
    Ok(())
}

/// Non-controller connections, with IPSec profiles that need an XFRM parent
/// placed after every profile that does not.
///
/// Activation is otherwise ordered by priority and name
/// (`nm/connection.rs`). A combined apply can therefore reach the VPN
/// before the interface that will own `left` has its address. Pre-creation
/// needs that ifindex, so those profiles run first and the VPN is retried
/// if the address is not visible yet.
pub(super) fn order_ipsec_parents_first(
    nm_conns: &[NmConnection],
) -> Vec<&NmConnection> {
    let conns: Vec<&NmConnection> = nm_conns
        .iter()
        .filter(|nm_conn| {
            nm_conn
                .iface_type()
                .map(|iface_type| iface_type.is_controller())
                != Some(true)
        })
        .collect();
    let ranks: Vec<u32> = (0..conns.len())
        .map(|index| ipsec_activation_rank(&conns, index, 0))
        .collect();
    let mut order: Vec<usize> = (0..conns.len()).collect();
    order.sort_by_key(|index| (ranks[*index], *index));
    order.into_iter().map(|index| conns[index]).collect()
}

fn ipsec_activation_rank(
    conns: &[&NmConnection],
    index: usize,
    depth: usize,
) -> u32 {
    if depth > conns.len() {
        return 0;
    }
    let Some(target) = xfrm_precreate_target(conns[index]) else {
        return 0;
    };
    conns.iter().enumerate().fold(1, |rank, (pos, candidate)| {
        if pos != index && conn_has_address(candidate, target.left) {
            rank.max(1 + ipsec_activation_rank(conns, pos, depth + 1))
        } else {
            rank
        }
    })
}

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

fn conn_has_address(nm_conn: &NmConnection, left: IpAddr) -> bool {
    [&nm_conn.ipv4, &nm_conn.ipv6]
        .into_iter()
        .flatten()
        .any(|ip| {
            ip.addresses.iter().any(|addr| {
                addr.split_once('/')
                    .map(|(ip_addr, _prefix)| ip_addr)
                    .unwrap_or(addr)
                    .parse::<IpAddr>()
                    .ok()
                    == Some(left)
            })
        })
}

#[cfg(target_os = "linux")]
async fn prepare_linux(
    nm_api: &mut NmApi<'_>,
    target: &XfrmPrecreate,
) -> Result<(), NmstateError> {
    let mut state = kernel_state().await?;
    if !state.ifaces.contains_key(&target.name)
        && parent_index_for_left(&state, target.left).is_none()
    {
        for _ in 1..NM_DEVICE_WAIT_ATTEMPTS {
            tokio::time::sleep(NM_DEVICE_WAIT_INTERVAL).await;
            state = kernel_state().await?;
            if state.ifaces.contains_key(&target.name)
                || parent_index_for_left(&state, target.left).is_some()
            {
                break;
            }
        }
    }
    if !state.ifaces.contains_key(&target.name) {
        let parent_index = parent_index_for_left(&state, target.left)
            .ok_or_else(|| {
                NmstateError::new(
                    ErrorKind::Bug,
                    format!(
                        "no interface holds left address {} for {}",
                        target.left, target.name
                    ),
                )
            })?;
        create_xfrm_iface(&target.name, parent_index, target.if_id)
            .await
            .map_err(|err| {
                NmstateError::new(
                    ErrorKind::Bug,
                    format!(
                        "failed to create XFRM interface {}: {err}",
                        target.name
                    ),
                )
            })?;
        log::info!(
            "Created XFRM interface {} (if_id {}) on ifindex {parent_index} \
             before IPSec activation",
            target.name,
            target.if_id
        );
    }
    wait_for_nm_device(nm_api, &target.name).await
}

#[cfg(target_os = "linux")]
async fn kernel_state() -> Result<nispor::NetState, NmstateError> {
    let mut iface_filter = nispor::NetStateIfaceFilter::minimum();
    iface_filter.include_ip_address = true;
    let mut filter = nispor::NetStateFilter::minimum();
    filter.iface = Some(iface_filter);
    nispor::NetState::retrieve_with_filter_async(&filter)
        .await
        .map_err(|err| {
            NmstateError::new(
                ErrorKind::Bug,
                format!(
                    "failed to read interfaces before IPSec activation: {err}"
                ),
            )
        })
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
async fn wait_for_nm_device(
    nm_api: &mut NmApi<'_>,
    name: &str,
) -> Result<(), NmstateError> {
    for attempt in 0..NM_DEVICE_WAIT_ATTEMPTS {
        match nm_api.devices_get().await {
            Ok(devices) if devices.iter().any(|dev| dev.name == name) => {
                log::debug!(
                    "NetworkManager registered XFRM device {name} before \
                     IPSec activation"
                );
                return Ok(());
            }
            Ok(_) => {}
            Err(err) => {
                return Err(NmstateError::new(
                    ErrorKind::Bug,
                    format!(
                        "failed to list NetworkManager devices while \
                         preparing XFRM device {name}: {err}"
                    ),
                ));
            }
        }
        if attempt + 1 != NM_DEVICE_WAIT_ATTEMPTS {
            tokio::time::sleep(NM_DEVICE_WAIT_INTERVAL).await;
        }
    }
    Err(NmstateError::new(
        ErrorKind::Bug,
        format!(
            "NetworkManager did not register XFRM device {name} before IPSec \
             activation"
        ),
    ))
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
fn conn_with_address(addr: &str, iface_type: NmIfaceType) -> NmConnection {
    let mut ipv4 = NmSettingIp::default();
    ipv4.addresses = vec![addr.to_string()];
    let mut connection = NmSettingConnection::default();
    connection.iface_type = Some(iface_type);
    let mut nm_conn = NmConnection::default();
    nm_conn.connection = Some(connection);
    nm_conn.ipv4 = Some(ipv4);
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

    #[test]
    fn left_provider_is_ordered_before_ipsec() {
        let vpn = vpn_conn(NmSettingIpMethod::Disabled, "97", "192.0.2.2");
        let other = conn_with_address("198.51.100.9/24", NmIfaceType::Ethernet);
        let parent = conn_with_address("192.0.2.2/24", NmIfaceType::Ethernet);
        let bond = conn_with_address("192.0.2.2/24", NmIfaceType::Bond);
        let conns = [vpn, other, bond, parent];
        let ordered = order_ipsec_parents_first(&conns);

        assert!(
            ordered
                .iter()
                .all(|nm_conn| nm_conn.iface_type() != Some(&NmIfaceType::Bond))
        );
        let left = "192.0.2.2".parse::<IpAddr>().unwrap();
        let vpn_at = ordered
            .iter()
            .position(|nm_conn| nm_conn.vpn.is_some())
            .unwrap();
        let parent_at = ordered
            .iter()
            .position(|nm_conn| conn_has_address(nm_conn, left))
            .unwrap();
        assert!(parent_at < vpn_at);
        assert!(
            ordered[parent_at].ipv4.as_ref().unwrap().addresses[0]
                .starts_with("192.0.2.2")
        );
    }

    #[test]
    fn auto_ipsec_keeps_original_order() {
        let vpn = vpn_conn(NmSettingIpMethod::Auto, "97", "192.0.2.2");
        let parent = conn_with_address("192.0.2.2/24", NmIfaceType::Ethernet);
        let conns = [vpn, parent];
        let ordered = order_ipsec_parents_first(&conns);
        assert!(ordered[0].vpn.is_some());
    }
}
