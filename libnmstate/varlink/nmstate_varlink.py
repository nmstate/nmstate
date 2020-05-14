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
import os
import libnmstate
import logging
import errno
import io
import json
import libnmstate.error as libnmError


try:
    import varlink

except ModuleNotFoundError:
    raise libnmError.NmstateDependencyError("python3 varlink module not found")


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
log_stringio = io.StringIO()
handler = logging.StreamHandler(log_stringio)
handler.setLevel(logging.DEBUG)
handler.setFormatter(
    logging.Formatter(
        '{"time": "%(asctime)s",'
        + '"level": "%(levelname)s", "message": "%(message)s"}',
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)
logger.addHandler(handler)

service = varlink.Service(
    vendor="Red Hat",
    product="Nmstate",
    version=libnmstate.__version__,
    url="https://www.nmstate.io",
    interface_dir=os.path.dirname(__file__),
    namespaced=False,
)


def clean_log():
    """
    Cleaning previous logs
    """
    log_stringio.seek(0)
    log_stringio.truncate()


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


def get_logs():
    """
    Returns list of logs in dictionary.
    """
    log_list = list()
    log_stringio.seek(0)
    for log in log_stringio.getvalue().replace("x\00", "").split("\n")[:-1]:
        log_list.append(json.loads(log))
    clean_log()
    log_stringio.truncate(0)
    return log_list


def get_varlink_server(address):
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


class NmstateError(varlink.VarlinkError):
    def __init__(self, message):
        varlink.VarlinkError.__init__(
            self,
            {
                "error": self.__class__.__name__,
                "parameters": {"error_message": message, "log": get_logs()},
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
    service = service


@service.interface("io.nmstate")
class NmstateVarlinkService:
    def Show(self, arguments):
        """
        Reports the state data on the system
        """
        clean_log()
        method_args = ["include_status_data"]
        show_kwargs = validate_method_arguments(arguments, method_args)
        try:
            configured_state = libnmstate.show(**show_kwargs)
            return {"state": configured_state, "log": get_logs()}
        except libnmstate.error.NmstateValueError as exception:
            logging.error(str(exception))
            raise NmstateValueError(str(exception))

    def Apply(self, arguments):
        """
        Apply desired state declared in json format
        which is parsed as dictionary
        """
        clean_log()
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
            raise NmstateValueError("desired_state: No state specified")
        try:
            libnmstate.apply(**apply_kwargs)
            return {"log": get_logs()}
        except TypeError as exception:
            logging.error(str(exception))
            raise varlink.InvalidParameter(exception)
        except libnmstate.error.NmstatePermissionError as exception:
            logging.error(str(exception))
            raise NmstatePermissionError(str(exception))
        except libnmstate.error.NmstateValueError as exception:
            logging.error(str(exception))
            raise NmstateValueError(str(exception))
        except libnmstate.error.NmstateConflictError as exception:
            logging.error(str(exception))
            raise NmstateConflictError(str(exception))
        except libnmstate.error.NmstateVerificationError as exception:
            logging.error(str(exception))
            raise NmstateVerificationError(str(exception))

    def Commit(self, arguments):
        """
        Commits the checkpoint
        """
        clean_log()
        method_args = ["checkpoint"]
        commit_kwargs = validate_method_arguments(arguments, method_args)
        try:
            libnmstate.commit(**commit_kwargs)
            return {"log": get_logs()}
        except libnmstate.error.NmstateValueError as exception:
            logging.error(str(exception))
            raise NmstateValueError(str(exception))

    def Rollback(self, arguments):
        """
        Roll back to the checkpoint
        """
        clean_log()
        method_args = ["checkpoint"]
        rollback_kwargs = validate_method_arguments(arguments, method_args)
        try:
            libnmstate.rollback(**rollback_kwargs)
            return {"log": get_logs()}
        except libnmstate.error.NmstateValueError as exception:
            logging.error(str(exception))
            raise NmstateValueError(str(exception))
