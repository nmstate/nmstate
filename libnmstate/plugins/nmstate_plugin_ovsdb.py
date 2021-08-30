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

import copy
import os
import time

import ovs
from ovs.db.idl import Transaction, Idl, SchemaHelper

from libnmstate.plugin import NmstatePlugin
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge
from libnmstate.schema import OvsDB
from libnmstate.state import merge_dict
from libnmstate.error import NmstateNotImplementedError
from libnmstate.error import NmstateTimeoutError
from libnmstate.error import NmstatePermissionError
from libnmstate.error import NmstateValueError
from libnmstate.error import NmstatePluginError

TIMEOUT = 5

DEFAULT_OVS_DB_SOCKET_PATH = "/run/openvswitch/db.sock"
DEFAULT_OVS_SCHEMA_PATH = "/usr/share/openvswitch/vswitch.ovsschema"

NM_EXTERNAL_ID = "NM.connection.uuid"

GLOBAL_CONFIG_TABLE = "Open_vSwitch"

ALL_SUPPORTED_GLOBAL_COLUMNS = [OvsDB.EXTERNAL_IDS, OvsDB.OTHER_CONFIG]


class _Changes:
    def __init__(self, table_name, column_name, row_name, column_value):
        self.table_name = table_name
        self.column_name = column_name
        self.row_name = row_name
        self.column_value = column_value

    def __str__(self):
        return f"{self.__dict__}"


class NmstateOvsdbPlugin(NmstatePlugin):
    def __init__(self):
        self._schema = None
        self._idl = None
        self._transaction = None
        self._seq_no = 0
        self._load_schema()
        self._connect_to_ovs_db()

    @property
    def is_supplemental_only(self):
        return True

    def unload(self):
        if self._transaction:
            self._transaction.abort()
            self._transaction = None
        if self._idl:
            self._idl.close()
            self._idl = None

    def _load_schema(self):
        schema_path = os.environ.get(
            "OVS_SCHEMA_PATH", DEFAULT_OVS_SCHEMA_PATH
        )
        if not os.path.exists(schema_path):
            raise NmstateValueError(
                f"OVS schema file {schema_path} does not exist, "
                "please define the correct one via "
                "environment variable 'OVS_SCHEMA_PATH'"
            )
        if not os.access(schema_path, os.R_OK):
            raise NmstatePermissionError(
                f"Has no read permission to OVS schema file {schema_path}"
            )
        self._schema = SchemaHelper(schema_path)
        self._schema.register_columns(
            "Interface", [OvsDB.EXTERNAL_IDS, "name", "type"]
        )
        self._schema.register_columns("Bridge", [OvsDB.EXTERNAL_IDS, "name"])
        self._schema.register_columns(
            GLOBAL_CONFIG_TABLE,
            ALL_SUPPORTED_GLOBAL_COLUMNS,
        )

    def _connect_to_ovs_db(self):
        socket_path = os.environ.get(
            "OVS_DB_UNIX_SOCKET_PATH", DEFAULT_OVS_DB_SOCKET_PATH
        )
        if not os.path.exists(socket_path):
            raise NmstateValueError(
                f"OVS database socket file {socket_path} does not exist, "
                "please start the OVS daemon or define the socket path via "
                "environment variable 'OVS_DB_UNIX_SOCKET_PATH'"
            )
        if not os.access(socket_path, os.R_OK):
            raise NmstatePermissionError(
                f"Has no read permission to OVS db socket file {socket_path}"
            )

        self._idl = Idl(f"unix:{socket_path}", self._schema)
        self.refresh_content()
        if not self._idl.has_ever_connected():
            self._idl = None
            raise NmstatePluginError("Failed to connect to OVS DB")

    def refresh_content(self):
        if self._idl:
            timeout_end = time.time() + TIMEOUT
            self._idl.run()
            if self._idl.change_seqno == self._seq_no and self._seq_no:
                return
            while True:
                changed = self._idl.run()
                cur_seq_no = self._idl.change_seqno
                if cur_seq_no != self._seq_no or changed:
                    self._seq_no = cur_seq_no
                    return
                poller = ovs.poller.Poller()
                self._idl.wait(poller)
                poller.timer_wait(TIMEOUT * 1000)
                poller.block()
                if time.time() > timeout_end:
                    raise NmstateTimeoutError(
                        f"Plugin {self.name} timeout({TIMEOUT} "
                        "seconds) when refresh OVS database connection"
                    )

    @property
    def name(self):
        return "nmstate-plugin-ovsdb"

    @property
    def priority(self):
        return NmstatePlugin.DEFAULT_PRIORITY + 1

    @property
    def plugin_capabilities(self):
        return NmstatePlugin.PLUGIN_CAPABILITY_IFACE

    def get_interfaces(self):
        ifaces = []
        for row in self._idl.tables["Interface"].rows.values():
            if row.type in ("internal", "patch"):
                iface_type = InterfaceType.OVS_INTERFACE
            elif row.type == "system":
                # Let other plugin decide the interface type
                iface_type = InterfaceType.UNKNOWN
            else:
                continue

            modified_external_ids = self._drop_nm_external_ids(
                row.external_ids
            )
            ifaces.append(
                {
                    Interface.NAME: row.name,
                    Interface.TYPE: iface_type,
                    OvsDB.OVS_DB_SUBTREE: {
                        OvsDB.EXTERNAL_IDS: modified_external_ids,
                    },
                }
            )

        for row in self._idl.tables["Bridge"].rows.values():
            modified_external_ids = self._drop_nm_external_ids(
                row.external_ids
            )
            ifaces.append(
                {
                    Interface.NAME: row.name,
                    Interface.TYPE: InterfaceType.OVS_BRIDGE,
                    OvsDB.OVS_DB_SUBTREE: {
                        OvsDB.EXTERNAL_IDS: modified_external_ids,
                    },
                }
            )
        return ifaces

    def _drop_nm_external_ids(self, external_ids):
        modified_external_ids = copy.deepcopy(external_ids)
        modified_external_ids.pop(NM_EXTERNAL_ID, None)

        return modified_external_ids

    def apply_changes(self, net_state, save_to_disk):
        # State might changed after other plugin invoked apply_changes()
        self.refresh_content()
        cur_iface_to_ext_ids = {}
        for iface_info in self.get_interfaces():
            cur_iface_to_ext_ids[iface_info[Interface.NAME]] = iface_info[
                OvsDB.OVS_DB_SUBTREE
            ][OvsDB.EXTERNAL_IDS]

        pending_changes = []
        for iface in net_state.ifaces.all_ifaces():
            if not iface.is_changed and not iface.is_desired:
                continue
            if not iface.is_up:
                continue
            if iface.type == OVSBridge.TYPE:
                table_name = "Bridge"
            elif OvsDB.OVS_DB_SUBTREE in iface.to_dict():
                table_name = "Interface"
            else:
                continue
            ids_after_nm_applied = cur_iface_to_ext_ids.get(iface.name, {})
            ids_before_nm_applied = (
                iface.to_dict()
                .get(OvsDB.OVS_DB_SUBTREE, {})
                .get(OvsDB.EXTERNAL_IDS, {})
            )
            original_desire_ids = iface.original_desire_dict.get(
                OvsDB.OVS_DB_SUBTREE, {}
            ).get(OvsDB.EXTERNAL_IDS)

            desire_ids = []

            if original_desire_ids is None:
                desire_ids = ids_before_nm_applied
            else:
                desire_ids = original_desire_ids

            if desire_ids != ids_after_nm_applied:
                pending_changes.append(
                    _generate_db_change_external_ids(
                        table_name, iface.name, desire_ids
                    )
                )
        global_config = net_state.desire_state.get(OvsDB.KEY)
        if global_config is not None:
            _merge_global_config(
                global_config, net_state.current_state.get(OvsDB.KEY, {})
            )
            pending_changes.extend(self._apply_global_config(global_config))

        if pending_changes:
            if not save_to_disk:
                raise NmstateNotImplementedError(
                    "ovsdb plugin does not support memory only changes"
                )
            elif self._idl:
                self._start_transaction()
                self._db_write(pending_changes)
                self._commit_transaction()

    def _apply_global_config(self, global_config):
        if global_config:
            return [
                _Changes(GLOBAL_CONFIG_TABLE, key, None, value)
                for key, value in global_config.items()
                if key in ALL_SUPPORTED_GLOBAL_COLUMNS
            ]
        else:
            # Remove all settings, assuming type is dict
            return [
                _Changes(GLOBAL_CONFIG_TABLE, key, None, {})
                for key in ALL_SUPPORTED_GLOBAL_COLUMNS
            ]

    def _db_write(self, changes):
        for change in changes:
            for row in self._idl.tables[change.table_name].rows.values():
                if (
                    change.table_name == GLOBAL_CONFIG_TABLE
                    or row.name == change.row_name
                ):
                    setattr(row, change.column_name, change.column_value)
                    break

    def _start_transaction(self):
        self._transaction = Transaction(self._idl)

    def _commit_transaction(self):
        if self._transaction:
            status = self._transaction.commit()
            timeout_end = time.time() + TIMEOUT
            while status == Transaction.INCOMPLETE:
                self._idl.run()
                poller = ovs.poller.Poller()
                self._idl.wait(poller)
                self._transaction.wait(poller)
                poller.timer_wait(TIMEOUT * 1000)
                poller.block()
                if time.time() > timeout_end:
                    raise NmstateTimeoutError(
                        f"Plugin {self.name} timeout({TIMEOUT} "
                        "seconds) when commit OVS database transaction"
                    )
                status = self._transaction.commit()

            if status == Transaction.SUCCESS:
                self.refresh_content()

            transaction_error = self._transaction.get_error()
            self._transaction = None

            if status not in (Transaction.SUCCESS, Transaction.UNCHANGED):
                raise NmstatePluginError(
                    f"Plugin {self.name} failure on commiting OVS database "
                    f"transaction: status: {status} "
                    f"error: {transaction_error}"
                )
        else:
            raise NmstatePluginError(
                "BUG: _commit_transaction() invoked with "
                "self._transaction is None"
            )

    def get_global_state(self):
        """
        Provide database information of global config table
        """
        info = {}
        for row in self._idl.tables[GLOBAL_CONFIG_TABLE].rows.values():
            for column_name in self._idl.tables[GLOBAL_CONFIG_TABLE].columns:
                info[column_name] = getattr(row, column_name)
            # There is only one row in global config table
            break

        return {OvsDB.KEY: info}


def _generate_db_change_external_ids(table_name, iface_name, desire_ids):
    if desire_ids and not isinstance(desire_ids, dict):
        raise NmstateValueError("Invalid external_ids, should be dictionary")

    # Convert all value to string
    for key, value in desire_ids.items():
        desire_ids[key] = str(value)

    return _Changes(table_name, OvsDB.EXTERNAL_IDS, iface_name, desire_ids)


def _merge_global_config(desire_global_config, current_global_config):
    """
    If any value been set to None, it means remove it.
    """
    # User can delete all global config by {OvsDB.KEY: {}}
    if desire_global_config != {}:
        merge_dict(desire_global_config, current_global_config)
        for column_name in ALL_SUPPORTED_GLOBAL_COLUMNS:
            if column_name in desire_global_config:
                keys_to_delete = [
                    key
                    for key, value in desire_global_config[column_name].items()
                    if value is None
                ]
                for key in keys_to_delete:
                    del desire_global_config[column_name][key]


NMSTATE_PLUGIN = NmstateOvsdbPlugin
