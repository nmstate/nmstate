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

import errno


def enable_ipv6(dev):
    set_disable_ipv6(dev, value='0')


def disable_ipv6(dev):
    set_disable_ipv6(dev, value='1')


def set_disable_ipv6(dev, value):
    try:
        disable_ipv6_path = '/proc/sys/net/ipv6/conf/' + dev + '/disable_ipv6'
        with open(disable_ipv6_path, 'w') as f:
            f.write(value)
    except IOError as e:
        if e.errno == errno.ENOENT and int(value):
            # IPv6 stack is (already) not available on this device
            return
        raise


def is_ipv6_disabled(dev='default'):
    try:
        with open('/proc/sys/net/ipv6/conf/' + dev + '/disable_ipv6') as f:
            return bool(int(f.read()))
    except IOError as e:
        if e.errno == errno.ENOENT:
            return True
        else:
            raise
