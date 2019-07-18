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

import errno

from . import error


class ChangeIpv6StateError(error.NmstateError):
    pass


def enable_ipv6(dev):
    _change_ipv6_state(dev, disable=False)


def disable_ipv6(dev):
    _change_ipv6_state(dev, disable=True)


def _change_ipv6_state(dev, disable):
    try:
        with open('/proc/sys/net/ipv6/conf/%s/disable_ipv6' % dev, 'w') as f:
            f.write('1' if disable else '0')
    except IOError as e:
        if e.errno == errno.ENOENT and disable:
            # IPv6 stack is (already) not available on this device
            return
        raise ChangeIpv6StateError(str(e))


def is_disabled_ipv6(dev='default'):
    try:
        with open('/proc/sys/net/ipv6/conf/%s/disable_ipv6' % dev) as f:
            return int(f.read())
    except IOError as e:
        if e.errno == errno.ENOENT:
            return 1
        else:
            raise error.NmstateError(str(e))
