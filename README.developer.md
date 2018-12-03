# NMState Coding Guidelines

- NMState is written primarily in Python, and its coding style should follow
  the best practices of Python coding unless otherwise declared.
- PEP8 is holy.
- Tests are holy.
  Production code must be covered by unit tests and/or basic integration tests.
  When too many mocks are required, it is often a smell that the tested code
  is not well structured or in some cases a candidate for integration tests.
- Commit message should use the provided commit-template.txt as template:
  You can set the template for nmstate by configuring git:
  `git config commit.template commit-template.txt` 
- Packages, modules, functions, methods and variables should use
  underscore_separated_names.
- Class names are in CamelCase.
- Imports should be grouped in the following order:
-- Standard library imports
-- Related third party imports
-- Local application-specific or library-specific imports.
- All indentation is made of the space characters.
  Tabs are evil. In makefiles, however, tabs are obligatory.
  White space between code stanzas are welcome. They help to create breathing
  while reading long code.
  However, splitting stanzas into helper functions could be even better.
- Prefer single quotes (') whenever possible.

Note: This is a modified version of VDSM conding guidelines:
https://www.ovirt.org/develop/developer-guide/vdsm/coding-guidelines/

## Create debug information for libnm bugs

Run the integration tests with valgrind (it can also be used to run nmstate
directly):

```shell
G_DEBUG=fatal-warnings,gc-friendly G_SLICE=always-malloc valgrind --num-callers=100 --log-file=valgrind-log pytest tests/integration/
```

Send `valgrind-log`, core-files and Network Manager log with trace enabled to
Network Manager developers.
