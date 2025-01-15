SRPM_DEPENDENCIES=python3-setuptools git cargo
PROJECT_DIR:=$(realpath $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))/../)

srpm:
	rpm -q --whatprovides $(SRPM_DEPENDENCIES) || \
		dnf -y install $(SRPM_DEPENDENCIES)
	git config --global --add safe.directory $(PROJECT_DIR)
	env SKIP_VENDOR_CREATION=1 outdir=$(outdir) \
		make srpm -C $(PROJECT_DIR)
