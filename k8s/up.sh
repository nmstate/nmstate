#!/bin/bash

set -ex

source ./k8s/kubevirtci.sh
kubevirtci::install

if ! ./k8s/kubectl.sh get pod ; then
    $(kubevirtci::path)/cluster-up/down.sh
    $(kubevirtci::path)/cluster-up/up.sh
fi

if [[ "$KUBEVIRT_PROVIDER" =~ ^(okd|ocp)-.*$$ ]]; then \
		while ! $(KUBECTL) get securitycontextconstraints; do sleep 1; done; \
fi

for node in $(./k8s/kubectl.sh get nodes --no-headers | awk '{print $1}'); do
    # Upgrade NetworkManager to the latest available version.
    # The base node image ships an older NM whose "strictly unmanaged"
    # enforcement and OVS activation paths differ from the container CI
    # environment, causing spurious test failures. This aligns the k8s CI
    # node with the kubernetes-nmstate project's setup.
    ./k8s/ssh.sh $node -- "sudo dnf upgrade -y NetworkManager --allowerasing"
    # Remove the dhclient drop-in shipped by newer kubevirtci images.
    # This keeps the NM internal DHCP client consistent with the container
    # CI and with kubernetes-nmstate's cluster/up.sh.
    ./k8s/ssh.sh $node -- "sudo rm -f /etc/NetworkManager/conf.d/002-dhclient.conf"
    # openvswitch is already installed in the node image, so just enable
    # the service.
    ./k8s/ssh.sh $node -- \
        "sudo systemctl enable openvswitch && \
        sudo sed -i -e 's/^#RateLimitInterval=.*/RateLimitInterval=0/' \
            -e 's/^#RateLimitBurst=.*/RateLimitBurst=0/' \
            /etc/systemd/journald.conf"
    ./k8s/ssh.sh $node  -- "echo "[logging]" | sudo tee /etc/NetworkManager/conf.d/97-trace-logging.conf && \
                            echo "level=TRACE" | sudo tee -a /etc/NetworkManager/conf.d/97-trace-logging.conf && \
                            echo "domain=ALL" | sudo tee -a /etc/NetworkManager/conf.d/97-trace-logging.conf"
    # The integration tests create veth pairs with arbitrary names
    # (veth1, veth1peer, 1x_cli, …).  NetworkManager ships a udev rule
    # (/usr/lib/udev/rules.d/85-nm-unmanaged.rules) that sets
    # NM_UNMANAGED=1 for every veth whose name does not match eth[0-9]*.
    # This makes the devices "strictly unmanaged" at the udev level —
    # neither `nmcli device set … managed yes` nor an NM conf [device]
    # section can override it.
    #
    # Fix: install an override in /etc/udev/rules.d/ (which takes
    # priority over /usr/lib/) that keeps the VirtualBox / VMWare /
    # Parallels / USB-gadget rules but drops the blanket veth rule.
    ./k8s/ssh.sh $node -- 'cat <<'"'"'EOF'"'"' | sudo tee /etc/udev/rules.d/85-nm-unmanaged.rules >/dev/null
SUBSYSTEM!="net", GOTO="nm_unmanaged_end"
ACTION!="add|change|move", GOTO="nm_unmanaged_end"
ENV{INTERFACE}=="vboxnet[0-9]*", ENV{NM_UNMANAGED}="1"
ATTR{address}=="00:50:56:*", ENV{INTERFACE}=="vmnet[0-9]*", ENV{NM_UNMANAGED}="1"
ATTR{address}=="00:1c:42:*", ENV{INTERFACE}=="vnic[0-9]*", ENV{NM_UNMANAGED}="1"
ENV{DEVTYPE}=="gadget", ENV{NM_UNMANAGED}="1"
LABEL="nm_unmanaged_end"
EOF'
    ./k8s/ssh.sh $node -- 'sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=net'
    ./k8s/ssh.sh $node -- sudo systemctl daemon-reload
    ./k8s/ssh.sh $node -- sudo systemctl restart NetworkManager
    ./k8s/ssh.sh $node -- sudo systemctl restart openvswitch
    # Enable persistent journal so logs survive node reboots
    ./k8s/ssh.sh $node -- sudo mkdir -p /var/log/journal
    ./k8s/ssh.sh $node -- sudo systemctl restart systemd-journald
    for nic in $FIRST_SECONDARY_NIC $SECOND_SECONDARY_NIC; do
	      uuid=$(./k8s/cli.sh ssh $node -- nmcli --fields=device,uuid  c show  |grep $nic|awk '{print $2}')
	      if [ ! -z "$uuid" ]; then
        	  echo "$node: Flushing nic $nic"
        	  ./k8s/cli.sh ssh $node -- sudo nmcli con del $uuid
	      fi
    done
done
