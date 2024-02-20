// SPDX-License-Identifier: Apache-2.0

const BACKEND_OPT_REF_BY_NAME: &str = "nm:refer_controller_parent_by_name";

pub(crate) fn backend_opt_has_ref_by_name(backend_opts: &[String]) -> bool {
    backend_opts.contains(&BACKEND_OPT_REF_BY_NAME.to_string())
}
