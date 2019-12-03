# Creating a New Release

Important: If you do not finish these steps, add Jira cards for the remaining
tasks and ensure that they are taken care of in a timely manner.

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

## PyPi Release

```bash
# Make sure you installed python package: wheel and twine.
yum install twine python3-wheel
rm dist  -rf
python setup.py sdist bdist_wheel

# Upload to pypi test.
python3 -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*
# Now, check https://test.pypi.org/project/nmstate/

# If it works, now upload to pypi.
python3 -m twine upload dist/*
```

## Post Release

* Create a pull request with increased version number in the `VERSION` file and
  merge it before any other PR. This is necessary to ensure that the
  development RPMs are newer than the stable version in distributions.

* Send out a notification to the network manager mailing list

* Update the SPEC files in Fedora


[1]: https://github.com/nmstate/nmstate/releases/new
