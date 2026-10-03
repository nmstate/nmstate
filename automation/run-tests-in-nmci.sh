#!/bin/bash -ex

EXEC_DIR=$(dirname "$(realpath "$0")")
PROJECT_DIR="$(dirname $EXEC_DIR)"
TEST_CMD="${EXEC_DIR}/run-tests.sh"

options=$(getopt --options "" \
    --long "copr:,rpm-dir:,compiled-rpms-dir:,nmstate-copr:,help,debug-shell,el8,el9,el10,fed,rawhide" \
    -- "${@}")
eval set -- "$options"
while true; do
    case "$1" in
    --el8)
        use_el8="1"
        ;;
    --el9)
        ;;
    --el10)
        use_el10="1"
        ;;
    --fed)
        use_fed="1"
        ;;
    --rawhide)
        use_rawhide="1"
        ;;
    --copr)
        shift
        NM_COPR="$1"
        ;;
    --rpm-dir)
        shift
        COMPILED_RPMS_DIR="$1"
        ;;
    --compiled-rpms-dir)
        shift
        COMPILED_RPMS_DIR="$1"
        ;;
    --nmstate-copr)
        shift
        NMSTATE_COPR="$1"
        ;;
    --debug-shell)
        debug_exit_shell="1"
        ;;
    --help)
        set +x
        echo -n "$0 [--copr=...] [--compiled-rpms-dir=...] [--nmstate-copr=...] "
        echo -n "[--debug-shell] "
        echo -n "[--el8] [--el9] [--el10] [--fed] [--rawhide]"
        echo
        exit
        ;;
    --)
        shift
        break
        ;;
    esac
    shift
done

echo "NM_COPR: ${NM_COPR:-}"
echo "NMSTATE_COPR: ${NMSTATE_COPR:-}"
echo "COMPILED_RPMS_DIR: ${COMPILED_RPMS_DIR:-}"

ARGS=("--test-type" "integ_tier1" "--nolog")
if [[ -v NM_COPR ]];then
    ARGS+=("--copr" "$NM_COPR")
fi

if [[ -v COMPILED_RPMS_DIR ]];then
    ARGS+=("--compiled-rpms-dir" "$COMPILED_RPMS_DIR")
fi

if [[ -v NMSTATE_COPR ]];then
    ARGS+=("--use-installed-nmstate")
    COPR_CMD="dnf5 install --assumeyes 'dnf5-command(copr)' 2>/dev/null"
    COPR_CMD+=" || dnf install --assumeyes 'dnf-command(copr)' &&"
    COPR_CMD+=" dnf copr enable --assumeyes \"$NMSTATE_COPR\""
    COPR_CMD+=" && dnf install --assumeyes nmstate"
    ARGS+=("--customize" "$COPR_CMD")
fi

if [[ -v debug_exit_shell ]];then
    ARGS+=("--debug-shell")
fi

if [[ -v use_el8 ]];then
    ARGS+=("--el8")
elif [[ -v use_el10 ]];then
    ARGS+=("--el10")
elif [[ -v use_fed ]];then
    ARGS+=("--fed")
elif [[ -v use_rawhide ]];then
    ARGS+=("--rawhide")
else
    ARGS+=("--el9")
fi

cd $PROJECT_DIR
env CONTAINER_CMD="podman" CI="true" "$TEST_CMD" "${ARGS[@]}"
