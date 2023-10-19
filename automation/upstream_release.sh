#!/bin/bash -ex

MAIN_BRANCH_NAME="base"
UPSTERAM_GIT="https://github.com/nmstate/nmstate.git"
NEW_RELEASE_URL="https://github.com/nmstate/nmstate/releases/new"
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
git fetch upstream || (git remote add upstream $UPSTERAM_GIT; \
    git fetch upstream)
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
while true; do
    echo "Press 'y' to creating pull request or 'n' to exit."
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
git push origin +new_release
hub pull-request -b $MAIN_BRANCH_NAME --no-edit -o

while true; do
    echo "Press 'y' to do tagging on new release or 'n' to exit."
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

cd $CODE_BASE_DIR/rust/src/lib
cargo publish
cd $CODE_BASE_DIR/rust/src/cli
cargo publish

cd $CODE_BASE_DIR
RELEASE=1 make release
mv -v nmstate-$CUR_VERSION.tar* nmstate-vendor-$CUR_VERSION.tar.xz /tmp/
echo "Please upload these nmstate tarballs in /tmp folder"

URL="${NEW_RELEASE_URL}?tag=v$CUR_VERSION"
echo "${CHANGELOG_STR//=/#}"

if [ -n $BROWSER ];then
    $BROWSER $URL
else
    echo "Please visit $URL to create new release"
fi

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
hub pull-request -b $MAIN_BRANCH_NAME --no-edit -o
