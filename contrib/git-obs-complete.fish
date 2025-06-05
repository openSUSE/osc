# exit immediately if argcomplete is not available
[ -e '/usr/bin/register-python-argcomplete' ] || exit 0

eval "$(register-python-argcomplete --shell fish git-obs)"
