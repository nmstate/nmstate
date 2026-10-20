// SPDX-License-Identifier: Apache-2.0

use std::{collections::BTreeMap, convert::Infallible};

use futures_util::{
    Stream, StreamExt,
    future::{Either, select},
};
use netlink_packet_route::rule::{
    RuleAttribute, RuleFlags, RuleHeader, RuleMessage,
};
use nispor::RouteRule;
use nix::libc;
use rtnetlink::{
    packet_core::{
        DecodeError, DefaultNla, Emitable, NLM_F_ACK, NLM_F_CREATE, NLM_F_DUMP,
        NLM_F_DUMP_INTR, NLM_F_REQUEST, NetlinkDeserializable, NetlinkHeader,
        NetlinkMessage, NetlinkPayload, NetlinkSerializable, Nla, NlaBuffer,
        Parseable,
    },
    packet_route as netlink_packet_route,
    proto::{ConnectionHandle, new_connection},
    sys::{SocketAddr, protocols::NETLINK_ROUTE},
};
use serde::{Deserialize, Serialize};

use crate::{ErrorKind, NmstateError};

const FRA_TUN_ID: u16 = 12;

/// Failure to remove routing rules.
#[derive(Debug, Clone)]
pub(crate) enum RouteRuleRemoveError {
    /// The kernel denied a mutation before any mutation succeeded.
    PermissionDeniedBeforeChange(NmstateError),
    /// The operation failed and may have partially changed routing rules.
    Failed(NmstateError),
}

impl std::fmt::Display for RouteRuleRemoveError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::PermissionDeniedBeforeChange(error) | Self::Failed(error) => {
                error.fmt(f)
            }
        }
    }
}

impl std::error::Error for RouteRuleRemoveError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::PermissionDeniedBeforeChange(error) | Self::Failed(error) => {
                Some(error)
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct RawRuleMessage {
    message_type: u16,
    payload: Vec<u8>,
}

// The generic netlink codec skips messages whose inner decoder fails. Keep
// every payload here and validate it before any mutation.
impl NetlinkDeserializable for RawRuleMessage {
    type Error = Infallible;

    fn deserialize(
        header: &NetlinkHeader,
        payload: &[u8],
    ) -> Result<Self, Self::Error> {
        Ok(Self {
            message_type: header.message_type,
            payload: payload.to_vec(),
        })
    }
}

impl NetlinkSerializable for RawRuleMessage {
    fn message_type(&self) -> u16 {
        self.message_type
    }

    fn buffer_len(&self) -> usize {
        self.payload.len()
    }

    fn serialize(&self, buffer: &mut [u8]) {
        buffer.copy_from_slice(&self.payload);
    }
}

impl RawRuleMessage {
    fn parse(&self) -> Result<RuleMessage, DecodeError> {
        let header = RuleHeader::parse(self.payload.as_slice())?;
        let mut rule = RuleMessage::default();
        rule.header = header;
        let mut offset = rule.header.buffer_len();
        while offset < self.payload.len() {
            let attribute = NlaBuffer::new_checked(&self.payload[offset..])?;
            let length = (usize::from(attribute.length()) + 3) & !3;
            if length > self.payload.len() - offset {
                return Err("truncated routing rule attribute padding".into());
            }
            // FRA_TUN_ID is a big-endian u64; the published packet decoder
            // still expects u32. Preserve it as an opaque NLA for projection.
            let parsed = if attribute.kind() == FRA_TUN_ID {
                if attribute.value().len() != 8 {
                    return Err("invalid FRA_TUN_ID length".into());
                }
                RuleAttribute::Other(DefaultNla::parse(&attribute)?)
            } else {
                RuleAttribute::parse(&attribute)?
            };
            rule.attributes.push(parsed);
            offset += length;
        }
        Ok(rule)
    }

    fn normalize_for_replay(
        &mut self,
        header: &RuleHeader,
        missing_priority: bool,
    ) {
        let mut flags = header.flags;
        flags.remove(
            RuleFlags::Unresolved
                | RuleFlags::IifDetached
                | RuleFlags::OifDetached,
        );
        self.payload[8..12].copy_from_slice(&flags.bits().to_ne_bytes());
        if missing_priority {
            // Dumps omit priority zero; replay must select it explicitly.
            let priority = RuleAttribute::Priority(0);
            let offset = self.payload.len();
            self.payload.resize(offset + priority.buffer_len(), 0);
            priority.emit(&mut self.payload[offset..]);
        }
    }

    fn into_netlink(self) -> NetlinkMessage<Self> {
        NetlinkMessage::new(
            NetlinkHeader::default(),
            NetlinkPayload::InnerMessage(self),
        )
    }
}

/// Raw snapshot of the complete affected priority groups, journaled before
/// execution. Valid only on the same host and network namespace, with rule
/// writers serialized. Identical rules have no instance identifiers, so an
/// identical replacement is indistinguishable from a restored original.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub(crate) struct RouteRuleRemoval {
    version: u32,
    groups: Vec<RuleGroup>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct RuleGroup {
    family: u8,
    priority: u32,
    rules: Vec<SelectedRule>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    rollback_rules: Option<Vec<RawRuleMessage>>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    introduced_rules: Vec<RawRuleMessage>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct SelectedRule {
    raw: RawRuleMessage,
    remove: bool,
}

impl RuleGroup {
    fn key(&self) -> (u8, u32) {
        (self.family, self.priority)
    }

    fn baseline(&self) -> Vec<RawRuleMessage> {
        self.rules.iter().map(|rule| rule.raw.clone()).collect()
    }

    fn rollback_baseline(&self) -> Vec<RawRuleMessage> {
        self.rollback_rules
            .clone()
            .unwrap_or_else(|| self.baseline())
    }

    fn restore_allowance(&self) -> Vec<RawRuleMessage> {
        let mut allowed = self.rollback_baseline();
        allowed.extend(self.introduced_rules.iter().cloned());
        allowed
    }

    fn restore_target(&self, live: &[RawRuleMessage]) -> Vec<RawRuleMessage> {
        let mut target = self.rollback_baseline();
        target.extend(surplus_rules(&self.restore_allowance(), live));
        target
    }
}

impl<'de> Deserialize<'de> for RouteRuleRemoval {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        #[derive(Deserialize)]
        #[serde(deny_unknown_fields)]
        struct Journal {
            version: u32,
            groups: Vec<RuleGroup>,
        }

        let journal = Journal::deserialize(deserializer)?;
        let plan = Self {
            version: journal.version,
            groups: journal.groups,
        };
        plan.validate().map_err(serde::de::Error::custom)?;
        Ok(plan)
    }
}

impl RouteRuleRemoval {
    /// Snapshot the complete priority groups containing selected rules.
    pub async fn prepare<F>(
        mut selector: F,
    ) -> Result<Self, RouteRuleRemoveError>
    where
        F: FnMut(&RouteRule) -> bool,
    {
        Self::prepare_with_projection(|rule, _| selector(rule)).await
    }

    /// Prepare removals whose recovery restores `baseline`, captured with
    /// `Self::prepare(|_| true)` at transaction start. Records introduced
    /// after `baseline` are never restored.
    pub async fn prepare_with_baseline<F>(
        baseline: &Self,
        selector: F,
    ) -> Result<Self, RouteRuleRemoveError>
    where
        F: FnMut(&RouteRule) -> bool,
    {
        baseline.validate()?;
        let mut plan = Self::prepare(selector).await?;
        plan.set_rollback_baseline(baseline);
        plan.validate()?;
        Ok(plan)
    }

    fn set_rollback_baseline(&mut self, baseline: &Self) {
        for group in &mut self.groups {
            let original = baseline
                .groups
                .iter()
                .find(|original| original.key() == group.key())
                .map(RuleGroup::rollback_baseline)
                .unwrap_or_default();
            group.introduced_rules =
                surplus_rules(&original, &group.baseline());
            group.rollback_rules = Some(original);
        }
    }

    /// Like [`Self::prepare`], but the selector's second argument is false
    /// when the kernel record has fields [`RouteRule`] cannot represent, so
    /// equality with another owner's rule cannot be established.
    pub async fn prepare_with_projection<F>(
        mut selector: F,
    ) -> Result<Self, RouteRuleRemoveError>
    where
        F: FnMut(&RouteRule, bool) -> bool,
    {
        with_rule_socket(|handle| async move {
            let mut groups = Vec::new();
            for ((family, priority), raw_rules) in dump_rules(&handle).await? {
                let mut rules = Vec::new();
                for raw in raw_rules {
                    let parsed = raw.parse().map_err(rule_netlink_error)?;
                    let projected = project_rule(&parsed);
                    let complete = projection_complete(&raw, &parsed)
                        && projected.is_complete();
                    rules.push(SelectedRule {
                        raw,
                        remove: selector(&projected.rule, complete),
                    });
                }
                if rules.iter().any(|rule| rule.remove) {
                    groups.push(RuleGroup {
                        family,
                        priority,
                        rules,
                        rollback_rules: None,
                        introduced_rules: Vec::new(),
                    });
                }
            }
            let plan = Self { version: 1, groups };
            plan.validate()?;
            Ok(plan)
        })
        .await
    }

    /// Whether the snapshot contains any rules selected for removal.
    pub fn is_empty(&self) -> bool {
        self.groups.is_empty()
    }

    /// Remove selected rules after verifying every affected group is unchanged.
    /// An error or a dropped future may leave partial changes; recover with
    /// [`Self::prepare_restore`] and [`Self::restore_prepared`].
    pub async fn execute(&self) -> Result<(), RouteRuleRemoveError> {
        self.validate()?;
        if self.is_empty() {
            return Ok(());
        }
        with_rule_socket(|handle| async move {
            let current = dump_rules(&handle).await?;
            self.check_current(&current)?;
            let mut changed = false;
            for group in &self.groups {
                let retained: Vec<_> = group
                    .rules
                    .iter()
                    .filter(|rule| !rule.remove)
                    .map(|rule| rule.raw.clone())
                    .collect();
                replace_group(
                    &handle,
                    &group.baseline(),
                    &retained,
                    &mut changed,
                )
                .await?;
            }
            Ok(())
        })
        .await
    }

    /// Capture later-added rules into the restore target. Journal the result
    /// before [`Self::restore_prepared`] so an interrupted restoration does
    /// not lose them.
    pub async fn prepare_restore(&self) -> Result<Self, RouteRuleRemoveError> {
        self.validate()?;
        if self.is_empty() {
            return Ok(self.clone());
        }
        with_rule_socket(|handle| async move {
            let current = dump_rules(&handle).await?;
            let mut plan = self.clone();
            for group in &mut plan.groups {
                let live =
                    current.get(&group.key()).map(Vec::as_slice).unwrap_or(&[]);
                group.rollback_rules = Some(group.restore_target(live));
            }
            Ok(plan)
        })
        .await
    }

    /// Restore original counts and order, retaining surplus live records.
    /// Idempotent once the target is present.
    #[cfg(test)]
    pub async fn restore(&self) -> Result<(), RouteRuleRemoveError> {
        self.validate()?;
        if self.is_empty() {
            return Ok(());
        }
        with_rule_socket(|handle| async move {
            let current = dump_rules(&handle).await?;
            let mut changed = false;
            for group in &self.groups {
                let live =
                    current.get(&group.key()).map(Vec::as_slice).unwrap_or(&[]);
                let restored = group.restore_target(live);
                if restored != live {
                    replace_group(&handle, live, &restored, &mut changed)
                        .await?;
                }
            }
            Ok(())
        })
        .await
    }

    /// Replay exactly the saved target after [`Self::prepare_restore`].
    /// Records introduced within the transaction are removed; any other
    /// unjournaled addition fails before mutation. Keep the journal on failure.
    pub async fn restore_prepared(&self) -> Result<(), RouteRuleRemoveError> {
        self.validate()?;
        if self.is_empty() {
            return Ok(());
        }
        with_rule_socket(|handle| async move {
            let current = dump_rules(&handle).await?;
            self.check_restore_current(&current)?;
            let mut changed = false;
            for group in &self.groups {
                let live =
                    current.get(&group.key()).map(Vec::as_slice).unwrap_or(&[]);
                let target = group.rollback_baseline();
                if target != live {
                    replace_group(&handle, live, &target, &mut changed).await?;
                }
            }
            Ok(())
        })
        .await
    }

    fn check_restore_current(
        &self,
        current: &RuleGroups,
    ) -> Result<(), RouteRuleRemoveError> {
        for group in &self.groups {
            let live =
                current.get(&group.key()).map(Vec::as_slice).unwrap_or(&[]);
            let allowed = group.restore_allowance();
            if !surplus_rules(&allowed, live).is_empty() {
                return Err(rule_netlink_error(
                    "routing rules added after restoration was prepared",
                ));
            }
        }
        Ok(())
    }

    fn check_current(
        &self,
        current: &RuleGroups,
    ) -> Result<(), RouteRuleRemoveError> {
        for group in &self.groups {
            if current.get(&group.key()) != Some(&group.baseline()) {
                return Err(rule_netlink_error(
                    "routing rules changed after removal was prepared",
                ));
            }
        }
        Ok(())
    }

    fn validate(&self) -> Result<(), RouteRuleRemoveError> {
        if self.version != 1 {
            return Err(rule_netlink_error(
                "unsupported routing rule snapshot version",
            ));
        }
        let mut previous = None;
        for group in &self.groups {
            if ![libc::AF_INET as u8, libc::AF_INET6 as u8]
                .contains(&group.family)
                || previous.is_some_and(|key| key >= group.key())
                || group.rules.is_empty()
                || !group.rules.iter().any(|rule| rule.remove)
            {
                return Err(rule_netlink_error(
                    "invalid routing rule snapshot group",
                ));
            }
            previous = Some(group.key());
            if (!group.introduced_rules.is_empty()
                && group.rollback_rules.is_none())
                || !surplus_rules(&group.baseline(), &group.introduced_rules)
                    .is_empty()
            {
                return Err(rule_netlink_error(
                    "invalid intermediate routing rule snapshot",
                ));
            }
            for raw in group
                .rules
                .iter()
                .map(|rule| &rule.raw)
                .chain(group.rollback_rules.iter().flatten())
                .chain(group.introduced_rules.iter())
            {
                if raw.message_type != libc::RTM_NEWRULE {
                    return Err(rule_netlink_error(
                        "invalid routing rule snapshot message type",
                    ));
                }
                let parsed = raw.parse().map_err(rule_netlink_error)?;
                let max_prefix = if group.family == libc::AF_INET as u8 {
                    32
                } else {
                    128
                };
                if parsed.header.action
                    == netlink_packet_route::rule::RuleAction::Unspec
                    || parsed.header.src_len > max_prefix
                    || parsed.header.dst_len > max_prefix
                {
                    return Err(rule_netlink_error(
                        "invalid routing rule snapshot header",
                    ));
                }
                if parsed
                    .attributes
                    .iter()
                    .filter(|attr| matches!(attr, RuleAttribute::Priority(_)))
                    .count()
                    != 1
                {
                    return Err(rule_netlink_error(
                        "snapshot rule must have one explicit priority",
                    ));
                }
                let mut normalized = raw.clone();
                let projected = prepare_rule(&mut normalized)?;
                if normalized != *raw
                    || u8::from(parsed.header.family) != group.family
                    || projected.priority != Some(group.priority)
                {
                    return Err(rule_netlink_error(
                        "invalid routing rule snapshot record",
                    ));
                }
            }
        }
        Ok(())
    }
}

/// Remove selected rules without a rollback snapshot. Unselected records keep
/// their selectors, duplicate counts and order.
#[cfg(test)]
async fn remove_route_rules<F>(selector: F) -> Result<(), RouteRuleRemoveError>
where
    F: FnMut(&RouteRule) -> bool,
{
    RouteRuleRemoval::prepare(selector).await?.execute().await
}

async fn with_rule_socket<T, F, Fut>(
    operation: F,
) -> Result<T, RouteRuleRemoveError>
where
    F: FnOnce(ConnectionHandle<RawRuleMessage>) -> Fut,
    Fut: std::future::Future<Output = Result<T, RouteRuleRemoveError>>,
{
    let (mut connection, handle, _) =
        new_connection::<RawRuleMessage>(NETLINK_ROUTE)
            .map_err(rule_netlink_error)?;
    connection.set_forward_done(true);
    connection.set_forward_ack(true);
    let operation = std::pin::pin!(operation(handle));
    match select(operation, connection).await {
        Either::Left((result, _)) => result,
        Either::Right(_) => {
            Err(rule_netlink_error("kernel rule connection closed"))
        }
    }
}

type RuleGroups = BTreeMap<(u8, u32), Vec<RawRuleMessage>>;

async fn dump_rules(
    handle: &ConnectionHandle<RawRuleMessage>,
) -> Result<RuleGroups, RouteRuleRemoveError> {
    let mut groups = BTreeMap::<_, Vec<_>>::new();
    for family in [
        netlink_packet_route::AddressFamily::Inet,
        netlink_packet_route::AddressFamily::Inet6,
    ] {
        let header = RuleHeader {
            family,
            ..Default::default()
        };
        let mut payload = vec![0; header.buffer_len()];
        header.emit(&mut payload);
        let mut request = RawRuleMessage {
            message_type: libc::RTM_GETRULE,
            payload,
        }
        .into_netlink();
        request.header.flags = NLM_F_REQUEST | NLM_F_DUMP;
        let mut responses = handle
            .request(request, SocketAddr::new(0, 0))
            .map_err(rule_netlink_error)?;
        let mut done = false;
        while let Some(response) = responses.next().await {
            if response.header.flags & NLM_F_DUMP_INTR != 0 {
                return Err(rule_netlink_error(
                    "kernel rule dump was interrupted",
                ));
            }
            let mut raw = match response.payload {
                NetlinkPayload::InnerMessage(raw)
                    if raw.message_type == libc::RTM_NEWRULE =>
                {
                    raw
                }
                NetlinkPayload::Done(message) if message.code == 0 => {
                    done = true;
                    continue;
                }
                NetlinkPayload::Error(error) => {
                    return Err(rule_netlink_error(error));
                }
                _ => {
                    return Err(rule_netlink_error(
                        "invalid kernel rule dump response",
                    ));
                }
            };
            let projected = prepare_rule(&mut raw)?;
            if projected.address_family != family.into() {
                return Err(rule_netlink_error(
                    "unexpected family in kernel rule dump",
                ));
            }
            let key = (u8::from(family), projected.priority.unwrap_or(0));
            groups.entry(key).or_default().push(raw);
        }
        if !done {
            return Err(rule_netlink_error("incomplete kernel rule dump"));
        }
    }
    Ok(groups)
}

fn surplus_rules(
    baseline: &[RawRuleMessage],
    live: &[RawRuleMessage],
) -> Vec<RawRuleMessage> {
    let mut unmatched = std::collections::HashMap::new();
    for rule in baseline {
        *unmatched.entry(rule).or_insert(0usize) += 1;
    }
    live.iter()
        .filter(|rule| match unmatched.get_mut(rule) {
            Some(count) if *count > 0 => {
                *count -= 1;
                false
            }
            _ => true,
        })
        .cloned()
        .collect()
}

#[cfg(test)]
fn restore_rules(
    baseline: &[RawRuleMessage],
    live: &[RawRuleMessage],
) -> Vec<RawRuleMessage> {
    let mut restored = baseline.to_vec();
    restored.extend(surplus_rules(baseline, live));
    restored
}

async fn replace_group(
    handle: &ConnectionHandle<RawRuleMessage>,
    current: &[RawRuleMessage],
    target: &[RawRuleMessage],
    changed: &mut bool,
) -> Result<(), RouteRuleRemoveError> {
    // Delete in dump order: omitted selectors can match later records.
    // Rebuild the priority group to preserve survivors and their ordering.
    for rule in current {
        if let Err(error) = update_kernel_rule(handle, rule, false).await {
            if let rtnetlink::Error::NetlinkError(ref error) = error
                && error.to_io().raw_os_error() == Some(libc::ENOENT)
            {
                continue;
            }
            return Err(mutation_error(error, *changed));
        }
        *changed = true;
    }
    for rule in target {
        update_kernel_rule(handle, rule, true)
            .await
            .map_err(|error| mutation_error(error, *changed))?;
        *changed = true;
    }
    Ok(())
}

fn projection_complete(raw: &RawRuleMessage, parsed: &RuleMessage) -> bool {
    if raw.payload[5] != 0 || raw.payload[6] != 0 {
        return false;
    }
    let mut offset = parsed.header.buffer_len();
    while offset < raw.payload.len() {
        let kind = u16::from_ne_bytes([
            raw.payload[offset + 2],
            raw.payload[offset + 3],
        ]);
        if kind & 0xc000 != 0 {
            return false;
        }
        let length =
            u16::from_ne_bytes([raw.payload[offset], raw.payload[offset + 1]]);
        offset += (usize::from(length) + 3) & !3;
    }
    let mut seen = std::collections::BTreeSet::new();
    for attr in &parsed.attributes {
        if !seen.insert(attr.kind())
            || !(matches!(
                attr,
                RuleAttribute::Destination(_)
                    | RuleAttribute::Source(_)
                    | RuleAttribute::Iifname(_)
                    | RuleAttribute::Goto(_)
                    | RuleAttribute::Priority(_)
                    | RuleAttribute::FwMark(_)
                    | RuleAttribute::FwMask(_)
                    | RuleAttribute::Realm(_)
                    | RuleAttribute::SuppressIfGroup(_)
                    | RuleAttribute::SuppressPrefixLen(_)
                    | RuleAttribute::Table(_)
                    | RuleAttribute::Oifname(_)
                    | RuleAttribute::L3MDev(_)
                    | RuleAttribute::Protocol(_)
                    | RuleAttribute::IpProtocol(_)
            ) || matches!(attr, RuleAttribute::Other(nla) if nla.kind() & 0x3fff == FRA_TUN_ID))
        {
            return false;
        }
    }
    (parsed.header.src_len == 0
        || parsed
            .attributes
            .iter()
            .any(|attr| matches!(attr, RuleAttribute::Source(_))))
        && (parsed.header.dst_len == 0
            || parsed
                .attributes
                .iter()
                .any(|attr| matches!(attr, RuleAttribute::Destination(_))))
}

struct RuleProjection {
    rule: RouteRule,
    tunnel_id: Option<u64>,
    complete: bool,
}

impl RuleProjection {
    fn is_complete(&self) -> bool {
        self.complete
            && self.tunnel_id.is_none_or(|id| u32::try_from(id).is_ok())
    }
}

fn project_rule(message: &RuleMessage) -> RuleProjection {
    let mut rule = RouteRule::default();
    rule.address_family = message.header.family.into();
    rule.tos = message.header.tos;
    rule.action = message.header.action.into();
    rule.flags = message
        .header
        .flags
        .iter()
        .map(|flag| match flag {
            RuleFlags::Permanent => nispor::RouteRuleFlag::Permanent,
            RuleFlags::Invert => nispor::RouteRuleFlag::Invert,
            RuleFlags::Unresolved => nispor::RouteRuleFlag::Unresolved,
            RuleFlags::IifDetached => nispor::RouteRuleFlag::IifDetached,
            RuleFlags::OifDetached => nispor::RouteRuleFlag::OifDetached,
            other => nispor::RouteRuleFlag::Other(other.bits()),
        })
        .collect();
    if message.header.table != 0 {
        rule.table = Some(u32::from(message.header.table));
    }
    let mut tunnel_id = None;
    let mut complete = true;
    for attr in &message.attributes {
        match attr {
            RuleAttribute::Destination(address) => {
                rule.dst = Some(format!("{address}/{}", message.header.dst_len))
            }
            RuleAttribute::Source(address) => {
                rule.src = Some(format!("{address}/{}", message.header.src_len))
            }
            RuleAttribute::Iifname(name) => rule.iif = Some(name.clone()),
            RuleAttribute::Oifname(name) => rule.oif = Some(name.clone()),
            RuleAttribute::Goto(value) => rule.goto = Some(*value),
            RuleAttribute::Priority(value) => rule.priority = Some(*value),
            RuleAttribute::FwMark(value) => rule.fw_mark = Some(*value),
            RuleAttribute::FwMask(value) => rule.fw_mask = Some(*value),
            RuleAttribute::Realm(value) => rule.realm = Some((*value).into()),
            RuleAttribute::SuppressIfGroup(value) => {
                rule.suppress_ifgroup = (*value != u32::MAX).then_some(*value)
            }
            RuleAttribute::SuppressPrefixLen(value) => {
                rule.suppress_prefix_len =
                    (*value != u32::MAX).then_some(*value)
            }
            RuleAttribute::Table(value) if *value != 0 => {
                rule.table = Some(*value)
            }
            RuleAttribute::Table(_) => (),
            RuleAttribute::Protocol(value) => {
                rule.protocol = Some((*value).into())
            }
            RuleAttribute::IpProtocol(value) => {
                rule.ip_proto = Some((*value).into())
            }
            RuleAttribute::L3MDev(value) => rule.l3mdev = Some(*value),
            RuleAttribute::Other(value)
                if value.kind() & 0x3fff == FRA_TUN_ID =>
            {
                if value.value_len() == 8 {
                    let mut bytes = [0; 8];
                    value.emit_value(&mut bytes);
                    let value = u64::from_be_bytes(bytes);
                    tunnel_id = Some(value);
                    rule.tun_id = u32::try_from(value).ok();
                } else {
                    complete = false;
                }
            }
            _ => complete = false,
        }
    }
    RuleProjection {
        rule,
        tunnel_id,
        complete,
    }
}

fn prepare_rule(
    raw: &mut RawRuleMessage,
) -> Result<RouteRule, RouteRuleRemoveError> {
    let mut rule = raw.parse().map_err(rule_netlink_error)?;
    let missing_priority = !rule
        .attributes
        .iter()
        .any(|attribute| matches!(attribute, RuleAttribute::Priority(_)));
    if missing_priority {
        rule.attributes.push(RuleAttribute::Priority(0));
    }
    raw.normalize_for_replay(&rule.header, missing_priority);
    Ok(project_rule(&rule).rule)
}

async fn update_kernel_rule(
    handle: &ConnectionHandle<RawRuleMessage>,
    rule: &RawRuleMessage,
    add: bool,
) -> Result<(), rtnetlink::Error> {
    let mut raw = rule.clone();
    raw.message_type = if add {
        libc::RTM_NEWRULE
    } else {
        libc::RTM_DELRULE
    };
    let mut request = raw.into_netlink();
    // CREATE without EXCL preserves duplicate rule records.
    request.header.flags =
        NLM_F_REQUEST | NLM_F_ACK | if add { NLM_F_CREATE } else { 0 };
    let responses = handle
        .request(request, SocketAddr::new(0, 0))
        .map_err(|_| rtnetlink::Error::RequestFailed)?;
    check_acknowledgement(responses).await
}

async fn check_acknowledgement<S>(
    mut responses: S,
) -> Result<(), rtnetlink::Error>
where
    S: Stream<Item = NetlinkMessage<RawRuleMessage>> + Unpin,
{
    let mut acknowledged = false;
    while let Some(response) = responses.next().await {
        if let NetlinkPayload::Error(error) = response.payload {
            if error.code.is_some() {
                return Err(rtnetlink::Error::NetlinkError(error));
            }
            acknowledged = true;
        } else {
            return Err(rtnetlink::Error::RequestFailed);
        }
    }
    if acknowledged {
        Ok(())
    } else {
        Err(rtnetlink::Error::RequestFailed)
    }
}

fn rule_netlink_error(error: impl std::fmt::Display) -> RouteRuleRemoveError {
    RouteRuleRemoveError::Failed(NmstateError::new(
        ErrorKind::PluginFailure,
        format!("Failed to update routing rules: {error}"),
    ))
}

fn mutation_error(
    error: rtnetlink::Error,
    changed: bool,
) -> RouteRuleRemoveError {
    if let rtnetlink::Error::NetlinkError(ref netlink_error) = error
        && matches!(
            netlink_error.to_io().raw_os_error(),
            Some(libc::EPERM | libc::EACCES)
        )
    {
        let error =
            NmstateError::new(ErrorKind::PermissionError, error.to_string());
        if !changed {
            return RouteRuleRemoveError::PermissionDeniedBeforeChange(error);
        }
        return RouteRuleRemoveError::Failed(error);
    }
    rule_netlink_error(error)
}

#[cfg(test)]
mod tests {
    use std::num::NonZeroI32;

    use futures_util::stream;
    use netlink_packet_route::{AddressFamily, rule::RuleAction};
    use rtnetlink::packet_core::{DefaultNla, ErrorMessage};

    use super::*;

    fn tunnel_attribute(value: u64) -> RuleAttribute {
        RuleAttribute::Other(DefaultNla::new(
            FRA_TUN_ID,
            value.to_be_bytes().to_vec(),
        ))
    }

    fn raw_attributes(attributes: Vec<RuleAttribute>) -> RawRuleMessage {
        let mut rule = RuleMessage::default();
        rule.header.family = AddressFamily::Inet;
        rule.header.action = RuleAction::ToTable;
        rule.header.table = 10;
        rule.attributes = attributes;
        let mut payload = vec![0; rule.buffer_len()];
        rule.emit(&mut payload);
        RawRuleMessage {
            message_type: libc::RTM_NEWRULE,
            payload,
        }
    }

    #[test]
    fn tunnel_projection_preserves_big_endian_values_and_detects_overflow() {
        for value in [
            0,
            1,
            0x1234_5678,
            u32::MAX as u64,
            0x1_0000_0001,
            0x1234_5678_9abc_def0,
        ] {
            let raw = raw_attributes(vec![tunnel_attribute(value)]);
            let parsed = raw.parse().unwrap();
            let projected = project_rule(&parsed);
            assert_eq!(projected.tunnel_id, Some(value));
            assert_eq!(projected.rule.tun_id, u32::try_from(value).ok());
            assert_eq!(projected.is_complete(), value <= u32::MAX as u64);
            assert!(projection_complete(&raw, &parsed));
            let mut replayed = vec![0; parsed.buffer_len()];
            parsed.emit(&mut replayed);
            assert_eq!(replayed, raw.payload);
        }
    }

    #[test]
    fn tunnel_attribute_requires_eight_bytes_and_complete_padding() {
        for length in [0, 4, 7, 9, 12] {
            let mut raw = raw_attributes(vec![RuleAttribute::Other(
                DefaultNla::new(FRA_TUN_ID, vec![0; length]),
            )]);
            assert!(raw.parse().is_err(), "accepted length {length}");
            assert!(prepare_rule(&mut raw).is_err());
        }
        let mut raw = raw_attributes(vec![tunnel_attribute(1)]);
        raw.payload.pop();
        assert!(raw.parse().is_err());
    }

    #[test]
    fn tunnel_attribute_flags_and_duplicates_cannot_establish_ownership() {
        for flags in [0x4000, 0x8000, 0xc000] {
            let raw =
                raw_attributes(vec![RuleAttribute::Other(DefaultNla::new(
                    FRA_TUN_ID | flags,
                    7_u64.to_be_bytes().to_vec(),
                ))]);
            let parsed = raw.parse().unwrap();
            assert_eq!(project_rule(&parsed).tunnel_id, Some(7));
            assert!(!projection_complete(&raw, &parsed));
            let mut replayed = vec![0; parsed.buffer_len()];
            parsed.emit(&mut replayed);
            assert_eq!(replayed, raw.payload);
        }
        let raw =
            raw_attributes(vec![tunnel_attribute(7), tunnel_attribute(8)]);
        let parsed = raw.parse().unwrap();
        assert!(!projection_complete(&raw, &parsed));
        assert_eq!(parsed.attributes.len(), 2);
        assert_eq!(project_rule(&parsed).tunnel_id, Some(8));
    }

    #[cfg(target_endian = "little")]
    #[test]
    fn legacy_snapshot_fixture_preserves_complete_wire_format() {
        let saved: serde_json::Value =
            serde_json::from_str(include_str!("route_rule_v1.json")).unwrap();
        let plan: RouteRuleRemoval =
            serde_json::from_value(saved.clone()).unwrap();
        assert_eq!(serde_json::to_value(&plan).unwrap(), saved);
        assert_eq!(plan.groups[0].rollback_baseline().len(), 2);
        assert_eq!(plan.groups[0].introduced_rules.len(), 1);
        assert!(plan.groups[1].rollback_baseline().is_empty());
        for group in &plan.groups {
            for rule in &group.rules {
                let projected = project_rule(&rule.raw.parse().unwrap());
                assert_eq!(projected.tunnel_id, Some(0x1234_5678_9abc_def0));
                assert_eq!(projected.rule.tun_id, None);
                assert!(!projected.is_complete());
            }
        }
    }

    fn raw_rule(family: AddressFamily) -> RawRuleMessage {
        let mut rule = RuleMessage::default();
        rule.header.family = family;
        rule.header.table = 10;
        rule.header.action = RuleAction::ToTable;
        rule.attributes = vec![tunnel_attribute(0x1234_5678_9abc_def0)];
        let mut payload = vec![0; rule.buffer_len()];
        rule.emit(&mut payload);
        let unknown = DefaultNla::new(0x8000 | 4000, vec![0xab]);
        let offset = payload.len();
        payload.resize(offset + unknown.buffer_len(), 0);
        unknown.emit(&mut payload[offset..]);
        *payload.last_mut().unwrap() = 0xcd;
        RawRuleMessage {
            message_type: libc::RTM_NEWRULE,
            payload,
        }
    }

    fn error_ack(code: Option<i32>) -> NetlinkMessage<RawRuleMessage> {
        let mut error = ErrorMessage::default();
        error.code = code.and_then(NonZeroI32::new);
        NetlinkMessage::new(
            NetlinkHeader::default(),
            NetlinkPayload::Error(error),
        )
    }

    fn snapshot_rule(table: u8) -> RawRuleMessage {
        let mut raw = raw_rule(AddressFamily::Inet);
        raw.payload[4] = table;
        prepare_rule(&mut raw).unwrap();
        raw
    }

    fn snapshot() -> RouteRuleRemoval {
        RouteRuleRemoval {
            version: 1,
            groups: vec![RuleGroup {
                family: libc::AF_INET as u8,
                priority: 0,
                rules: vec![
                    SelectedRule {
                        raw: snapshot_rule(10),
                        remove: true,
                    },
                    SelectedRule {
                        raw: snapshot_rule(11),
                        remove: false,
                    },
                    SelectedRule {
                        raw: snapshot_rule(10),
                        remove: true,
                    },
                ],
                rollback_rules: None,
                introduced_rules: Vec::new(),
            }],
        }
    }

    #[test]
    fn projection_metadata_detects_hidden_selectors() {
        use netlink_packet_route::rule::{RulePortRange, RuleUidRange};

        let mut parsed = RuleMessage::default();
        parsed.header.family = AddressFamily::Inet;
        parsed.header.action = RuleAction::ToTable;
        parsed.header.table = 10;
        parsed.attributes = vec![RuleAttribute::Priority(0)];
        let to_raw = |rule: &RuleMessage| {
            let mut payload = vec![0; rule.buffer_len()];
            rule.emit(&mut payload);
            RawRuleMessage {
                message_type: libc::RTM_NEWRULE,
                payload,
            }
        };
        assert!(projection_complete(&to_raw(&parsed), &parsed));
        for attr in [
            RuleAttribute::UidRange(RuleUidRange {
                start: 1000,
                end: 2000,
            }),
            RuleAttribute::SourcePortRange(RulePortRange {
                start: 80,
                end: 80,
            }),
            RuleAttribute::DestinationPortRange(RulePortRange {
                start: 443,
                end: 443,
            }),
            RuleAttribute::Other(DefaultNla::new(4000, vec![1])),
            RuleAttribute::Priority(0),
        ] {
            let mut opaque = parsed.clone();
            opaque.attributes.push(attr);
            assert!(!projection_complete(&to_raw(&opaque), &opaque));
        }
        let mut raw = to_raw(&parsed);
        raw.payload[5] = 1;
        assert!(!projection_complete(&raw, &parsed));
        let mut raw = to_raw(&parsed);
        raw.payload[14..16].copy_from_slice(&(6_u16 | 0x8000).to_ne_bytes());
        assert!(!projection_complete(&raw, &parsed));
    }

    #[test]
    fn prepared_restore_rejects_surplus_before_rebuilding_any_group() {
        let plan = snapshot();
        let baseline = plan.groups[0].baseline();
        let key = plan.groups[0].key();
        for live in [Vec::new(), baseline[..1].to_vec(), baseline.clone()] {
            plan.check_restore_current(&BTreeMap::from([(key, live)]))
                .unwrap();
        }
        for live in [
            vec![snapshot_rule(12)],
            [baseline.clone(), vec![baseline[0].clone()]].concat(),
        ] {
            assert!(
                plan.check_restore_current(&BTreeMap::from([(key, live)]))
                    .is_err()
            );
        }
        plan.check_restore_current(&BTreeMap::new()).unwrap();
    }

    #[test]
    fn transaction_baseline_excludes_intermediate_rules_even_while_still_live()
    {
        let initial = snapshot();
        let original = initial.groups[0].baseline();
        let intermediate = snapshot_rule(12);
        let external = snapshot_rule(13);
        let mut removal = snapshot();
        removal.groups[0].rules.push(SelectedRule {
            raw: intermediate.clone(),
            remove: true,
        });
        removal.set_rollback_baseline(&initial);
        removal.validate().unwrap();
        let group = &removal.groups[0];
        assert_eq!(group.rollback_baseline(), original);
        assert_eq!(group.introduced_rules, vec![intermediate.clone()]);
        removal
            .check_current(&BTreeMap::from([(group.key(), group.baseline())]))
            .unwrap();
        assert_eq!(group.restore_target(&[]), original);
        assert_eq!(
            group.restore_target(std::slice::from_ref(&intermediate)),
            original
        );

        let mut expected = original.clone();
        expected.push(external.clone());
        let mut restoration = removal.clone();
        restoration.groups[0].rollback_rules = Some(
            group.restore_target(&[intermediate.clone(), external.clone()]),
        );
        let restoration: RouteRuleRemoval =
            serde_json::from_str(&serde_json::to_string(&restoration).unwrap())
                .unwrap();
        let restored_group = &restoration.groups[0];
        assert_eq!(restored_group.rollback_baseline(), expected);
        restoration
            .check_restore_current(&BTreeMap::from([(
                restored_group.key(),
                vec![intermediate, external.clone()],
            )]))
            .unwrap();
        assert_eq!(restored_group.restore_target(&[external]), expected);
        assert!(
            !restored_group
                .rollback_baseline()
                .contains(&snapshot_rule(12))
        );
    }

    #[test]
    fn transaction_baseline_supports_originally_empty_groups() {
        let initial = RouteRuleRemoval {
            version: 1,
            groups: Vec::new(),
        };
        let mut removal = snapshot();
        removal.set_rollback_baseline(&initial);
        removal.validate().unwrap();
        let group = &removal.groups[0];
        assert!(group.rollback_baseline().is_empty());
        assert_eq!(group.introduced_rules, group.baseline());
        assert!(group.restore_target(&group.baseline()).is_empty());
        removal
            .check_restore_current(&BTreeMap::from([(
                group.key(),
                group.baseline(),
            )]))
            .unwrap();
        let restored: RouteRuleRemoval =
            serde_json::from_str(&serde_json::to_string(&removal).unwrap())
                .unwrap();
        assert!(restored.groups[0].rollback_baseline().is_empty());
        assert_eq!(
            restored.groups[0].restore_target(&[snapshot_rule(13)]),
            vec![snapshot_rule(13)]
        );
    }

    #[test]
    fn intermediate_duplicate_allowance_is_counted_and_validated() {
        let initial = snapshot();
        let mut removal = snapshot();
        let duplicate = removal.groups[0].rules[0].clone();
        removal.groups[0].rules.push(duplicate);
        removal.set_rollback_baseline(&initial);
        removal.validate().unwrap();
        let group = &removal.groups[0];
        assert_eq!(group.introduced_rules, vec![snapshot_rule(10)]);
        assert_eq!(
            group.restore_target(&group.baseline()),
            initial.groups[0].baseline()
        );
        let mut invalid = serde_json::to_value(&removal).unwrap();
        invalid["groups"][0]["introduced_rules"] = serde_json::json!([
            { "message_type": libc::RTM_NEWRULE, "payload": snapshot_rule(13).payload }
        ]);
        assert!(serde_json::from_value::<RouteRuleRemoval>(invalid).is_err());
        let mut invalid = serde_json::to_value(&removal).unwrap();
        invalid["groups"][0]["rollback_rules"][0]["message_type"] =
            serde_json::json!(libc::RTM_DELRULE);
        assert!(serde_json::from_value::<RouteRuleRemoval>(invalid).is_err());
    }

    #[test]
    fn snapshot_roundtrip_preserves_raw_records_and_selection() {
        let plan = snapshot();
        plan.validate().unwrap();
        let json = serde_json::to_string(&plan).unwrap();
        let restored: RouteRuleRemoval = serde_json::from_str(&json).unwrap();
        assert_eq!(restored, plan);
        assert!(!restored.is_empty());
        assert_eq!(
            restored.groups[0].rules[0].raw.payload,
            snapshot_rule(10).payload
        );
        let empty = RouteRuleRemoval {
            version: 1,
            groups: Vec::new(),
        };
        assert!(
            serde_json::from_str::<RouteRuleRemoval>(
                &serde_json::to_string(&empty).unwrap()
            )
            .unwrap()
            .is_empty()
        );
    }

    #[test]
    fn snapshot_deserialization_rejects_invalid_version_groups_and_records() {
        let valid = serde_json::to_value(snapshot()).unwrap();
        let mut invalid = Vec::new();
        for (field, value) in [
            ("version", serde_json::json!(2)),
            ("unexpected", serde_json::json!(true)),
        ] {
            let mut json = valid.clone();
            json[field] = value;
            invalid.push(json);
        }
        for (field, value) in [
            ("family", serde_json::json!(libc::AF_UNIX)),
            ("family", serde_json::json!(libc::AF_INET6)),
            ("priority", serde_json::json!(1)),
            ("rules", serde_json::json!([])),
        ] {
            let mut json = valid.clone();
            json["groups"][0][field] = value;
            invalid.push(json);
        }
        let mut json = valid.clone();
        json["groups"]
            .as_array_mut()
            .unwrap()
            .push(valid["groups"][0].clone());
        invalid.push(json);
        let mut json = valid.clone();
        for rule in json["groups"][0]["rules"].as_array_mut().unwrap() {
            rule["remove"] = serde_json::json!(false);
        }
        invalid.push(json);
        let mut json = valid.clone();
        json["groups"][0]["rules"][0]["raw"]["message_type"] =
            serde_json::json!(libc::RTM_DELRULE);
        invalid.push(json);
        for payload in [
            vec![0; 11],
            raw_rule(AddressFamily::Inet).payload,
            {
                let mut raw = snapshot_rule(10);
                raw.payload[1] = 33;
                raw.payload
            },
            {
                let mut raw = snapshot_rule(10);
                raw.payload[7] = 0;
                raw.payload
            },
            {
                let mut raw = snapshot_rule(10);
                raw.payload[8..12].copy_from_slice(
                    &RuleFlags::Unresolved.bits().to_ne_bytes(),
                );
                raw.payload
            },
            {
                let mut raw = snapshot_rule(10);
                let priority = RuleAttribute::Priority(0);
                let offset = raw.payload.len();
                raw.payload.resize(offset + priority.buffer_len(), 0);
                priority.emit(&mut raw.payload[offset..]);
                raw.payload
            },
        ] {
            let mut json = valid.clone();
            json["groups"][0]["rules"][0]["raw"]["payload"] =
                serde_json::json!(payload);
            invalid.push(json);
        }
        for json in invalid {
            assert!(
                serde_json::from_value::<RouteRuleRemoval>(json.clone())
                    .is_err(),
                "accepted invalid snapshot: {json}"
            );
        }
    }

    #[test]
    fn snapshot_revalidation_checks_counts_order_and_every_group() {
        let plan = snapshot();
        let baseline = plan.groups[0].baseline();
        let key = plan.groups[0].key();
        let current = BTreeMap::from([(key, baseline.clone())]);
        plan.check_current(&current).unwrap();
        for changed in [
            Vec::new(),
            baseline[..2].to_vec(),
            vec![
                baseline[0].clone(),
                baseline[2].clone(),
                baseline[1].clone(),
            ],
            [baseline.clone(), vec![snapshot_rule(12)]].concat(),
        ] {
            assert!(
                plan.check_current(&BTreeMap::from([(key, changed)]))
                    .is_err()
            );
        }
        assert!(plan.check_current(&BTreeMap::new()).is_err());
        let mut unrelated = current;
        unrelated.insert((libc::AF_INET6 as u8, 1000), Vec::new());
        plan.check_current(&unrelated).unwrap();
    }

    #[test]
    fn restore_merges_original_order_duplicate_counts_and_live_surplus() {
        let a = snapshot_rule(10);
        let b = snapshot_rule(11);
        let c = snapshot_rule(12);
        let d = snapshot_rule(13);
        let baseline = vec![a.clone(), b.clone(), a.clone()];
        let live = vec![
            a.clone(),
            c.clone(),
            b.clone(),
            a.clone(),
            d.clone(),
            a.clone(),
            c.clone(),
        ];
        let expected =
            vec![a.clone(), b.clone(), a, c.clone(), d, snapshot_rule(10), c];
        assert_eq!(restore_rules(&baseline, &live), expected);
        assert_eq!(restore_rules(&baseline, &expected), expected);
        assert_eq!(restore_rules(&baseline, &[b]), baseline);
        assert_eq!(restore_rules(&baseline, &[]), baseline);
    }

    #[test]
    fn journaled_restore_recovers_every_partial_delete_and_replay_prefix() {
        let baseline = snapshot().groups[0].baseline();
        let live =
            vec![baseline[1].clone(), snapshot_rule(12), snapshot_rule(12)];
        let saved_target = restore_rules(&baseline, &live);
        for removed in 0..=live.len() {
            assert_eq!(
                restore_rules(&saved_target, &live[removed..]),
                saved_target
            );
        }
        for replayed in 0..=saved_target.len() {
            assert_eq!(
                restore_rules(&saved_target, &saved_target[..replayed]),
                saved_target
            );
        }
    }

    #[test]
    fn raw_rule_roundtrip_preserves_unknown_attributes_and_padding() {
        for family in [AddressFamily::Inet, AddressFamily::Inet6] {
            let raw = raw_rule(family);
            assert_eq!(
                project_rule(&raw.parse().unwrap()).tunnel_id,
                Some(0x1234_5678_9abc_def0)
            );
            let mut message = raw.clone().into_netlink();
            message.finalize();
            let mut bytes = vec![0; message.buffer_len()];
            message.serialize(&mut bytes);
            let decoded =
                NetlinkMessage::<RawRuleMessage>::deserialize(&bytes).unwrap();
            assert_eq!(decoded.payload, NetlinkPayload::InnerMessage(raw));
        }
    }

    #[test]
    fn zero_priority_is_explicit_before_selection_and_replay() {
        let mut raw = raw_rule(AddressFamily::Inet);
        let retained = RuleFlags::Invert | RuleFlags::from_bits_retain(1 << 31);
        let flags = retained
            | RuleFlags::Unresolved
            | RuleFlags::IifDetached
            | RuleFlags::OifDetached;
        raw.payload[8..12].copy_from_slice(&flags.bits().to_ne_bytes());
        let original = raw.payload.clone();

        let projected = prepare_rule(&mut raw).unwrap();
        assert_eq!(projected.priority, Some(0));
        assert_eq!(projected.tun_id, None);
        assert_eq!(
            project_rule(&raw.parse().unwrap()).tunnel_id,
            Some(0x1234_5678_9abc_def0)
        );
        assert_eq!(&raw.payload[..8], &original[..8]);
        assert_eq!(&raw.payload[12..original.len()], &original[12..]);
        let parsed = raw.parse().unwrap();
        assert_eq!(parsed.header.flags, retained);
        assert_eq!(parsed.attributes.last(), Some(&RuleAttribute::Priority(0)));

        let normalized = raw.clone();
        prepare_rule(&mut raw).unwrap();
        assert_eq!(raw, normalized);
    }

    #[test]
    fn malformed_rule_is_captured_and_rejected_explicitly() {
        let valid = raw_rule(AddressFamily::Inet);
        let mut missing_padding = valid.payload.clone();
        missing_padding.pop();
        let mut invalid_priority = valid.payload[..12].to_vec();
        invalid_priority.extend_from_slice(&6_u16.to_ne_bytes());
        invalid_priority.extend_from_slice(&6_u16.to_ne_bytes());
        invalid_priority.extend_from_slice(&[0; 4]);

        for payload in [vec![0; 11], missing_padding, invalid_priority] {
            let mut raw =
                <RawRuleMessage as NetlinkDeserializable>::deserialize(
                    &NetlinkHeader::default(),
                    &payload,
                )
                .unwrap();
            assert_eq!(raw.payload, payload);
            assert!(matches!(
                prepare_rule(&mut raw),
                Err(RouteRuleRemoveError::Failed(_))
            ));
        }
    }

    #[test]
    fn permission_fallback_requires_explicit_denial_before_change() {
        for code in [libc::EPERM, libc::EACCES] {
            let NetlinkPayload::Error(error) = error_ack(Some(-code)).payload
            else {
                unreachable!();
            };
            assert!(matches!(
                mutation_error(
                    rtnetlink::Error::NetlinkError(error.clone()),
                    false
                ),
                RouteRuleRemoveError::PermissionDeniedBeforeChange(_)
            ));
            assert!(matches!(
                mutation_error(rtnetlink::Error::NetlinkError(error), true),
                RouteRuleRemoveError::Failed(_)
            ));
        }
        assert!(matches!(
            mutation_error(rtnetlink::Error::RequestFailed, false),
            RouteRuleRemoveError::Failed(_)
        ));
        let NetlinkPayload::Error(error) =
            error_ack(Some(-libc::ENOENT)).payload
        else {
            unreachable!();
        };
        assert!(matches!(
            mutation_error(rtnetlink::Error::NetlinkError(error), false),
            RouteRuleRemoveError::Failed(_)
        ));
    }

    #[tokio::test]
    async fn mutation_requires_successful_acknowledgement() {
        assert!(
            check_acknowledgement(stream::iter(vec![error_ack(None)]))
                .await
                .is_ok()
        );
        for responses in [
            vec![],
            vec![raw_rule(AddressFamily::Inet).into_netlink()],
            vec![error_ack(Some(-libc::EPERM))],
        ] {
            assert!(
                check_acknowledgement(stream::iter(responses))
                    .await
                    .is_err()
            );
        }
    }
    #[tokio::test]
    #[ignore = "requires an isolated network namespace and CAP_NET_ADMIN"]
    async fn test_remove_route_rules_preserves_unselected_records() {
        use netlink_packet_route::{
            AddressFamily,
            rule::{RuleAction, RuleAttribute, RuleMessage},
        };

        let _cleanup = RuleRemovalTestCleanup;
        let mut rules = Vec::new();
        for family in [AddressFamily::Inet, AddressFamily::Inet6] {
            for priority in [1000, 0] {
                let mut rule = RuleMessage::default();
                rule.header.family = family;
                rule.header.action = RuleAction::ToTable;
                rule.attributes = vec![
                    RuleAttribute::Table(500),
                    RuleAttribute::Priority(priority),
                    RuleAttribute::FwMark(1),
                    RuleAttribute::FwMask(255),
                ];
                rules.push(rule.clone());
                rules.push(rule.clone());
                rule.attributes[2] = RuleAttribute::FwMark(0);
                rules.push(rule.clone());
                rule.attributes = vec![
                    RuleAttribute::Table(501),
                    RuleAttribute::Priority(priority),
                    tunnel_attribute(0x1_0000_0001),
                ];
                rules.push(rule);
            }
        }
        add_rule_removal_test_rules(rules).await;
        let before = kernel_rules_json();
        let expected: Vec<_> = before
            .iter()
            .filter(|rule| {
                kernel_rule_number(rule, "table") != Some(500)
                    || kernel_rule_number(rule, "fwmark") != Some(0)
            })
            .cloned()
            .collect();
        assert_eq!(before.len() - expected.len(), 4);
        assert_eq!(
            expected
                .iter()
                .filter(|rule| {
                    kernel_rule_number(rule, "fwmark") == Some(1)
                })
                .count(),
            8
        );
        assert_eq!(
            expected
                .iter()
                .filter(|rule| {
                    kernel_rule_number(rule, "tun_id") == Some(0x1_0000_0001)
                })
                .count(),
            4
        );
        for _ in 0..2 {
            remove_route_rules(|rule| {
                if rule.table == Some(501) {
                    assert_eq!(rule.tun_id, None);
                }
                let remove =
                    rule.table == Some(500) && rule.fw_mark.unwrap_or(0) == 0;
                if remove {
                    assert!(matches!(rule.priority, Some(0 | 1000)));
                    assert_eq!(rule.fw_mask, Some(255));
                }
                remove
            })
            .await
            .unwrap();
            assert_eq!(kernel_rules_json(), expected);
        }
        remove_route_rules(|rule| rule.table == Some(500))
            .await
            .unwrap();
        assert_eq!(
            kernel_rules_json(),
            expected
                .into_iter()
                .filter(|rule| {
                    kernel_rule_number(rule, "table") != Some(500)
                })
                .collect::<Vec<_>>()
        );
    }

    #[tokio::test]
    #[ignore = "requires an isolated network namespace and CAP_NET_ADMIN"]
    async fn test_route_rule_removal_journal_restores_raw_groups() {
        use netlink_packet_route::{
            AddressFamily,
            rule::{RuleAction, RuleAttribute, RuleMessage},
        };

        let _cleanup = RuleRemovalTestCleanup;
        let mut originals = Vec::new();
        let mut already_restored = Vec::new();
        let mut later = Vec::new();
        for family in [AddressFamily::Inet, AddressFamily::Inet6] {
            for priority in [0, 1000] {
                let mut rule = RuleMessage::default();
                rule.header.family = family;
                rule.header.action = RuleAction::ToTable;
                rule.attributes = vec![
                    RuleAttribute::Table(500),
                    RuleAttribute::Priority(priority),
                    RuleAttribute::FwMark(1),
                    RuleAttribute::FwMask(255),
                ];
                originals.extend([rule.clone(), rule.clone()]);
                already_restored.push(rule.clone());
                rule.attributes[2] = RuleAttribute::FwMark(0);
                originals.push(rule.clone());
                rule.attributes = vec![
                    RuleAttribute::Table(501),
                    RuleAttribute::Priority(priority),
                    tunnel_attribute(0x1_0000_0001),
                ];
                originals.push(rule.clone());
                rule.attributes.push(RuleAttribute::FwMark(7));
                later.extend([rule.clone(), rule]);
            }
            let mut unrelated = RuleMessage::default();
            unrelated.header.family = family;
            unrelated.header.action = RuleAction::ToTable;
            unrelated.attributes =
                vec![RuleAttribute::Table(501), RuleAttribute::Priority(2000)];
            later.push(unrelated);
        }
        add_rule_removal_test_rules(originals).await;
        let baseline = kernel_rules_json();
        let plan = RouteRuleRemoval::prepare(|rule| {
            rule.table == Some(500) && rule.fw_mark == Some(1)
        })
        .await
        .unwrap();
        let plan: RouteRuleRemoval =
            serde_json::from_str(&serde_json::to_string(&plan).unwrap())
                .unwrap();
        assert!(!plan.is_empty());
        plan.execute().await.unwrap();
        assert_eq!(
            kernel_rules_json(),
            baseline
                .iter()
                .filter(|rule| {
                    kernel_rule_number(rule, "table") != Some(500)
                        || kernel_rule_number(rule, "fwmark") != Some(1)
                })
                .cloned()
                .collect::<Vec<_>>()
        );

        add_rule_removal_test_rules(already_restored.clone()).await;
        add_rule_removal_test_rules(later).await;
        let changed = kernel_rules_json();
        assert!(plan.execute().await.is_err());
        assert_eq!(kernel_rules_json(), changed);

        let restoration = plan.prepare_restore().await.unwrap();
        let restoration: RouteRuleRemoval =
            serde_json::from_str(&serde_json::to_string(&restoration).unwrap())
                .unwrap();
        restoration.restore_prepared().await.unwrap();
        let expected = kernel_rules_json();
        assert_eq!(
            expected
                .iter()
                .filter(|rule| {
                    kernel_rule_number(rule, "fwmark") != Some(7)
                        && kernel_rule_number(rule, "priority") != Some(2000)
                })
                .cloned()
                .collect::<Vec<_>>(),
            baseline
        );
        assert_eq!(
            expected
                .iter()
                .filter(|rule| {
                    kernel_rule_number(rule, "fwmark") == Some(7)
                })
                .count(),
            8
        );
        restoration.restore_prepared().await.unwrap();
        assert_eq!(kernel_rules_json(), expected);

        // Reproduce interruption after draining the affected groups.
        remove_route_rules(|rule| {
            matches!(rule.table, Some(500 | 501))
                && matches!(rule.priority, Some(0 | 1000))
        })
        .await
        .unwrap();
        restoration.restore_prepared().await.unwrap();
        assert_eq!(kernel_rules_json(), expected);

        // Reproduce interruption after replaying only one of each
        // duplicate.
        remove_route_rules(|rule| {
            rule.table == Some(500) && rule.fw_mark == Some(1)
        })
        .await
        .unwrap();
        add_rule_removal_test_rules(already_restored).await;
        restoration.restore().await.unwrap();
        assert_eq!(kernel_rules_json(), expected);
    }

    async fn add_rule_removal_test_rules(rules: Vec<RuleMessage>) {
        with_rule_socket(|handle| async move {
            for rule in rules {
                let mut payload = vec![0; rule.buffer_len()];
                rule.emit(&mut payload);
                let raw = RawRuleMessage {
                    message_type: libc::RTM_NEWRULE,
                    payload,
                };
                update_kernel_rule(&handle, &raw, true)
                    .await
                    .map_err(rule_netlink_error)?;
            }
            Ok(())
        })
        .await
        .unwrap();
    }
    fn kernel_rules_json() -> Vec<serde_json::Value> {
        let mut rules = Vec::new();
        for family in ["-4", "-6"] {
            let output = std::process::Command::new("ip")
                .args([family, "-details", "-json", "rule"])
                .output()
                .unwrap();
            assert!(output.status.success());
            rules.extend(
                serde_json::from_slice::<Vec<serde_json::Value>>(
                    &output.stdout,
                )
                .unwrap(),
            );
        }
        rules
    }

    fn kernel_rule_number(rule: &serde_json::Value, key: &str) -> Option<u64> {
        match &rule[key] {
            serde_json::Value::Number(number) => number.as_u64(),
            serde_json::Value::String(number) => {
                if let Some(hex) = number.strip_prefix("0x") {
                    u64::from_str_radix(hex, 16).ok()
                } else {
                    number.parse().ok()
                }
            }
            _ => None,
        }
    }

    struct RuleRemovalTestCleanup;

    impl Drop for RuleRemovalTestCleanup {
        fn drop(&mut self) {
            for family in ["-4", "-6"] {
                for table in ["500", "501"] {
                    let _ = std::process::Command::new("ip")
                        .args([family, "rule", "flush", "table", table])
                        .status();
                }
            }
        }
    }
}
