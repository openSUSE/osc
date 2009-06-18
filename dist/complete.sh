test -z "$BASH_VERSION" && return
complete -o default _nullcommand &> /dev/null || return
complete -r _nullcommand &> /dev/null         || return
complete -o default -C /usr/lib/osc/complete osc
