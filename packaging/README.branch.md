# Branch maintaining

## The `master` branch

The `master` branch contains features and bug fixes since last tagged release.

## The `stable_v<x.y.z>` branch

This branch contains bug fixes since `v<x.y.z>` release.
For example, the `stable_v0.0.8` will contains backported bug fix patches
since `v0.0.8` release.

This branch will be used for [Fedora nmstate copr repos][1] for stable build.

The patches backported to this branch requires:

 * Bug fix only.
 * Should be in `master` branch.
 * Github pull request is required.
 * Extra test fix patch can be also included in order to pass the CI.


[1]: https://copr.fedorainfracloud.org/coprs/nmstate
