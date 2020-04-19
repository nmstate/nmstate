#! /bin/bash

set -e

OLD_PWD=$(pwd)
SRC_DIR="$(dirname "$0")/.."

cd "$SRC_DIR"

VERSION_STR="$(cat libnmstate/VERSION)"
VERSION=${VERSION_STR%-*}
PRE_RELEASE=${VERSION_STR:$(( ${#VERSION} + 1 ))}
: ${PRE_RELEASE:="alpha0"}
DATE="$(date +%Y%m%d)"

COMMIT_COUNT="$(git rev-list --count HEAD --)"
GIT_REVISION="$(git rev-parse --short HEAD)"

TAR_VERSION="${VERSION}dev${COMMIT_COUNT}git${GIT_REVISION}"

RPM_VERSION="${VERSION}"
RPM_RELEASE="0.${PRE_RELEASE}.${DATE}.${COMMIT_COUNT}git${GIT_REVISION}"

RPM_DATE="$(LC_TIME=C date +"%a %b %d %Y")"

RPM_CHANGELOG="* ${RPM_DATE} N. N. - ${RPM_VERSION}-${RPM_RELEASE}"

echo VERSION="${VERSION}"
echo RPM_VERSION="${RPM_VERSION}"
echo RPM_RELEASE="${RPM_RELEASE}"
echo RPM_CHANGELOG="'${RPM_CHANGELOG}'"
cd "$OLD_PWD"
