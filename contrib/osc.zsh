#compdef osc
#
# Copyright (C) 2009,2010 Holger Macht <holger@homac.de>
# Copyright (C) 2023      Björn Bidar  <bjorn.bidar@jolla.com>
#
# This file is released under the GPLv2.
#
# Based on the zsh guide from http://zsh.dotsrc.org/Guide/zshguide06.html
#
# Toggle verbose completions: zstyle ':completion:*:osc:*' verbose no
#                             zstyle ':completion:*:osc-subcommand:*' verbose no
#
# version 0.2
#

# Main dispatcher

_osc() {
    # Variables shared by all internal functions
    local osc_projects osc_rc osc_cmd osc_alias
    _osc_complete_prepare
    osc_projects="${XDG_CACHE_HOME}/osc.projects"
    osc_rc="${XDG_CONFIG_HOME}/osc/oscrc"
    osc_cmd=osc

    if [[ "${words[0]}" = "isc" ]] ; then
        osc_alias=internal
    fi

    if [ -s "${PWD}/.osc/_apiurl" -a -s "${osc_rc}" ]; then
        local osc_apiurl
        read osc_apiurl < "${PWD}/.osc/_apiurl"
        # We prefer to match an apiurl with an alias so that the project list
        # cache would match also when -A was passed with said alias.
        # If there's no alias for that api url match to use the plain apiurl instead.
        osc_alias=$(sed -rn '\@^\['${apiurl}'@,\@=@{\@^aliases=@{s@[^=]+=([^,]+),.*@\1@p};}' < "${osc_rc}" 2> /dev/null)
        if [ -z $osc_alias ] ; then
            osc_alias=${osc_apiurl}
        fi
    fi

    if (( CURRENT > 2 )) && [[ ${words[2]} != "help" ]]; then
        # Remember the subcommand name
	local cmd=${words[2]}
        # Set the context for the subcommand.
	curcontext="${curcontext%:*:*}:osc-subcommand"
        # Narrow the range of words we are looking at to exclude `osc'
	(( CURRENT-- ))
	shift words
        # Run the completion for the subcommand
    if [ $cmd = -A -o $cmd = --apiurl ] ; then
        if [[ -s "${osc_rc}" ]] ; then
            local hints=($(sed -rn '/^(aliases=|\[http)/{s/,/ /g;s/(aliases=|\[|\])//gp}' < "${osc_rc}" 2> /dev/null))
            if [[ -n "${words[2]}" ]]; then
	            for h in ${hints[@]} ; do
	                case "$h" in
	                    http*)
		                    local tmp=$(sed -rn '\@^\['${h}'@,\@=@{\@^aliases=@{s@[^=]+=([^,]+),.*@\1@p};}' < "${osc_rc}" 2> /dev/null)
		                    if [[ "${words[2]}" = "$h" ]]; then
		                        osc_alias=$tmp
		                        break
		                    fi
		                    ;;
	                    *)
		                    if [[ "${words[2]}" = "$h" ]]; then
		                        osc_alias=$h
		                        break
		                    fi
	                esac
	            done
            else
                _arguments '1:ALIAS:( `echo $hints`)'
                return
            fi
        fi
    fi

    if [[ -n "$osc_alias" ]] ; then
        osc_projects="${osc_projects}.${osc_alias//\//_}"
        osc_command="$osc_command -A ${osc_alias}"
    fi

    _osc_update_project_list

    case $cmd in
        submitrequest|submitreq|sr) _osc_cmd_submitreq ;;
        getbinaries) _osc_cmd_getbinaries ;;
        build) _osc_cmd_build ;;
        checkout|co|branch|getpac|bco|branchco) _osc_cmd_checkout ;;
        buildlog|buildinfo|bl|blt|buildlogtail) _osc_cmd_buildlog ;;
        *) _osc_cmd_do $cmd
    esac
    else
	local hline
	local -a cmdlist
	local tag=0
	_call_program help-commands osc help | while read -A hline; do
	    # start parsing with "commands:"
	    [[ $hline[1] = "commands:" ]] && tag=1
	    # stop parsing at the line starting with "For"
	    [[ $hline[1] = "For" ]] && tag=0
	    [[ $tag = 0 ]] && continue
	    # all commands have to start with lower case letters
	    [[ $hline[1] =~ ^[A-Z] ]] && continue
	    (( ${#hline} < 2 )) && continue

    	    # ${hline[1]%,} truncates the last ','
	    cmdlist=($cmdlist "${hline[1]%,}:${hline[2,-1]}")
	done
	_describe -t osc-commands 'osc command' cmdlist
    fi
}

_osc_call_me_maybe()
{
    typeset -i ctime=$(command date -d "$(command stat -c '%z' ${1})" +'%s')
    typeset -i   now=$(command date -d now +'%s')
    if ((now - ctime < 86400)) ; then
        return 1
    fi
    return 0
}

_osc_complete_prepare() {
    local xdg_dir
    for xdg_dir in "${XDG_CACHE_HOME:=$HOME/.cache}" "${XDG_CONFIG_HOME:=$HOME/.config}"; do
        if [[ ! -d "${xdg_dir}" ]]; then
            mkdir -p "${xdg_dir}"
        fi
    done

    if [[ -f ~/.osc.projects ]]; then
        rm ~/.osc.projects -f
    fi
}

_osc_update_project_list() {
    if [[ -s "${osc_projects}" ]] ; then
        if _osc_call_me_maybe "$osc_projects" ; then
            if tmp=$(mktemp ${osc_projects}.XXXXXX) ; then
                command ${osc_cmd} ls / >| $tmp
	            mv -uf $tmp ${osc_projects}
	        fi
        fi
    else
        command ${osc_cmd} ls / >| "${osc_projects}"
    fi
}

_osc_project_repositories() {
    if [ ! -s $PWD/.osc/_build_repositories ] || \
           _osc_call_me_maybe $PWD/.osc/_build_repositories ; then
        osc repositories > /dev/null
    fi
    # Just check if file exist in case the call to the api failed
    if [ -s $PWD/.osc/_build_repositories ] ; then
        cat $PWD/.osc/_build_repositories | while read build_repository ; do
            # Only output first word of each line
            echo ${build_repository%\ *}
        done | sort -u
    fi
}

_osc_project_repositories_arches() {
    if [ ! -s $PWD/.osc/_build_repositories ] || \
           _osc_call_me_maybe $PWD/.osc/_build_repositories ; then
        osc repositories > /dev/null
    fi
    # Just check if file exist in case the call to the api failed
    if [ -s $PWD/.osc/_build_repositories ] ; then
        grep -- $1 $PWD/.osc/_build_repositories | while read build_repository ; do
            # Only output second word of each line
            echo ${build_repository#*\ }
        done | sort -u
    fi
}


_osc_cmd_getbinaries() {
    if [ "$words[2]" = "-" ]; then
	    _osc_complete_help_commands 'options' 'option'
	    return
    else
        if [ -n "$words[2]" ] ; then
            local osc_project_repository_arch=$(_osc_project_repositories_arches \
                                                    "${words[2]}")
        fi
        _arguments \
	        '1:PROJECT:( `cat $osc_projects` )' \
	        '2:PACKAGE:(PACKAGE)' \
	        '3:REPOSITORY:( `_osc_project_repositories`' \
	        '4:ARCHITECTURE:(`echo $osc_project_repository_arch`)'
    fi
}

_osc_cmd_checkout() {
    if [ "$words[2]" = "-" ]; then
	    _osc_complete_help_commands 'options' 'option'
	    return
    else
        _arguments \
	        '1:PROJECT:( `cat $osc_projects` )' \
	        '2:PACKAGE:(PACKAGE)'
    fi
}

_osc_cmd_buildlog() {
    if [ "$words[2]" = "-" ]; then
	    _osc_complete_help_commands 'options' 'option'
	    return
    else
        if [ -n "$words[2]" ] ; then
            local osc_project_repository_arch=$(_osc_project_repositories_arches \
                                                    "${words[2]}")
        fi
        _arguments \
	        '1:REPOSITORY:( `_osc_project_repositories` )' \
	        '2:ARCHITECTURE:(`echo $osc_project_repository_arch`)'
    fi
}

_osc_cmd_build() {
    if [ "$words[2]" = "-" ]; then
	    _osc_complete_help_commands 'options' 'option'
	    return
    else
        if [ -n "$words[2]" ] ; then
            local osc_project_repository_arch=$(_osc_project_repositories_arches \
                                                    "${words[2]}")
        fi
        _arguments \
	        '1:REPOSITORY:( `_osc_project_repositories` )' \
	        '2:ARCHITECTURE:(`echo $osc_project_repository_arch`)' \
            '3:Build Description:_files'
    fi
}

_osc_cmd_submitreq() {
    _osc_complete_help_commands 'options' 'option'
}

_osc_complete_help_commands() {
    local hline
    local -a cmdlist
    local tag=0
    _call_program help-commands osc help $cmd | while read -A hline; do
        # start parsing from "usage:"
	[[ $hline[1] = "${1}:" ]] && tag=1
	[[ $tag = 0 ]] && continue

	if [[ $hline[1] =~ ^osc ]]; then
	    shift hline; shift hline
	elif ! [[ $hline[1] =~ ^- ]]; then
            # Option has to start with a '-' or 'osc submitrequest'
	    continue
	fi

	(( ${#hline} < 2 )) && continue

    cmdlist=($cmdlist "${hline[1]%,}:${hline[2,-1]}")

    done

    if [ -n "$cmdlist" ] ; then
        _describe -t osc-commands "osc $2" cmdlist
    else
        return 1
    fi
}

_osc_cmd_do() {
    # only start completion if there's some '-' on the line
    if ! [ "$words[2]" = "-" ]; then
	    _complete
	    return
    fi

    if ! _osc_complete_help_commands 'options' 'option'; then
        _complete
    fi
}

# Code to make sure _osc is run when we load it
_osc "$@"


