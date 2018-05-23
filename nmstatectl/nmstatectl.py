#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#
from __future__ import absolute_import

import argparse
import json

from libnmstate import netinfo


def main():
    parser = argparse.ArgumentParser()

    setup_subcommand_show(parser)

    args = parser.parse_args()
    args.func()


def setup_subcommand_show(parser):
    subparsers = parser.add_subparsers(help='Show network state')
    parser_show = subparsers.add_parser('show')
    parser_show.set_defaults(func=show)


def show():
    print(json.dumps(netinfo.show(), indent=4, sort_keys=True,
                     separators=(',', ': ')))
