#
# Copyright (c) 2019-2020 Red Hat, Inc.
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


class NmstateError(Exception):
    """
    The base exception of libnmstate.
    """

    pass


class NmstateDependencyError(NmstateError):
    """
    Nmstate requires external tools installed and/or started for desired state.
    """

    pass


class NmstateValueError(NmstateError, ValueError):
    """
    Exception happens at pre-apply check, user should resubmit the amended
    desired state. Example:
        * JSON/YAML syntax issue.
        * Nmstate schema issue.
        * Invalid value of desired property, like bond missing port.
    """

    pass


class NmstatePermissionError(NmstateError, PermissionError):
    """
    Permission deny when applying the desired state.
    """

    pass


class NmstateConflictError(NmstateError, RuntimeError):
    """
    Something else is already editing the network state via Nmstate.
    """

    pass


class NmstateLibnmError(NmstateError):
    """
    Exception for unexpected libnm failure.
    """

    pass


class NmstateVerificationError(NmstateError):
    """
    After applied desired state, current state does not match desired state for
    unknown reason.
    """

    pass


class NmstateKernelIntegerRoundedError(NmstateVerificationError):
    """
    After applied desired state, current state does not match desire state
    due to integer been rounded by kernel.
    For example, with HZ configured as 250 in kernel, the linux bridge option
    multicast_startup_query_interval, 3125 will be rounded to 3124.
    """

    pass


class NmstateNotImplementedError(NmstateError, NotImplementedError):
    """
    Desired feature is not supported by Nmstate yet.
    """

    pass


class NmstateInternalError(NmstateError):
    """
    Unexpected behaviour happened. It is a bug of libnmstate which should be
    fixed.
    """

    pass


class NmstateNotSupportedError(NmstateError):
    """
    A resource like a device does not support the requested feature.
    """

    pass


class NmstateTimeoutError(NmstateLibnmError):
    """
    The transaction execution timed out.
    """

    pass


class NmstatePluginError(NmstateError):
    """
    Unexpected plugin behaviour happens, it is a bug of the plugin.
    """

    pass
