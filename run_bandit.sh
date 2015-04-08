#!/bin/bash

# you can pass as argument "csv","json" or "txt" (default)
if [ "$1" != "" ];then
    OUTPUT=$1
else
    OUTPUT="txt"
fi

# check if bandit is installed
command -v bandit >/dev/null 2>&1 || { echo "bandit should be installed. get the package from https://build.opensuse.org/package/show/home:vpereirabr/python-bandit.  Aborting." >&2; exit 1; }

bandit -c /usr/etc/bandit/bandit.yaml -r osc -f $OUTPUT

if [ "$OUTPUT" == "csv" ];then
    cat bandit_results.csv
    rm -f bandit_results.csv
fi
