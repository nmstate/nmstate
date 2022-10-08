#!/bin/bash -xe

function eventually {
    timeout=10
    interval=2
    cmd=$@
    echo "Checking eventually $cmd"
    while ! $cmd; do
        sleep $interval
        timeout=$(( $timeout - $interval ))
        if [ $timeout -le 0 ]; then
            return 1
        fi
    done
}

function k8s::cli {
    k8s/cli.sh $@
}

function k8s::kubectl_exec {
    ${KUBECTL_CMD} exec $USE_TTY -n nmstate $POD_ID -- /bin/bash -c "cd $CONTAINER_WORKSPACE && $1"
}


function k8s::open_shell {
    res=$?
    [ "$res" -ne 0 ] && echo "*** ERROR: $res"
    set +o errexit
    k8s::kubectl_exec 'echo "pytest tests/integration --pdb" >> ~/.bash_history'
    USE_TTY="-it" k8s::kubectl_exec 'exec /bin/bash'
    run_exit
}


function k8s::create_pod {
    ${KUBECTL_CMD} delete namespace nmstate --ignore-not-found=true
    cat <<EOF | ${KUBECTL_CMD} apply -f -
---
kind: Namespace
apiVersion: v1
metadata:
  name: nmstate
EOF
    eventually ${KUBECTL_CMD} get serviceaccount -n nmstate default
    cat <<EOF | ${KUBECTL_CMD} apply -f -
---
kind: Pod
apiVersion: v1
metadata:
  name: conformance
  namespace: nmstate
  labels:
    name: nmstate-conformance
spec:
  hostNetwork: true
  dnsPolicy: Default
  containers:
    - name: conformance
      image: ${CONTAINER_IMAGE}
      command: ["/bin/bash"]
      args:
      - "-c"
      - "trap : TERM INT; sleep infinity & wait"
      env:
      - name: CI
        value: "${CI}"
      - name: COVERALLS_REPO_TOKEN
        value: "${COVERALLS_REPO_TOKEN}"
      - name: SHIPPABLE
        value: "${SHIPPABLE}"
      - name: RUN_K8S
        value: "true"
      - name: NMSTATE_TEST_IGNORE_IFACE
        value: "cali"
      volumeMounts:
      - name: dbus-socket
        mountPath: /run/dbus/system_bus_socket
      - name: ovs-socket
        mountPath: /run/openvswitch/db.sock
      - name: cgroup
        mountPath: /sys/fs/cgroup
        readOnly: true
      - name: nm-profiles
        mountPath: /etc/NetworkManager/system-connections/
      securityContext:
        privileged: true
  volumes:
    - name: cgroup
      hostPath:
        path: /sys/fs/cgroup
    - name: dbus-socket
      hostPath:
        path: /run/dbus/system_bus_socket
        type: Socket
    - name: ovs-socket
      hostPath:
        path: /run/openvswitch/db.sock
        type: Socket
    - name: nm-profiles
      hostPath:
        path: /etc/NetworkManager/system-connections/
EOF
export POD_ID=conformance

[ -n "$debug_exit_shell" ] && trap k8s::open_shell EXIT || trap run_exit EXIT
$KUBECTL_CMD wait pod -n nmstate $POD_ID --for=condition=Ready --timeout=100s
}
function k8s::pre_test_setup {
    set -x

    if [[ "$CI" == "true" ]];then
        rebuild_container_images
    fi

    k8s::create_pod

    ${KUBECTL_CMD} exec -n nmstate conformance -- rm -rf /workspace/
    ${KUBECTL_CMD} exec -n nmstate conformance -- mkdir -p /workspace/
    ${KUBECTL_CMD} exec -n nmstate conformance -- mkdir -p /exported-artifacts/
    ${KUBECTL_CMD} cp -n nmstate $(pwd) conformance:/workspace/nmstate/

    k8s::kubectl_exec "echo '$CONT_EXPORT_DIR/core.%h.%e.%t' > \
        /proc/sys/kernel/core_pattern"
    k8s::kubectl_exec "ulimit -c unlimited"
    # Enable IPv6 in container globally
    k8s::kubectl_exec  "echo 0 > /proc/sys/net/ipv6/conf/all/disable_ipv6"

}
function k8s::start_cluster {
    if [ "${KUBEVIRT_PROVIDER}" != "external" ]; then
        KUBEVIRT_NUM_SECONDARY_NICS=2
        k8s/up.sh
    fi
}

function k8s::stop_cluster {
    if [ "${KUBEVIRT_PROVIDER}" != "external" ]; then
        k8s/down.sh
    fi
}

function k8s::cleanup {
    ${KUBECTL_CMD} delete namespace nmstate --ignore-not-found=true
}

function k8s::collect_artifacts {
    rm -rf ${EXPORT_DIR}
    mkdir -p ${EXPORT_DIR}
    # TODO: Parameterize how to do SSH to external providers
    if [ "${KUBEVIRT_PROVIDER}" != "external" ]; then
        k8s::cli ssh node01 -- sudo journalctl > ${EXPORT_DIR}/journalctl.log
       k8s::cli ssh node01 -- sudo dmesg > ${EXPORT_DIR}/dmesg.log
       k8s::cli ssh node01 -- sudo cat /var/log/openvswitch/ovsdb-server.log  > ${EXPORT_DIR}/ovsdb-server.log
    fi
    ${KUBECTL_CMD} cp -n nmstate conformance:${CONTAINER_WORKSPACE}/pytest-run.log $EXPORT_DIR/pytest-run.log
    # To use wildcard we have to use exec
    ${KUBECTL_CMD} exec -i -n nmstate conformance -- bash -c "cd ${CONTAINER_WORKSPACE} && tar cf - *.xml" | tar xf - -C $EXPORT_DIR

}

function copy_workspace_container {
    if [[ "$CI" != "true" ]];then
        if $CONTAINER_CMD --version | grep -qv podman; then
          container_exec "cp -rf $CONTAINER_WORKSPACE /root/nmstate-workspace || true"
        else
          container_exec "cp -rf $CONTAINER_WORKSPACE /root/nmstate-workspace"
        fi
        # Change workspace to keep the original one clean
        CONTAINER_WORKSPACE="/root/nmstate-workspace"
    fi
}
