# Copyright (C) 2008 Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.


class OscBaseError(Exception):
    def __init__(self, args=()):
        super().__init__()
        self.args = args

    def __str__(self):
        return ''.join(self.args)


class UserAbort(OscBaseError):
    """Exception raised when the user requested abortion"""


class ConfigError(OscBaseError):
    """Exception raised when there is an error in the config file"""

    def __init__(self, msg, fname):
        super().__init__()
        self.msg = msg
        self.file = fname

    def __str__(self):
        return f"Error in config file {self.file}\n   {self.msg}"


class ConfigMissingApiurl(ConfigError):
    """Exception raised when a apiurl does not exist in the config file"""

    def __init__(self, msg, fname, url):
        super().__init__(msg, fname)
        self.url = url


class ConfigMissingCredentialsError(ConfigError):
    def __init__(self, msg, fname, url):
        super().__init__(msg, fname)
        self.url = url


class APIError(OscBaseError):
    """Exception raised when there is an error in the output from the API"""

    def __init__(self, msg):
        super().__init__()
        self.msg = msg

    def __str__(self):
        return f"{self.__class__.__name__}: {self.msg}"


class NotFoundAPIError(APIError):
    """
    Requested data was not found.
    """


class NoConfigfile(OscBaseError):
    """Exception raised when osc's configfile cannot be found"""

    def __init__(self, fname, msg):
        super().__init__()
        self.file = fname
        self.msg = msg

    def __str__(self):
        return f"Config file cannot be found: {self.file}\n   {self.msg}"


class ExtRuntimeError(OscBaseError):
    """Exception raised when there is a runtime error of an external tool"""

    def __init__(self, msg, fname):
        super().__init__()
        self.msg = msg
        self.file = fname


class ServiceRuntimeError(OscBaseError):
    """Exception raised when the execution of a source service failed"""

    def __init__(self, msg):
        super().__init__()
        self.msg = msg


class WrongArgs(OscBaseError):
    """Exception raised by the cli for wrong arguments usage"""


class WrongOptions(OscBaseError):
    """Exception raised by the cli for wrong option usage"""
    # def __str__(self):
    #    s = 'Sorry, wrong options.'
    #    if self.args:
    #        s += '\n' + self.args
    #    return s


class NoWorkingCopy(OscBaseError):
    """Exception raised when directory is neither a project dir nor a package dir"""


class NotMissing(OscBaseError):
    """Exception raised when link target should not exist, but it does"""


class WorkingCopyWrongVersion(OscBaseError):
    """Exception raised when working copy's .osc/_osclib_version doesn't match"""


class WorkingCopyOutdated(OscBaseError):
    """Exception raised when the working copy is outdated.
    It takes a tuple with three arguments: path to wc,
    revision that it has, revision that it should have.
    """

    def __str__(self):
        return ('Working copy \'%s\' is out of date (rev %s vs rev %s).\n'
                'Looks as if you need to update it first.'
                % (self.args[0], self.args[1], self.args[2]))


class ProjectError(OscBaseError):
    """Base class for all Project related exceptions"""

    def __init__(self, prj, msg=None):
        super().__init__()
        self.prj = prj
        self.msg = msg

    def __str__(self):
        result = f"{self.__class__.__name__}: {self.prj}"
        if self.msg:
            result += f": {self.msg}"
        return result


class PackageError(OscBaseError):
    """Base class for all Package related exceptions"""

    def __init__(self, prj, pac, msg=None):
        super().__init__()
        self.prj = prj
        self.pac = pac
        self.msg = msg

    def __str__(self):
        result = f"{self.__class__.__name__}: {self.prj}/{self.pac}"
        if self.msg:
            result += f": {self.msg}"
        return result


class WorkingCopyInconsistent(PackageError):
    """Exception raised when the working copy is in an inconsistent state"""

    def __init__(self, prj, pac, dirty_files, msg):
        super().__init__(prj, pac, msg)
        self.dirty_files = dirty_files


class LinkExpandError(PackageError):
    """Exception raised when source link expansion fails"""


class OscIOError(OscBaseError):
    def __init__(self, e, msg):
        super().__init__()
        self.e = e
        self.msg = msg


class OscValueError(OscBaseError):
    """
    Invalid argument value (of correct type).
    """
    pass


class OscInvalidRevision(OscValueError):
    """
    Invalid revision value.
    """

    def __str__(self):
        return "Invalid revision value: {}".format("".join(self.args))


class PackageNotInstalled(OscBaseError):
    """
    Exception raised when a package is not installed on local system
    """

    def __init__(self, pkg):
        super().__init__((pkg,))

    def __str__(self):
        return 'Package %s is required for this operation' % self.args


class SignalInterrupt(Exception):
    """Exception raised on SIGTERM and SIGHUP."""


class PackageExists(PackageError):
    """
    Exception raised when a local object already exists
    """


class PackageMissing(PackageError):
    """
    Exception raised when a local object doesn't exist
    """


class PackageFileConflict(PackageError):
    """
    Exception raised when there's a file conflict.
    Conflict doesn't mean an unsuccessfull merge in this context.
    """

    def __init__(self, prj, pac, file, msg):
        super().__init__(prj, pac, msg)
        self.file = file


class PackageInternalError(PackageError):
    pass


# vim: sw=4 et
