#
# Copyright (c) 2019 Red Hat, Inc.
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

import json
import logging

from libnmstate import iplib
from . import cmd as libcmd


def ip_rule_exist_in_os(ip_from, ip_to, priority, table):
    expected_rule = locals()
    logging.debug('Checking ip rule for {}'.format(expected_rule))
    cmds = ['ip']
    if (ip_from and iplib.is_ipv6_address(ip_from)) or (
        ip_to and iplib.is_ipv6_address(ip_to)
    ):
        cmds.append('-6')
    result = libcmd.exec_cmd(cmds + ['--json', 'rule'])
    logging.debug(f'Current ip rules in OS: {result[1]}')
    assert result[0] == 0
    current_rules = json.loads(result[1])
    for rule in current_rules:
        found = False
        if ip_from and not _is_rule_addr_match(
            ip_from, rule.get('src'), rule.get('srclen')
        ):
            continue
        if ip_to and not _is_rule_addr_match(
            ip_to, rule.get('dst'), rule.get('dstlen')
        ):
            continue

        if rule.get('table') == 'main':
            rule['table'] = f'{iplib.KERNEL_MAIN_ROUTE_TABLE_ID}'

        logging.debug(f'Checking ip rule is OS: {rule}')
        if priority is not None and rule['priority'] != priority:
            continue
        if table is not None and rule['table'] != f'{table}':
            continue
        found = True
        break
    if not found:
        logging.debug(f'Failed to find expected ip rule: {expected_rule}')
    assert found


def _is_rule_addr_match(expected_addr, rule_addr, rule_addr_len):
    if rule_addr == 'all' or rule_addr is None:
        rule_addr_full = None
    else:
        rule_addr_full = iplib.to_ip_address_full(rule_addr, rule_addr_len)

    return expected_addr == rule_addr_full
