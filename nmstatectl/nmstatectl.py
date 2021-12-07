#
# Copyright (c) 2018-2021 Red Hat, Inc.
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
import argparse
import errno
import fnmatch
import json
import logging
import os
import subprocess
import sys
import tempfile
import warnings

import yaml

import libnmstate
from libnmstate import PrettyState
from libnmstate.error import NmstateConflictError
from libnmstate.error import NmstatePermissionError
from libnmstate.error import NmstateValueError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import Route
from libnmstate.schema import RouteRule
from libnmstate.state import hide_the_secrets


def main():
    logging.basicConfig(
        format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
        level=logging.DEBUG,
    )

    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers()
    _setup_subcommand_commit(subparsers)
    _setup_subcommand_edit(subparsers)
    _setup_subcommand_rollback(subparsers)
    _setup_subcommand_set(subparsers)
    _setup_subcommand_apply(subparsers)
    _setup_subcommand_show(subparsers)
    _setup_subcommand_version(subparsers)
    _setup_subcommand_gen_config(subparsers)
    parser.add_argument(
        "--version", action="store_true", help="Display nmstate version"
    )

    if len(sys.argv) == 1:
        parser.print_usage()
        return errno.EINVAL
    args = parser.parse_args()
    if args.version:
        print(libnmstate.__version__)
    else:
        return args.func(args)


def _setup_subcommand_commit(subparsers):
    parser_commit = subparsers.add_parser("commit", help="Commit a change")
    parser_commit.add_argument(
        "checkpoint", nargs="?", default=None, help="checkpoint to commit"
    )
    parser_commit.set_defaults(func=commit)


def _setup_subcommand_edit(subparsers):
    parser_edit = subparsers.add_parser(
        "edit", help="Edit network state in EDITOR"
    )
    parser_edit.set_defaults(func=edit)
    parser_edit.add_argument(
        "--json",
        help="Edit as JSON",
        default=True,
        action="store_false",
        dest="yaml",
    )
    parser_edit.add_argument(
        "only",
        default="*",
        nargs="?",
        metavar=Interface.KEY,
        help="Edit only specified interfaces (comma-separated)",
    )
    parser_edit.add_argument(
        "--no-verify",
        action="store_false",
        dest="verify",
        default=True,
        help="Do not verify that the state was completely set and disable "
        "rollback to previous state.",
    )
    parser_edit.add_argument(
        "--memory-only",
        action="store_false",
        dest="save_to_disk",
        default=True,
        help="Do not make the state persistent.",
    )


def _setup_subcommand_rollback(subparsers):
    parser_rollback = subparsers.add_parser(
        "rollback", help="Rollback a change"
    )
    parser_rollback.add_argument(
        "checkpoint", nargs="?", default=None, help="checkpoint to roll back"
    )
    parser_rollback.set_defaults(func=rollback)


def _setup_subcommand_apply(subparsers):
    parser_set = subparsers.add_parser("apply", help="Apply network state")
    parser_set.add_argument(
        "file",
        help="File containing desired state. "
        "stdin is used when no file is specified.",
        nargs="*",
    )
    parser_set.add_argument(
        "--no-verify",
        action="store_false",
        dest="verify",
        default=True,
        help="Do not verify that the state was completely set and disable "
        "rollback to previous state",
    )
    parser_set.add_argument(
        "--no-commit",
        action="store_false",
        dest="commit",
        default=True,
        help="Do not commit new state after verification",
    )
    parser_set.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout in seconds before reverting uncommited changes.",
    )
    parser_set.add_argument(
        "--memory-only",
        action="store_false",
        dest="save_to_disk",
        default=True,
        help="Do not make the state persistent.",
    )
    parser_set.set_defaults(func=apply)


def _setup_subcommand_set(subparsers):
    parser_set = subparsers.add_parser(
        "set",
        help=(
            "Set network state, deprecated please consider using"
            "'apply' instead."
        ),
    )
    parser_set.add_argument(
        "file",
        help="File containing desired state. "
        "stdin is used when no file is specified.",
        nargs="*",
    )
    parser_set.add_argument(
        "--no-verify",
        action="store_false",
        dest="verify",
        default=True,
        help="Do not verify that the state was completely set and disable "
        "rollback to previous state",
    )
    parser_set.add_argument(
        "--no-commit",
        action="store_false",
        dest="commit",
        default=True,
        help="Do not commit new state after verification",
    )
    parser_set.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout in seconds before reverting uncommited changes.",
    )
    parser_set.add_argument(
        "--memory-only",
        action="store_false",
        dest="save_to_disk",
        default=True,
        help="Do not make the state persistent.",
    )
    parser_set.set_defaults(func=set)


def _setup_subcommand_show(subparsers):
    parser_show = subparsers.add_parser("show", help="Show network state")
    parser_show.set_defaults(func=show)
    parser_show.add_argument(
        "--json",
        help="Edit as JSON",
        default=True,
        action="store_false",
        dest="yaml",
    )
    parser_show.add_argument(
        "-r",
        "--running-config",
        help="Show running configurations",
        default=False,
        action="store_true",
        dest="running_config",
    )
    parser_show.add_argument(
        "-s",
        "--show-secrets",
        help="Show secrets also",
        default=False,
        action="store_true",
        dest="include_secrets",
    )
    parser_show.add_argument(
        "only",
        default="*",
        nargs="?",
        metavar=Interface.KEY,
        help="Show only specified interfaces (comma-separated)",
    )


def _setup_subcommand_version(subparsers):
    parser_version = subparsers.add_parser(
        "version", help="Display nmstate version"
    )
    parser_version.set_defaults(func=version)


def _setup_subcommand_gen_config(subparsers):
    parser_gc = subparsers.add_parser("gc", help="Generate configurations")
    parser_gc.add_argument(
        "file",
        help="File containing desired state. ",
        nargs="*",
    )
    parser_gc.set_defaults(func=_run_gen_config)


def version(args):
    print(libnmstate.__version__)


def commit(args):
    try:
        libnmstate.commit(checkpoint=args.checkpoint)
    except NmstateValueError as e:
        print("ERROR committing change: {}\n".format(str(e)))
        return os.EX_DATAERR


def edit(args):
    state = _filter_state(libnmstate.show(), args.only)

    if not state[Interface.KEY]:
        sys.stderr.write("ERROR: No such interface\n")
        return os.EX_USAGE

    pretty_state = PrettyState(state)

    if args.yaml:
        suffix = ".yaml"
        txtstate = pretty_state.yaml
    else:
        suffix = ".json"
        txtstate = pretty_state.json

    new_state = _get_edited_state(txtstate, suffix, args.yaml)
    if not new_state:
        return os.EX_DATAERR

    print("Applying the following state: ")
    _print_state(new_state, use_yaml=args.yaml)

    libnmstate.apply(
        new_state, verify_change=args.verify, save_to_disk=args.save_to_disk
    )


def rollback(args):
    try:
        libnmstate.rollback(checkpoint=args.checkpoint)
    except NmstateValueError as e:
        print("ERROR rolling back change: {}\n".format(str(e)))
        return os.EX_DATAERR


def show(args):
    if args.running_config:
        full_state = libnmstate.show_running_config(
            include_secrets=args.include_secrets
        )
    else:
        full_state = libnmstate.show(include_secrets=args.include_secrets)
    state = _filter_state(full_state, args.only)
    _print_state(state, use_yaml=args.yaml)


def set(args):
    warnings.warn("Using 'set' is deprecated, use 'apply' instead.")
    return apply(args)


def apply(args):
    if args.file:
        for statefile in args.file:
            if statefile == "-" and not os.path.isfile(statefile):
                statedata = sys.stdin.read()
            else:
                with open(statefile) as statefile:
                    statedata = statefile.read()

            ret = _apply_state(
                statedata,
                args.verify,
                args.commit,
                args.timeout,
                args.save_to_disk,
            )
            if ret:
                return ret
    elif not sys.stdin.isatty():
        statedata = sys.stdin.read()
        return _apply_state(
            statedata,
            args.verify,
            args.commit,
            args.timeout,
            args.save_to_disk,
        )
    else:
        sys.stderr.write("ERROR: No state specified\n")
        return 1


def _run_gen_config(args):
    if args.file:
        for statefile in args.file:
            if statefile == "-" and not os.path.isfile(statefile):
                statedata = sys.stdin.read()
            else:
                with open(statefile) as statefile:
                    statedata = statefile.read()

            # JSON dictionaries start with a curly brace
            if statedata[0] == "{":
                state = json.loads(statedata)
                use_yaml = False
            else:
                state = yaml.load(statedata, Loader=yaml.SafeLoader)
                use_yaml = True
            _print_state(
                libnmstate.generate_configurations(state), use_yaml=use_yaml
            )
    else:
        sys.stderr.write("ERROR: No state specified\n")
        return 1


def _apply_state(statedata, verify_change, commit, timeout, save_to_disk):
    use_yaml = False
    # JSON dictionaries start with a curly brace
    if statedata[0] == "{":
        state = json.loads(statedata)
    else:
        state = yaml.load(statedata, Loader=yaml.SafeLoader)
        use_yaml = True

    try:
        checkpoint = libnmstate.apply(
            state,
            verify_change=verify_change,
            commit=commit,
            rollback_timeout=timeout,
            save_to_disk=save_to_disk,
        )
    except NmstatePermissionError as e:
        sys.stderr.write("ERROR: Missing permissions:{}\n".format(str(e)))
        return os.EX_NOPERM
    except NmstateConflictError:
        sys.stderr.write(
            "ERROR: State editing already in progress.\n"
            "Commit, roll back or wait before retrying.\n"
        )
        return os.EX_UNAVAILABLE

    hide_the_secrets(state)
    print("Desired state applied: ")
    _print_state(state, use_yaml=use_yaml)
    if checkpoint:
        print("Checkpoint: {}".format(checkpoint))


def _filter_state(state, allowlist):
    if allowlist != "*":
        patterns = [p for p in allowlist.split(",")]
        state[Interface.KEY] = _filter_interfaces(state, patterns)
        state[Route.KEY] = _filter_routes(state, patterns)
        state[RouteRule.KEY] = _filter_route_rule(state, patterns)
    return state


def _filter_interfaces(state, patterns):
    """
    return the states for all interfaces from `state` that match at least one
    of the provided patterns.
    """
    showinterfaces = []

    for interface in state[Interface.KEY]:
        for pattern in patterns:
            if fnmatch.fnmatch(interface["name"], pattern):
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
    editor = os.environ.get("EDITOR", "vi")
    with tempfile.NamedTemporaryFile(
        suffix=suffix, prefix="nmstate-"
    ) as statefile:
        statefile.write(txtstate.encode("utf-8"))
        statefile.flush()

        try:
            subprocess.check_call([editor, statefile.name])
            statefile.seek(0)
            return statefile.read()

        except subprocess.CalledProcessError:
            sys.stderr.write("Error running editor, exiting...\n")
            return None


def _parse_state(txtstate, parse_yaml):
    error = ""
    state = {}
    if parse_yaml:
        try:
            state = yaml.load(txtstate, Loader=yaml.SafeLoader)
        except yaml.parser.ParserError as e:
            error = "Invalid YAML syntax: %s\n" % e
        except yaml.parser.ScannerError as e:
            error = "Invalid YAML syntax: %s\n" % e
    else:
        try:
            state = json.loads(txtstate)
        except ValueError as e:
            error = "Invalid JSON syntax: %s\n" % e

    if not error and Interface.KEY not in state:
        # Allow editing routes only.
        state[Interface.KEY] = []

    return state, error


def _try_edit_again(error):
    """
    Print error and ask for user feedback. Return True, if the state should be
    edited again and False otherwise.
    """

    sys.stderr.write("ERROR: " + error)
    response = ""
    while response not in ("y", "n"):
        response = input(
            "Try again? [y,n]:\n"
            "y - yes, start editor again\n"
            "n - no, throw away my changes\n"
            "> "
        ).lower()
        if response == "n":
            return False
    return True


def _print_state(state, use_yaml=False):
    state = PrettyState(state)
    if use_yaml:
        sys.stdout.write(state.yaml)
    else:
        print(state.json)


def _filter_routes(state, patterns):
    """
    return the states for all routes from `state` that match at least one
    of the provided patterns.
    """
    routes = {}
    for route_type in state.get(Route.KEY, {}).keys():
        routes[route_type] = []
        for route in state.get(Route.KEY, {}).get(route_type, []):
            for pattern in patterns:
                if fnmatch.fnmatch(route[Route.NEXT_HOP_INTERFACE], pattern):
                    routes[route_type].append(route)
    return routes


def _filter_route_rule(state, patterns):
    route_rules = _filter_route_rule_by_table_id(state)
    _filter_route_rule_by_autorule_table_id(state, patterns, route_rules)
    return route_rules


def _filter_route_rule_by_table_id(state):
    """
    return the rules for state's route rule that match the table_id of the
    filtered route of state by interface
    """
    route_rules = {RouteRule.CONFIG: []}
    table_ids = []
    for routes in {Route.CONFIG: [], Route.RUNNING: []}:
        for route in state.get(Route.KEY, {}).get(routes, []):
            if route.get(Route.TABLE_ID) not in table_ids:
                table_ids.append(route.get(Route.TABLE_ID))
    for rule in state.get(RouteRule.KEY, {}).get(RouteRule.CONFIG, []):
        if rule.get(RouteRule.ROUTE_TABLE) in table_ids:
            route_rules[RouteRule.CONFIG].append(rule)
    return route_rules


def _filter_route_rule_by_autorule_table_id(state, patterns, route_rules):
    """
    return the rules that match the iface's name and AUTO_ROUTE_TABLE_ID
    """
    table_ids = []
    for pattern in patterns:
        for interface in state[Interface.KEY]:
            if fnmatch.fnmatch(interface[Interface.NAME], pattern):
                autotable = interface.get(Interface.IPV4, {}).get(
                    InterfaceIP.AUTO_ROUTE_TABLE_ID
                )
                if autotable:
                    table_ids.append(autotable)
                autotable = interface.get(Interface.IPV6, {}).get(
                    InterfaceIP.AUTO_ROUTE_TABLE_ID
                )
                if autotable:
                    table_ids.append(autotable)
    for rule in state.get(RouteRule.KEY, {}).get(RouteRule.CONFIG, []):
        if (
            rule.get(RouteRule.ROUTE_TABLE) in table_ids
            and rule not in route_rules[RouteRule.CONFIG]
        ):
            route_rules[RouteRule.CONFIG].append(rule)
