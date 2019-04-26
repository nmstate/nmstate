# Automation Environment
The automation env is serving the tests of Nmstate.
It may be used both locally and through CI.

## Components
- Dockerfile: Defines a Centos 7 based container image which includes systemd,
  NetworkManager and other basic build tools (e.g. tox).

  The image can be found at:
  https://hub.docker.com/r/nmstate/centos7-nmstate-dev/

- Dockerfile.fedora: Defines a Fedora based container image for Nmstate test
  purpose.

  The image can be found at:
  https://hub.docker.com/r/nmstate/fedora-nmstate-dev/

- run-tests.sh: Execute the tests in a container using
  'nmstate/fedora-nmstate-dev' docker image.

  The following steps are executed:
  - Run the container (defined in the Dockerfile) as a daemon.
  - Stop NetworkManager before adding additional networks (ifaces).
  - Add additonal networks (ifaces) to the container.
  - Start NetworkManager.
  - Execute all tests in the container.

  It also handles the cleanup of the container and nets (stop,rm).

- run-tests.mounts: Includes mounts to be used by the oVirt CI (STDCI) worker.

- run-tests.packages: Includes the packages needed by the oVirt CI (STDCI)
  worker.

- run-tests.environment.yaml: Instruct the oVirt CI (STDCI) to run
  integration test.

## Running the Tests
Assuming *docker* is installed on the host, just run:
`./automation/run-tests.sh`

By default, `./automation/run-tests.sh` will run all tests in the container
using 'nmstate/fedora-nmstate-dev' docker image.
You may change the test type by using:

 * `./automation/run-tests.sh --test-type lint`:
   Static analysis of code using 'nmstate/fedora-nmstate-dev' docker image.

 * `./automation/run-tests.sh --test-type unit_py27`:
   Unit tests in Python 2.7 using 'nmstate/fedora-nmstate-dev' docker image.

 * `./automation/run-tests.sh --test-type unit_py36`:
   Unit tests in Python 3.6 using 'nmstate/fedora-nmstate-dev' docker image.

 * `./automation/run-tests.sh --test-type unit_py37`:
   Unit tests in Python 3.7 using 'nmstate/fedora-nmstate-dev' docker image.

 * `./automation/run-tests.sh --test-type integ --el7`:
   Integration tests using 'nmstate/centos7-nmstate-dev' docker image.

 * `./automation/run-tests.sh --test-type integ`:
   Integration tests using 'nmstate/fedora-nmstate-dev' docker image.

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
`DOCKER_IMAGE` variable:

`DOCKER_IMAGE=local/centos7-nmstate-dev debug_exit_shell=1 ./automation/run-tests.sh`

It is also possible to pass extra arguments to PDB using the
`nmstate_pytest_extra_args` variable or via `--pytest-args` command-line
option, for example:

`nmstate_pytest_extra_args="--pdb -x" ./automation/run-tests.sh`

or:

`./automation/run-integration-tests.sh --pytest-args "--pdb -x"`


Alternatively, the following commands start the container manually:

```
DOCKER_IMAGE="nmstate/fedora-nmstate-dev"
NET0="nmstate-net0"
NET1="nmstate-net1"

CONTAINER_ID="$(docker run --privileged -d -v /sys/fs/cgroup:/sys/fs/cgroup:ro -v $PWD:/workspace/nmstate $DOCKER_IMAGE)"
docker exec $USE_TTY -i $CONTAINER_ID /bin/bash -c 'systemctl stop NetworkManager'
docker network create $NET0 || true
docker network create $NET1 || true
docker network connect $NET0 $CONTAINER_ID
docker network connect $NET1 $CONTAINER_ID
docker exec -ti $CONTAINER_ID /bin/bash
systemctl start NetworkManager
cd /workspace/nmstate
tox -e check-integ-py27
```

### Build a new container image

```
sudo ../packaging/build-container.sh local/centos7-nmstate-dev
sudo ../packaging/build-container.sh local/fedora-nmstate-dev
```

To test the image, either specify it manually as described above or tag it locally:

```
sudo docker tag local/centos7-nmstate-dev nmstate/centos7-nmstate-dev:latest
sudo docker tag local/fedora-nmstate-dev nmstate/fedora-nmstate-dev:latest
```

### Push local image to the docker hub
The container images are automatically rebuilt for new commits to the master
branch or new tags. Therefore updates to the Docker Hub images should always
happen with a pull request that is merged to ensure that the change is
persistent. If this is not feasible, a new build could be pushed as follow to
the Docker Hub:

```shell
sudo docker tag local/centos7-nmstate-dev nmstate/centos7-nmstate-dev:latest
sudo docker push nmstate/centos7-nmstate-dev:latest

sudo docker tag local/fedora-nmstate-dev nmstate/fedora-nmstate-dev:latest
sudo docker push nmstate/fedora-nmstate-dev:latest
```

It will be overwritten after the next commit to master, though.
