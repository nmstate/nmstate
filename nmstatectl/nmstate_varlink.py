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
import errno
import logging
import os

import libnmstate
import libnmstate.error as libnmError

try:
    import varlink
except ModuleNotFoundError:
    raise libnmError.NmstateDependencyError("python3 varlink module not found")


class NmstateVarlinkLogHandler(logging.Handler):
    def __init__(self):
        self._log_records = list()
        super().__init__()

    def filter(self, record):
        return True

    def emit(self, record):
        self._log_records.append(record)

    @property
    def logs(self):
        """
        Return a list of dict, example:
            [
                {
                    "time": "2003-07-08 16:49:45,896",
                    "level": "DEBUG",
                    "message": "foo is changed",
                }
            ]
        """
        return [
            {
                "time": record.asctime,
                "level": record.levelname,
                "message": record.message,
            }
            for record in self._log_records
        ]


@contextmanager
def nmstate_varlink_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    handler = NmstateVarlinkLogHandler()
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)


def validate_method_arguments(user_args, method_args):
    """
    Returns dictionary with validated arguments values.
    """
    kwargs = {}
    for arg in user_args.keys():
        if arg not in method_args or user_args[arg] == {}:
            raise varlink.InvalidParameter(arg)
        if user_args[arg] is not None:
            kwargs[arg] = user_args[arg]
    return kwargs


def gen_varlink_server(address):
    """
    Returns varlink server object
    Checks if the varlink address already in use.
    """
    address = "unix:" + address
    server = varlink.ThreadingServer(
        address, ServiceRequestHandler, bind_and_activate=False
    )
    server.allow_reuse_address = True
    try:
        server.server_bind()
        server.server_activate()
    except OSError as exception:
        server.shutdown()
        server.server_close()
        if exception.errno == errno.EADDRINUSE:
            server = varlink.ThreadingServer(
                address, ServiceRequestHandler, bind_and_activate=True
            )
        else:
            logging.error(exception.strerror)
            raise exception
    return server


def start_varlink_server(address):
    """
    Runs the varlink server in the specified the file path
    """
    varlink_server = gen_varlink_server(address)
    try:
        with varlink_server as server:
            server.serve_forever()
    except Exception as exception:
        logging.error(str(exception))
        varlink_server.shutdown()
    finally:
        varlink_server.server_close()


class NmstateError(varlink.VarlinkError):
    def __init__(self, message, logs):
        varlink.VarlinkError.__init__(
            self,
            {
                "error": self.__class__.__name__,
                "parameters": {
                    "error_message": message,
                    "log": logs,
                },
            },
        )


class NmstateValueError(NmstateError):
    pass


class NmstatePermissionError(NmstateError):
    pass


class NmstateConflictError(NmstateError):
    pass


class NmstateLibnmError(NmstateError):
    pass


class NmstateVerificationError(NmstateError):
    pass


class NmstateNotImplementedError(NmstateError):
    pass


class NmstateInternalError(NmstateError):
    pass


class NmstateDependencyError(NmstateError):
    pass


class ServiceRequestHandler(varlink.RequestHandler):
    service = varlink.Service(
        vendor="Red Hat",
        product="Nmstate",
        version=libnmstate.__version__,
        url="https://www.nmstate.io",
        interface_dir=os.path.dirname(__file__),
        namespaced=False,
    )


@ServiceRequestHandler.service.interface("io.nmstate")
class NmstateVarlinkService:
    def Show(self, arguments):
        """
        Reports the state data on the system
        """
        with nmstate_varlink_logger() as log_handler:
            method_args = ["include_status_data"]
            show_kwargs = validate_method_arguments(arguments, method_args)
            try:
                configured_state = libnmstate.show(**show_kwargs)
                return {"state": configured_state, "log": log_handler.logs}
            except libnmstate.error.NmstateValueError as exception:
                logging.error(str(exception))
                raise NmstateValueError(str(exception), log_handler.logs)

    def ShowRunningConfig(self, arguments):
        with nmstate_varlink_logger() as log_handler:
            method_args = []
            validate_method_arguments(arguments, method_args)
            try:
                configured_state = libnmstate.show_running_config()
                return {"state": configured_state, "log": log_handler.logs}
            except libnmstate.error.NmstateValueError as exception:
                logging.error(str(exception))
                raise NmstateValueError(str(exception), log_handler.logs)

    def Apply(self, arguments):
        """
        Apply desired state declared in json format
        which is parsed as dictionary
        """
        with nmstate_varlink_logger() as log_handler:
            method_args = [
                "desired_state",
                "verify_change",
                "commit",
                "rollback_timeout",
                "save_to_disk",
            ]
            apply_kwargs = validate_method_arguments(arguments, method_args)
            if "desired_state" not in apply_kwargs.keys():
                logging.error("Desired_state not specified")
                raise NmstateValueError(
                    "desired_state: No state specified", log_handler.logs
                )
            try:
                libnmstate.apply(**apply_kwargs)
                return {"log": log_handler.logs}
            except TypeError as exception:
                logging.error(str(exception), log_handler.logs)
                raise varlink.InvalidParameter(exception)
            except libnmstate.error.NmstatePermissionError as exception:
                logging.error(str(exception))
                raise NmstatePermissionError(str(exception), log_handler.logs)
            except libnmstate.error.NmstateValueError as exception:
                logging.error(str(exception))
                raise NmstateValueError(str(exception), log_handler.logs)
            except libnmstate.error.NmstateConflictError as exception:
                logging.error(str(exception))
                raise NmstateConflictError(str(exception), log_handler.logs)
            except libnmstate.error.NmstateVerificationError as exception:
                logging.error(str(exception))
                raise NmstateVerificationError(
                    str(exception), log_handler.logs
                )

    def Commit(self, arguments):
        """
        Commits the checkpoint
        """
        with nmstate_varlink_logger() as log_handler:
            method_args = ["checkpoint"]
            commit_kwargs = validate_method_arguments(arguments, method_args)
            try:
                libnmstate.commit(**commit_kwargs)
                return {"log": log_handler.logs}
            except libnmstate.error.NmstateValueError as exception:
                logging.error(str(exception))
                raise NmstateValueError(str(exception), log_handler.logs)

    def Rollback(self, arguments):
        """
        Roll back to the checkpoint
        """
        with nmstate_varlink_logger() as log_handler:
            method_args = ["checkpoint"]
            rollback_kwargs = validate_method_arguments(arguments, method_args)
            try:
                libnmstate.rollback(**rollback_kwargs)
                return {"log": log_handler.logs}
            except libnmstate.error.NmstateValueError as exception:
                logging.error(str(exception))
                raise NmstateValueError(str(exception), log_handler.logs)
