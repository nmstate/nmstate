# Integration Tests #

The integration tests are written as Ansible playbooks targetted for all hosts.
They follow the [Fedora's Standard Test
Interface](https://fedoraproject.org/wiki/CI/Standard_Test_Interface) and can
be run by the [Linux Sytem Roles Test
Harness](https://github.com/linux-system-roles/test-harness). You can also run
them directly, for example to run them against the [CentOS Cloud
Images](https://cloud.centos.org/centos/7/images/) download one of them,
install `standard-test-roles` from Fedora and execute `ansible-playbook`:

```
dnf install standard-test-roles
TEST_SUBJECTS=CentOS-7-x86_64-GenericCloud.qcow2c TEST_ARTIFACTS=$PWD ansible-playbook -i /usr/share/ansible/inventory/standard-inventory-qcow2 tests_*.yml
```

The tests are defined in Ansible playbooks named `tests_*.yml` that must run
sucessfully when the tests passes or skips and fail otherwise. The `playbooks/`
directory contains helper playbooks for the tests and `ci_*.yml` playbooks are
used to workaround a deficit in Ansible to skip tests when they do not work on
a certain hosts (e.g. hosts with a distribution that is missing Network
Manager).
