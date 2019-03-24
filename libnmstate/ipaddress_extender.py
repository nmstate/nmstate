#
# Copyright 2007 Google Inc.
#  Licensed to PSF under a Contributor Agreement.
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

import ipaddress


class IPv4Network(ipaddress.IPv4Network):

    def subnet_of(self, other):
        """Return True if this network is a subnet of other."""
        return self._is_subnet_of(self, other)

    @staticmethod
    def _is_subnet_of(a, b):
        try:
            # Always false if one is v4 and the other is v6.
            if a._version != b._version:
                raise TypeError(
                    '{} and {} are not of the same version'.format(a, b))
            return (b.network_address <= a.network_address and
                    b.broadcast_address >= a.broadcast_address)
        except AttributeError:
            raise TypeError('Unable to test subnet containment '
                            'between {} and {}'.format(a, b))
