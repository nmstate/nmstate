// SPDX-License-Identifier: Apache-2.0

// The code is copy from https://github.com/rust-netlink/rtnetlink/
// `examples/ip_monitor.rs`

use crate::{ErrorKind, NmstateError};

use futures::stream::StreamExt;
use rtnetlink::new_connection;
use rtnetlink::sys::{AsyncSocket, SocketAddr};

// Even we don't get netlink notification, we should check the
// links every 5 seconds in case.
const MANUAL_CHECK_INTERVAL: u64 = 5;

const RTNLGRP_LINK: u32 = 1;

pub(crate) async fn is_missing_ifaces_up(ifaces: &[&str]) -> bool {
    let mut filter = nispor::NetStateFilter::minimum();
    filter.iface = Some(Default::default());
    if let Ok(np_state) =
        nispor::NetState::retrieve_with_filter_async(&filter).await
    {
        ifaces
            .iter()
            .all(|iface| np_state.ifaces.contains_key(&iface.to_string()))
    } else {
        false
    }
}

pub(crate) async fn wait_iface_async(
    ifaces: &[&str],
    timeout_sec: u32,
) -> Result<(), NmstateError> {
    if is_missing_ifaces_up(ifaces).await {
        return Ok(());
    }
    log::info!(
        "Waiting missing interfaces to show up: {}",
        ifaces.join(",")
    );

    let (mut conn, mut _handle, mut messages) =
        new_connection().map_err(|e| {
            NmstateError::new(
                ErrorKind::Bug,
                format!("Failed to start rtnetlink socket {e}"),
            )
        })?;

    let groups = 1 << (RTNLGRP_LINK - 1);

    let addr = SocketAddr::new(0, groups);
    conn.socket_mut()
        .socket_mut()
        .bind(&addr)
        .expect("Failed to bind");

    // Spawn `Connection` to start polling netlink socket.
    tokio::spawn(conn);

    let tmo =
        tokio::time::sleep(std::time::Duration::from_secs(timeout_sec.into()));
    tokio::pin!(tmo);

    let mut interval = tokio::time::interval(std::time::Duration::from_secs(
        MANUAL_CHECK_INTERVAL,
    ));

    loop {
        tokio::select! {
            v = messages.next() => {
                // TODO: Check whether waiting interfaces included in message
                if v.is_some() && is_missing_ifaces_up(ifaces).await {
                    return Ok(());
                }
            },
            _ = interval.tick() => {
                if is_missing_ifaces_up(ifaces).await {
                    return Ok(());
                }
            },
            () = &mut tmo => {
                return Err(
                    NmstateError::new(
                        ErrorKind::Timeout,
                        format!("Timeout on waiting missing interfaces: '{}'",
                            ifaces.join(","))));
            }
        }
    }
}
