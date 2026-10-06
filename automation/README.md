# Automation Environment
The automation env is serving the tests of Nmstate.
It may be used both locally and through CI.

## Components
- Container specifications to be used for the tests are in the `packaging`
  directory. The images are published on quay:
  https://quay.io/organization/nmstate

- run-tests.sh: Execute the tests in a container using
  'nmstate/fed-nmstate-dev' container image.

  The following steps are executed:
  - Run the container (defined in the Dockerfile) as a daemon.
  - Stop NetworkManager before adding additional networks (ifaces).
  - Add additonal networks (ifaces) to the container.
  - Start NetworkManager.
  - Execute all tests in the container.

  It also handles the cleanup of the container and nets (stop,rm).

## Running the Tests
Assuming *podman* is installed on the host, just run:
`./automation/run-tests.sh`

By default, `./automation/run-tests.sh` will run all tests in the container
using 'nmstate/fed-nmstate-dev' container image.
You may change the test type by specifying the `--test-type` flag, for example:

 * `./automation/run-tests.sh --test-type integ --el8`:
   Integration tests (without slow test cases) using
   'nmstate/c8s-nmstate-dev' container image.

 * `./automation/run-tests.sh --test-type integ`:
   Integration tests (without slow test cases) using
   'nmstate/fed-nmstate-dev' container image.

 * `./automation/run-tests.sh --test-type integ_tier1`:
   Integration tier1 test cases using `nmstate/fed-nmstate-dev` container
   image.

 * `./automation/run-tests.sh --test-type integ_tier2`:
   Integration tier2 test cases using `nmstate/fed-nmstate-dev` container
   image.

 * `./automation/run-tests.sh --test-type integ_kernel`:
   Integration kernel test cases using `nmstate/fed-nmstate-dev` container
   image.

 * `./automation/run-tests.sh --test-type integ_slow`:
   Integration slow test cases using `nmstate/fed-nmstate-dev` container
   image.

For a full list of command-line flags, run `./automation/run-tests.sh --help`.

## Development

### Run the tests manually in the container
For debugging, it is convenient to run the container and then connect to it in
order to run the tests. Setting the environment variable `debug_exit_shell`
will make the script start a shell instead of exiting the script after an error
or running the scripts:

`debug_exit_shell=1 ./automation/run-tests.sh`

After closing the shell, the container will be removed. Alternatively it is
possible to provide the `--debug-shell` command-line option.

To specify a different container image for the tests, specify it with the
`CONTAINER_IMAGE` variable:

`CONTAINER_IMAGE=local/c8s-nmstate-dev debug_exit_shell=1 ./automation/run-tests.sh`

`CONTAINER_IMAGE` overrides OS options such as `--el9`. If it is unset or
empty, the last OS option selects the image.

With `CI=true`, setup rebuilds the image when `packaging/` differs from
`BRANCH_NAME` (default: `base`) in `NMSTATE_REPO` (default:
`https://github.com/nmstate/nmstate.git`). The fetch leaves Git remotes unchanged.
Only `quay.io/nmstate/` images with a matching `packaging/Dockerfile.<name>`
can be rebuilt; with any other image, a `packaging/` difference fails setup.
Set `NMSTATE_SKIP_IMAGE_REBUILD=1` to pull the image without that Git check
or rebuild. This uses the CentOS Stream 9 image to build nmstate and run tier1
tests:

```shell
CI=true NMSTATE_SKIP_IMAGE_REBUILD=1 ./automation/run-tests.sh \
    --el9 --test-type integ_tier1
```

`NMSTATE_IPSEC_IMAGE` selects the IPsec server image and is passed into the test
container. It defaults to `quay.io/nmstate/test-env:libreswan-srv-c10s`. Both
image variables accept digests. To use a registry mirror, set both variables
to images already published there.

The test image needs the test dependencies and, with `--use-installed-nmstate`,
the nmstate packages to test. Source builds and COPR/DNF commands still use
their configured repositories, Rust dependencies and build tools. Setup stops
if the baseline fetch fails or all five attempts to pull the test image fail.
A failed IPsec image pull does not stop the session; IPsec tests still need
a usable image.

Run `python3 automation/test_container_sources.py` from the repository root
to check these options. It uses temporary Git repositories and stubbed
container/build commands, without root or network access.

It is also possible to pass extra arguments to PDB using the
`nmstate_pytest_extra_args` variable or via `--pytest-args` command-line
option, for example:

`nmstate_pytest_extra_args="--pdb -x" ./automation/run-tests.sh`

or:

`./automation/run-tests.sh --pytest-args "--pdb -x"`

### Build a new container image

```
../packaging/build-container.sh local/c8s-nmstate-dev
../packaging/build-container.sh local/fed-nmstate-dev
```

To test the image, either specify it manually as described above or tag it locally:

```
podman tag local/c8s-nmstate-dev quay.io/nmstate/c8s-nmstate-dev:latest
podman tag local/fed-nmstate-dev quay.io/nmstate/fed-nmstate-dev:latest
```

### Push local image to Quay

The container images are automatically rebuilt for new commits to the base
branch or new tags. Therefore updates to the quay images should always
happen with a pull request that is merged to ensure that the change is
persistent. If this is not feasible, a new build could be pushed as follow to
quay.io:

```shell
podman login quay.io
podman tag local/c8s-nmstate-dev nmstate/c8s-nmstate-dev:latest
podman push nmstate/c8s-nmstate-dev:latest \
    quay.io/nmstate/c8s-nmstate-dev:latest

podman tag local/fed-nmstate-dev nmstate/fed-nmstate-dev:latest
podman push nmstate/fed-nmstate-dev:latest \
    quay.io/nmstate/fed-nmstate-dev:latest
```

It will be overwritten after the next commit to base, though.


### Test in bare-metal OS for InfiniBand

In order to perform integration test cases against InfiniBand feature,
running test in bare-metal OS is required.

Assuming the InfiniBand card is listed in `ip link` as `mlx5_ib0` and been
configured as `datagram` mode.

```shell
sudo dnf install `./packaging/make_rpm.sh|tail -1`

sudo ip netns add tmp
sudo ip link add eth1 type veth peer name eth1peer
sudo ip link add eth2 type veth peer name eth2peer
sudo ip link set eth1 up
sudo ip link set eth2 up
sudo ip link set eth1peer netns tmp
sudo ip link set eth2peer netns tmp
sudo ip netns exec tmp ip link set eth1peer up
sudo ip netns exec tmp ip link set eth2peer up

sudo nmcli device set eth1 managed yes
sudo nmcli device set eth2 managed yes

cd tests/integration
# Set TEST_IB_CONNECTED_MODE=1 when cards are configured as connected mode
sudo env TEST_REAL_NIC=mlx5_ib0 pytest-3 -vv  ./infiniband_test.py
```
