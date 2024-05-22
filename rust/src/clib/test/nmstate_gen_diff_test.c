// SPDX-License-Identifier: Apache-2.0

#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include <nmstate.h>

int main(void) {
	int rc = EXIT_SUCCESS;
	const char *new_state = "---\n"
		"interfaces:\n"
		"  - name: eth1\n"
		"    type: ethernet\n"
		"    state: up\n"
		"    ipv4:\n"
		"      enabled: true\n"
		"      dhcp: true\n"
		"    ipv6:\n"
		"      enabled: false";
	const char *old_state = "---\n"
		"interfaces:\n"
		"  - name: eth1\n"
		"    type: ethernet\n"
		"    state: up\n"
		"    ipv4:\n"
		"      enabled: true\n"
		"      dhcp: true\n"
		"    ipv6:\n"
		"      enabled: true\n"
		"      dhcp: true\n"
		"      autoconf: true";
	char *diff_state = NULL;
	char *err_kind = NULL;
	char *err_msg = NULL;

	if (nmstate_generate_differences(new_state,
					 old_state,
					 &diff_state,
					 &err_kind,
					 &err_msg) == NMSTATE_PASS) {
		printf("%s\n", diff_state);
	} else {
		printf("%s: %s\n", err_kind, err_msg);
		rc = EXIT_FAILURE;
	}

	nmstate_cstring_free(diff_state);
	nmstate_cstring_free(err_kind);
	nmstate_cstring_free(err_msg);
	exit(rc);
}
