# Contributing to Nmstate

:+1: Thank you for contributing! :+1:

The *Nmstate* team is following the guidelines presented in this document.
These are mostly guidelines, not rules. Use your best judgment and follow
these guidelines when contributing to the project.

## Code of Conduct

This project and everyone participating in it is governed by the
[Nmstate Code of Conduct](CODE_OF_CONDUCT.md).
By participating, you are expected to uphold this code.
Please report unacceptable behavior to the nmstate team.

## How to Contribute

- Bugs: Tracked as ([Jira](https://nmstate.atlassian.net)) issues.
- Enhancements: RFE suggestions are tracked as
  ([Jira](https://nmstate.atlassian.net)) issues.
- Code: Managed on [GitHub](https://github.com/nmstate/nmstate) through
  Pull Requests ([PR](https://github.com/nmstate/nmstate/pulls)).

#### Pull Requests
Please follow these steps to have your contribution considered by the maintainers:

1. Run and pass the unit tests and integration tests locally.
2. Follow the instructions on
[how to open a PR](https://opensource.guide/how-to-contribute/#opening-a-pull-request).
3. Follow the [Coding and Style Guidelines](#Coding-and-Style-Guidelines).
4. After you submit your pull request, verify that all
[status checks](https://help.github.com/articles/about-status-checks/) are passing.


## Coding and Style Guidelines

- Nmstate is written primarily in Python, and its coding style should follow
  the best practices of Python coding unless otherwise declared.
- Nmstate uses the [black](https://github.com/python/black) code formatter
- PEP8 is holy.
- Tests are holy.
  Production code must be covered by unit tests and/or basic integration tests.
  When too many mocks are required, it is often a smell that the tested code
  is not well structured or in some cases a candidate for integration tests.
- Commit message should use the provided [commit-template](commit-template.txt):
  Set the template for nmstate by configuring git:
  `git config commit.template commit-template.txt`
- Packages, modules, functions, methods and variables should use
  underscore_separated_names.
- Class names are in CamelCase.
- Imports should be grouped in the following order:
  - Standard library imports
  - Related third party imports
  - Local application-specific or library-specific imports.
- All indentation is made of the space characters.
  Tabs must be avoided. In makefiles, however, tabs are obligatory.
  White space between code stanzas are welcome. They help to create breathing
  while reading long code.
  However, splitting stanzas into helper functions could be even better.

Ref:
https://www.ovirt.org/develop/developer-guide/vdsm/coding-guidelines/

### Clean Code
Do your best to follow the clean code guidelines.

- Name classes using a noun.
- Name functions/methods using a verb.
- Make them as small as possible.
- They should do one thing only and do it well.
  One thing means one level of abstraction.
  The names and code should reflect that.
- Methods/functions should be organized per level of abstraction,
  where callee sits below their caller.
- Avoid output-arguments (arguments to output data out of a function/method).
- Don’t use boolean arguments, use 2 functions/methods instead.
- Don’t return an error code, throw an exception instead.

Ref: Book: Clean Code by Robert C. Martin (Uncle Bob)
