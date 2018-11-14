# Distribute and Install NMState
NMState is distributed on PyPI and Docker Hub.

First prepare and upload to PyPI and then build and upload the docker image.
 

## Package and Upload to PyPI
The following procedures can be reviewed in detail [here](https://packaging.python.org/tutorials/packaging-projects/#uploading-the-distribution-archives).
```
cd <project-path>
python setup.py sdist bdist_wheel
twine upload dist/*
```

## Build a new container image and push to the docker hub

- CentOS 7:
```
cd <project-path/packaging>
sudo docker build --rm -t local/centos7-nmstate .
docker tag local/centos7-nmstate nmstate/centos7-nmstate:<ver>
docker tag local/centos7-nmstate nmstate/centos7-nmstate:latest
docker push nmstate/centos7-nmstate:<ver>
docker push nmstate/centos7-nmstate:latest
```

## Run the NMState docker image:

```
CONTAINER_ID="$(docker run --privileged -d -v /sys/fs/cgroup:/sys/fs/cgroup:ro centos7-nmstate)"
docker exec -ti $CONTAINER_ID /bin/bash
```
