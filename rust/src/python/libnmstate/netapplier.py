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

from .clib_wrapper import apply_net_state
from .clib_wrapper import commit_checkpoint
from .clib_wrapper import rollback_checkpoint


def apply(
    desired_state,
    *,
    kernel_only=False,
    verify_change=True,
    save_to_disk=True,
    commit=True,
    rollback_timeout=60,
    verbose_on_retry=False,
):
    return apply_net_state(
        desired_state,
        kernel_only=kernel_only,
        verify_change=verify_change,
        save_to_disk=save_to_disk,
        commit=commit,
        rollback_timeout=rollback_timeout,
        verbose_on_retry=verbose_on_retry,
    )


def commit(*, checkpoint=None):
    commit_checkpoint(checkpoint)


def rollback(*, checkpoint=None):
    rollback_checkpoint(checkpoint)
