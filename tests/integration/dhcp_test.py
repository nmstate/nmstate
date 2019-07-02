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
from libnmstate.schema import Route as RT

from libnmstate.error import NmstateNotImplementedError

from .testlib import assertlib
from .testlib import cmd as libcmd
from .testlib import statelib
from .testlib.statelib import INTERFACES


IPV4_ADDRESS1 = '192.0.2.251'
IPV4_ADDRESS2 = '192.0.2.252'
IPV6_ADDRESS1 = '2001:db8:1::1'
IPV6_ADDRESS2 = '2001:db8:2::1'
IPV4_CLASSLESS_ROUTE_DST_NET1 = '198.51.100.0/24'
IPV4_CLASSLESS_ROUTE_NEXT_HOP1 = '192.0.2.1'
IPV6_CLASSLESS_ROUTE_DST_NET1 = '2001:db8:f::/64'

DHCP_SRV_NIC = 'dhcpsrv'
DHCP_CLI_NIC = 'dhcpcli'
DHCP_SRV_IP4 = IPV4_ADDRESS1
DHCP_SRV_IP6 = IPV6_ADDRESS1
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
    }
)

RADVD_CONF_STR = """
interface {}
{{
    AdvSendAdvert on;
    MinRtrAdvInterval 30;
    MaxRtrAdvInterval 100;
    prefix {} {{
        AdvOnLink on;
        AdvAutonomous on;
        AdvRouterAddr off;
    }};
    route {} {{
    }};
}};
""".format(
    DHCP_SRV_NIC, DHCP_SRV_IP6_NETWORK, IPV6_CLASSLESS_ROUTE_DST_NET1
)

RADVD_CONF_PATH = '/etc/radvd.conf'
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

        with open(RADVD_CONF_PATH, 'w') as fd:
            fd.write(RADVD_CONF_STR)
        assert libcmd.exec_cmd(['systemctl', 'restart', 'radvd'])[0] == 0
        yield
    finally:
        _clean_up()


@pytest.fixture
def setup_remove_bond99():
    yield
    remove_bond = {
        INTERFACES: [{'name': 'bond99', 'type': 'bond', 'state': 'absent'}]
    }
    libnmstate.apply(remove_bond)


@pytest.fixture
def setup_remove_dhcpcli():
    yield
    remove_bond = {
        INTERFACES: [
            {'name': 'dhcpcli', 'type': 'ethernet', 'state': 'absent'}
        ]
    }
    libnmstate.apply(remove_bond)


def test_ipv4_dhcp(dhcp_env):
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv4']['enabled'] = True
    dhcp_cli_desired_state['ipv4']['dhcp'] = True
    dhcp_cli_desired_state['ipv4']['auto-routes'] = True
    dhcp_cli_desired_state['ipv4']['auto-dns'] = True
    dhcp_cli_desired_state['ipv4']['auto-gateway'] = True
    dhcp_cli_desired_state['ipv6']['enabled'] = True

    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)
    time.sleep(5)  # wait to get resolv.conf updated
    assert _has_ipv4_dhcp_nameserver()
    assert _has_ipv4_dhcp_gateway()
    assert _has_ipv4_classless_route()


def test_ipv6_dhcp_only(dhcp_env):
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv6']['enabled'] = True
    dhcp_cli_desired_state['ipv6']['dhcp'] = True
    dhcp_cli_desired_state['ipv6']['autoconf'] = False
    dhcp_cli_desired_state['ipv6']['auto-routes'] = True
    dhcp_cli_desired_state['ipv6']['auto-dns'] = True
    dhcp_cli_desired_state['ipv6']['auto-gateway'] = True

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    time.sleep(5)  # libnm does not wait on ipv6-ra or DHCPv6.
    current_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_current_state = current_state[INTERFACES][0]
    has_dhcp_ip_addr = False
    for addr in dhcp_cli_current_state['ipv6']['address']:
        if addr['prefix-length'] == 128 and DHCP_SRV_IP6_PREFIX in addr['ip']:
            has_dhcp_ip_addr = True
            break
    assert has_dhcp_ip_addr
    assert not _has_ipv6_auto_gateway()  # DHCPv6 does not provide routes
    assert not _has_ipv6_auto_extra_route()  # DHCPv6 does not provide routes
    assert _has_ipv6_auto_nameserver()


def test_ipv6_dhcp_and_autoconf(dhcp_env):
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv6']['enabled'] = True
    dhcp_cli_desired_state['ipv6']['dhcp'] = True
    dhcp_cli_desired_state['ipv6']['autoconf'] = True
    dhcp_cli_desired_state['ipv6']['auto-dns'] = True
    dhcp_cli_desired_state['ipv6']['auto-gateway'] = True
    dhcp_cli_desired_state['ipv6']['auto-routes'] = True

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    time.sleep(5)  # libnm does not wait on ipv6-ra or DHCPv6.
    assert _has_ipv6_auto_gateway()
    assert _has_ipv6_auto_extra_route()
    assert _has_ipv6_auto_nameserver()


@pytest.mark.xfail(raises=NmstateNotImplementedError)
def test_ipv6_autoconf_only(dhcp_env):
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['ipv6']['dhcp'] = False
    dhcp_cli_desired_state['ipv6']['autoconf'] = True

    libnmstate.apply(desired_state)


def test_dhcp_with_addresses(dhcp_env):
    desired_state = {
        INTERFACES: [
            {
                'name': DHCP_CLI_NIC,
                'type': 'ethernet',
                'state': 'up',
                'ipv4': {
                    'enabled': True,
                    'dhcp': True,
                    'address': [
                        {'ip': IPV4_ADDRESS1, 'prefix-length': 24},
                        {'ip': IPV4_ADDRESS2, 'prefix-length': 24},
                    ],
                },
                'ipv6': {
                    'enabled': True,
                    'dhcp': True,
                    'autoconf': True,
                    'address': [
                        {'ip': IPV6_ADDRESS1, 'prefix-length': 64},
                        {'ip': IPV6_ADDRESS2, 'prefix-length': 64},
                    ],
                },
            }
        ]
    }

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_dhcp_for_bond_with_ip_address_and_slave(
    dhcp_env, setup_remove_dhcpcli, setup_remove_bond99
):
    desired_state = {
        INTERFACES: [
            {
                'name': 'bond99',
                'type': 'bond',
                'state': 'up',
                'ipv4': {'enabled': True, 'dhcp': False},
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
    desired_state[INTERFACES][0]['ipv4']['dhcp'] = True
    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_ipv4_dhcp_ignore_gateway(dhcp_env):
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv4']['enabled'] = True
    dhcp_cli_desired_state['ipv4']['dhcp'] = True
    dhcp_cli_desired_state['ipv4']['auto-gateway'] = False
    dhcp_cli_desired_state['ipv4']['auto-routes'] = True
    dhcp_cli_desired_state['ipv4']['auto-dns'] = True
    dhcp_cli_desired_state['ipv6']['enabled'] = True

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    time.sleep(5)  # wait to get resolv.conf updated
    assert _has_ipv4_dhcp_nameserver()
    assert not _has_ipv4_dhcp_gateway()
    assert _has_ipv4_classless_route()


def test_ipv4_dhcp_ignore_dns(dhcp_env):
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv4']['enabled'] = True
    dhcp_cli_desired_state['ipv4']['dhcp'] = True
    dhcp_cli_desired_state['ipv4']['auto-dns'] = False
    dhcp_cli_desired_state['ipv4']['auto-gateway'] = True
    dhcp_cli_desired_state['ipv6']['enabled'] = True

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    assert not _has_ipv4_dhcp_nameserver()
    assert _has_ipv4_dhcp_gateway()
    assert _has_ipv4_classless_route()


def test_ipv4_dhcp_ignore_routes(dhcp_env):
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv4']['enabled'] = True
    dhcp_cli_desired_state['ipv4']['dhcp'] = True
    dhcp_cli_desired_state['ipv4']['auto-routes'] = False
    dhcp_cli_desired_state['ipv4']['auto-gateway'] = True
    dhcp_cli_desired_state['ipv4']['auto-dns'] = True
    dhcp_cli_desired_state['ipv6']['enabled'] = True

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    time.sleep(5)  # wait to get resolv.conf updated
    assert _has_ipv4_dhcp_nameserver()
    assert not _has_ipv4_dhcp_gateway()
    assert not _has_ipv4_classless_route()


def test_ipv6_dhcp_and_autoconf_ignore_gateway(dhcp_env):
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv6']['dhcp'] = True
    dhcp_cli_desired_state['ipv6']['autoconf'] = True
    dhcp_cli_desired_state['ipv6']['auto-dns'] = True
    dhcp_cli_desired_state['ipv6']['auto-gateway'] = False
    dhcp_cli_desired_state['ipv6']['auto-routes'] = True

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    time.sleep(5)  # libnm does not wait on ipv6-ra or DHCPv6.
    assert not _has_ipv6_auto_gateway()
    assert _has_ipv6_auto_extra_route()
    assert _has_ipv6_auto_nameserver()


def test_ipv6_dhcp_and_autoconf_ignore_dns(dhcp_env):
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv6']['dhcp'] = True
    dhcp_cli_desired_state['ipv6']['autoconf'] = True
    dhcp_cli_desired_state['ipv6']['auto-dns'] = False
    dhcp_cli_desired_state['ipv6']['auto-gateway'] = True
    dhcp_cli_desired_state['ipv6']['auto-routes'] = True

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    time.sleep(5)  # libnm does not wait on ipv6-ra or DHCPv6.
    assert _has_ipv6_auto_gateway()
    assert _has_ipv6_auto_extra_route()
    assert not _has_ipv6_auto_nameserver()


def test_ipv6_dhcp_and_autoconf_ignore_routes(dhcp_env):
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv6']['dhcp'] = True
    dhcp_cli_desired_state['ipv6']['autoconf'] = True
    dhcp_cli_desired_state['ipv6']['auto-dns'] = True
    dhcp_cli_desired_state['ipv6']['auto-gateway'] = True
    dhcp_cli_desired_state['ipv6']['auto-routes'] = False

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    time.sleep(5)  # libnm does not wait on ipv6-ra or DHCPv6.
    assert not _has_ipv6_auto_gateway()
    assert not _has_ipv6_auto_extra_route()
    assert _has_ipv6_auto_nameserver()


def test_ipv4_dhcp_off_and_option_on(dhcp_env):
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv4']['dhcp'] = False
    # Below options should be silently ignored.
    dhcp_cli_desired_state['ipv4']['auto-routes'] = False
    dhcp_cli_desired_state['ipv4']['auto-dns'] = False
    dhcp_cli_desired_state['ipv4']['auto-gateway'] = False
    dhcp_cli_desired_state['ipv6']['enabled'] = True

    libnmstate.apply(desired_state)

    dhcp_cli_current_state = statelib.show_only((DHCP_CLI_NIC,))[INTERFACES][0]
    assert not dhcp_cli_current_state['ipv4']['dhcp']
    assert 'auto-routes' not in dhcp_cli_current_state['ipv4']
    assert 'auto-dns' not in dhcp_cli_current_state['ipv4']
    assert 'auto-gateway' not in dhcp_cli_current_state['ipv4']
    assert not _has_ipv4_dhcp_nameserver()
    assert not _has_ipv4_dhcp_gateway()
    assert not _has_ipv4_classless_route()


def test_ipv6_dhcp_off_and_option_on(dhcp_env):
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv6']['dhcp'] = False
    dhcp_cli_desired_state['ipv6']['autoconf'] = False
    # Below options should be silently ignored.
    dhcp_cli_desired_state['ipv6']['auto-routes'] = False
    dhcp_cli_desired_state['ipv6']['auto-dns'] = False
    dhcp_cli_desired_state['ipv6']['auto-gateway'] = False

    libnmstate.apply(desired_state)

    dhcp_cli_current_state = statelib.show_only((DHCP_CLI_NIC,))[INTERFACES][0]
    assert not dhcp_cli_current_state['ipv6']['dhcp']
    assert 'auto-routes' not in dhcp_cli_current_state['ipv6']
    assert 'auto-dns' not in dhcp_cli_current_state['ipv6']
    assert 'auto-gateway' not in dhcp_cli_current_state['ipv6']
    assert not _has_ipv6_auto_gateway()
    assert not _has_ipv6_auto_extra_route()
    assert not _has_ipv6_auto_nameserver()


def test_ipv4_dhcp_switch_on_to_off(dhcp_env):
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv4']['enabled'] = True
    dhcp_cli_desired_state['ipv4']['dhcp'] = True
    dhcp_cli_desired_state['ipv4']['auto-gateway'] = True
    dhcp_cli_desired_state['ipv4']['auto-dns'] = True
    dhcp_cli_desired_state['ipv4']['auto-routes'] = True
    dhcp_cli_desired_state['ipv6']['enabled'] = True

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
    dhcp_cli_desired_state['ipv4']['enabled'] = True
    dhcp_cli_desired_state['ipv4']['dhcp'] = False
    dhcp_cli_desired_state['ipv6']['enabled'] = True

    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)
    assert not _has_ipv4_dhcp_nameserver()
    assert not _has_ipv4_dhcp_gateway()
    assert not _has_ipv4_classless_route()


def test_ipv6_dhcp_switch_on_to_off(dhcp_env):
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv6']['dhcp'] = True
    dhcp_cli_desired_state['ipv6']['autoconf'] = True
    dhcp_cli_desired_state['ipv6']['auto-gateway'] = True
    dhcp_cli_desired_state['ipv6']['auto-dns'] = True
    dhcp_cli_desired_state['ipv6']['auto-routes'] = True

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
    dhcp_cli_desired_state['ipv6']['dhcp'] = False
    dhcp_cli_desired_state['ipv6']['autoconf'] = False

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
    with open(SYSFS_DISABLE_RA_SRV, 'w') as fd:
        fd.write('0')

    # This stop dhcp server NIC get another IPv6 address from radvd.
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


def _clean_up():
    libcmd.exec_cmd(['systemctl', 'stop', 'dnsmasq'])
    libcmd.exec_cmd(['systemctl', 'stop', 'radvd'])
    _remove_veth_pair()
    try:
        os.unlink(DNSMASQ_CONF_PATH)
    except (FileNotFoundError, OSError):
        pass
    try:
        os.unlink(RADVD_CONF_PATH)
    except (FileNotFoundError, OSError):
        pass


def test_slave_ipaddr_learned_via_dhcp_added_as_static_to_linux_bridge(
    dhcp_env, setup_remove_dhcpcli
):
    desired_state = {
        INTERFACES: [
            {
                'name': 'dhcpcli',
                'type': 'ethernet',
                'state': 'up',
                'ipv4': {'enabled': True, 'dhcp': True},
            }
        ]
    }

    libnmstate.apply(desired_state)

    current_state = statelib.show_only(('dhcpcli',))
    client_current_state = current_state[INTERFACES][0]
    dhcpcli_ip = client_current_state['ipv4']['address']

    bridge_desired_state = {
        INTERFACES: [
            {
                'name': 'linux-br0',
                'type': 'linux-bridge',
                'state': 'up',
                'ipv4': {
                    'enabled': True,
                    'dhcp': False,
                    'address': dhcpcli_ip,
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
                'ipv4': {'enabled': False, 'dhcp': False},
                'ipv6': {'enabled': False, 'dhcp': False},
            },
        ]
    }

    libnmstate.apply(bridge_desired_state)
    assertlib.assert_state(bridge_desired_state)


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
