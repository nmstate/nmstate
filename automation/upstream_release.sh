#!/bin/bash -e

MAIN_BRANCH_NAME="base"
UPSTREAM_GIT_HTTPS="https://github.com/nmstate/nmstate.git"
UPSTREAM_GIT_SSH="git@github.com:nmstate/nmstate.git"
TMP_CHANGELOG_FILE=$(mktemp)

CHANGLOG_FORMAT="
### Breaking changes\n\
 - N/A\n\
\n\
### New features\n\
 - N/A\n\
\n\
### Bug fixes"

function cleanup {
    rm -f $TMP_CHANGELOG_FILE
    rm -f /tmp/nmstate*.tar.*
}

trap cleanup ERR EXIT

CODE_BASE_DIR=$(readlink -f "$(dirname -- "$0")/..");

cd $CODE_BASE_DIR;

# Check prerequisites
err=0
for cmd in git hub cargo curl grep sed vim gpg cargo-vendor-filterer; do
    if ! command -v $cmd > /dev/null 2>&1; then
        echo "$cmd not found. Please install it." >&2
        err=1
    fi
done
if [ $err = 1 ]; then
    exit 1
fi

if ! git fetch upstream 2>/dev/null; then
    echo "Upstream repository not found. If you use ssh keys to push, add it using:" >&2
    echo " $ git remote add upstream $UPSTREAM_GIT_SSH" >&2
    echo "Otherwise, if you use HTTPS, add it using:" >&2
    echo " $ git remote add upstream $UPSTREAM_GIT_HTTPS" >&2
    exit 1
fi

CARGO_REGISTRY_TOKEN=$(grep -oP 'token = "\K[^"]+' ~/.cargo/credentials.toml || :)
if [ -z "$CARGO_REGISTRY_TOKEN" ] || \
   ! curl -s "https://crates.io/api/v1/crates?following=1" \
          -H "Authorization: Bearer $CARGO_REGISTRY_TOKEN" \
          -H "User-Agent: nmstate-upstream-release (https://github.com/nmstate/nmstate)" | grep -q "perform this action"; then
    # crates.io does not provide access to any normal API to query user status,
    # so we (ab)use the crate search API to check if the token is valid.
    echo "Cargo registry token is missing or invalid (may be expired). Please log in using:" >&2
    echo " $ cargo login" >&2
    echo "and confirm your email on crates.io: https://crates.io/settings/profile" >&2
    echo "The token you use to log in should have at least 'publish-update' permissions." >&2
    exit 1
fi

if ! hub pr list < /dev/null >/dev/null 2>&1; then
    echo '"hub pr list" failed, this might mean your github login is invalid.' >&2
    echo "To log in, you can run that command. As the password, you should use" >&2
    echo "a GitHub personal access token with 'repo' scope." >&2
    echo "You can make it here: https://github.com/settings/tokens/new" >&2
    exit 1
fi

set -x
CUR_VERSION=$(cat VERSION);
CUR_MAJOR_VERSION=$(echo $CUR_VERSION|cut -f1 -d.)
CUR_MINOR_VERSION=$(echo $CUR_VERSION|cut -f2 -d.)
CUR_MICRO_VERSION=$(echo $CUR_VERSION|cut -f3 -d.)
PRE_VERSION="${CUR_MAJOR_VERSION}.${CUR_MINOR_VERSION}.$(( \
    CUR_MICRO_VERSION - 1))";
NEXT_VERSION="${CUR_MAJOR_VERSION}.${CUR_MINOR_VERSION}.$(( \
    CUR_MICRO_VERSION + 1))";

git branch new_release || true
git checkout new_release
git reset --hard upstream/$MAIN_BRANCH_NAME
echo "# Changelog" > $TMP_CHANGELOG_FILE
echo "## [$CUR_VERSION] - $(date +%F)" >> $TMP_CHANGELOG_FILE
echo -e $CHANGLOG_FORMAT >> $TMP_CHANGELOG_FILE
git log --oneline --format=" - %s. (%h)" \
    v${PRE_VERSION}..upstream/$MAIN_BRANCH_NAME -- | \
    grep -v -E '^ - test:' | \
    grep -v -E '^ - Bump version' | \
    grep -v -E 'cargo clippy'  >> $TMP_CHANGELOG_FILE
echo "" >> $TMP_CHANGELOG_FILE

vim $TMP_CHANGELOG_FILE
CHANGELOG_STR=$(sed -n '3,$p' $TMP_CHANGELOG_FILE|tr '#' '=')
sed -n '2,$p' CHANGELOG >> $TMP_CHANGELOG_FILE

mv $TMP_CHANGELOG_FILE $CODE_BASE_DIR/CHANGELOG
git commit --signoff $CODE_BASE_DIR/CHANGELOG -m "New release ${CUR_VERSION}" \
    -m "$CHANGELOG_STR"
git push origin +new_release
hub pull-request -b $MAIN_BRANCH_NAME --no-edit

while true; do
    echo "Press 'y' after new release PR merged or 'n' to exit."
    read -s -n 1 key

    case $key in
            y|Y)
            echo "You pressed 'y'. Continuing..."
            break
            ;;
        n|N)
            echo "You pressed 'n'. Exiting..."
            exit 1
            ;;
        *)
            echo "Invalid input. Please press 'y' or 'n'."
            ;;
    esac
done

git checkout $MAIN_BRANCH_NAME
git fetch upstream
git reset --hard upstream/$MAIN_BRANCH_NAME
git tag --sign v$CUR_VERSION -m "New release ${CUR_VERSION}" \
    -m "$CHANGELOG_STR"
git push upstream --tags

cd $CODE_BASE_DIR
RELEASE=1 make release

echo "New release $CUR_VERSION

${CHANGELOG_STR//=/#}" |
hub release create \
    -a nmstate-$CUR_VERSION.tar.gz -a nmstate-$CUR_VERSION.tar.gz.asc \
    -a nmstate-vendor-$CUR_VERSION.tar.xz \
    -F - "v$CUR_VERSION"

publish_crate() {
    cd $CODE_BASE_DIR/rust/src/$1
    cargo publish --allow-dirty
    cd $CODE_BASE_DIR
}

publish_crate lib
publish_crate cli
publish_crate clib

# Bump version
git branch bump_version || true
git checkout bump_version
git reset --hard upstream/$MAIN_BRANCH_NAME
sed -i -e "s/$CUR_VERSION/$NEXT_VERSION/" \
    VERSION \
    rust/src/cli/Cargo.toml \
    rust/src/clib/Cargo.toml \
    rust/src/lib/Cargo.toml \
    rust/src/python/setup.py \
    rust/src/python/libnmstate/__init__.py
git commit -a --signoff -m "Bump version to $NEXT_VERSION"
git push origin +bump_version
hub pull-request -b $MAIN_BRANCH_NAME --no-edit
