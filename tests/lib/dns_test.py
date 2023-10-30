# SPDX-License-Identifier: LGPL-2.1-or-later

from copy import deepcopy

import pytest

from libnmstate.error import NmstateVerificationError
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import Route

from libnmstate.ifaces import BaseIface
from libnmstate.ifaces import Ifaces
from libnmstate.route import RouteState
from libnmstate.dns import DnsState

from .testlib.ifacelib import gen_foo_iface_info
from .testlib.ifacelib import gen_two_static_ip_ifaces
from .testlib.routelib import IPV4_ROUTE_IFACE_NAME
from .testlib.routelib import IPV6_ROUTE_IFACE_NAME
from .testlib.routelib import gen_ipv4_default_gateway
from .testlib.routelib import gen_ipv6_default_gateway


IPV4_DNS_SERVER1 = "192.0.2.1"
IPV4_DNS_SERVER2 = "192.0.2.2"
IPV4_DNS_SERVER3 = "192.0.2.3"
IPV6_DNS_SERVER1 = "2001:db8:a::1"
IPV6_DNS_SERVER2 = "2001:db8:a::2"
IPV6_DNS_SERVER3 = "2001:db8:a::3"

DNS_SEARCHES_1 = ["example.com", "example.org"]
DNS_SEARCHES_2 = ["example.info", "example.net"]

DNS_OPTOINS1 = ["debug", "rotate"]
DNS_OPTOINS2 = ["debug", "single-request"]

DNS_CONFIG1 = {
    DNS.SERVER: [IPV4_DNS_SERVER1, IPV6_DNS_SERVER1],
    DNS.SEARCH: DNS_SEARCHES_1,
    DNS.OPTIONS: DNS_OPTOINS1,
}

DNS_CONFIG2 = {
    DNS.SERVER: [IPV6_DNS_SERVER2, IPV4_DNS_SERVER2],
    DNS.SEARCH: DNS_SEARCHES_2,
    DNS.OPTIONS: DNS_OPTOINS2,
}


class TestDnsState:
    def test_merge_without_desire_with_current(self):
        dns_state = DnsState({}, {DNS.CONFIG: DNS_CONFIG1})

        assert dns_state.config == DNS_CONFIG1
        assert dns_state.current_config == DNS_CONFIG1

    def test_merge_by_overriding_current(self):
        dns_state = DnsState(
            {DNS.CONFIG: DNS_CONFIG2},
            {DNS.CONFIG: DNS_CONFIG1},
        )

        assert dns_state.config == DNS_CONFIG2
        assert dns_state.current_config == DNS_CONFIG1

    def test_merge_by_discarding_current(self):
        dns_state = DnsState({DNS.CONFIG: {}}, {DNS.CONFIG: DNS_CONFIG1})

        assert dns_state.config == {
            DNS.SERVER: [],
            DNS.SEARCH: [],
            DNS.OPTIONS: [],
        }
        assert dns_state.current_config == DNS_CONFIG1

    def test_gen_metadadata_use_default_gateway_ipv4_server_prefered(self):
        ifaces = self._gen_static_ifaces()
        route_state = self._gen_route_state(ifaces)
        dns_state = DnsState({DNS.CONFIG: DNS_CONFIG1}, {})
        ifaces.gen_dns_metadata(dns_state, route_state)
        ipv4_iface = ifaces.all_kernel_ifaces[IPV4_ROUTE_IFACE_NAME]
        ipv6_iface = ifaces.all_kernel_ifaces[IPV6_ROUTE_IFACE_NAME]

        assert dns_state.config == DNS_CONFIG1
        assert ipv4_iface.to_dict()[Interface.IPV4][
            BaseIface.DNS_METADATA
        ] == {
            DnsState.PRIORITY_METADATA: 0,
            DNS.SERVER: [IPV4_DNS_SERVER1],
            DNS.SEARCH: DNS_SEARCHES_1,
            DNS.OPTIONS: DNS_OPTOINS1,
        }
        assert ipv6_iface.to_dict()[Interface.IPV6][
            BaseIface.DNS_METADATA
        ] == {
            DnsState.PRIORITY_METADATA: 1,
            DNS.SERVER: [IPV6_DNS_SERVER1],
            DNS.SEARCH: [],
            DNS.OPTIONS: [],
        }

    def test_gen_metadadata_use_default_gateway_ipv6_server_prefered(self):
        ifaces = self._gen_static_ifaces()
        route_state = self._gen_route_state(ifaces)
        dns_state = DnsState({DNS.CONFIG: DNS_CONFIG2}, {})
        ifaces.gen_dns_metadata(dns_state, route_state)
        ipv4_iface = ifaces.all_kernel_ifaces[IPV4_ROUTE_IFACE_NAME]
        ipv6_iface = ifaces.all_kernel_ifaces[IPV6_ROUTE_IFACE_NAME]

        assert dns_state.config == DNS_CONFIG2
        assert ipv4_iface.to_dict()[Interface.IPV4][
            BaseIface.DNS_METADATA
        ] == {
            DnsState.PRIORITY_METADATA: 1,
            DNS.SERVER: [IPV4_DNS_SERVER2],
            DNS.SEARCH: [],
            DNS.OPTIONS: [],
        }
        assert ipv6_iface.to_dict()[Interface.IPV6][
            BaseIface.DNS_METADATA
        ] == {
            DnsState.PRIORITY_METADATA: 0,
            DNS.SERVER: [IPV6_DNS_SERVER2],
            DNS.SEARCH: DNS_SEARCHES_2,
            DNS.OPTIONS: DNS_OPTOINS2,
        }

    def test_gen_metadata_use_dynamic_interface(self):
        ifaces = self._gen_dynamic_ifaces_with_no_auto_dns()
        route_state = self._gen_empty_route_state()
        dns_state = DnsState({DNS.CONFIG: DNS_CONFIG1}, {})
        ifaces.gen_dns_metadata(dns_state, route_state)
        ipv4_iface = ifaces.all_kernel_ifaces[IPV4_ROUTE_IFACE_NAME]
        ipv6_iface = ifaces.all_kernel_ifaces[IPV6_ROUTE_IFACE_NAME]

        assert dns_state.config == DNS_CONFIG1
        assert ipv4_iface.to_dict()[Interface.IPV4][
            BaseIface.DNS_METADATA
        ] == {
            DnsState.PRIORITY_METADATA: 0,
            DNS.SERVER: [IPV4_DNS_SERVER1],
            DNS.SEARCH: DNS_SEARCHES_1,
            DNS.OPTIONS: DNS_OPTOINS1,
        }
        assert ipv6_iface.to_dict()[Interface.IPV6][
            BaseIface.DNS_METADATA
        ] == {
            DnsState.PRIORITY_METADATA: 1,
            DNS.SERVER: [IPV6_DNS_SERVER1],
            DNS.SEARCH: [],
            DNS.OPTIONS: [],
        }

    def test_gen_metadata_with_auto_interface_only(self):
        ifaces = self._gen_dynamic_ifaces()
        route_state = self._gen_empty_route_state()
        dns_state = DnsState({DNS.CONFIG: DNS_CONFIG1}, {})
        ifaces.gen_dns_metadata(dns_state, route_state)
        ipv4_iface = ifaces.all_kernel_ifaces[IPV4_ROUTE_IFACE_NAME]
        ipv6_iface = ifaces.all_kernel_ifaces[IPV6_ROUTE_IFACE_NAME]

        assert dns_state.config == DNS_CONFIG1
        assert ipv4_iface.to_dict()[Interface.IPV4][
            BaseIface.DNS_METADATA
        ] == {
            DnsState.PRIORITY_METADATA: 0,
            DNS.SERVER: [IPV4_DNS_SERVER1],
            DNS.SEARCH: DNS_SEARCHES_1,
            DNS.OPTIONS: DNS_OPTOINS1,
        }
        assert ipv6_iface.to_dict()[Interface.IPV6][
            BaseIface.DNS_METADATA
        ] == {
            DnsState.PRIORITY_METADATA: 1,
            DNS.SERVER: [IPV6_DNS_SERVER1],
            DNS.SEARCH: [],
            DNS.OPTIONS: [],
        }

    @pytest.fixture
    def with_dns_metadata(self):
        ifaces = self._gen_static_ifaces()
        route_state = self._gen_route_state(ifaces)
        dns_state = DnsState({}, {DNS.CONFIG: DNS_CONFIG1})
        ifaces.gen_dns_metadata(dns_state, route_state)
        ipv4_iface = ifaces.all_kernel_ifaces[IPV4_ROUTE_IFACE_NAME]
        ipv6_iface = ifaces.all_kernel_ifaces[IPV6_ROUTE_IFACE_NAME]

        assert dns_state.config == DNS_CONFIG1
        assert ipv4_iface.to_dict()[Interface.IPV4][
            BaseIface.DNS_METADATA
        ] == {
            DnsState.PRIORITY_METADATA: 0,
            DNS.SERVER: [IPV4_DNS_SERVER1],
            DNS.SEARCH: DNS_SEARCHES_1,
            DNS.OPTIONS: DNS_OPTOINS1,
        }
        assert ipv6_iface.to_dict()[Interface.IPV6][
            BaseIface.DNS_METADATA
        ] == {
            DnsState.PRIORITY_METADATA: 1,
            DNS.SERVER: [IPV6_DNS_SERVER1],
            DNS.SEARCH: [],
            DNS.OPTIONS: [],
        }
        yield ipv4_iface, ipv6_iface

    def test_remove_metadata(self, with_dns_metadata):
        ipv4_iface, ipv6_iface = with_dns_metadata
        ipv4_iface.remove_dns_metadata()
        ipv6_iface.remove_dns_metadata()

        assert (
            BaseIface.DNS_METADATA not in ipv4_iface.to_dict()[Interface.IPV4]
        )
        assert (
            BaseIface.DNS_METADATA not in ipv6_iface.to_dict()[Interface.IPV6]
        )

    def test_verify_identical_state(self):
        dns_state = DnsState({DNS.CONFIG: DNS_CONFIG1}, {})
        dns_state.verify({DNS.CONFIG: DNS_CONFIG1})

    def test_verify_not_match(self):
        dns_state = DnsState({DNS.CONFIG: DNS_CONFIG1}, {})
        print("HAHA ", dns_state.config_changed)
        with pytest.raises(NmstateVerificationError):
            dns_state.verify({DNS.CONFIG: DNS_CONFIG2})

    @pytest.mark.parametrize(
        "dns_servers",
        [
            ([IPV4_DNS_SERVER1, IPV4_DNS_SERVER2, IPV4_DNS_SERVER3]),
            ([IPV6_DNS_SERVER1, IPV6_DNS_SERVER2, IPV6_DNS_SERVER3]),
            ([IPV4_DNS_SERVER1, IPV4_DNS_SERVER2, IPV6_DNS_SERVER1]),
            ([IPV6_DNS_SERVER1, IPV6_DNS_SERVER2, IPV4_DNS_SERVER1]),
            ([IPV4_DNS_SERVER1, IPV6_DNS_SERVER1, IPV4_DNS_SERVER2]),
            ([IPV6_DNS_SERVER1, IPV4_DNS_SERVER1, IPV6_DNS_SERVER2]),
            (
                [
                    IPV4_DNS_SERVER1,
                    IPV4_DNS_SERVER2,
                    IPV6_DNS_SERVER1,
                    IPV6_DNS_SERVER2,
                ]
            ),
            (
                [
                    IPV6_DNS_SERVER1,
                    IPV6_DNS_SERVER2,
                    IPV4_DNS_SERVER1,
                    IPV4_DNS_SERVER2,
                ]
            ),
        ],
        ids=[
            "3ipv4",
            "3ipv6",
            "2ipv4+ipv6",
            "2ipv6+ipv4",
            "ipv4+ipv6+ipv4",
            "ipv6+ipv4+ipv6",
            "2ipv4+2ipv6",
            "2ipv6+2ipv4",
        ],
    )
    def test_validate_3_more_name_servers(self, dns_servers):
        dns_config = deepcopy(DNS_CONFIG1)
        dns_config[DNS.SERVER] = dns_servers
        DnsState({DNS.CONFIG: dns_config}, {})

    def test_3_dns_ipv4_servers(self):
        dns_config = deepcopy(DNS_CONFIG1)
        dns_config[DNS.SERVER] = [
            IPV4_DNS_SERVER1,
            IPV4_DNS_SERVER2,
            IPV4_DNS_SERVER3,
        ]

        dns_state = DnsState({DNS.CONFIG: dns_config}, {})
        ifaces = self._gen_static_ifaces()
        route_state = self._gen_route_state(ifaces)
        ifaces.gen_dns_metadata(dns_state, route_state)

        ipv4_iface = ifaces.all_kernel_ifaces[IPV4_ROUTE_IFACE_NAME]

        assert dns_state.config == dns_config
        assert ipv4_iface.to_dict()[Interface.IPV4][
            BaseIface.DNS_METADATA
        ] == {
            DnsState.PRIORITY_METADATA: 0,
            DNS.SERVER: dns_config[DNS.SERVER],
            DNS.SEARCH: DNS_SEARCHES_1,
            DNS.OPTIONS: DNS_OPTOINS1,
        }

    def test_3_dns_ipv6_servers(self):
        dns_config = deepcopy(DNS_CONFIG1)
        dns_config[DNS.SERVER] = [
            IPV6_DNS_SERVER1,
            IPV6_DNS_SERVER2,
            IPV6_DNS_SERVER3,
        ]

        ifaces = self._gen_static_ifaces()
        route_state = self._gen_route_state(ifaces)
        dns_state = DnsState({DNS.CONFIG: dns_config}, {})
        ifaces.gen_dns_metadata(dns_state, route_state)
        ipv6_iface = ifaces.all_kernel_ifaces[IPV6_ROUTE_IFACE_NAME]

        assert dns_state.config == dns_config
        assert ipv6_iface.to_dict()[Interface.IPV6][
            BaseIface.DNS_METADATA
        ] == {
            DnsState.PRIORITY_METADATA: 0,
            DNS.SERVER: dns_config[DNS.SERVER],
            DNS.SEARCH: DNS_SEARCHES_1,
            DNS.OPTIONS: DNS_OPTOINS1,
        }

    def _gen_dynamic_ifaces_with_no_auto_dns(self):
        ipv4_iface_info = gen_foo_iface_info()
        ipv4_iface_info[Interface.NAME] = IPV4_ROUTE_IFACE_NAME
        ipv4_iface_info[Interface.IPV4] = {
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.DHCP: True,
            InterfaceIPv4.AUTO_DNS: False,
        }
        ipv6_iface_info = gen_foo_iface_info()
        ipv6_iface_info[Interface.NAME] = IPV6_ROUTE_IFACE_NAME
        ipv6_iface_info[Interface.IPV6] = {
            InterfaceIPv6.ENABLED: True,
            InterfaceIPv6.DHCP: True,
            InterfaceIPv6.AUTOCONF: True,
            InterfaceIPv6.AUTO_DNS: False,
        }
        return Ifaces([], [ipv4_iface_info, ipv6_iface_info])

    def _gen_dynamic_ifaces(self):
        ipv4_iface_info = gen_foo_iface_info()
        ipv4_iface_info[Interface.NAME] = IPV4_ROUTE_IFACE_NAME
        ipv4_iface_info[Interface.IPV4] = {
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.DHCP: True,
            InterfaceIPv4.AUTO_DNS: True,
        }
        ipv6_iface_info = gen_foo_iface_info()
        ipv6_iface_info[Interface.NAME] = IPV6_ROUTE_IFACE_NAME
        ipv6_iface_info[Interface.IPV6] = {
            InterfaceIPv6.ENABLED: True,
            InterfaceIPv6.DHCP: True,
            InterfaceIPv6.AUTOCONF: True,
            InterfaceIPv6.AUTO_DNS: True,
        }
        return Ifaces([], [ipv4_iface_info, ipv6_iface_info])

    def _gen_static_ifaces(self):
        return gen_two_static_ip_ifaces(
            IPV4_ROUTE_IFACE_NAME, IPV6_ROUTE_IFACE_NAME
        )

    def _gen_empty_route_state(self):
        return RouteState(Ifaces({}, {}), {}, {})

    def _gen_route_state(self, ifaces):
        return RouteState(
            ifaces,
            {},
            {
                Route.CONFIG: [
                    gen_ipv4_default_gateway().to_dict(),
                    gen_ipv6_default_gateway().to_dict(),
                ]
            },
        )

    def test_desire_search_only_will_merge_current(self):
        des_config = {
            DNS.CONFIG: {
                DNS.SEARCH: DNS_SEARCHES_1,
            }
        }
        cur_config = {
            DNS.CONFIG: {
                DNS.SERVER: [IPV4_DNS_SERVER1, IPV6_DNS_SERVER1],
                DNS.OPTIONS: DNS_OPTOINS1,
            }
        }
        dns_state = DnsState(des_config, cur_config)

        assert dns_state.config == DNS_CONFIG1
