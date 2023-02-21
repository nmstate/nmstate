// SPDX-License-Identifier: Apache-2.0

#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include <nmstate.h>

int main(void) {
	int rc = EXIT_SUCCESS;
	const char *policy = "\
capture:\n\
  default-gw: override me with the cache\n\
  base-iface: >\n\
    interfaces.name == capture.default-gw.routes.running.0.next-hop-interface\n\
  base-iface-routes: >\n\
    routes.running.next-hop-interface ==\n\
    capture.default-gw.routes.running.0.next-hop-interface\n\
  bridge-routes: >\n\
    capture.base-iface-routes | routes.running.next-hop-interface:=\"br1\"\n\
desired:\n\
  interfaces:\n\
  - name: br1\n\
    description: Linux bridge with base interface as a port\n\
    type: linux-bridge\n\
    state: up\n\
    bridge:\n\
      options:\n\
        stp:\n\
          enabled: false\n\
      port:\n\
      - name: '{{ capture.base-iface.interfaces.0.name }}'\n\
    ipv4: '{{ capture.base-iface.interfaces.0.ipv4 }}'\n\
  routes:\n\
    config: '{{ capture.bridge-routes.routes.running }}'";
	const char *current_state = "\
interfaces:\n\
- name: eth1\n\
  type: ethernet\n\
  state: up\n\
  mac-address: 1c:c1:0c:32:3b:ff\n\
  ipv4:\n\
    address:\n\
    - ip: 192.0.2.251\n\
      prefix-length: 24\n\
    dhcp: false\n\
    enabled: true\n\
routes:\n\
  config:\n\
  - destination: 0.0.0.0/0\n\
    next-hop-address: 192.0.2.1\n\
    next-hop-interface: eth1\n\
  running:\n\
  - destination: 0.0.0.0/0\n\
    next-hop-address: 192.0.2.1\n\
    next-hop-interface: eth1";
	char *state = NULL;
	char *err_kind = NULL;
	char *err_msg = NULL;
	char *log = NULL;

	if (nmstate_net_state_from_policy(policy, current_state, &state, &log,
					  &err_kind, &err_msg) == NMSTATE_PASS)
	{
		printf("%s\n", state);
	} else {
		printf("%s: %s\n", err_kind, err_msg);
		rc = EXIT_FAILURE;
	}

	assert(state[0] != '{');

	nmstate_cstring_free(state);
	nmstate_cstring_free(err_kind);
	nmstate_cstring_free(err_msg);
	nmstate_cstring_free(log);
	exit(rc);
}
