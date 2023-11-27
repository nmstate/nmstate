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
    ./k8s/ssh.sh $node -- \
        "sudo dnf upgrade -y \
            openvswitch \
            NetworkManager \
            NetworkManager-ovs && \
        sudo systemctl enable openvswitch && \
        sudo sed -i -e 's/^#RateLimitInterval=.*/RateLimitInterval=0/' \
            -e 's/^#RateLimitBurst=.*/RateLimitBurst=0/' \
            /etc/systemd/journald.conf"
    ./k8s/ssh.sh $node  -- "echo "[logging]" | sudo tee /etc/NetworkManager/conf.d/97-trace-logging.conf && \
                            echo "level=TRACE" | sudo tee -a /etc/NetworkManager/conf.d/97-trace-logging.conf && \
                            echo "domain=ALL" | sudo tee -a /etc/NetworkManager/conf.d/97-trace-logging.conf"
    ./k8s/ssh.sh $node -- sudo systemctl daemon-reload
    ./k8s/ssh.sh $node -- sudo systemctl restart NetworkManager
    ./k8s/ssh.sh $node -- sudo systemctl restart openvswitch
    for nic in $FIRST_SECONDARY_NIC $SECOND_SECONDARY_NIC; do
	      uuid=$(./k8s/cli.sh ssh $node -- nmcli --fields=device,uuid  c show  |grep $nic|awk '{print $2}')
	      if [ ! -z "$uuid" ]; then
        	  echo "$node: Flushing nic $nic"
        	  ./k8s/cli.sh ssh $node -- sudo nmcli con del $uuid
	      fi
    done
done

