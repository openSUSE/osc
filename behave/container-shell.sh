#!/bin/sh

TOPDIR=$(dirname $(readlink -f $0))

podman exec \
    --interactive \
    --tty \
    obs-server \
    /bin/bash

exit $?
