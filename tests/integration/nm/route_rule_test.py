#
# Copyright (c) 2020 Red Hat, Inc.
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

import logging

import pytest

import libnmstate
from libnmstate import nm
from libnmstate import iplib
from libnmstate.ifaces import BaseIface
from libnmstate.schema import RouteRule
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6

from ..testlib import iprule
from .testlib import main_context


ETH1 = "eth1"

IPV4_ADDRESS1 = "192.0.2.251"
IPV6_ADDRESS1 = "2001:db8:1::1"


@pytest.fixture(scope="function", autouse=True)
def remove_route_rules_when_cleanup():
    libnmstate.apply({RouteRule.KEY: {RouteRule.CONFIG: []}})


@pytest.fixture(scope="function")
def eth1_up_with_static(eth1_up):
    state = eth1_up
    iface_state = state[Interface.KEY][0]
    iface_state.update(
        {
            Interface.IPV4: {
                InterfaceIPv4.ADDRESS: [
                    {
                        InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                        InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                    }
                ],
                InterfaceIPv4.DHCP: False,
                InterfaceIPv4.ENABLED: True,
            },
            Interface.IPV6: {
                InterfaceIPv6.ADDRESS: [
                    {
                        InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                        InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                    }
                ],
                InterfaceIPv6.DHCP: False,
                InterfaceIPv6.AUTOCONF: False,
                InterfaceIPv6.ENABLED: True,
            },
        }
    )
    libnmstate.apply(state)
    yield state


def test_create_rule_add_full(eth1_up_with_static, nm_plugin):
    rule_v4_0 = _create_route_rule("198.51.100.0/24", "192.0.2.1/32", 50, 103)
    rule_v4_1 = _create_route_rule("198.51.100.0/24", "192.0.2.2/32", 51, 104)
    rule_v6_0 = _create_route_rule(
        "2001:db8:a::/64", "2001:db8:1::a/128", 50, 103
    )
    rule_v6_1 = _create_route_rule(
        "2001:db8:b::/64", "2001:db8:1::a/128", 51, 104
    )

    ipv4_state = eth1_up_with_static[Interface.KEY][0][Interface.IPV4]
    ipv4_state.update({BaseIface.ROUTE_RULES_METADATA: [rule_v4_0, rule_v4_1]})
    ipv6_state = eth1_up_with_static[Interface.KEY][0][Interface.IPV6]
    ipv6_state.update({BaseIface.ROUTE_RULES_METADATA: [rule_v6_0, rule_v6_1]})

    _modify_interface(nm_plugin.context, ipv4_state, ipv6_state)

    expected_rules = [rule_v4_0, rule_v4_1, rule_v6_0, rule_v6_1]
    _assert_route_rules(nm_plugin, expected_rules)
    _check_ip_rules_exist_in_os(expected_rules)


def test_route_rule_without_prioriry(eth1_up_with_static, nm_plugin):
    rule = _create_route_rule("198.51.100.0/24", "192.0.2.1/32", 50, 103)
    del rule[RouteRule.PRIORITY]
    ipv4_state = eth1_up_with_static[Interface.KEY][0][Interface.IPV4]
    ipv4_state.update({BaseIface.ROUTE_RULES_METADATA: [rule]})

    _modify_interface(nm_plugin.context, ipv4_state, {})

    rule[RouteRule.PRIORITY] = nm.route.ROUTE_RULE_DEFAULT_PRIORIRY
    _assert_route_rules(nm_plugin, [rule])
    _check_ip_rules_exist_in_os([rule])


def test_route_rule_without_table(eth1_up_with_static, nm_plugin):
    rule = _create_route_rule("198.51.100.0/24", "192.0.2.1/32", 50, 103)
    del rule[RouteRule.ROUTE_TABLE]
    ipv4_state = eth1_up_with_static[Interface.KEY][0][Interface.IPV4]
    ipv4_state.update({BaseIface.ROUTE_RULES_METADATA: [rule]})

    _modify_interface(nm_plugin.context, ipv4_state, {})

    rule[RouteRule.ROUTE_TABLE] = iplib.KERNEL_MAIN_ROUTE_TABLE_ID
    _assert_route_rules(nm_plugin, [rule])
    _check_ip_rules_exist_in_os([rule])


def test_route_rule_without_from(eth1_up_with_static, nm_plugin):
    rule = _create_route_rule("198.51.100.0/24", "192.0.2.1/32", 50, 103)
    del rule[RouteRule.IP_FROM]
    ipv4_state = eth1_up_with_static[Interface.KEY][0][Interface.IPV4]
    ipv4_state.update({BaseIface.ROUTE_RULES_METADATA: [rule]})

    _modify_interface(nm_plugin.context, ipv4_state, {})

    _assert_route_rules(nm_plugin, [rule])
    _check_ip_rules_exist_in_os([rule])


def test_route_rule_without_to(eth1_up_with_static, nm_plugin):
    rule = _create_route_rule("198.51.100.0/24", "192.0.2.1/32", 50, 103)
    del rule[RouteRule.IP_TO]
    ipv4_state = eth1_up_with_static[Interface.KEY][0][Interface.IPV4]
    ipv4_state.update({BaseIface.ROUTE_RULES_METADATA: [rule]})

    _modify_interface(nm_plugin.context, ipv4_state, {})

    _assert_route_rules(nm_plugin, [rule])
    _check_ip_rules_exist_in_os([rule])


def _create_route_rule(ip_from, ip_to, priority, table):
    return {
        RouteRule.IP_FROM: ip_from,
        RouteRule.IP_TO: ip_to,
        RouteRule.PRIORITY: priority,
        RouteRule.ROUTE_TABLE: table,
    }


def _modify_interface(ctx, ipv4_state, ipv6_state):
    conn = nm.connection.ConnectionProfile(ctx)
    conn.import_by_id(ETH1)
    settings = _create_iface_settings(conn, ipv4_state, ipv6_state)
    new_conn = nm.connection.ConnectionProfile(ctx)

    with main_context(ctx):
        new_conn.create(settings)
        conn.update(new_conn)
        ctx.wait_all_finish()
        nmdev = ctx.get_nm_dev(ETH1)
        nm.device.modify(ctx, nmdev, new_conn.profile)


def _create_iface_settings(con_profile, ipv4_state, ipv6_state):
    con_setting = nm.connection.ConnectionSetting()
    con_setting.import_by_profile(con_profile)

    ipv4_setting = nm.ipv4.create_setting(ipv4_state, None)
    ipv6_setting = nm.ipv6.create_setting(ipv6_state, None)

    return con_setting.setting, ipv4_setting, ipv6_setting


def _check_ip_rules_exist_in_os(rules):
    for rule in rules:
        iprule.ip_rule_exist_in_os(
            rule.get(RouteRule.IP_FROM),
            rule.get(RouteRule.IP_TO),
            rule.get(RouteRule.PRIORITY),
            rule.get(RouteRule.ROUTE_TABLE),
        )


def _assert_route_rules(nm_plugin, expected_rules):
    nm_plugin.refresh_content()
    cur_rules = nm.ipv4.get_routing_rule_config(
        nm_plugin.context.client
    ) + nm.ipv6.get_routing_rule_config(nm_plugin.context.client)
    logging.debug(f"Current route rules reported by NM {cur_rules}")
    for rule in expected_rules:
        assert rule in expected_rules
