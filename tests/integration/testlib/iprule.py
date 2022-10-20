#
# Copyright (c) 2019-2020 Red Hat, Inc.
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
from . import cmdlib


def ip_rule_exist_in_os(ip_from, ip_to, priority, table, fwmark, fwmask):
    expected_rule = locals()
    logging.debug("Checking ip rule for {}".format(expected_rule))
    cmds = ["ip"]
    if (ip_from and iplib.is_ipv6_address(ip_from)) or (
        ip_to and iplib.is_ipv6_address(ip_to)
    ):
        cmds.append("-6")
    if ip_from and "/" not in ip_from:
        ip_from = iplib.to_ip_address_full(ip_from)
    if ip_to and "/" not in ip_to:
        ip_to = iplib.to_ip_address_full(ip_to)
    result = cmdlib.exec_cmd(cmds + ["--json", "rule"])
    logging.debug(f"Current ip rules in OS: {result[1]}")
    assert result[0] == 0
    current_rules = json.loads(result[1])
    found = True
    for rule in current_rules:
        if rule.get("src") == "all" or rule.get("dst") == "all":
            continue

        if rule.get("table") == "main":
            rule["table"] = f"{iplib.KERNEL_MAIN_ROUTE_TABLE_ID}"

        logging.debug(f"Checking ip rule is OS: {rule}")
        found = True
        if ip_from and ip_from != iplib.to_ip_address_full(
            rule["src"], rule.get("srclen")
        ):
            found = False
            continue
        if ip_to and ip_to != iplib.to_ip_address_full(
            rule["dst"], rule.get("dstlen")
        ):
            found = False
            continue
        if priority is not None and rule["priority"] != priority:
            found = False
            continue
        if table is not None and rule["table"] != f"{table}":
            found = False
            continue
        if fwmark is not None and rule["fwmark"] != hex(fwmark):
            found = False
            continue
        if fwmask is not None and rule["fwmask"] != hex(fwmask):
            found = False
            continue
        if found:
            break
    if not found:
        logging.debug(f"Failed to find expected ip rule: {expected_rule}")
    assert found
