# Creating a New Release

Important: If you do not finish these steps, add Jira cards for the remaining
tasks and ensure that they are taken care of in a timely manner.

## Changelog

First, update the CHANGELOG file in the project root directory. Use the command
`git log  --oneline --since v0.1.2` to get the changes since the last tag. Add
an entry like the following:

```
## [X.Y.Z] - YYYY-MM-DD
### Breaking Changes
 - ...

### New Features
 - ...

### Bug Fixes
 - ...

```

## Tagging

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

## GitHub Release

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
* The content should be copied from the `CHANGELOG` file.


 * Click `Attach binaries by dropping them here or selecting them.` and
   upload the `dist/nmstate-<version>.tar.gz` and
   `dist/nmstate-<version>.tar.gz.asc`.

 * Click `Save draft` and seek for review.

 * Click `Publish release` once approved.

## PyPi Release

```bash
# Make sure you installed python package: wheel and twine.
yum install twine python3-wheel
rm -rf dist
python3 setup.py sdist bdist_wheel

# Upload to pypi test.
python3 -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*
# Now, check https://test.pypi.org/project/nmstate/

# If it works, now upload to pypi.
python3 -m twine upload dist/*
```

## Post Release

1. Create a pull request with increased version number in the `VERSION` file
   and merge it before any other PR. This is necessary to ensure that the
   development RPMs are newer than the stable version in distributions.

2. Update the SPEC files in Fedora, create new builds and updates as neccessary

3. Rebuild Copr repositories for stable releases as necessary (this requires
   the SPEC files in Fedora to be updated, first)
   https://copr.fedorainfracloud.org/coprs/nmstate/

4. Send out a notification to the fedorahosted mailing list:
   nmstate-devel@lists.fedorahosted.org

[1]: https://github.com/nmstate/nmstate/releases/new
