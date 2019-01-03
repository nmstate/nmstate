SRPM_DEPENDENCIES=python-setuptools git

srpm:
	rpm -q --whatprovides $(SRPM_DEPENDENCIES) || dnf -y install $(SRPM_DEPENDENCIES)
	$(dir $(realpath $(firstword $(MAKEFILE_LIST))))../packaging/make_srpm.sh
