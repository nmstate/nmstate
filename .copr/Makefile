python_major_version=$(shell command -v python3 &>/dev/null && echo 3 || echo 2)
SRPM_DEPENDENCIES=python$(python_major_version)-setuptools git
PROJECT_DIR:=$(realpath $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))/../)

srpm:
	rpm -q --whatprovides $(SRPM_DEPENDENCIES) || \
		dnf -y install $(SRPM_DEPENDENCIES)
	git config --global --add safe.directory $(PROJECT_DIR)
	env SKIP_VENDOR_CREATION=1 outdir=$(outdir) \
		make srpm -C $(PROJECT_DIR)
