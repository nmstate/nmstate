# Copyright 2021 Red Hat
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ctypes import c_int, c_char_p, c_uint32, POINTER, byref, cdll
import json

from .error import (
    NmstateError,
    NmstateVerificationError,
    NmstateValueError,
    NmstateInternalError,
    NmstatePluginError,
    NmstateNotImplementedError,
    NmstateKernelIntegerRoundedError,
)

lib = cdll.LoadLibrary("libnmstate.so.1")

lib.nmstate_net_state_retrieve.restype = c_int
lib.nmstate_net_state_retrieve.argtypes = (
    c_uint32,
    POINTER(c_char_p),
    POINTER(c_char_p),
    POINTER(c_char_p),
    POINTER(c_char_p),
)

lib.nmstate_err_kind_free.restype = None
lib.nmstate_err_kind_free.argtypes = (c_char_p,)
lib.nmstate_err_msg_free.restype = None
lib.nmstate_err_msg_free.argtypes = (c_char_p,)
lib.nmstate_log_free.restype = None
lib.nmstate_log_free.argtypes = (c_char_p,)
lib.nmstate_net_state_free.restype = None
lib.nmstate_net_state_free.argtypes = (c_char_p,)

NMSTATE_FLAG_NONE = 0
NMSTATE_FLAG_KERNEL_ONLY = 1 << 1
NMSTATE_FLAG_NO_VERIFY = 1 << 2
NMSTATE_FLAG_INCLUDE_STATUS_DATA = 1 << 3
NMSTATE_FLAG_INCLUDE_SECRETS = 1 << 4
NMSTATE_FLAG_MEMORY_ONLY = 1 << 5
NMSTATE_PASS = 0


def retrieve_net_state_json(
    kernel_only=False, include_status_data=False, include_secrets=False
):
    c_err_msg = c_char_p()
    c_err_kind = c_char_p()
    c_state = c_char_p()
    c_log = c_char_p()
    flags = NMSTATE_FLAG_NONE
    if kernel_only:
        flags |= NMSTATE_FLAG_KERNEL_ONLY
    if include_status_data:
        flags |= NMSTATE_FLAG_INCLUDE_STATUS_DATA
    if include_secrets:
        flags |= NMSTATE_FLAG_INCLUDE_SECRETS

    rc = lib.nmstate_net_state_retrieve(
        flags,
        byref(c_state),
        byref(c_log),
        byref(c_err_kind),
        byref(c_err_msg),
    )
    state = c_state.value
    err_msg = c_err_msg.value
    err_kind = c_err_kind.value
    lib.nmstate_log_free(c_log)
    lib.nmstate_net_state_free(c_state)
    lib.nmstate_err_kind_free(c_err_kind)
    lib.nmstate_err_msg_free(c_err_msg)
    if rc != NMSTATE_PASS:
        raise NmstateError(f"{err_kind}: {err_msg}")
    return state.decode("utf-8")


def apply_net_state(
    state, kernel_only=False, verify_change=True, save_to_disk=True
):
    c_err_msg = c_char_p()
    c_err_kind = c_char_p()
    c_state = c_char_p(json.dumps(state).encode("utf-8"))
    c_log = c_char_p()
    flags = NMSTATE_FLAG_NONE
    if kernel_only:
        flags |= NMSTATE_FLAG_KERNEL_ONLY

    if not verify_change:
        flags |= NMSTATE_FLAG_NO_VERIFY

    if not save_to_disk:
        flags |= NMSTATE_FLAG_MEMORY_ONLY

    rc = lib.nmstate_net_state_apply(
        flags,
        c_state,
        byref(c_log),
        byref(c_err_kind),
        byref(c_err_msg),
    )
    err_msg = c_err_msg.value
    err_kind = c_err_kind.value
    lib.nmstate_log_free(c_log)
    lib.nmstate_err_kind_free(c_err_kind)
    lib.nmstate_err_msg_free(c_err_msg)
    if rc != NMSTATE_PASS:
        err_msg = err_msg.decode("utf-8")
        err_kind = err_kind.decode("utf-8")
        if err_kind == "VerificationError":
            raise NmstateVerificationError(err_msg)
        elif err_kind == "InvalidArgument":
            raise NmstateValueError(err_msg)
        elif err_kind == "Bug":
            raise NmstateInternalError(err_msg)
        elif err_kind == "PluginFailure":
            raise NmstatePluginError(err_msg)
        elif err_kind == "NotImplementedError":
            raise NmstateNotImplementedError(err_msg)
        elif err_kind == "KernelIntegerRoundedError":
            raise NmstateKernelIntegerRoundedError(err_msg)
        else:
            raise NmstateError(f"{err_kind}: {err_msg}")
