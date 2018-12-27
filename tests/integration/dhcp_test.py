#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
import os

import pytest

from libnmstate import netapplier
from libnmstate import nm

from .testlib import assertlib
from .testlib import cmd as libcmd
from .testlib import statelib
from .testlib.statelib import INTERFACES


IPV4_ADDRESS1 = '192.0.2.251'
IPV4_ADDRESS2 = '192.0.2.252'
IPV6_ADDRESS1 = '2001:db8:1::1'
IPV6_ADDRESS2 = '2001:db8:2::1'

DHCP_SRV_NIC = 'dhcpsrv'
DHCP_CLI_NIC = 'dhcpcli'

DNSMASQ_CONF_STR = """
interface={}
dhcp-range=192.0.2.200,192.0.2.250,255.255.255.0,48h
enable-ra
dhcp-range=2001:db8:1::100,2001:db8:1::fff,64,480h
""".format(DHCP_SRV_NIC)

DNSMASQ_CONF_PATH = '/etc/dnsmasq.d/nmstate.conf'

SYSFS_DISABLE_IPV6_FILE = '/proc/sys/net/ipv6/conf/{}/disable_ipv6'.format(
    DHCP_SRV_NIC)

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


def test_ipv4_dhcp(dhcp_env):
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv4']['enabled'] = True
    dhcp_cli_desired_state['ipv4']['dhcp'] = True
    dhcp_cli_desired_state['ipv6']['enabled'] = True

    netapplier.apply(desired_state)
    assertlib.assert_state(desired_state)


def test_ipv6_dhcp_only(dhcp_env):
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv6']['enabled'] = True
    dhcp_cli_desired_state['ipv6']['dhcp'] = True
    dhcp_cli_desired_state['ipv6']['autoconf'] = False

    netapplier.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_ipv6_dhcp_and_autoconf(dhcp_env):
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['state'] = 'up'
    dhcp_cli_desired_state['ipv6']['dhcp'] = True
    dhcp_cli_desired_state['ipv6']['autoconf'] = True

    netapplier.apply(desired_state)

    assertlib.assert_state(desired_state)


@pytest.mark.xfail(raises=nm.ipv6.NoSupportDynamicIPv6OptionError)
def test_ipv6_autoconf_only(dhcp_env):
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[INTERFACES][0]
    dhcp_cli_desired_state['ipv6']['dhcp'] = False
    dhcp_cli_desired_state['ipv6']['autoconf'] = True

    netapplier.apply(desired_state)


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
                        {'ip': IPV4_ADDRESS2, 'prefix-length': 24}
                    ]
                },
                'ipv6': {
                    'enabled': True,
                    'dhcp': True,
                    'autoconf': True,
                    'address': [
                        {'ip': IPV6_ADDRESS1, 'prefix-length': 64},
                        {'ip': IPV6_ADDRESS2, 'prefix-length': 64}
                    ]
                }
            }
        ]
    }

    netapplier.apply(desired_state)

    assertlib.assert_state(desired_state)


def _create_veth_pair():
    assert libcmd.exec_cmd(['ip', 'link', 'add', DHCP_SRV_NIC, 'type', 'veth',
                            'peer', 'name', DHCP_CLI_NIC])[0] == 0


def _remove_veth_pair():
    libcmd.exec_cmd(['ip', 'link', 'del', 'dev', DHCP_SRV_NIC])


def _setup_dhcp_nics():
    assert libcmd.exec_cmd(['ip', 'link', 'set', DHCP_SRV_NIC, 'up'])[0] == 0
    assert libcmd.exec_cmd(['ip', 'link', 'set', DHCP_CLI_NIC, 'up'])[0] == 0
    assert libcmd.exec_cmd(['ip', 'addr', 'add', IPV4_ADDRESS1, 'dev',
                            DHCP_SRV_NIC])[0] == 0
    with open(SYSFS_DISABLE_IPV6_FILE, 'w') as fd:
        fd.write('0')
    assert libcmd.exec_cmd(['ip', 'addr', 'add', IPV6_ADDRESS1, 'dev',
                            DHCP_SRV_NIC])[0] == 0


def _clean_up():
    libcmd.exec_cmd(['systemctl', 'stop', 'dnsmasq'])
    _remove_veth_pair()
    try:
        os.unlink(DNSMASQ_CONF_PATH)
    except FileNotFoundError:
        pass
