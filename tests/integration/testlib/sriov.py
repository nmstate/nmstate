# SPDX-License-Identifier: Apache-2.0

import glob
import os


def get_sriov_vf_names(pf_name):
    ret = []
    for folder in glob.glob(f"/sys/class/net/{pf_name}/device/virtfn*/net/"):
        ret.extend(os.listdir(folder))
    return ret
