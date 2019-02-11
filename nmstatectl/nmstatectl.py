#
# Copyright 2018-2019 Red Hat, Inc.
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
import errno
import fnmatch
import json
import logging
import os
import subprocess
import sys
import tempfile

from six.moves import input
import yaml

from libnmstate import netapplier
from libnmstate import netinfo
from libnmstate.prettystate import PrettyState
from libnmstate.schema import Constants


def main():
    logging.basicConfig(
        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
        level=logging.DEBUG)

    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers()
    setup_subcommand_edit(subparsers)
    setup_subcommand_show(subparsers)
    setup_subcommand_set(subparsers)

    if len(sys.argv) == 1:
        parser.print_usage()
        return errno.EINVAL
    args = parser.parse_args()
    return args.func(args)


def setup_subcommand_edit(subparsers):
    parser_edit = subparsers.add_parser('edit',
                                        help='Edit network state in EDITOR')
    parser_edit.set_defaults(func=edit)
    parser_edit.add_argument('--json', help='Edit as JSON', default=True,
                             action='store_false', dest='yaml')
    parser_edit.add_argument(
        'only', default='*', nargs='?', metavar=Constants.INTERFACES,
        help='Edit only specified interfaces (comma-separated)'
    )
    parser_edit.add_argument(
        '--no-verify', action='store_false', dest='verify', default=True,
        help='Do not verify that the state was completely set and disable '
        'rollback to previous state.'
    )


def setup_subcommand_show(subparsers):
    parser_show = subparsers.add_parser('show', help='Show network state')
    parser_show.set_defaults(func=show)
    parser_show.add_argument('--json', help='Edit as JSON', default=True,
                             action='store_false', dest='yaml')
    parser_show.add_argument(
        'only', default='*', nargs='?', metavar=Constants.INTERFACES,
        help='Show only specified interfaces (comma-separated)'
    )


def setup_subcommand_set(subparsers):
    parser_set = subparsers.add_parser('set', help='Set network state')
    parser_set.add_argument('file', help='File containing desired state. '
                            'stdin is used when no file is specified.',
                            nargs='*')
    parser_set.add_argument(
        '--no-verify', action='store_false', dest='verify', default=True,
        help='Do not verify that the state was completely set and disable '
        'rollback to previous state.'
    )
    parser_set.set_defaults(func=apply)


def edit(args):
    state = _filter_state(netinfo.show(), args.only)

    if not state[Constants.INTERFACES]:
        sys.stderr.write('ERROR: No such interface\n')
        return os.EX_USAGE

    pretty_state = PrettyState(state)

    if args.yaml:
        suffix = '.yaml'
        txtstate = pretty_state.yaml
    else:
        suffix = '.json'
        txtstate = pretty_state.json

    new_state = _get_edited_state(txtstate, suffix, args.yaml)
    if not new_state:
        return os.EX_DATAERR

    print('Applying the following state: ')
    print_state(new_state, use_yaml=args.yaml)

    netapplier.apply(new_state, verify_change=args.verify)


def show(args):
    state = _filter_state(netinfo.show(), args.only)
    print_state(state, use_yaml=args.yaml)


def apply(args):
    if args.file:
        for statefile in args.file:
            if statefile == '-' and not os.path.isfile(statefile):
                statedata = sys.stdin.read()
            else:
                with open(statefile) as statefile:
                    statedata = statefile.read()

            apply_state(statedata, args.verify)
    elif not sys.stdin.isatty():
        statedata = sys.stdin.read()
        apply_state(statedata, args.verify)
    else:
        sys.stderr.write('ERROR: No state specified\n')
        return 1


def apply_state(statedata, verify_change):
    use_yaml = False
    # JSON dictionaries start with a curly brace
    if statedata[0] == '{':
        state = json.loads(statedata)
    else:
        state = yaml.load(statedata)
        use_yaml = True
    netapplier.apply(state, verify_change)
    print('Desired state applied: ')
    print_state(state, use_yaml=use_yaml)


def _filter_state(state, whitelist):
    if whitelist != '*':
        patterns = [p for p in whitelist.split(',')]
        state[Constants.INTERFACES] = _filter_interfaces(state, patterns)
    return state


def _filter_interfaces(state, patterns):
    """
    return the states for all interfaces from `state` that match at least one
    of the provided patterns.
    """
    showinterfaces = []

    for interface in state[Constants.INTERFACES]:
        for pattern in patterns:
            if fnmatch.fnmatch(interface['name'], pattern):
                showinterfaces.append(interface)
                break
    return showinterfaces


def _get_edited_state(txtstate, suffix, use_yaml):
    while True:
        txtstate = _run_editor(txtstate, suffix)

        if txtstate is None:
            return None

        new_state, error = _parse_state(txtstate, use_yaml)

        if error:
            if not _try_edit_again(error):
                return None
        else:
            return new_state


def _run_editor(txtstate, suffix):
    editor = os.environ.get('EDITOR', 'vi')
    with tempfile.NamedTemporaryFile(suffix=suffix,
                                     prefix='nmstate-') as statefile:
        statefile.write(txtstate.encode('utf-8'))
        statefile.flush()

        try:
            subprocess.check_call([editor, statefile.name])
            statefile.seek(0)
            return statefile.read()

        except subprocess.CalledProcessError:
            sys.stderr.write('Error running editor, aborting...\n')
            return None


def _parse_state(txtstate, parse_yaml):
    error = ''
    state = {}
    if parse_yaml:
        try:
            state = yaml.load(txtstate)
        except yaml.parser.ParserError as e:
            error = 'Invalid YAML syntax: %s\n' % e
        except yaml.parser.ScannerError as e:
            error = 'Invalid YAML syntax: %s\n' % e
    else:
        try:
            state = json.loads(txtstate)
        except ValueError as e:
            error = 'Invalid JSON syntax: %s\n' % e

    if not error and Constants.INTERFACES not in state:
        error = 'Invalid state: should contain "interfaces" entry.\n'

    return state, error


def _try_edit_again(error):
    """
    Print error and ask for user feedback. Return True, if the state should be
    edited again and False otherwise.
    """

    sys.stderr.write('ERROR: ' + error)
    response = ''
    while response not in ('y', 'n'):
        response = input('Try again? [y,n]:\n'
                         'y - yes, start editor again\n'
                         'n - no, throw away my changes\n'
                         '> ').lower()
        if response == 'n':
            return False
    return True


def print_state(state, use_yaml=False):
    state = PrettyState(state)
    if use_yaml:
        sys.stdout.write(state.yaml)
    else:
        print(state.json)
