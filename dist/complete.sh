test -z "$BASH_VERSION" && return
complete -o default _nullcommand >/dev/null 2>&1 || return
complete -r _nullcommand >/dev/null 2>&1         || return
COMP_WORDBREAKS="${COMP_WORDBREAKS//:}"
test -s /usr/share/osc/complete && complete -o default -C /usr/share/osc/complete osc
test -s /usr/lib64/osc/complete && complete -o default -C /usr/lib64/osc/complete osc
test -s /usr/lib/osc/complete   && complete -o default -C /usr/lib/osc/complete osc
