<!-- vim-markdown-toc GFM -->

* [Persisting NIC names for OCP upgrade from 4.12(RHEL 8) to 4.13+(RHEL 9)](#persisting-nic-names-for-ocp-upgrade-from-412rhel-8-to-413rhel-9)
    * [Workflow](#workflow)
    * [How to debug OCP upgrade failure on NIC names](#how-to-debug-ocp-upgrade-failure-on-nic-names)
    * [How to build new OCP image using scratch build of nmstate](#how-to-build-new-ocp-image-using-scratch-build-of-nmstate)

<!-- vim-markdown-toc -->

**Note: The OpenShift related notes might be outdated, be cautious!**

## Persisting NIC names for OCP upgrade from 4.12(RHEL 8) to 4.13+(RHEL 9)

OpenShift(OCP) Machine Config Operator(MCO) is responsible to persistent NIC
names after upgrade. MCO is using nmstatectl for this work.

### Workflow

 * Nmstate been included into OCP 4.13+ MCO operator image:
    https://github.com/openshift/machine-config-operator/blob/master/Dockerfile

 * For OCP 4.12(RHEL 8.6), nmstate 2.x is included in RHEL AOS repo for MCO
   to consume.

 * MCO operator using nmstate to persist NIC names:
    https://github.com/openshift/machine-config-operator/blob/master/pkg/daemon/daemon.go

 * Before OCP upgrade the node RHEL CoreOS, MCO operator will invoke
   `nmstatectl persist-nic-names --root <real_root> --kargs-out <tmp_file>`
    * The kargs-out will be used as kernel boot argument.
    * Nmstate will create file like `/etc/systemd/network/98-nmstate-ens4.link`
      with content:
      ```bash
      [Match]
      MACAddress=52:54:00:de:a8:2f

      Driver=e1000

      [Link]
      Name=ens4
      ```

 * After OCP upgrade the node RHEL CoreOS 9, MCO operator will invoke
   `nmstatectl persist-nic-names --cleanup --root <real_root>`
    * Nmstate will try to check whether NIC will hold identical name
      after OS upgrade. If unchanged, the link file `/etc/systemd/network/`
      will be removed.

### How to debug OCP upgrade failure on NIC names

This command could retrieve the log related to OCP upgrade:

```bash
oc logs $(oc get pod -n openshift-cluster-version \
    -l k8s-app=cluster-version-operator -oname) \
    -n openshift-cluster-version
```

You may also enter MCO pod to debug:

```bash
oc get pod -n openshift-machine-config-operator
oc exec -it <mco-pod-name-of-node> -n openshift-machine-config-operator -- bash
```

### How to build new OCP image using scratch build of nmstate

The goal is generate a custom OCP release referring to a custom MCO container.
So we will build up to container image, one for MCO, one for OCP.

* Upload nmstate scratch rpm to public accessible web URL. e.g.
  https://fedorapeople.org/

* Git clone https://github.com/openshift/machine-config-operator

* Switch to the right branch of MCO. e.g. `git checkout release-4.13`
* Modify MCO `Dockerfile` to install this scratch rpm. e.g.
  `dnf install -y <url_of_your_rpm>`

* Check [MCO document][mco_hack_doc] on how to build a container and upload to
  quay.io. I used these commands on 2024 March 21
    ```bash
    # with all credential setup correctly in advance

    make image

    RELEASE="4.13.37"
    QUAY_ID="cathay4t"
    MCO="machine-config-operator"

    # Create MCO image: quay.io/<your_account>/machine-config-operator:4.13.37
    podman push localhost/machine-config-operator \
        quay.io:443/$QUAY_ID/$MCO:$RELEASE

    # Create OCP release image: quay.io/<your_account>/origin-release:v4.13.37
    oc adm release new \
        -a ~/.kube/pull-secret.txt \
        --from-release \
        quay.io/openshift-release-dev/ocp-release:${RELEASE}-x86_64 \
        --name ${RELEASE} \
        --to-image quay.io:443/$QUAY_ID/origin-release:v${RELEASE} \
        $MCO=quay.io/$QUAY_ID/$MCO:${RELEASE}
    ```

 * Visit `quay.io/<your_account>/origin-release` to check whether it is
   accessible with correct tag.

 * Now, you can force a OCP cluster to upgrade to your custom OCP release via
    ```bash
    RELEASE="4.13.37"
    QUAY_ID="cathay4t"

    oc adm upgrade --force \
        --to-image quay.io/$QUAY_ID/origin-release:v${RELEASE} \
        --allow-explicit-upgrade
    ```

[mco_hack_doc]: https://github.com/openshift/machine-config-operator/blob/master/docs/HACKING.md
