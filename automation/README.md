# Automation Environment
The automation env is serving the integration tests of nmstate.
It may be used both locally and through CI.

## Components
- Dockerfile: Defines a container image which includes systemd,
  NetworkManager and other basic build tools (e.g. tox).

  The image can be found at:
  https://hub.docker.com/r/nmstate/centos7-nmstate-dev/

- run-integration-tests.sh: Execute the integration tests in a
  container using docker.

  The following steps are executed:
  - Run the container (defined in the Dockerfile) as a daemon.
  - Stop NetworkManager before adding additional networks (ifaces).
  - Add additonal networks (ifaces) to the container.
  - Start NetworkManager.
  - Execute the integration tests (using tox) in the container.

  It also handles the cleanup of the container and nets (stop,rm).

- run-integration-tests.mounts: Includes mounts to be used by the
  oVirt CI (STDCI) worker.

- run-integration-tests.packages: Includes the packages needed by
  the oVirt CI (STDCI) worker.

## Running the Tests
Assuming *docker* is installed on the host,
just run:
`./automation/run-integration-tests.sh`

## Development

### Run the tests manually in the container
For debugging, it is convenient to run the container and then connect to it in
order to run the tests. Setting the environment variable `debug_exit_shell`
will make the script start a shell instead of exiting the script after an error
or running the scripts:

`debug_exit_shell=1 ./automation/run-integration-tests.sh`


After closing the shell, the container will be removed.

To specify a different container image for the tests, specify it with the
`DOCKER_IMAGE` variable:

`DOCKER_IMAGE=local/centos7-nmstate-dev debug_exit_shell=1 ./automation/run-integration-tests.sh`

It is also possible to pass extra arguments to PDB using the
`nmstate_pytest_extra_args` variable, for example:
`nmstate_pytest_extra_args="--pdb -x" ./automation/run-integration-tests.sh`


Alternatively, the following commands start the container manually:

```
DOCKER_IMAGE="nmstate/centos7-nmstate-dev"
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
sudo docker build --rm -t local/centos7-nmstate-dev .
```

To test the image, either specify it manually as described above or tag it locally:

```
docker tag local/centos7-nmstate-dev nmstate/centos7-nmstate-dev:latest
```

### Push local image to the docker hub
```
docker tag local/centos7-nmstate-dev nmstate/centos7-nmstate-dev:<ver>
docker tag local/centos7-nmstate-dev nmstate/centos7-nmstate-dev:latest
docker push nmstate/centos7-nmstate-dev:<ver>
docker push nmstate/centos7-nmstate-dev:latest
```
