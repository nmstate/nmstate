# SPDX-License-Identifier: Apache-2.0

from contextlib import contextmanager

import libnmstate
from libnmstate.schema import IpTunnel
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType


@contextmanager
def ip_tunnel_interface(
    name,
    mode,
    local,
    remote,
    parent=None,
    ttl=None,
    tos=None,
    path_mtu_discovery=None,
    encap_limit=None,
    flow_label=None,
    ip6tun_flags=None,
    create=True,
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: name,
                Interface.TYPE: InterfaceType.IP_TUNNEL,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
                    InterfaceIPv4.ENABLED: False,
                },
                Interface.IPV6: {
                    InterfaceIPv6.ENABLED: False,
                },
                IpTunnel.CONFIG_SUBTREE: {
                    IpTunnel.MODE: mode,
                    IpTunnel.LOCAL: local,
                    IpTunnel.REMOTE: remote,
                },
            }
        ]
    }

    if parent is not None:
        desired_state[Interface.KEY][0][IpTunnel.CONFIG_SUBTREE][
            IpTunnel.BASE_IFACE
        ] = parent

    if ttl is not None:
        desired_state[Interface.KEY][0][IpTunnel.CONFIG_SUBTREE][
            IpTunnel.TTL
        ] = ttl

    if tos is not None:
        desired_state[Interface.KEY][0][IpTunnel.CONFIG_SUBTREE][
            IpTunnel.TOS
        ] = tos

    if ip6tun_flags is not None:
        desired_state[Interface.KEY][0][IpTunnel.CONFIG_SUBTREE][
            IpTunnel.IP6TUN_FLAGS
        ] = ip6tun_flags

    if flow_label is not None:
        desired_state[Interface.KEY][0][IpTunnel.CONFIG_SUBTREE][
            IpTunnel.FLOW_LABEL
        ] = flow_label

    if path_mtu_discovery is not None:
        desired_state[Interface.KEY][0][IpTunnel.CONFIG_SUBTREE][
            IpTunnel.PMTU_DISC
        ] = path_mtu_discovery

    if encap_limit is not None:
        desired_state[Interface.KEY][0][IpTunnel.CONFIG_SUBTREE][
            IpTunnel.ENCAP_LIMIT
        ] = encap_limit

    if create:
        libnmstate.apply(desired_state)

    try:
        yield desired_state
    finally:
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: name,
                        Interface.TYPE: InterfaceType.IP_TUNNEL,
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            },
        )
