#!/bin/sh

TOPDIR=$(dirname $(readlink -f $0))

podman build "$@" \
    --tag obs-server \
    --volume="$TOPDIR":/opt/obs \
    $TOPDIR \
    2>&1 | tee container-build.log

exit $?
