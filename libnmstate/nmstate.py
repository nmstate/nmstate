#
# Copyright (c) 2020-2021 Red Hat, Inc.
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
from operator import attrgetter
from operator import itemgetter
import importlib
import logging
import os
import pkgutil

from libnmstate import validator
from libnmstate.error import NmstateError
from libnmstate.error import NmstateValueError
from libnmstate.error import NmstateDependencyError
from libnmstate.ifaces import BaseIface
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import Route
from libnmstate.schema import RouteRule

from .net_state import NetState
from .nispor.plugin import NisporPlugin
from .plugin import NmstatePlugin
from .state import hide_the_secrets
from .state import merge_dict

_INFO_TYPE_RUNNING = 1
_INFO_TYPE_RUNNING_CONFIG = 2


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


def show_with_plugins(
    plugins,
    include_status_data=None,
    info_type=_INFO_TYPE_RUNNING,
    include_secrets=False,
    include_controller_prop=True,
):
    for plugin in plugins:
        plugin.refresh_content()
    report = {}
    if include_status_data and info_type == _INFO_TYPE_RUNNING:
        report["capabilities"] = plugins_capabilities(plugins)

    report[Interface.KEY] = _get_interface_info_from_plugins(
        plugins, info_type, include_controller_prop=include_controller_prop
    )

    report[Route.KEY] = _get_routes_from_plugins(plugins, info_type)

    report[RouteRule.KEY] = _get_route_rules_from_plugins(plugins)

    dns_plugin = _find_plugin_for_capability(
        plugins, NmstatePlugin.PLUGIN_CAPABILITY_DNS
    )
    if dns_plugin:
        report[DNS.KEY] = dns_plugin.get_dns_client_config()
        if info_type != _INFO_TYPE_RUNNING:
            report[DNS.KEY].pop(DNS.RUNNING, None)

    for plugin in plugins:
        report.update(plugin.get_global_state())

    validator.schema_validate(report)

    if not include_secrets:
        hide_the_secrets(report)

    return report


def plugins_capabilities(plugins):
    capabilities = set()
    for plugin in plugins:
        capabilities.update(set(plugin.capabilities))
    return list(capabilities)


def remove_metadata_leftover(info):
    """
    Remove the metadata introduced on the original state. Nmstate should not
    report metadata to the users.
    """
    for iface_info in info.get(Interface.KEY, []):
        # Remove _perm_mac_address metadata from Nispor
        iface_info.pop(BaseIface.PERMANENT_MAC_ADDRESS_METADATA, None)

    return info


def _load_plugins():
    plugins = [NisporPlugin()]
    plugins.extend(_load_external_py_plugins())
    plugins.extend(_load_nm_plugin())
    return plugins


def _load_nm_plugin():
    """
    Makin NetworkManager plugin as optional
    """
    try:
        from libnmstate.nm import NetworkManagerPlugin

        return [NetworkManagerPlugin()]
    except Exception as e:
        logging.warning(f"Failed to load NetworkManager plugin: {e}")
        return []


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
        if capability in plugin.plugin_capabilities:
            if (
                chose_plugin and plugin.priority > chose_plugin.priority
            ) or not chose_plugin:
                chose_plugin = plugin
    return chose_plugin


def _get_interface_info_from_plugins(
    plugins, info_type, include_controller_prop=True
):
    all_ifaces = {}
    IFACE_PRIORITY_METADATA = "_plugin_priority"
    IFACE_PLUGIN_SRC_METADATA = "_plugin_source"
    for plugin in plugins:
        if (
            NmstatePlugin.PLUGIN_CAPABILITY_IFACE
            not in plugin.plugin_capabilities
        ):
            continue
        try:
            if info_type == _INFO_TYPE_RUNNING_CONFIG:
                ifaces = plugin.get_running_config_interfaces()
            else:
                ifaces = plugin.get_interfaces()
        except NmstateDependencyError as e:
            logging.warning(f"Plugin {plugin.name} error: {e}")
            continue

        for iface in ifaces:
            iface[IFACE_PRIORITY_METADATA] = plugin.priority
            iface[IFACE_PLUGIN_SRC_METADATA] = [plugin.name]
            iface_name = iface[Interface.NAME]
            iface_type = iface.get(Interface.TYPE, InterfaceType.UNKNOWN)
            # When NetworkManager does not support Veth interfaces will report
            # them as Ethernet. Therefore, the information will not be merged
            # correctly from Nispor and NetworkManager, in order to solve that,
            # we are considering Veth as Ethernet when merging.
            if iface_type == InterfaceType.VETH:
                iface_type = InterfaceType.ETHERNET
            iface_index = f"{iface_type}.{iface_name}"
            if iface_index in all_ifaces:
                logging.debug(
                    f"Interface {iface_index} found. Merging the interface "
                    "information."
                )
                existing_iface = all_ifaces[iface_index]
                existing_priority = existing_iface[IFACE_PRIORITY_METADATA]
                current_priority = plugin.priority
                if current_priority > existing_priority:
                    merge_dict(iface, existing_iface)
                    iface[IFACE_PLUGIN_SRC_METADATA].extend(
                        existing_iface[IFACE_PLUGIN_SRC_METADATA]
                    )
                    all_ifaces[iface_index] = iface
                else:
                    merge_dict(existing_iface, iface)
                    existing_iface[IFACE_PLUGIN_SRC_METADATA].extend(
                        iface[IFACE_PLUGIN_SRC_METADATA]
                    )
            else:
                all_ifaces[iface_index] = iface

    # For any unknown interface, we merge it when there is only one interface
    # with the same name and valid type.
    # This save plugin(e.g. ovsdb) from detecting interface type but still want
    # data been merged.
    to_be_removed_index = set()
    for iface in all_ifaces.values():
        iface_type = iface.get(Interface.TYPE, InterfaceType.UNKNOWN)
        iface_name = iface[Interface.NAME]
        if iface_type == InterfaceType.UNKNOWN:
            iface_types = _get_iface_types_by_name(
                all_ifaces.values(), iface_name
            )
            if len(iface_types) == 1:
                to_be_removed_index.add(
                    f"{InterfaceType.UNKNOWN}.{iface_name}"
                )
                iface_index = f"{iface_types[0]}.{iface_name}"
                existing_iface = all_ifaces[iface_index]
                iface[Interface.TYPE] = existing_iface[Interface.TYPE]
                current_priority = iface[IFACE_PRIORITY_METADATA]
                existing_priority = existing_iface[IFACE_PRIORITY_METADATA]
                if current_priority > existing_priority:
                    merge_dict(iface, existing_iface)
                    iface[IFACE_PLUGIN_SRC_METADATA].extend(
                        existing_iface[IFACE_PLUGIN_SRC_METADATA]
                    )
                    all_ifaces[iface_index] = iface
                else:
                    merge_dict(existing_iface, iface)
                    existing_iface[IFACE_PLUGIN_SRC_METADATA].extend(
                        iface[IFACE_PLUGIN_SRC_METADATA]
                    )

    supplemental_plugin_names = set(
        [plugin.name for plugin in plugins if plugin.is_supplemental_only]
    )

    for iface_index, iface in all_ifaces.items():
        cur_plugin_names = set(iface[IFACE_PLUGIN_SRC_METADATA])
        if cur_plugin_names.issubset(supplemental_plugin_names):
            to_be_removed_index.add(iface_index)

    for iface_index in to_be_removed_index:
        del all_ifaces[iface_index]

    # Remove metadata
    for iface in all_ifaces.values():
        iface.pop(IFACE_PRIORITY_METADATA)
        iface.pop(IFACE_PLUGIN_SRC_METADATA)
        if not include_controller_prop:
            iface.pop(Interface.CONTROLLER, None)

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


def _get_routes_from_plugins(plugins, info_type):
    ret = {Route.RUNNING: [], Route.CONFIG: []}
    for plugin in plugins:
        if NmstatePlugin.PLUGIN_CAPABILITY_ROUTE in plugin.plugin_capabilities:
            plugin_routes = plugin.get_routes()
            if info_type == _INFO_TYPE_RUNNING:
                ret[Route.RUNNING].extend(plugin_routes.get(Route.RUNNING, []))
            ret[Route.CONFIG].extend(plugin_routes.get(Route.CONFIG, []))
    if info_type != _INFO_TYPE_RUNNING:
        ret.pop(Route.RUNNING)
    return ret


def _get_route_rules_from_plugins(plugins):
    ret = {RouteRule.CONFIG: []}
    for plugin in plugins:
        if (
            NmstatePlugin.PLUGIN_CAPABILITY_ROUTE_RULE
            in plugin.plugin_capabilities
        ):
            plugin_route_rules = plugin.get_route_rules()
            ret[RouteRule.CONFIG].extend(
                plugin_route_rules.get(RouteRule.CONFIG, [])
            )
    return ret


def _get_iface_types_by_name(iface_infos, name):
    """
    Return the type of all ifaces with valid type and specified name
    """
    iface_types = []
    for iface_info in iface_infos:
        iface_type = iface_info.get(Interface.TYPE, InterfaceType.UNKNOWN)
        if (
            iface_type != InterfaceType.UNKNOWN
            and iface_info[Interface.NAME] == name
        ):
            if iface_type == InterfaceType.VETH:
                iface_type = InterfaceType.ETHERNET
            iface_types.append(iface_type)

    return iface_types


def show_running_config_with_plugins(plugins, include_secrets):
    return show_with_plugins(
        plugins,
        info_type=_INFO_TYPE_RUNNING_CONFIG,
        include_secrets=include_secrets,
        include_controller_prop=False,
    )


def generate_configurations(desire_state):
    """
    Return a dictionary with:
        * key: plugin name
        * vlaue: list of strings for configruations
    This function will not merge or verify desire state with current state, so
    you may run this function on different system.
    """
    configs = {}
    net_state = NetState(desire_state, gen_conf_mode=True)

    with plugin_context() as plugins:
        for plugin in plugins:
            config = plugin.generate_configurations(net_state)
            if config:
                configs[plugin.name] = config
    return configs
