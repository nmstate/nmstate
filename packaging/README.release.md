The `make upstream_release` command is intended to do upstream releases.

In order to make it work:

 * Your github account has enough right to do release in nmstate.
 * Your git setup is OK for force pushing to your github fork.
 * Your GPG public key has been listed in `nmstate.gpg` file.
 * The script assumes that `origin` is your own personal fork, and `upstream`
   points to `nmstate/nmstate` (the main repo). If you use ssh keys to push to
   GitHub, make sure to add the upstream repo as SSH *before* you run the release
   script: `git remote add upstream git@github.com:nmstate/nmstate.git`.
 * Install `hub` command from https://hub.github.com/ and configure it. So it
   can create pull request without intervention.
   * If you are on RHEL/Fedora, try `dnf install hub`. Otherwise, you can try
     installing it from the tarball: https://github.com/github/hub/releases/latest
   * Run `hub pr list` to ensure you are logged in and everything is working.
   * If you need to log in, you need to use an access token with `repo` permissions
     as the password. It can be created here: https://github.com/settings/tokens/new?scopes=repo
 * Run `cargo install cargo-vendor-filterer`, so `make release` can work.
 * Make sure you are logged into crates.io using `cargo login`.
   You only need to log in once. If you already logged in before, you
   do not need to re-login for every upstream release.
 * Make sure your email is verified on crates.io, so you can publish
   packages: https://crates.io/settings/profile
 * Make sure you are a crates.io package owner of the `nmstate`,
   `nmstatectl` and `nmstate-clib` crates.
 * Configure your GPG system, so `make release` can sign the tarball.

The script will create a PR updating the changelog and tagging the new
release. It will also publish the new release in GitHub and the crates
in crates.io.

The maintainer executing it will have to:
 * Edit the changelog when the editor opens
 * Review the PR with the new release. Ensure that the CI passes before
   merging.
 * Review the PR bumping to the next version. Ensure that the CI passes
   before merging.
