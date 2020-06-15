#
# Copyright (c) 2020 Red Hat, Inc.
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

from contextlib import contextmanager
import importlib
import logging
from operator import itemgetter
from operator import attrgetter
import os
import pkgutil

from libnmstate import validator
from libnmstate.error import NmstateError
from libnmstate.error import NmstateValueError
from libnmstate.nm import NetworkManagerPlugin
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import Route
from libnmstate.schema import RouteRule

from .plugin import NmstatePlugin
from .state import merge_dict


@contextmanager
def plugin_context():
    plugins = _load_plugins()
    try:
        # Lowest priority plugin should perform actions first.
        plugins.sort(key=attrgetter("priority"))
        yield plugins
    except (Exception, KeyboardInterrupt):
        for plugin in plugins:
            if plugin.checkpoint:
                try:
                    plugin.rollback_checkpoint()
                # Don't complex thing by raise exception when handling another
                # exception, just log the rollback failure.
                except Exception as e:
                    logging.error(f"Rollback failed with error {e}")
        raise
    finally:
        for plugin in plugins:
            plugin.unload()


def show_with_plugins(plugins, include_status_data=None):
    for plugin in plugins:
        plugin.refresh_content()
    report = {}
    if include_status_data:
        report["capabilities"] = plugins_capabilities(plugins)

    report[Interface.KEY] = _get_interface_info_from_plugins(plugins)

    route_plugin = _find_plugin_for_capability(
        plugins, NmstatePlugin.PLUGIN_CAPABILITY_ROUTE
    )
    if route_plugin:
        report[Route.KEY] = route_plugin.get_routes()

    route_rule_plugin = _find_plugin_for_capability(
        plugins, NmstatePlugin.PLUGIN_CAPABILITY_ROUTE_RULE
    )
    if route_rule_plugin:
        report[RouteRule.KEY] = route_rule_plugin.get_route_rules()

    dns_plugin = _find_plugin_for_capability(
        plugins, NmstatePlugin.PLUGIN_CAPABILITY_DNS
    )
    if dns_plugin:
        report[DNS.KEY] = dns_plugin.get_dns_client_config()

    validator.schema_validate(report)
    return report


def plugins_capabilities(plugins):
    capabilities = set()
    for plugin in plugins:
        capabilities.update(set(plugin.capabilities))
    return list(capabilities)


def _load_plugins():
    plugins = [NetworkManagerPlugin()]
    plugins.extend(_load_external_py_plugins())
    return plugins


def _load_external_py_plugins():
    """
    Load module from folder defined in system evironment NMSTATE_PLUGIN_DIR,
    if empty, use the 'plugins' folder of current python file.
    """
    plugins = []
    plugin_dir = os.environ.get("NMSTATE_PLUGIN_DIR")
    if not plugin_dir:
        plugin_dir = f"{os.path.dirname(os.path.realpath(__file__))}/plugins"

    for _, name, ispkg in pkgutil.iter_modules([plugin_dir]):
        if name.startswith("nmstate_plugin_"):
            try:
                spec = importlib.util.spec_from_file_location(
                    name, f"{plugin_dir}/{name}.py"
                )
                plugin_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(plugin_module)
                plugin = plugin_module.NMSTATE_PLUGIN()
                plugins.append(plugin)
            except Exception as error:
                logging.warning(f"Failed to load plugin {name}: {error}")

    return plugins


def _find_plugin_for_capability(plugins, capability):
    """
    Return the plugin with specified capability and highest priority.
    """
    chose_plugin = None
    for plugin in plugins:
        if (
            chose_plugin
            and capability in plugin.plugin_capabilities
            and plugin.priority > chose_plugin.priority
        ) or not chose_plugin:
            chose_plugin = plugin
    return chose_plugin


def _get_interface_info_from_plugins(plugins):
    all_ifaces = {}
    IFACE_PRIORITY_METADATA = "_plugin_priority"
    for plugin in plugins:
        if (
            NmstatePlugin.PLUGIN_CAPABILITY_IFACE
            not in plugin.plugin_capabilities
        ):
            continue
        for iface in plugin.get_interfaces():
            iface[IFACE_PRIORITY_METADATA] = plugin.priority
            iface_name = iface[Interface.NAME]
            if iface_name in all_ifaces:
                existing_iface = all_ifaces[iface_name]
                existing_priority = existing_iface[IFACE_PRIORITY_METADATA]
                current_priority = plugin.priority
                if current_priority > existing_priority:
                    merge_dict(iface, existing_iface)
                    all_ifaces[iface_name] = iface
                else:
                    merge_dict(existing_iface, iface)
            else:
                all_ifaces[iface_name] = iface

    # Remove metadata
    for iface in all_ifaces.values():
        iface.pop(IFACE_PRIORITY_METADATA)

    return sorted(all_ifaces.values(), key=itemgetter(Interface.NAME))


def create_checkpoints(plugins, timeout):
    """
    Return a string containing all the check point created by each plugin in
    the format:
        plugin.name|<checkpoing_path>|plugin.name|<checkpoing_path|...

    """
    checkpoints = []
    for plugin in plugins:
        checkpoint = plugin.create_checkpoint(timeout)
        if checkpoint:
            checkpoints.append(f"{plugin.name}|{checkpoint}")
    return "|".join(checkpoints)


def destroy_checkpoints(plugins, checkpoints):
    _checkpoint_action(plugins, _parse_checkpoints(checkpoints), "destroy")


def rollback_checkpoints(plugins, checkpoints):
    _checkpoint_action(plugins, _parse_checkpoints(checkpoints), "rollback")


def _checkpoint_action(plugins, checkpoint_index, action):
    errors = []
    for plugin in plugins:
        if checkpoint_index and plugin.name not in checkpoint_index:
            continue
        checkpoint = (
            checkpoint_index[plugin.name] if checkpoint_index else None
        )
        try:
            if action == "destroy":
                plugin.destroy_checkpoint(checkpoint)
            else:
                plugin.rollback_checkpoint(checkpoint)
        except (Exception, KeyboardInterrupt) as error:
            errors.append(error)

    if errors:
        if len(errors) == 1:
            raise errors[0]
        else:
            raise NmstateError(
                "Got multiple exception during checkpoint "
                f"{action}: {errors}"
            )


def _parse_checkpoints(checkpoints):
    """
    Return a dict mapping plugin name to checkpoint
    """
    if not checkpoints:
        return None
    parsed = checkpoints.split("|")
    if len(parsed) % 2:
        raise NmstateValueError("Invalid format of checkpoint")
    checkpoint_index = {}
    for plugin_name, checkpoint in zip(parsed[0::2], parsed[1::2]):
        checkpoint_index[plugin_name] = checkpoint
