# fish completion for git
# vim: smartindent:expandtab:ts=2:sw=2

function __fish_osc_needs_command
  set cmd (commandline -opc)
  if contains "$cmd" 'osc' 'osc help'
    return 0
  end
  return 1
end

function __fish_osc_using_command
  set cmd (commandline -opc)
  if [ (count $cmd) -gt 1 ]
    for arg in $argv
      if [ $arg = $cmd[2] ]
        return 0
      end
    end
  end
  return 1
end

# general options
complete -f -c osc -n 'not __fish_osc_needs_command' -s A -l apiurl           -d 'specify URL to access API server at or an alias' 
complete -f -c osc -n 'not __fish_osc_needs_command' -s c -l config           -d 'specify alternate configuration file' 
complete -f -c osc -n 'not __fish_osc_needs_command' -s d -l debug            -d 'print info useful for debugging' 
complete -f -c osc -n 'not __fish_osc_needs_command'      -l debugger         -d 'jump into the debugger before executing anything' 
complete -f -c osc -n 'not __fish_osc_needs_command' -s h -l help             -d 'show this help message and exit' 
complete -f -c osc -n 'not __fish_osc_needs_command' -s H -l http-debug       -d 'debug HTTP traffic (filters some headers)' 
complete -f -c osc -n 'not __fish_osc_needs_command'      -l http-full-debug  -d 'debug HTTP traffic (filters no headers)' 
complete -f -c osc -n 'not __fish_osc_needs_command'      -l no-gnome-keyring -d 'disable usage of GNOME Keyring' 
complete -f -c osc -n 'not __fish_osc_needs_command'      -l no-keyring       -d 'disable usage of desktop keyring system' 
complete -f -c osc -n 'not __fish_osc_needs_command'      -l post-mortem      -d 'jump into the debugger in case of errors' 
complete -f -c osc -n 'not __fish_osc_needs_command' -s q -l quiet            -d 'be quiet, not verbose' 
complete -f -c osc -n 'not __fish_osc_needs_command' -s t -l traceback        -d 'print call trace in case of errors' 
complete -f -c osc -n 'not __fish_osc_needs_command' -s v -l verbose          -d 'increase verbosity' 
complete -f -c osc -n 'not __fish_osc_needs_command'      -l version          -d 'show program\'s version number and exit' 

# osc commands
complete -f -c osc -n '__fish_osc_needs_command' -a 'add'                                                                                     -d 'Mark files to be added upon the next commit'
complete -f -c osc -n '__fish_osc_needs_command' -a 'addremove ar'                                                                            -d 'Adds new files, removes disappeared files'
complete -f -c osc -n '__fish_osc_needs_command' -a 'aggregatepac'                                                                            -d '"Aggregate" a package to another package'
complete -f -c osc -n '__fish_osc_needs_command' -a 'api'                                                                                     -d 'Issue an arbitrary request to the API'
complete -f -c osc -n '__fish_osc_needs_command' -a 'branch bco branchco getpac'                                                              -d 'Branch a package'
complete -f -c osc -n '__fish_osc_needs_command' -a 'chroot'                                                                                  -d 'into the buildchroot'
complete -f -c osc -n '__fish_osc_needs_command' -a 'clean'                                                                                   -d 'removes all untracked files from the package working ...'
complete -f -c osc -n '__fish_osc_needs_command' -a 'commit checkin ci'                                                                       -d 'Upload content to the repository server'
complete -f -c osc -n '__fish_osc_needs_command' -a 'config'                                                                                  -d 'get/set a config option'
complete -f -c osc -n '__fish_osc_needs_command' -a 'copypac'                                                                                 -d 'Copy a package'
complete -f -c osc -n '__fish_osc_needs_command' -a 'createincident'                                                                          -d 'Create a maintenance incident'
complete -f -c osc -n '__fish_osc_needs_command' -a 'createrequest creq'                                                                      -d 'create multiple requests with a single command'
complete -f -c osc -n '__fish_osc_needs_command' -a 'delete del remove rm'                                                                    -d 'Mark files or package directories to be deleted upon ...'
complete -f -c osc -n '__fish_osc_needs_command' -a 'deleterequest deletereq dr dropreq droprequest'                                          -d 'Request to delete (or "drop") a package or project'
complete -f -c osc -n '__fish_osc_needs_command' -a 'dependson whatdependson'                                                                 -d 'Show the build dependencies'
complete -f -c osc -n '__fish_osc_needs_command' -a 'detachbranch'                                                                            -d 'replace a link with its expanded sources'
complete -f -c osc -n '__fish_osc_needs_command' -a 'develproject bsdevelproject dp'                                                          -d 'print the devel project / package of a package'
complete -f -c osc -n '__fish_osc_needs_command' -a 'diff di ldiff linkdiff'                                                                  -d 'Generates a diff'
complete -f -c osc -n '__fish_osc_needs_command' -a 'distributions dists'                                                                     -d 'Shows all available distributions'
complete -f -c osc -n '__fish_osc_needs_command' -a 'getbinaries'                                                                             -d 'Download binaries to a local directory'
complete -f -c osc -n '__fish_osc_needs_command' -a 'help ? h'                                                                                -d 'give detailed help on a specific sub-command'
complete -f -c osc -n '__fish_osc_needs_command' -a 'importsrcpkg'                                                                            -d 'Import a new package from a src.rpm'
complete -f -c osc -n '__fish_osc_needs_command' -a 'info'                                                                                    -d 'Print information about a working copy'
complete -f -c osc -n '__fish_osc_needs_command' -a 'init'                                                                                    -d 'Initialize a directory as working copy'
complete -f -c osc -n '__fish_osc_needs_command' -a 'jobhistory jobhist'                                                                      -d 'Shows the job history of a project'
complete -f -c osc -n '__fish_osc_needs_command' -a 'linkpac'                                                                                 -d '"Link" a package to another package'
complete -f -c osc -n '__fish_osc_needs_command' -a 'linktobranch'                                                                            -d 'Convert a package containing a classic link with patc...'
complete -f -c osc -n '__fish_osc_needs_command' -a 'list LL lL ll ls'                                                                        -d 'List sources or binaries on the server'
complete -f -c osc -n '__fish_osc_needs_command' -a 'localbuildlog lbl'                                                                       -d 'Shows the build log of a local buildchroot'
complete -f -c osc -n '__fish_osc_needs_command' -a 'log'                                                                                     -d 'Shows the commit log of a package'
complete -f -c osc -n '__fish_osc_needs_command' -a 'maintainer bugowner'                                                                     -d 'Show maintainers according to server side configuration'
complete -f -c osc -n '__fish_osc_needs_command' -a 'maintenancerequest mr'                                                                   -d 'Create a request for starting a maintenance incident.'
complete -f -c osc -n '__fish_osc_needs_command' -a 'man'                                                                                     -d 'generates a man page'
complete -f -c osc -n '__fish_osc_needs_command' -a 'mbranch maintained sm'                                                                   -d 'Search or banch multiple instances of a package'
complete -f -c osc -n '__fish_osc_needs_command' -a 'meta'                                                                                    -d 'Show meta information, or edit it'
complete -f -c osc -n '__fish_osc_needs_command' -a 'mkpac'                                                                                   -d 'Create a new package under version control'
complete -f -c osc -n '__fish_osc_needs_command' -a 'mv'                                                                                      -d 'Move SOURCE file to DEST and keep it under version co...'
complete -f -c osc -n '__fish_osc_needs_command' -a 'my'                                                                                      -d 'show waiting work, packages, projects or requests inv...'
complete -f -c osc -n '__fish_osc_needs_command' -a 'patchinfo'                                                                               -d 'Generate and edit a patchinfo file.'
complete -f -c osc -n '__fish_osc_needs_command' -a 'pdiff'                                                                                   -d 'Quick alias to diff the content of a package with its...'
complete -f -c osc -n '__fish_osc_needs_command' -a 'prdiff projdiff projectdiff'                                                             -d 'Server-side diff of two projects'
complete -f -c osc -n '__fish_osc_needs_command' -a 'prjresults pr'                                                                           -d 'Shows project-wide build results'
complete -f -c osc -n '__fish_osc_needs_command' -a 'pull'                                                                                    -d 'merge the changes of the link target into your workin...'
complete -f -c osc -n '__fish_osc_needs_command' -a 'rdelete'                                                                                 -d 'Delete a project or packages on the server.'
complete -f -c osc -n '__fish_osc_needs_command' -a 'rdiff'                                                                                   -d 'Server-side "pretty" diff of two packages'
complete -f -c osc -n '__fish_osc_needs_command' -a 'rebuild rebuildpac'                                                                      -d 'Trigger package rebuilds'
complete -f -c osc -n '__fish_osc_needs_command' -a 'release'                                                                                 -d 'Release sources and binaries'
complete -f -c osc -n '__fish_osc_needs_command' -a 'releaserequest'                                                                          -d 'Create a request for releasing a maintenance update.'
complete -f -c osc -n '__fish_osc_needs_command' -a 'remotebuildlog rbl rblt rbuildlog rbuildlogtail remotebuildlogtail'                      -d 'Shows the build log of a package'
complete -f -c osc -n '__fish_osc_needs_command' -a 'repairlink'                                                                              -d 'Repair a broken source link'
complete -f -c osc -n '__fish_osc_needs_command' -a 'repairwc'                                                                                -d 'try to repair an inconsistent working copy'
complete -f -c osc -n '__fish_osc_needs_command' -a 'repositories platforms repos'                                                            -d 'shows repositories configured for a project. It skips...'
complete -f -c osc -n '__fish_osc_needs_command' -a 'repourls'                                                                                -d 'Shows URLs of .repo files'
complete -f -c osc -n '__fish_osc_needs_command' -a 'request review rq'                                                                       -d 'Show or modify requests and reviews'
complete -f -c osc -n '__fish_osc_needs_command' -a 'requestmaintainership reqbs reqbugownership reqmaintainership reqms requestbugownership' -d 'requests to add user as maintainer or bugowner'
complete -f -c osc -n '__fish_osc_needs_command' -a 'resolved'                                                                                -d 'Remove "conflicted" state on working copy files'
complete -f -c osc -n '__fish_osc_needs_command' -a 'restartbuild abortbuild'                                                                 -d 'Restart the build of a certain project or package'
complete -f -c osc -n '__fish_osc_needs_command' -a 'results r'                                                                               -d 'Shows the build results of a package or project'
complete -f -c osc -n '__fish_osc_needs_command' -a 'revert'                                                                                  -d 'Restore changed files or the entire working copy.'
complete -f -c osc -n '__fish_osc_needs_command' -a 'rremove'                                                                                 -d 'Remove source files from selected package'
complete -f -c osc -n '__fish_osc_needs_command' -a 'search bse se'                                                                           -d 'Search for a project and/or package.'
complete -f -c osc -n '__fish_osc_needs_command' -a 'service'                                                                                 -d 'Handle source services'
complete -f -c osc -n '__fish_osc_needs_command' -a 'setdevelproject sdp'                                                                     -d 'Set the devel project / package of a package'
complete -f -c osc -n '__fish_osc_needs_command' -a 'setlinkrev'                                                                              -d 'Updates a revision number in a source link.'
complete -f -c osc -n '__fish_osc_needs_command' -a 'signkey'                                                                                 -d 'Manage Project Signing Key'
complete -f -c osc -n '__fish_osc_needs_command' -a 'status st'                                                                               -d 'Show status of files in working copy'
complete -f -c osc -n '__fish_osc_needs_command' -a 'submitrequest sr submitpac submitreq'                                                    -d 'Create request to submit source into another Project'
complete -f -c osc -n '__fish_osc_needs_command' -a 'token'                                                                                   -d 'Show and manage authentication token'
complete -f -c osc -n '__fish_osc_needs_command' -a 'triggerreason tr'                                                                        -d 'Show reason why a package got triggered to build'
complete -f -c osc -n '__fish_osc_needs_command' -a 'undelete'                                                                                -d 'Restores a deleted project or package on the server.'
complete -f -c osc -n '__fish_osc_needs_command' -a 'unlock'                                                                                  -d 'Unlocks a project or package'
complete -f -c osc -n '__fish_osc_needs_command' -a 'update up'                                                                               -d 'Update a working copy'
complete -f -c osc -n '__fish_osc_needs_command' -a 'updatepacmetafromspec metafromspec updatepkgmetafromspec'                                -d 'Update package meta information from a specfile'
complete -f -c osc -n '__fish_osc_needs_command' -a 'vc'                                                                                      -d 'Edit the changes file'
complete -f -c osc -n '__fish_osc_needs_command' -a 'whois user who'                                                                          -d 'Show fullname and email of a buildservice user'
complete -f -c osc -n '__fish_osc_needs_command' -a 'wipebinaries'                                                                            -d 'Delete all binary packages of a certain project/package'
