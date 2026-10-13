# SPDX-License-Identifier: Apache-2.0

"""Record Podman calls and simulate results for container-source tests.

Each invocation appends its arguments to COMMAND_LOG. FAIL_PULL_IMAGES,
PULL_FAILURES and FAIL_PULL control pull failures; FAIL_RUN and
IMAGE_INSPECT_RC control run and image-inspection results.
"""

import json
import os
import sys


def main():
    arguments = sys.argv[1:]
    with open(os.environ["COMMAND_LOG"], "a") as log:
        log.write(json.dumps(arguments) + "\n")

    if arguments[0] == "run":
        fail_run = os.environ.get("FAIL_RUN")
        if fail_run:
            return int(fail_run)
        print("test-container")
    elif arguments[0] == "--version":
        print("podman test stub")
    elif arguments[:2] == ["image", "inspect"]:
        return int(os.environ.get("IMAGE_INSPECT_RC", "1"))
    elif arguments[0] == "pull":
        failing_images = json.loads(os.environ.get("FAIL_PULL_IMAGES", "[]"))
        if arguments[-1] in failing_images:
            return 1
        with open(os.environ["COMMAND_LOG"]) as log:
            commands = [json.loads(line)[0] for line in log]
        attempts = commands.count("pull")
        if attempts <= int(os.environ.get("PULL_FAILURES", "0")):
            return 1
        return int(os.environ.get("FAIL_PULL", "0"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
