# Automation Environment
The automation env is serving the tests of Nmstate.
It may be used both locally and through CI.

## Components
- Container specifications to be used for the tests are in the `packaging`
  directory. The images are published on docker hub:
  https://hub.docker.com/r/nmstate/

- run-tests.sh: Execute the tests in a container using
  'nmstate/fedora-nmstate-dev' container image.

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
using 'nmstate/fedora-nmstate-dev' container image.
You may change the test type by specifying the `--test-type` flag, for example:

 * `./automation/run-tests.sh --test-type integ --el8`:
   Integration tests (without slow test cases) using
   'nmstate/centos8-nmstate-dev' container image.

 * `./automation/run-tests.sh --test-type integ`:
   Integration tests (without slow test cases) using
   'nmstate/fedora-nmstate-dev' container image.

 * `./automation/run-tests.sh --test-type integ_slow`:
   Integration slow test cases using `nmstate/fedora-nmstate-dev` container
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

`CONTAINER_IMAGE=local/centos8-nmstate-dev debug_exit_shell=1 ./automation/run-tests.sh`

It is also possible to pass extra arguments to PDB using the
`nmstate_pytest_extra_args` variable or via `--pytest-args` command-line
option, for example:

`nmstate_pytest_extra_args="--pdb -x" ./automation/run-tests.sh`

or:

`./automation/run-tests.sh --pytest-args "--pdb -x"`

### Build a new container image

```
../packaging/build-container.sh local/centos8-nmstate-dev
../packaging/build-container.sh local/fedora-nmstate-dev
```

To test the image, either specify it manually as described above or tag it locally:

```
podman tag local/centos8-nmstate-dev docker.io/nmstate/centos8-nmstate-dev:latest
podman tag local/fedora-nmstate-dev docker.io/nmstate/fedora-nmstate-dev:latest
```

### Push local image to the docker hub
The container images are automatically rebuilt for new commits to the master
branch or new tags. Therefore updates to the Docker Hub images should always
happen with a pull request that is merged to ensure that the change is
persistent. If this is not feasible, a new build could be pushed as follow to
the Docker Hub:

```shell
podman login docker.io
podman tag local/centos8-nmstate-dev nmstate/centos8-nmstate-dev:latest
podman push nmstate/centos8-nmstate-dev:latest \
    docker://docker.io/nmstate/centos8-nmstate-dev:latest

podman tag local/fedora-nmstate-dev nmstate/fedora-nmstate-dev:latest
podman push nmstate/fedora-nmstate-dev:latest \
    docker://docker.io/nmstate/fedora-nmstate-dev:latest
```

It will be overwritten after the next commit to master, though.
