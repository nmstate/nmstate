// SPDX-License-Identifier: Apache-2.0

#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include <nmstate.h>

int main(void) {
	int rc = EXIT_SUCCESS;
	const char *state = "---\n"
		"interfaces:\n"
		"  - type: ethernet\n"
		"    name: eth1\n";
	char *formated_state = NULL;
	char *err_kind = NULL;
	char *err_msg = NULL;

	if (nmstate_net_state_format(state,
				     &formated_state,
				     &err_kind,
				     &err_msg) == NMSTATE_PASS) {
		printf("%s\n", formated_state);
	} else {
		printf("%s: %s\n", err_kind, err_msg);
		rc = EXIT_FAILURE;
	}

	nmstate_cstring_free(formated_state);
	nmstate_cstring_free(err_kind);
	nmstate_cstring_free(err_msg);
	exit(rc);
}
