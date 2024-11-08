# Title: ADR-001: Differentiate NetworkState and NetworkPolicy

## Status: Accepted

## Context

Many feature request could be done by either via nmpolicy(`NetworkPolicy`) or
via nmstate(`NetworkState`). Hence we need a policy on when to suggest user
to use `NetworkPolicy` and when to expand `NetworkState`.

## Decision

The design principles of `NetworkState`(aka nmstate) are:
 * Describe use case in final state form.
 * Idempotent
 * Apply state should be identical(except cosmetic clean up) to post applied
   current state
 * No information lose when converting between native language use case and
   `NetworkState` YAML/JSON file.

The design principles of `NetworkPolicy`(aka nmpolicy) are:
 * Only valid when bond with specified current `NetworkState`
 * Expressing a set of actions for generating the final `NetworkState`
 * Could not be idempotent

### Example
#### Use case

Create a active-backup bond interface bond0 with ethernet interface holding
`00:23:45:67:89:1a` and `00:23:45:67:89:1b`, regardless the changing NIC name
after kernel changes

#### Complainant approach

Expand `NetworkState` by adding `permananet-mac-address` and `iface-type` to
port settings of controllers, when applying, nmstate should instruct
network backend to make sure no interface name is hard coded in persistent
configurations.

With this approach, the same `NetworkState` YAML file could applied multiple
times because the `permananet-mac-address` are immutable to network
confirmation changes.

#### Bad approach

Instruct user to use `NetworkPolicy` with `capture` rule to find out the
interface name of `00:23:45:67:89:1a` and `00:23:45:67:89:1b`, then generate
a `NetworkState`.

With this approach, the final `NetworkState` has hard coded interface name
for bond port which is different from user's original desire.

## Consequences

### Better

Clear isolation of `NetworkState` and `NetworkPolicy`.

### Worse

* Extra developer effort required on planing a new feature.

## Enforcement

Once AI YAML converter can be trusted, a test case could be created to confirm
there is no information lose when converting use case to `NetworkState` YAML
and convert it back.

Maintainers' manual inspection is required to enforce this ADR by questioning
patch contributor when use case can be done by `NetworkPolicy`:
 * Why `NetworkPolicy` cannot express the use case?
 * Is the patch meet the above rules of `NetworkState`?

Considering only less than 1% of feature require of this evolution, it only
added limited amount of work to maintainers.
