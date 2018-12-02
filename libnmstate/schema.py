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
from __future__ import absolute_import

import pkgutil
import yaml


def load(schema_name):
    return yaml.load(
        pkgutil.get_data('libnmstate', 'schemas/' + schema_name + '.yaml'))


ifaces_schema = load('operational-state')


class Constants(object):
    INTERFACES = 'interfaces'

    BOND = 'bond'
    LINUX_BRIDGE = 'linux-bridge'
    OVS_BRIDGE = 'ovs-bridge'
    OVS_PORT = 'ovs-port'
    VLAN = 'vlan'

    VIRT_IFACE_TYPES = (
        BOND,
        LINUX_BRIDGE,
        OVS_BRIDGE,
        OVS_PORT,
        VLAN
    )


class LinuxBridge(object):
    TYPE = 'linux-bridge'
    CONFIG_SUBTREE = 'bridge'

    MAC_AGEING_TIME = 'mac-ageing-time'
    GROUP_FORWARD_MASK = 'group-forward-mask'
    MULTICAST_SNOOPING = 'multicast-snooping'

    STP_SUBTREE = 'stp'
    STP_ENABLED = 'enabled'
    STP_PRIORITY = 'priority'
    STP_FORWARD_DELAY = 'forward-delay'
    STP_HELLO_TIME = 'hello-time'
    STP_MAX_AGE = 'max-age'

    PORT_SUBTREE = 'port'
    PORT_NAME = 'name'
    PORT_STP_PRIORITY = 'stp-priority'
    PORT_STP_HAIRPIN_MODE = 'stp-hairpin-mode'
    PORT_STP_PATH_COST = 'stp-path-cost'
