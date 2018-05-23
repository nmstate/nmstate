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

from libnmstate import netapplier
from libnmstate import netinfo


def main():
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers()
    setup_subcommand_show(subparsers)
    setup_subcommand_set(subparsers)

    args = parser.parse_args()
    args.func(args)


def setup_subcommand_show(subparsers):
    parser_show = subparsers.add_parser('show', help='Show network state')
    parser_show.set_defaults(func=show)


def setup_subcommand_set(subparsers):
    parser_set = subparsers.add_parser('set', help='Set network state')
    parser_set.add_argument('-f', '--file',
                            help='File containing desired state')
    parser_set.set_defaults(func=apply)


def show(args):
    print(json.dumps(netinfo.show(), indent=4, sort_keys=True,
                     separators=(',', ': ')))


def apply(args):
    with open(args.file) as f:
        state = json.load(f)
        netapplier.apply(state)
    print('Desired state applied: ', state)
