// SPDX-License-Identifier: Apache-2.0

#[cfg(feature = "query_apply")]
mod active_connection;
mod backend_opt;
#[cfg(feature = "query_apply")]
mod checkpoint;
#[cfg(feature = "query_apply")]
mod device;
pub(crate) mod dns;
#[cfg(feature = "query_apply")]
mod error;
#[cfg(feature = "gen_conf")]
mod gen_conf;
#[allow(unused_imports)]
mod nm_dbus;
mod profile;
#[cfg(feature = "query_apply")]
mod query_apply;
pub(crate) mod route;
pub(crate) mod route_rule;
mod settings;
#[cfg(feature = "query_apply")]
mod show;
#[cfg(test)]
mod unit_tests;

#[cfg(feature = "query_apply")]
pub(crate) use checkpoint::{
    nm_checkpoint_create, nm_checkpoint_destroy, nm_checkpoint_rollback,
    nm_checkpoint_timeout_extend,
};
#[cfg(feature = "gen_conf")]
pub(crate) use gen_conf::nm_gen_conf;
#[cfg(feature = "query_apply")]
pub(crate) use query_apply::nm_apply;
#[cfg(feature = "query_apply")]
pub(crate) use show::nm_retrieve;
