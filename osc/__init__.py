__all__ = [
    'babysitter',
    'build',
    'connection',
    'commandline',
    'core',
    'fetch',
    'grabber',
    'meter',
    'oscerr',
    'oscssl',
]


from .util import git_version
__version__ = git_version.get_version('1.8.3')


# vim: sw=4 et
