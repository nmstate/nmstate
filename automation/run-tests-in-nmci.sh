#!/bin/bash -ex

EXEC_DIR=$(dirname "$(realpath "$0")")
PROJECT_DIR="$(dirname $EXEC_DIR)"
TEST_CMD="${EXEC_DIR}/run-tests.sh"

options=$(getopt --options "" \
    --long "copr:,rpm-dir:,help,debug-shell,el8,el9,fed,rawhide" \
    -- "${@}")
eval set -- "$options"
while true; do
    case "$1" in
    --el8)
        use_el8="1"
        ;;
    --el9)
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
        NM_RPM_DIR="$1"
        ;;
    --debug-shell)
        debug_exit_shell="1"
        ;;
    --help)
        set +x
        echo -n "$0 [--copr=...] [--rpm-dir=...] [--debug-shell] "
        echo -n "[--el8] [--el9] [--fed] [--rawhide]"
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

ARGS="--test-type integ_tier1"
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
elif [[ -v use_fed ]];then
    ARGS="$ARGS --fed"
elif [[ -v use_rawhide ]];then
    ARGS="$ARGS --rawhide"
else
    ARGS="$ARGS --el9"
fi

cd $PROJECT_DIR
env CONTAINER_CMD="podman" CI="true" $TEST_CMD $ARGS
