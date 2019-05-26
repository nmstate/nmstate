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

from contextlib import contextmanager

import pytest

from .netlink import link
from .netlink import monitor
from .netlink import waitfor


@contextmanager
def monitor_stable_link_state(device, wait_for_linkup=True):
    """Raises an exception if it detects that the device link state changes."""
    if wait_for_linkup:
        with waitfor.waitfor_linkup(device):
            pass
    iface_properties = link.get_link(device)
    original_state = iface_properties['state']
    try:
        with monitor.Monitor(groups=('link',)) as mon:
            yield
    finally:
        state_changes = (e['state'] for e in mon if e['name'] == device)
        for state in state_changes:
            if state != original_state:
                raise pytest.fail(
                    '{} link state changed: {} -> {}'.format(
                        device, original_state, state))
