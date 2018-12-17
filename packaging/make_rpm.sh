#!/bin/bash

set -e

SRC_DIR="$(dirname "$0")/.."
TMP_DIR=$(mktemp -d)
SPEC_FILE="$TMP_DIR/nmstate.spec"
OLD_PWD=$(pwd)
if [ $EUID -ne 0 ]; then
    SUDO="sudo"
else
    SUDO=""
fi

trap 'rm -rf "$TMP_DIR"' INT TERM HUP EXIT

cd $SRC_DIR

MAIN_VERSION=$(python setup.py --version)
COMMIT_COUNT=$(git rev-list --count HEAD --)
VERSION="${MAIN_VERSION}dev${COMMIT_COUNT}git$(git rev-parse --short HEAD)"

if [ -n "$(rpm -E %{?fedora} 2>/dev/null)" ] ||
   [ -n "$(rpm -E %{?el8} 2>/dev/null)" ] ;then
    cp packaging/nmstate.py3.spec.in $SPEC_FILE
    sed -i -e "s/@VERSION@/$VERSION/" $SPEC_FILE
    sed -i -e "s/@SRC_VERSION@/$MAIN_VERSION/" $SPEC_FILE
    $SUDO dnf install -y rpm-build
    $SUDO dnf builddep -y $SPEC_FILE
elif [ -n "$(rpm -E %{?el7} 2>/dev/null)" ];then
    cp packaging/nmstate.py2.spec.in $SPEC_FILE
    sed -i -e "s/@VERSION@/$VERSION/" $SPEC_FILE
    sed -i -e "s/@SRC_VERSION@/$MAIN_VERSION/" $SPEC_FILE
    $SUDO yum install -y rpm-build yum-utils
    $SUDO yum-builddep -y $SPEC_FILE
else
    echo "Not supported"
    exit 1
fi

TAR_FILE="$TMP_DIR/nmstate-$VERSION.tar"

python setup.py sdist --format tar --dist-dir $TMP_DIR
mv $TMP_DIR/nmstate*.tar $TAR_FILE
tar --append --file=$TAR_FILE $SPEC_FILE 1>/dev/null 2>/dev/null

rpmbuild --define "_rpmdir $TMP_DIR/" --define "_srcrpmdir $TMP_DIR/" \
    -ta $TAR_FILE
RPMS=$(find $TMP_DIR -type f -name \*.noarch.rpm -exec basename {} \;)
SRPM=$(find $TMP_DIR -type f -name \*.src.rpm -exec basename {} \;)
find $TMP_DIR -type f -name \*.rpm -exec mv {} $OLD_PWD \;
echo "SRPM CREATED:"
echo $OLD_PWD/$SRPM
echo "RPM CREATED:"
for RPM in $RPMS; do
    echo -n "$OLD_PWD/$RPM "
done
echo
