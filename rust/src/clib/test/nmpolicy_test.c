#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include <nmstate.h>

int main(void) {
	int rc = EXIT_SUCCESS;
	const char *policy = "{"
"  \"capture\": {"
"    \"default-gw\": \"override me with the cache\","
"    \"base-iface\": \"interfaces.name== capture.default-gw.routes.running.0.next-hop-interface\","
"    \"base-iface-routes\": \"routes.running.next-hop-interface== capture.default-gw.routes.running.0.next-hop-interface\","
"    \"bridge-routes\": \"capture.base-iface-routes | routes.running.next-hop-interface:=\\\"br1\\\"\""
"  },"
"  \"desiredState\": {"
"    \"interfaces\": ["
"      {"
"        \"name\": \"br1\","
"        \"description\": \"Linux bridge with base interface as a port\","
"        \"type\": \"linux-bridge\","
"        \"state\": \"up\","
"        \"ipv4\": \"{{ capture.base-iface.interfaces.0.ipv4 }}\","
"        \"bridge\": {"
"          \"options\": {"
"            \"stp\": {"
"              \"enabled\": false"
"            }"
"          },"
"          \"port\": ["
"            {"
"              \"name\": \"{{ capture.base-iface.interfaces.0.name }}\""
"            }"
"          ]"
"        }"
"      }"
"    ],"
"    \"routes\": {"
"      \"config\": \"{{ capture.bridge-routes.routes.running }}\""
"    }"
"  }"
"}";
	const char *current_state = "{"
"  \"interfaces\": ["
"    {"
"      \"name\": \"eth1\","
"      \"type\": \"ethernet\","
"      \"state\": \"up\","
"      \"mac-address\": \"1c:c1:0c:32:3b:ff\","
"      \"ipv4\": {"
"        \"address\": ["
"          {"
"            \"ip\": \"192.0.2.251\","
"            \"prefix-length\": 24"
"          }"
"        ],"
"        \"dhcp\": false,"
"        \"enabled\": true"
"      }"
"    }"
"  ],"
"  \"routes\": {"
"    \"running\": ["
"      {"
"        \"destination\": \"0.0.0.0/0\","
"        \"next-hop-address\": \"192.0.2.1\","
"        \"next-hop-interface\": \"eth1\""
"      }"
"    ],"
"    \"config\": ["
"      {"
"        \"destination\": \"0.0.0.0/0\","
"        \"next-hop-address\": \"192.0.2.1\","
"        \"next-hop-interface\": \"eth1\""
"      }"
"    ]"
"  }"
"}";
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

	nmstate_cstring_free(state);
	nmstate_cstring_free(err_kind);
	nmstate_cstring_free(err_msg);
	nmstate_cstring_free(log);
	exit(rc);
}
