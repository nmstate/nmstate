#!/bin/bash -ex

EXEC_DIR=$(dirname "$(realpath "$0")")
PROJECT_DIR="$(dirname $EXEC_DIR)"
TEST_CMD="${EXEC_DIR}/run-tests.sh"

options=$(getopt --options "" \
    --long "copr:,rpm-dir:,help,debug-shell,el8,el9" \
    -- "${@}")
eval set -- "$options"
while true; do
    case "$1" in
    --el8)
        use_el8="1"
        ;;
    --el9)
        use_el9="1"
        ;;
    --copr)
        shift
        NM_COPR="$1"
        ;;
    --rpm-dir)
        shift
        NM_RPM_DIR="$1"
        ;;
    --debug-shell)
        debug_exit_shell="1"
        ;;
    --help)
        set +x
        echo -n "$0 [--copr=...] [--rpm-dir=...] [--debug-shell] "
        echo -n "[--el8] [--el9]"
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

echo $NM_COPR
echo $NM_RPM_DIR

ARGS="--test-type integ_tier1 --el9"
if [[ -v NM_COPR ]];then
    ARGS="$ARGS --copr $NM_COPR"
fi

if [[ -v NM_RPM_DIR ]];then
    ARGS="$ARGS --nm-rpm-dir $NM_RPM_DIR"
fi

if [[ -v debug_exit_shell ]];then
    ARGS="$ARGS --debug-shell"
fi

if [[ -v use_el8 ]];then
    ARGS="$ARGS --el8"
fi

if [[ -v use_el9 ]];then
    ARGS="$ARGS --el9"
fi

cd $PROJECT_DIR
env CONTAINER_CMD="podman" CI="true" $TEST_CMD $ARGS
