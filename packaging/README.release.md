The `make upstream_release` command is created to do auto release in upstream.
In order to make it works:

 * Your github account has enough right to do release in nmstate.
 * Your git setup is OK for force pushing to your github fork.
 * Your GPG public key has been listed in `nmstate.gpg` file.
 * Install `hub` command from https://hub.github.com/ and configure it. So it
   can create pull request without intervention.
 * Run `cargo install cargo-vendor-filterer`, so `make release` can work.
 * Configure your GPG system, so `make release` can sign the tarball.
