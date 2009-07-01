test -z "$BASH_VERSION" && return
complete -o default _nullcommand &> /dev/null || return
complete -r _nullcommand &> /dev/null         || return
test -s /usr/share/osc/complete && complete -o default -C /usr/share/osc/complete osc
test -s /usr/lib64/osc/complete && complete -o default -C /usr/lib64/osc/complete osc
test -s /usr/lib/osc/complete   && complete -o default -C /usr/lib/osc/complete osc
