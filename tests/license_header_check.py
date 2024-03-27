# SPDX-License-Identifier: LGPL-2.1-or-later

import re
import sys
from pathlib import Path

paths = ["rust/src", "tests"]

header_pattern = r"(?:\/\/|\#)\s*SPDX-License-Identifier: (LGPL-2\.1-or-later|Apache-2\.0)(?:\r?\n)?"

excludes = [
    "**/*.json",
    "**/*.txt",
    "**/*.in",
    ".gitignore",
    ".gitmodules",
    "LICENSE",
    "NOTICE",
    "go.mod",
    "go.sum",
    ".git/*",
    "logo/*",
    "licenses",
    "**/*.md",
    "**/*.lock",
    "**/*.toml",
    "**/*.yml",
    "tests/integration/test_802.1x_srv_files/*",
    "tests/integration/test_ipsec_certs/*",
    "tests/integration/test_captures/*",
    "rust/target/*",
    "rust/src/python/dist/*",
    "rust/src/python/build/*",
    "rust/src/python/nmstate.egg-info/*",
    "examples/*",
    "packaging/*",
]

total_files = 0
files_with_header = 0
files_without_header = 0
excluded_files = 0


def get_included_files():
    global total_files
    global excluded_files
    directory_paths = (Path(directory) for directory in paths)
    files = []
    for directory_path in directory_paths:
        for file in directory_path.glob("**/*"):
            if file.is_dir():
                continue

            total_files += 1

            if any(file.match(pattern) for pattern in excludes):
                excluded_files += 1
                continue

            files.append(file)

    return files


print(
    "------------------------- License Header Check Start -------------------------"
)

for file_path in get_included_files():

    with open(file_path, "r") as file:
        content = file.readline()

        # Read second line if the first is a shebang
        if content.startswith("#!"):
            content = file.readline()

        matches = re.fullmatch(header_pattern, content.strip())
        if matches is None:
            if files_without_header <= 0:
                print(
                    "Here is the list of files that do not have a license header:"
                )

            print(file_path)
            files_without_header += 1
        else:
            files_with_header += 1

print(
    f"\nTotal: {total_files}, Passed: {files_with_header}, Failed: {files_without_header}, Skipped: {excluded_files}"
)
print(
    "------------------------- License Header Check End -------------------------"
)

if files_without_header > 0:
    sys.exit(
        f"Could not identify license header in {files_without_header} files"
    )
