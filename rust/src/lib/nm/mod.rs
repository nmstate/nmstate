// SPDX-License-Identifier: Apache-2.0

#[cfg(feature = "query_apply")]
mod checkpoint;
mod conn_matcher;
mod connection;
mod device;
pub(crate) mod dns;
#[cfg(feature = "query_apply")]
mod error;
#[cfg(feature = "gen_conf")]
mod gen_conf;
#[allow(unused_imports)]
mod nm_dbus;
#[cfg(feature = "query_apply")]
mod query_apply;
pub(crate) mod route;
pub(crate) mod route_rule;
mod settings;
#[cfg(feature = "query_apply")]
mod show;

#[cfg(feature = "query_apply")]
pub(crate) use checkpoint::{
    RuleCheckpointConnections, nm_checkpoint_create, nm_checkpoint_destroy,
    nm_checkpoint_exists, nm_checkpoint_owner, nm_checkpoint_rollback,
    nm_checkpoint_rollback_for_rules, nm_checkpoint_rule_connections,
    nm_checkpoint_timeout_disable, nm_checkpoint_timeout_extend,
};
#[cfg(feature = "gen_conf")]
pub(crate) use gen_conf::nm_gen_conf;
#[cfg(feature = "query_apply")]
pub(crate) use query_apply::{dispatch::dispatch_dir, nm_apply};
#[cfg(feature = "query_apply")]
pub(crate) use show::nm_retrieve;

pub(crate) use self::conn_matcher::NmConnectionMatcher;
