#!/usr/bin/python

# Copyright (C) 2008 Peter Poeml / Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.



class OscBaseError(Exception):
    def __init__(self, args=()):
        Exception.__init__(self)
        self.args = args
    def __str__(self):
        return ''.join(self.args)

class UserAbort(OscBaseError):
    """Exception raised when the user requested abortion"""

class ConfigError(OscBaseError):
    """Exception raised when there is an error in the config file"""
    def __init__(self, msg):
        OscBaseError.__init__(self)
        self.msg = msg

class APIError(OscBaseError):
    """Exception raised when there is an error in the output from the API"""
    def __init__(self, msg):
        OscBaseError.__init__(self)
        self.msg = msg

class NoConfigfile(OscBaseError):
    """Exception raised when osc's configfile cannot be found"""
    def __init__(self, fname, msg):
        OscBaseError.__init__(self)
        self.file = fname
        self.msg = msg

class WrongArgs(OscBaseError):
    """Exception raised by the cli for wrong arguments usage"""

class WrongOptions(OscBaseError):
    """Exception raised by the cli for wrong option usage"""
    #def __str__(self):
    #    s = 'Sorry, wrong options.'
    #    if self.args:
    #        s += '\n' + self.args
    #    return s

class NoWorkingCopy(OscBaseError):
    """Exception raised when directory is neither a project dir nor a package dir"""

class WorkingCopyWrongVersion(OscBaseError):
    """Exception raised when working copy's .osc/_osclib_version doesn't match"""

class WorkingCopyOutdated(OscBaseError):
    """Exception raised when the working copy is outdated.
    It takes a tuple with three arguments: path to wc, 
    revision that it has, revision that it should have.
    """
    def __str__(self):
        return ('Working copy \'%s\' is out of date (rev %s vs rev %s).\n'
               'Looks as if you need to update it first.' \
                    % (self[0], self[1], self[2]))


class UnreadableFile(OscBaseError):
    def __init__(self, msg):
        OscBaseError.__init__(self)
        self.msg = msg 

class OscIOError(OscBaseError):
    def __init__(self, e, msg):
        OscBaseError.__init__(self)
        self.e = e
        self.msg = msg

class SignalInterrupt(Exception):
    """Exception raised on SIGTERM and SIGHUP."""

class PackageError(OscBaseError):
    """Base class for all Package related exceptions"""
    def __init__(self, prj, pac):
        OscBaseError.__init__(self)
        self.prj = prj
        self.pac = pac

class PackageExists(PackageError):
    """
    Exception raised when a local object already exists 
    """
    def __init__(self, prj, pac, msg):
        PackageError.__init__(self, prj, pac)
        self.msg = msg

class PackageMissing(PackageError):
    """
    Exception raised when a local object doesn't exist
    """
    def __init__(self, prj, pac, msg):
        PackageError.__init__(self, prj, pac)
        self.msg = msg
