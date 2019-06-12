#
# Copyright 2019 Red Hat, Inc.
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

import pytest

from libnmstate.schema import DNS
import libnmstate.nm.connection as nm_connection
import libnmstate.nm.dns as nm_dns
import libnmstate.nm.ipv4 as nm_ipv4
import libnmstate.nm.ipv6 as nm_ipv6


def _get_test_dns_v4():
    return {
        nm_dns.DNS_METADATA_PRIORITY: 40,
        DNS.SERVER: ['8.8.8.8', '1.1.1.1'],
        DNS.SEARCH: ['example.org', 'example.com']
    }


def _get_test_dns_v6():
    return {
        nm_dns.DNS_METADATA_PRIORITY: 40,
        DNS.SERVER: ['2001:4860:4860::8888', '2606:4700:4700::1111'],
        DNS.SEARCH: ['example.net', 'example.edu']
    }


parametrize_ip_ver = pytest.mark.parametrize(
    'nm_ip',
    [(nm_ipv4), (nm_ipv6)],
    ids=['ipv4', 'ipv6'])


parametrize_ip_ver_dns = pytest.mark.parametrize(
    'nm_ip, get_test_dns_func',
    [(nm_ipv4, _get_test_dns_v4),
     (nm_ipv6, _get_test_dns_v6)],
    ids=['ipv4', 'ipv6'])


@parametrize_ip_ver
def test_add_dns_empty(nm_ip):
    dns_conf = {}
    setting_ip = nm_ip.create_setting({
        'enabled': True,
        nm_dns.DNS_METADATA: dns_conf
    }, base_con_profile=None)

    _assert_dns(setting_ip, dns_conf)


@parametrize_ip_ver_dns
def test_add_dns(nm_ip, get_test_dns_func):
    dns_conf = get_test_dns_func()
    setting_ip = nm_ip.create_setting({
        'enabled': True,
        nm_dns.DNS_METADATA: dns_conf
    }, base_con_profile=None)

    _assert_dns(setting_ip, dns_conf)


@parametrize_ip_ver_dns
def test_add_dns_duplicate_server(nm_ip, get_test_dns_func):
    dns_conf = get_test_dns_func()
    dns_conf[DNS.SERVER] = [dns_conf[DNS.SERVER][0], dns_conf[DNS.SERVER][0]]
    setting_ip = nm_ip.create_setting({
        'enabled': True,
        nm_dns.DNS_METADATA: dns_conf
    }, base_con_profile=None)

    dns_conf[DNS.SERVER] = [dns_conf[DNS.SERVER][0]]
    _assert_dns(setting_ip, dns_conf)


@parametrize_ip_ver_dns
def test_add_dns_duplicate_search(nm_ip, get_test_dns_func):
    dns_conf = get_test_dns_func()
    dns_conf[DNS.SEARCH] = [dns_conf[DNS.SEARCH][0], dns_conf[DNS.SEARCH][0]]
    setting_ip = nm_ip.create_setting({
        'enabled': True,
        nm_dns.DNS_METADATA: dns_conf
    }, base_con_profile=None)

    dns_conf[DNS.SEARCH] = [dns_conf[DNS.SEARCH][0]]
    _assert_dns(setting_ip, dns_conf)


@parametrize_ip_ver_dns
def test_clear_dns(nm_ip, get_test_dns_func):
    dns_conf = get_test_dns_func()
    setting_ip = nm_ip.create_setting({
        'enabled': True,
        nm_dns.DNS_METADATA: dns_conf
    }, base_con_profile=None)
    con_profile = nm_connection.ConnectionProfile()
    con_profile.create([setting_ip])
    new_setting_ip = nm_ip.create_setting({
        'enabled': True,
        nm_dns.DNS_METADATA: {}
    }, base_con_profile=con_profile.profile)

    _assert_dns(new_setting_ip, {})


def _assert_dns(setting_ip, dns_conf):
    assert setting_ip.props.dns == dns_conf.get(DNS.SERVER, [])
    assert setting_ip.props.dns_search == dns_conf.get(DNS.SEARCH, [])
    priority = dns_conf.get(nm_dns.DNS_METADATA_PRIORITY,
                            nm_dns.DEFAULT_DNS_PRIORITY)
    assert setting_ip.props.dns_priority == priority
