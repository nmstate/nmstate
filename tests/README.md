# Nmstate integration tests

`tests/integration/` contains root-privileged pytest tests that apply nmstate
configuration to the running kernel and NetworkManager. Run them only in a
disposable VM or the project test container; they are not safe for a developer
workstation and must not run in parallel.

This document contains some tips and insights about the tests.

## Running tests

The recommended entry point is:

```sh
./automation/run-tests.sh --test-type integ
```

Other test types are `integ_tier1`, `integ_tier2`, `integ_slow`, and
`integ_kernel`. Use `--pytest-args "-k TEST_NAME"` to select a test or pass
other pytest options. See `automation/run-tests.sh --help` and
[`automation/README.md`](../automation/README.md).

In an already prepared VM, tests can be run directly as root:

```sh
sudo pytest tests/integration/linux_bridge_test.py::test_create_and_remove_linux_bridge_with_one_port
```

See [`CONTRIBUTING.md`](../CONTRIBUTING.md#running-the-integration-tests) when
testing a build from the repository rather than an installed nmstate package.

## Writing tests

- Request `eth1_up`/`eth2_up`, or their generic aliases
  `port0_up`/`port1_up`, for clean test interfaces. `eth3_up` is provisioned
  lazily for tests that need a third interface.
- Use the context managers in `tests/integration/testlib/` to create bonds,
  bridges, VLANs, dummy interfaces, and other network constructs. They apply
  the desired state and remove it on exit, including after a failure.
- Build fixtures from those context managers with `yield`; do not duplicate
  setup and teardown in each test.
- Use `assert_state()` for a normalized exact check, `assert_state_match()`
  for a partial check with retries, and `assert_absent()` after removal. All
  of these use `libnmstate.show()` underneath to retrieve the current state.
- Complex desired states may be expressed as inline YAML with `load_yaml()`.

A minimal lifecycle test looks like this:

```python
from .testlib.assertlib import assert_absent, assert_state
from .testlib.bridgelib import linux_bridge


def test_bridge_lifecycle():
    name = "test-br0"
    with linux_bridge(name, None) as desired_state:
        assert_state(desired_state)

    assert_absent(name)
```

Shared test setup restores the test interfaces and DNS between tests, but each
test remains responsible for cleaning up any resource it creates.

## Markers

- `tier1`: critical coverage selected by maintainers and adopters. New tier 1
  tests require a link to the motivating GitHub, Jira, or other tracked issue.
- `tier2`: the default; tests not marked `tier1` or `kernel` receive it
  automatically.
- `slow`: skipped unless pytest is given `--runslow`.
- `kernel`: tests for the kernel-only backend.
