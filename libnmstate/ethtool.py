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
""" Minimal wrapper around the SIOCETHTOOL IOCTL to provide data that Network
Manager is not yet providing.

https://bugzilla.redhat.com/show_bug.cgi?id=1621188
"""

import array
import struct
import fcntl
import socket

ETHTOOL_GSET = 0x00000001  # Get settings
SIOCETHTOOL = 0x8946


def minimal_ethtool(interface):
    """
    Return dictionary with speed, duplex and auto-negotiation settings for the
    specified interface using the ETHTOOL_GSET command. The speed is returned n
    MBit/s, 0 means that the speed could not be determined. The duplex setting
    is 'unknown', 'full' or 'half. The auto-negotiation setting True or False
    or None if it could not be determined.

    Based on:
    https://github.com/rlisagor/pynetlinux/blob/master/pynetlinux/ifconfig.py
    https://elixir.bootlin.com/linux/v4.19-rc1/source/include/uapi/linux/ethtool.h

    :param interface str: Name of interface
    :returns dict: Dictionary with the keys speed, duplex, auto-negotiation

    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sockfd = sock.fileno()

        ecmd = array.array('B', struct.pack('I39s', ETHTOOL_GSET, b'\x00'*39))

        interface = interface.encode('utf-8')
        ifreq = struct.pack('16sP', interface, ecmd.buffer_info()[0])

        fcntl.ioctl(sockfd, SIOCETHTOOL, ifreq)
        res = ecmd.tostring()
        speed, duplex, auto = struct.unpack('12xHB3xB24x', res)
    except IOError:
        speed, duplex, auto = 65535, 255, 255
    finally:
        sock.close()

    if speed == 65535:
        speed = 0

    if duplex == 255:
        duplex = 'unknown'
    else:
        duplex = 'full' if bool(duplex) else 'half'

    if auto == 255:
        auto = None
    else:
        auto = bool(auto)

    return {"speed": speed, "duplex": duplex, "auto-negotiation": auto}
