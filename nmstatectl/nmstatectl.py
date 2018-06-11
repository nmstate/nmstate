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

import argparse
import fnmatch
import json
import logging
import os
import sys

import yaml

from libnmstate import netapplier
from libnmstate import netinfo


def main():
    logging.basicConfig(
        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
        level=logging.DEBUG)

    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers()
    setup_subcommand_show(subparsers)
    setup_subcommand_set(subparsers)

    args = parser.parse_args()
    return args.func(args)


def setup_subcommand_show(subparsers):
    parser_show = subparsers.add_parser('show', help='Show network state')
    parser_show.set_defaults(func=show)
    parser_show.add_argument('--yaml', help='Output as yaml', default=False,
                             action='store_true')
    parser_show.add_argument(
        '--only', default='*',
        help='Show only specified interfaces (comma-separated)'
    )


def setup_subcommand_set(subparsers):
    parser_set = subparsers.add_parser('set', help='Set network state')
    parser_set.add_argument('file', help='File containing desired state. '
                            'stdin is used when no file is specified.',
                            nargs='?')
    parser_set.set_defaults(func=apply)


def print_state(state, use_yaml=False):
    if use_yaml:
        print(yaml.dump(state, default_flow_style=False))
    else:
        print(json.dumps(state, indent=4, sort_keys=True,
                         separators=(',', ': ')))


def _filter_interfaces(state, patterns):
    """
    return the states for all interfaces from `state` that match at least one
    of the provided patterns.
    """
    showinterfaces = []

    for interface in state['interfaces']:
        for pattern in patterns:
            if fnmatch.fnmatch(interface['name'], pattern):
                showinterfaces.append(interface)
                break
    return showinterfaces


def show(args):
    state = netinfo.show()
    if args.only != '*':
        patterns = [p for p in args.only.split(',')]
        state['interfaces'] = _filter_interfaces(state, patterns)

    print_state(state, use_yaml=args.yaml)


def apply(args):
    # read from file when it is not '-' unless '-' actually exists
    if args.file and (args.file != '-' or os.path.isfile(args.file)):
        with open(args.file) as statefile:
            statedata = statefile.read()
    elif not sys.stdin.isatty() or args.file == '-':
        statedata = sys.stdin.read()
    else:
        sys.stderr.write('ERROR: No state specified\n')
        return 1

    use_yaml = False
    # JSON dictionaries start with a curly brace
    if statedata[0] == '{':
        state = json.loads(statedata)
    else:
        state = yaml.load(statedata)
        use_yaml = True
    netapplier.apply(state)
    print('Desired state applied: ')
    print_state(state, use_yaml=use_yaml)
