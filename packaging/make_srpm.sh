#!/bin/bash

set -e

SRC_DIR="$(dirname "$0")/.."
TMP_DIR=$(mktemp -d)
SPEC_FILE="$TMP_DIR/nmstate.spec"
OLD_PWD=$(pwd)
BASE_URL="https://github.com/nmstate/nmstate/"

for candidate in python3 python
do
    python="$(command -v "${candidate}" || true)"
    if [[ -n "${python}" ]]
    then
        break
    fi
done


if [[ -z "${python}" ]]
then
    echo >/dev/stderr "ERROR: No python command found."
    exit 127
fi

# outdir is used by COPR as well: https://docs.pagure.org/copr.copr/user_documentation.html
: ${outdir:=${OLD_PWD}}

trap 'rm -rf "$TMP_DIR"' INT TERM HUP EXIT

cd $SRC_DIR

eval "$(./packaging/get_version.sh)"


TAR_FILE="${TMP_DIR}/nmstate-${VERSION}.tar"
(
    "${python}" setup.py sdist --format tar --dist-dir $TMP_DIR

    ./packaging/make_spec.sh > "${SPEC_FILE}"
    tar --append --file=$TAR_FILE $SPEC_FILE
    gzip "${TAR_FILE}"
    curl -L ${BASE_URL}/releases/download/v1.4.5/nmstate-vendor-1.4.5.tar.xz \
        --output $TMP_DIR/nmstate-vendor-1.4.5.tar.xz

    rpmbuild --define "_rpmdir $TMP_DIR/" --define "_srcrpmdir $TMP_DIR/" \
    -ts $TAR_FILE.gz
) &> /dev/stderr

SRPM=$(find $TMP_DIR -type f -name \*.src.rpm -exec basename {} \;)
find $TMP_DIR -type f -name \*.rpm -exec mv {} "${outdir}" \;
echo ${outdir}/$SRPM
