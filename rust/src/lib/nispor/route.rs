use log::warn;

use crate::{RouteEntry, Routes};

const SUPPORTED_ROUTE_SCOPE: [nispor::RouteScope; 2] =
    [nispor::RouteScope::Universe, nispor::RouteScope::Link];

const LOCAL_ROUTE_TABLE: u32 = 255;
const IPV4_DEFAULT_GATEWAY: &str = "0.0.0.0/0";
const IPV6_DEFAULT_GATEWAY: &str = "::/0";
const IPV4_EMPTY_NEXT_HOP_ADDRESS: &str = "0.0.0.0";
const IPV6_EMPTY_NEXT_HOP_ADDRESS: &str = "::";

pub(crate) fn get_routes(np_routes: &[nispor::Route]) -> Routes {
    let mut ret = Routes::new();

    ret.running = Some(
        np_routes
            .iter()
            .filter(|np_route| {
                SUPPORTED_ROUTE_SCOPE.contains(&np_route.scope)
                    && np_route.table != LOCAL_ROUTE_TABLE
                    && np_route.oif.as_ref() != Some(&"lo".to_string())
            })
            .map(np_route_to_nmstate)
            .collect(),
    );

    ret.config = Some(
        np_routes
            .iter()
            .filter(|np_route| {
                SUPPORTED_ROUTE_SCOPE.contains(&np_route.scope)
                    && np_route.protocol == nispor::RouteProtocol::Static
                    && np_route.table != LOCAL_ROUTE_TABLE
                    && np_route.oif.as_ref() != Some(&"lo".to_string())
            })
            .map(np_route_to_nmstate)
            .collect(),
    );
    ret
}

fn np_route_to_nmstate(np_route: &nispor::Route) -> RouteEntry {
    let destination = match &np_route.dst {
        Some(dst) => Some(dst.to_string()),
        None => match np_route.address_family {
            nispor::AddressFamily::IPv4 => {
                Some(IPV4_DEFAULT_GATEWAY.to_string())
            }
            nispor::AddressFamily::IPv6 => {
                Some(IPV6_DEFAULT_GATEWAY.to_string())
            }
            _ => {
                warn!(
                    "Route {:?} is holding unknown IP family {:?}",
                    np_route, np_route.address_family
                );
                None
            }
        },
    };

    let next_hop_addr = if let Some(via) = &np_route.via {
        Some(via.to_string())
    } else if let Some(gateway) = &np_route.gateway {
        Some(gateway.to_string())
    } else {
        match np_route.address_family {
            nispor::AddressFamily::IPv4 => {
                Some(IPV4_EMPTY_NEXT_HOP_ADDRESS.to_string())
            }
            nispor::AddressFamily::IPv6 => {
                Some(IPV6_EMPTY_NEXT_HOP_ADDRESS.to_string())
            }
            _ => {
                warn!(
                    "Route {:?} is holding unknown IP family {:?}",
                    np_route, np_route.address_family
                );
                None
            }
        }
    };

    let mut route_entry = RouteEntry::new();
    route_entry.destination = destination;
    route_entry.next_hop_iface = np_route.oif.as_ref().cloned();
    route_entry.next_hop_addr = next_hop_addr;
    route_entry.metric = np_route.metric.map(i64::from);
    route_entry.table_id = Some(np_route.table);

    route_entry
}
