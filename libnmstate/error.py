#
# Copyright 2019 Red Hat, Inc.
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

try:
    PermissionError
except NameError:
    # Python 2 does not have PermissionError.
    class PermissionError(Exception):
        pass


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
        * Invalid value of desired property, like bond missing slave.
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
