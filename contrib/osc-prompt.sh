#!/bin/bash

__osc_prompt() {
    # Git has a precedence
    if git rev-parse --quiet --git-dir >/dev/null 2>&1 ; then
        # Test for the existence of bash function
        declare -F __git_ps1 >/dev/null && printf "%s" "$(__git_ps1 "$@")"
        return
    fi
    # Are we even in the OSC checkout?
    [ -d .osc ] || return

    local osc_binary osc_pattern osc_str;
    osc_binary=$(type -p osc)
    if [ -n "$1" ] ; then osc_pattern="${*}" ; else osc_pattern="(%s)" ; fi
    if [ -n "$osc_binary" ] && [ -x "$osc_binary" ] && [ -f .osc/_package ] ; then
        osc_str="$(osc status 2>/dev/null |cut -d' ' -f 1|sort|uniq -c|tr -d ' \n')"
        # shellcheck disable=SC2059
        printf " ${osc_pattern}" "$osc_str"
    fi
}
