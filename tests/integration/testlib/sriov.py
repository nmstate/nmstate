# SPDX-License-Identifier: LGPL-2.1-or-later

import glob
import os


def get_sriov_vf_names(pf_name):
    ret = []
    for folder in glob.glob(f"/sys/class/net/{pf_name}/device/virtfn*/net/"):
        ret.extend(os.listdir(folder))
    return ret
