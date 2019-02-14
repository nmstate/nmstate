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
  - Standard library imports
  - Related third party imports
  - Local application-specific or library-specific imports.
- All indentation is made of the space characters.
  Tabs are evil. In makefiles, however, tabs are obligatory.
  White space between code stanzas are welcome. They help to create breathing
  while reading long code.
  However, splitting stanzas into helper functions could be even better.
- Prefer single quotes (') whenever possible.

## Clean Code
Do your best to follow the clean code guidelines.

- Name classes using a noun.
- Name functions/methods using a verb.
- Make them as small as possible.
- Should do one thing only and do it well.
  One thing means one level of abstraction.
  The names and code should reflect that.
- Methods/functions should be organized per level of abstraction,
  where callee sits below their caller.
- Avoid output-arguments (arguments to output data out of a function/method).
- Don’t use boolean arguments, use 2 functions/methods instead.

  Not both

- Don’t return an error code, throw an exception instead.


References:
https://www.ovirt.org/develop/developer-guide/vdsm/coding-guidelines/
Book: Clean Code by Robert C. Martin (Uncle Bob)

## Create debug information for libnm bugs

Run the integration tests with valgrind (it can also be used to run nmstate
directly):

```shell
G_DEBUG=fatal-warnings,gc-friendly G_SLICE=always-malloc valgrind --num-callers=100 --log-file=valgrind-log pytest tests/integration/
```

Send `valgrind-log`, core-files and Network Manager log with trace enabled to
Network Manager developers.

## Creating a New Release

* Tag new release in git.
```bash
# Make sure your local git repo is sync with upstream.
# The whole version string should be like `v0.0.3`.
# Put strings like `nmstate 0.0.3 release` as commit message.
git tag --sign v<version>
git push upstream --tags
```

* If you need to remove a tag because something needs to be fixed:
```bash
# Remove local tag
git tag -d <tag_name>

# Remove upstream tag
git push --delete upstream <tag_name>
```

* Generate and sign the tarball.

```bash
git clean -d -n
# before running the next command check, that it is ok to remove the files
git clean -d -f
python setup.py sdist
gpg2 --armor --detach-sign dist/nmstate-<version>.tar.gz
```

* Visit [github draft release page][1].
* Make sure you are in `Release` tab.
* Choose the git tag just pushed.
* Title should be like `Version 0.0.3 release`.
* The content should be like:

```
Changes since 0.0.2:

 * Enhancements:
    * Added DHCP support.
 * Bug fixes:
    * <List import bug fix here>.
      Use command `git log  --oneline --since v0.0.2` to find out.

```

 * Click `Attach binaries by dropping them here or selecting them.` and
   upload the `dist/nmstate-<version>.tar.gz` and
   `dist/nmstate-<version>.tar.gz.asc`.

 * Click `Save draft` and seek for review.

 * Click `Publish release` once approved.

 * Create a pull request with increased version number in the `VERSION` file.

* Release to PyPi.
```
# Make sure you installed python package: wheel and twine.
rm dist  -rf
python setup.py sdist bdist_wheel

# Upload to pypi test.
python3 -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*
# Now, check https://test.pypi.org/project/nmstate/

# If it works, now upload to pypi.
python3 -m twine upload dist/*
```

* Send out a notification to the network manager mailing list

* Update the SPEC files in Fedora

[1]: https://github.com/nmstate/nmstate/releases/new
