#
# Copyright (c) 2018-2019 Red Hat, Inc.
#
# This file is part of nmstate
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
import os
import time

import pytest

import libnmstate
from libnmstate.schema import Constants
from libnmstate.schema import DNS
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import Route as RT

from libnmstate.error import NmstateNotImplementedError

from .testlib import assertlib
from .testlib import cmd as libcmd
from .testlib import ifacelib
from .testlib import statelib
from .testlib.statelib import INTERFACES


IPV4_ADDRESS1 = '192.0.2.251'
IPV4_ADDRESS2 = '192.0.2.252'
IPV6_ADDRESS1 = '2001:db8:1::1'
IPV6_ADDRESS2 = '2001:db8:2::1'
IPV4_CLASSLESS_ROUTE_DST_NET1 = '198.51.100.0/24'
IPV4_CLASSLESS_ROUTE_NEXT_HOP1 = '192.0.2.1'
IPV6_CLASSLESS_ROUTE_PREFIX = '2001:db8:f'
IPV6_CLASSLESS_ROUTE_DST_NET1 = '{}::/64'.format(IPV6_CLASSLESS_ROUTE_PREFIX)

DHCP_SRV_NIC = 'dhcpsrv'
DHCP_CLI_NIC = 'dhcpcli'
DHCP_SRV_IP4 = IPV4_ADDRESS1
DHCP_SRV_IP6 = IPV6_ADDRESS1
DHCP_SRV_IP6_2 = "{}::1".format(IPV6_CLASSLESS_ROUTE_PREFIX)
DHCP_SRV_IP4_PREFIX = '192.0.2'
DHCP_SRV_IP6_PREFIX = '2001:db8:1'
DHCP_SRV_IP6_NETWORK = '{}::/64'.format(DHCP_SRV_IP6_PREFIX)

IPV6_DEFAULT_GATEWAY = '::/0'
IPV4_DEFAULT_GATEWAY = '0.0.0.0/0'

DNSMASQ_CONF_STR = """
interface={iface}
dhcp-range={ipv4_prefix}.200,{ipv4_prefix}.250,255.255.255.0,48h
enable-ra
dhcp-range={ipv6_prefix}::100,{ipv6_prefix}::fff,ra-names,slaac,64,480h
dhcp-range={ipv6_classless_route}::100,{ipv6_classless_route}::fff,static
dhcp-option=option:classless-static-route,{classless_rt},{classless_rt_dst}
dhcp-option=option:dns-server,{v4_dns_server}
""".format(
    **{
        'iface': DHCP_SRV_NIC,
        'ipv4_prefix': DHCP_SRV_IP4_PREFIX,
        'ipv6_prefix': DHCP_SRV_IP6_PREFIX,
        'classless_rt': IPV4_CLASSLESS_ROUTE_DST_NET1,
        'classless_rt_dst': IPV4_CLASSLESS_ROUTE_NEXT_HOP1,
        'v4_dns_server': DHCP_SRV_IP4,
        'ipv6_classless_route': IPV6_CLASSLESS_ROUTE_PREFIX,
    }
)

DNSMASQ_CONF_PATH = '/etc/dnsmasq.d/nmstate.conf'
# Docker does not allow NetworkManager to edit /etc/resolv.conf.
# Have to read NetworkManager internal resolv.conf
RESOLV_CONF_PATH = '/var/run/NetworkManager/resolv.conf'

SYSFS_DISABLE_IPV6_FILE = '/proc/sys/net/ipv6/conf/{}/disable_ipv6'.format(
    DHCP_SRV_NIC
)
SYSFS_DISABLE_RA_SRV = '/proc/sys/net/ipv6/conf/{}/accept_ra'.format(
    DHCP_SRV_NIC
)

# Python 2 does not have FileNotFoundError and treat file not exist as IOError
try:
    FileNotFoundError
except NameError:
    FileNotFoundError = IOError


@pytest.fixture(scope='module')
def dhcp_env():
    try:
        _create_veth_pair()
        _setup_dhcp_nics()

        with open(DNSMASQ_CONF_PATH, 'w') as fd:
            fd.write(DNSMASQ_CONF_STR)
        assert libcmd.exec_cmd(['systemctl', 'restart', 'dnsmasq'])[0] == 0

        yield
    finally:
        _clean_up()


@pytest.fixture
def dhcpcli_up(dhcp_env):
    with ifacelib.iface_up(DHCP_CLI_NIC) as ifstate:
        yield ifstate


@pytest.fixture
def setup_remove_bond99():
    yield
    remove_bond = {
        INTERFACES: [{'name': 'bond99', 'type': 'bond', 'state': 'absent'}]
    }
    libnmstate.apply(remove_bond)


def test_ipv4_dhcp(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.ENABLED] = True
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.DHCP] = True
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.AUTO_ROUTES] = True
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.AUTO_DNS] = True
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.AUTO_GATEWAY] = True

    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)
    time.sleep(5)  # wait to get resolv.conf updated
    assert _has_ipv4_dhcp_nameserver()
    assert _has_ipv4_dhcp_gateway()
    assert _has_ipv4_classless_route()


def test_ipv6_dhcp_only(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.ENABLED] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.DHCP] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTOCONF] = False
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_ROUTES] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_DNS] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_GATEWAY] = True

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    time.sleep(5)  # libnm does not wait on ipv6-ra or DHCPv6.
    current_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_current_state = current_state[INTERFACES][0]
    has_dhcp_ip_addr = False
    for addr in dhcp_cli_current_state['ipv6'][InterfaceIPv6.ADDRESS]:
        if (
            addr[InterfaceIPv6.ADDRESS_PREFIX_LENGTH] == 128
            and DHCP_SRV_IP6_PREFIX in addr[InterfaceIPv6.ADDRESS_IP]
        ):
            has_dhcp_ip_addr = True
            break
    assert has_dhcp_ip_addr
    assert not _has_ipv6_auto_gateway()  # DHCPv6 does not provide routes
    assert not _has_ipv6_auto_extra_route()  # DHCPv6 does not provide routes
    assert _has_ipv6_auto_nameserver()


def test_ipv6_dhcp_and_autoconf(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.ENABLED] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.DHCP] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTOCONF] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_DNS] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_GATEWAY] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_ROUTES] = True

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    time.sleep(5)  # libnm does not wait on ipv6-ra or DHCPv6.
    assert _has_ipv6_auto_gateway()
    assert _has_ipv6_auto_extra_route()
    assert _has_ipv6_auto_nameserver()


def test_dhcp_with_addresses(dhcpcli_up):
    desired_state = {
        INTERFACES: [
            {
                'name': DHCP_CLI_NIC,
                'type': 'ethernet',
                'state': 'up',
                'ipv4': {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.DHCP: True,
                    InterfaceIPv4.ADDRESS: [
                        {
                            InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                        },
                        {
                            InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS2,
                            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                        },
                    ],
                },
                'ipv6': {
                    InterfaceIPv6.ENABLED: True,
                    InterfaceIPv6.DHCP: True,
                    InterfaceIPv6.AUTOCONF: True,
                    InterfaceIPv6.ADDRESS: [
                        {
                            InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                        },
                        {
                            InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS2,
                            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                        },
                    ],
                },
            }
        ]
    }

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_dhcp_for_bond_with_ip_address_and_slave(
    dhcpcli_up, setup_remove_bond99
):
    desired_state = {
        INTERFACES: [
            {
                'name': 'bond99',
                'type': 'bond',
                'state': 'up',
                'ipv4': {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.DHCP: False,
                },
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': [DHCP_CLI_NIC],
                    'options': {'miimon': '140'},
                },
            }
        ]
    }

    libnmstate.apply(desired_state, verify_change=False)
    # Long story for why we doing 'dhcp=False' with 'verify_change=False'
    # above:
    #   For `dhcp=False`:
    #       If there is a change, the master profile (bond99) might get
    #       activated before the slave profile (dhcpcli). In this case, the
    #       master does not have an active slave. Hence, the master will not
    #       have an active link and there will be a IPv4 DHCP timeout failure.
    #       As a workaround the interface is created initially without DHCP.
    #   For `verify_change=False`:
    #       As above, the master bond99 might has no link carrier, hence the
    #       interface will result in `state:down`. As a workaround the
    #       verification is ignored.
    desired_state[INTERFACES][0]['ipv4'][InterfaceIPv4.DHCP] = True
    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_ipv4_dhcp_ignore_gateway(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.ENABLED] = True
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.DHCP] = True
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.AUTO_GATEWAY] = False
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.AUTO_ROUTES] = True
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.AUTO_DNS] = True

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    time.sleep(5)  # wait to get resolv.conf updated
    assert _has_ipv4_dhcp_nameserver()
    assert not _has_ipv4_dhcp_gateway()
    assert _has_ipv4_classless_route()


def test_ipv4_dhcp_ignore_dns(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.ENABLED] = True
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.DHCP] = True
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.AUTO_DNS] = False
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.AUTO_GATEWAY] = True

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    assert not _has_ipv4_dhcp_nameserver()
    assert _has_ipv4_dhcp_gateway()
    assert _has_ipv4_classless_route()


def test_ipv4_dhcp_ignore_routes(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.ENABLED] = True
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.DHCP] = True
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.AUTO_ROUTES] = False
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.AUTO_GATEWAY] = True
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.AUTO_DNS] = True

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    time.sleep(5)  # wait to get resolv.conf updated
    assert _has_ipv4_dhcp_nameserver()
    assert not _has_ipv4_dhcp_gateway()
    assert not _has_ipv4_classless_route()


def test_ipv6_dhcp_and_autoconf_ignore_gateway(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.ENABLED] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.DHCP] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTOCONF] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_DNS] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_GATEWAY] = False
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_ROUTES] = True

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    time.sleep(5)  # libnm does not wait on ipv6-ra or DHCPv6.
    assert not _has_ipv6_auto_gateway()
    assert _has_ipv6_auto_extra_route()
    assert _has_ipv6_auto_nameserver()


def test_ipv6_dhcp_and_autoconf_ignore_dns(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.ENABLED] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.DHCP] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTOCONF] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_DNS] = False
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_GATEWAY] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_ROUTES] = True

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    time.sleep(5)  # libnm does not wait on ipv6-ra or DHCPv6.
    assert _has_ipv6_auto_gateway()
    assert _has_ipv6_auto_extra_route()
    assert not _has_ipv6_auto_nameserver()


def test_ipv6_dhcp_and_autoconf_ignore_routes(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.ENABLED] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.DHCP] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTOCONF] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_DNS] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_GATEWAY] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_ROUTES] = False

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    time.sleep(5)  # libnm does not wait on ipv6-ra or DHCPv6.
    assert not _has_ipv6_auto_gateway()
    assert not _has_ipv6_auto_extra_route()
    assert _has_ipv6_auto_nameserver()


def test_ipv4_dhcp_off_and_option_on(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.DHCP] = False
    # Below options should be silently ignored.
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.AUTO_ROUTES] = False
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.AUTO_DNS] = False
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.AUTO_GATEWAY] = False

    libnmstate.apply(desired_state)

    dhcp_cli_current_state = statelib.show_only((DHCP_CLI_NIC,))[INTERFACES][0]
    assert not dhcp_cli_current_state['ipv4'][InterfaceIPv4.DHCP]
    assert InterfaceIPv4.AUTO_ROUTES not in dhcp_cli_current_state['ipv4']
    assert InterfaceIPv4.AUTO_DNS not in dhcp_cli_current_state['ipv4']
    assert InterfaceIPv4.AUTO_GATEWAY not in dhcp_cli_current_state['ipv4']
    assert not _has_ipv4_dhcp_nameserver()
    assert not _has_ipv4_dhcp_gateway()
    assert not _has_ipv4_classless_route()


def test_ipv6_dhcp_off_and_option_on(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.ENABLED] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.DHCP] = False
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTOCONF] = False
    # Below options should be silently ignored.
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_ROUTES] = False
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_DNS] = False
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_GATEWAY] = False

    libnmstate.apply(desired_state)

    dhcp_cli_current_state = statelib.show_only((DHCP_CLI_NIC,))[INTERFACES][0]
    assert not dhcp_cli_current_state['ipv6'][InterfaceIPv6.DHCP]
    assert InterfaceIPv6.AUTO_ROUTES not in dhcp_cli_current_state['ipv6']
    assert InterfaceIPv6.AUTO_DNS not in dhcp_cli_current_state['ipv6']
    assert InterfaceIPv6.AUTO_GATEWAY not in dhcp_cli_current_state['ipv6']
    assert not _has_ipv6_auto_gateway()
    assert not _has_ipv6_auto_extra_route()
    assert not _has_ipv6_auto_nameserver()


def test_ipv4_dhcp_switch_on_to_off(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.ENABLED] = True
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.DHCP] = True
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.AUTO_GATEWAY] = True
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.AUTO_DNS] = True
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.AUTO_ROUTES] = True

    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)
    time.sleep(5)  # wait to get resolv.conf updated
    assert _has_ipv4_dhcp_nameserver()
    assert _has_ipv4_dhcp_gateway()
    assert _has_ipv4_classless_route()

    # disable dhcp and make sure dns, route, gone.
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.ENABLED] = True
    dhcp_cli_desired_state['ipv4'][InterfaceIPv4.DHCP] = False

    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)
    assert not _has_ipv4_dhcp_nameserver()
    assert not _has_ipv4_dhcp_gateway()
    assert not _has_ipv4_classless_route()


def test_ipv6_dhcp_switch_on_to_off(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.ENABLED] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.DHCP] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTOCONF] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_GATEWAY] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_DNS] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTO_ROUTES] = True

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    time.sleep(5)  # libnm does not wait on ipv6-ra or DHCPv6.
    assert _has_ipv6_auto_gateway()
    assert _has_ipv6_auto_extra_route()
    assert _has_ipv6_auto_nameserver()

    # disable dhcp and make sure dns, route, gone.
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.DHCP] = False
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTOCONF] = False

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    assert not _has_ipv6_auto_gateway()
    assert not _has_ipv6_auto_extra_route()
    assert not _has_ipv6_auto_nameserver()


def _create_veth_pair():
    assert (
        libcmd.exec_cmd(
            [
                'ip',
                'link',
                'add',
                DHCP_SRV_NIC,
                'type',
                'veth',
                'peer',
                'name',
                DHCP_CLI_NIC,
            ]
        )[0]
        == 0
    )


def _remove_veth_pair():
    libcmd.exec_cmd(['ip', 'link', 'del', 'dev', DHCP_SRV_NIC])


def _setup_dhcp_nics():
    assert libcmd.exec_cmd(['ip', 'link', 'set', DHCP_SRV_NIC, 'up'])[0] == 0
    assert libcmd.exec_cmd(['ip', 'link', 'set', DHCP_CLI_NIC, 'up'])[0] == 0
    assert (
        libcmd.exec_cmd(
            [
                'ip',
                'addr',
                'add',
                "{}/24".format(DHCP_SRV_IP4),
                'dev',
                DHCP_SRV_NIC,
            ]
        )[0]
        == 0
    )
    # This stop dhcp server NIC get another IPv6 address from dnsmasq.
    with open(SYSFS_DISABLE_RA_SRV, 'w') as fd:
        fd.write('0')

    with open(SYSFS_DISABLE_IPV6_FILE, 'w') as fd:
        fd.write('0')

    assert (
        libcmd.exec_cmd(
            [
                'ip',
                'addr',
                'add',
                "{}/64".format(DHCP_SRV_IP6),
                'dev',
                DHCP_SRV_NIC,
            ]
        )[0]
        == 0
    )

    assert (
        libcmd.exec_cmd(
            [
                'ip',
                'addr',
                'add',
                "{}/64".format(DHCP_SRV_IP6_2),
                'dev',
                DHCP_SRV_NIC,
            ]
        )[0]
        == 0
    )


def _clean_up():
    libcmd.exec_cmd(['systemctl', 'stop', 'dnsmasq'])
    _remove_veth_pair()
    try:
        os.unlink(DNSMASQ_CONF_PATH)
    except (FileNotFoundError, OSError):
        pass


def test_slave_ipaddr_learned_via_dhcp_added_as_static_to_linux_bridge(
    dhcpcli_up
):
    desired_state = {
        INTERFACES: [
            {
                'name': 'dhcpcli',
                'type': 'ethernet',
                'state': 'up',
                'ipv4': {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.DHCP: True,
                },
            }
        ]
    }

    libnmstate.apply(desired_state)

    current_state = statelib.show_only(('dhcpcli',))
    client_current_state = current_state[INTERFACES][0]
    dhcpcli_ip = client_current_state['ipv4'][InterfaceIPv4.ADDRESS]

    bridge_desired_state = {
        INTERFACES: [
            {
                'name': 'linux-br0',
                'type': 'linux-bridge',
                'state': 'up',
                'ipv4': {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.DHCP: False,
                    InterfaceIPv4.ADDRESS: dhcpcli_ip,
                },
                'bridge': {
                    'options': {},
                    'port': [
                        {
                            'name': 'dhcpcli',
                            'stp-hairpin-mode': False,
                            'stp-path-cost': 100,
                            'stp-priority': 32,
                        }
                    ],
                },
            },
            {
                'name': 'dhcpcli',
                'type': 'ethernet',
                'state': 'up',
                'ipv4': {
                    InterfaceIPv4.ENABLED: False,
                    InterfaceIPv4.DHCP: False,
                },
                'ipv6': {
                    InterfaceIPv6.ENABLED: False,
                    InterfaceIPv6.DHCP: False,
                },
            },
        ]
    }

    libnmstate.apply(bridge_desired_state)
    assertlib.assert_state(bridge_desired_state)


@pytest.mark.xfail(raises=NmstateNotImplementedError)
def test_ipv6_autoconf_only(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.ENABLED] = True
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.DHCP] = False
    dhcp_cli_desired_state['ipv6'][InterfaceIPv6.AUTOCONF] = True

    libnmstate.apply(desired_state)


def _get_nameservers():
    """
    Return a list of name server string configured in RESOLV_CONF_PATH.
    """
    return (
        libnmstate.show()
        .get(Constants.DNS, {})
        .get(DNS.RUNNING, {})
        .get(DNS.SERVER, [])
    )


def _get_running_routes():
    """
    return a list of running routes
    """
    return libnmstate.show().get(Constants.ROUTES, {}).get(RT.RUNNING, [])


def _has_ipv6_auto_gateway():
    routes = _get_running_routes()
    for route in routes:
        if (
            route[RT.DESTINATION] == IPV6_DEFAULT_GATEWAY
            and route[RT.NEXT_HOP_INTERFACE] == DHCP_CLI_NIC
        ):
            return True
    return False


def _has_ipv6_auto_extra_route():
    routes = _get_running_routes()
    for route in routes:
        if (
            route[RT.DESTINATION] == IPV6_CLASSLESS_ROUTE_DST_NET1
            and route[RT.NEXT_HOP_INTERFACE] == DHCP_CLI_NIC
        ):
            return True
    return False


def _has_ipv6_auto_nameserver():
    return DHCP_SRV_IP6 in _get_nameservers()


def _has_ipv4_dhcp_nameserver():
    return DHCP_SRV_IP4 in _get_nameservers()


def _has_ipv4_dhcp_gateway():
    routes = _get_running_routes()
    for route in routes:
        if (
            route[RT.DESTINATION] == IPV4_DEFAULT_GATEWAY
            and route[RT.NEXT_HOP_INTERFACE] == DHCP_CLI_NIC
        ):
            return True
    return False


def _has_ipv4_classless_route():
    routes = _get_running_routes()
    for route in routes:
        if (
            route[RT.DESTINATION] == IPV4_CLASSLESS_ROUTE_DST_NET1
            and route[RT.NEXT_HOP_ADDRESS] == IPV4_CLASSLESS_ROUTE_NEXT_HOP1
            and route[RT.NEXT_HOP_INTERFACE] == DHCP_CLI_NIC
        ):
            return True
    return False
