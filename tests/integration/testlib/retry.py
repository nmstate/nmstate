# SPDX-License-Identifier: LGPL-2.1-or-later

import time


def retry_till_true_or_timeout(timeout, func, *args, **kwargs):
    ret = func(*args, **kwargs)
    while timeout > 0:
        if ret:
            break
        print(f"Got False return from {func.__name__}: retrying")
        time.sleep(1)
        timeout -= 1
        ret = func(*args, **kwargs)
    return ret


def retry_till_false_or_timeout(timeout, func, *args, **kwargs):
    ret = func(*args, **kwargs)
    while timeout > 0:
        if not ret:
            break
        time.sleep(1)
        timeout -= 1
        ret = func(*args, **kwargs)
    return ret
