# Copyright Contributors to the osc project.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.


"""
This module handles configuration of osc.


Configuring osc from oscrc
--------------------------

To configure osc from oscrc, do following::

    import osc.conf

    # see ``get_config()`` documentation for available function arguments
    # see ``oscrc(5)`` man page for oscrc configuration options
    osc.conf.get_config()


Configuring osc from API
------------------------

To configure osc purely from the API (without reading oscrc), do following::

    import osc.conf

    # initialize the main config object
    config = osc.conf.Options()

    # configure host options for an apiurl
    apiurl = osc.conf.sanitize_apiurl(apiurl)
    host_options = HostOptions(apiurl=apiurl, username=..., _parent=config)
    config.api_host_options[apiurl] = host_options

    # set the default ``apiurl``
    config.apiurl = ...

    # place the config object in `osc.conf`
    osc.conf.config = config

    # optional: enable http debugging according to the ``http_debug`` and ``http_full_debug`` options
    from osc.connection import enable_http_debug
    enable_http_debug(osc.conf.config)
"""


import collections
import errno
import getpass
import http.client
import os
import re
import shutil
import sys
import textwrap
from io import BytesIO
from io import StringIO
from urllib.parse import urlsplit

from . import credentials
from . import OscConfigParser
from . import oscerr
from .output import tty
from .util import xdg
from .util.helper import raw_input
from .util.models import *


GENERIC_KEYRING = False

try:
    import keyring  # pylint: disable=import-error
    GENERIC_KEYRING = True
except:
    pass


__all__ = [
    "get_config",
    "Options",
    "HostOptions",
    "Password",
    "config",
]


class Password(collections.UserString):
    """
    Lazy password that wraps either a string or a function.
    The result of the function gets returned any time the object is used as a string.
    """

    def __init__(self, data):
        self._data = data

    @property
    def data(self):
        if callable(self._data):
            # if ``data`` is a function, call it every time the string gets evaluated
            # we use the password only from time to time to make a session cookie
            # and there's no need to keep the password in program memory longer than necessary
            result = self._data()

            # the function can also return a function, let's evaluate them recursively
            while callable(result):
                result = result()

            if result is None:
                raise oscerr.OscIOError(None, "Unable to retrieve password")
            return result
        return self._data

    def __format__(self, format_spec):
        if format_spec.endswith("s"):
            return f"{self.__str__():{format_spec}}"
        return super().__format__(format_spec)

    def encode(self, *args, **kwargs):
        if sys.version_info < (3, 8):
            # avoid returning the Password object on python < 3.8
            return str(self).encode(*args, **kwargs)
        return super().encode(*args, **kwargs)


HttpHeader = NewType("HttpHeader", Tuple[str, str])


class OscOptions(BaseModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._allow_new_attributes = True
        self._extra_fields = {}
        self._allow_new_attributes = False

    # compat function with the config dict
    def _get_field_name(self, name):
        if name in self.__fields__:
            return name

        for field_name, field in self.__fields__.items():
            ini_key = field.extra.get("ini_key", None)
            if ini_key == name:
                return field_name

        return None

    # compat function with the config dict
    def __getitem__(self, name):
        field_name = self._get_field_name(name)

        if field_name is None and not hasattr(self, name):
            return self._extra_fields[name]

        field_name = field_name or name
        try:
            return getattr(self, field_name)
        except AttributeError:
            raise KeyError(name)

    # compat function with the config dict
    def __setitem__(self, name, value):
        field_name = self._get_field_name(name)

        if field_name is None and not hasattr(self, name):
            self._extra_fields[name] = value
            return

        field_name = field_name or name
        setattr(self, field_name, value)

    # compat function with the config dict
    def __contains__(self, name):
        try:
            self[name]
        except KeyError:
            return False
        return True

    # compat function with the config dict
    def setdefault(self, name, default=None):
        field_name = self._get_field_name(name)
        # we're ignoring ``default`` because the field always exists
        return getattr(self, field_name, None)

    # compat function with the config dict
    def get(self, name, default=None):
        try:
            return self[name]
        except KeyError:
            return default

    def set_value_from_string(self, name, value):
        field_name = self._get_field_name(name)
        field = self.__fields__[field_name]

        if not isinstance(value, str):
            setattr(self, field_name, value)
            return

        if not value.strip():
            if field.is_optional:
                setattr(self, field_name, None)
                return

        if field.origin_type is Password:
            value = Password(value)
            setattr(self, field_name, value)
            return

        if field.type is List[HttpHeader]:
            value = http.client.parse_headers(BytesIO(value.strip().encode("utf-8"))).items()
            setattr(self, field_name, value)
            return

        if field.origin_type is list:
            # split list options into actual lists
            value = re.split(r"[, ]+", value)
            setattr(self, field_name, value)
            return

        if field.origin_type is bool:
            if value.lower() in ["1", "yes", "true", "on"]:
                value = True
                setattr(self, field_name, value)
                return
            if value.lower() in ["0", "no", "false", "off"]:
                value = False
                setattr(self, field_name, value)
                return

        if field.origin_type is int:
            value = int(value)
            setattr(self, field_name, value)
            return

        setattr(self, field_name, value)


class HostOptions(OscOptions):
    """
    Configuration options for individual apiurls.
    """

    def __init__(self, _parent, **kwargs):
        super().__init__(_parent=_parent, **kwargs)

    apiurl: str = Field(
        default=None,
        description=textwrap.dedent(
            """
            URL to the API server.
            """
        ),
    )  # type: ignore[assignment]

    aliases: List[str] = Field(
        default=[],
        description=textwrap.dedent(
            """
            Aliases of the apiurl.
            """
        ),
    )  # type: ignore[assignment]

    username: str = Field(
        default=None,
        description=textwrap.dedent(
            """
            Username for the apiurl.
            """
        ),
        ini_key="user",
    )  # type: ignore[assignment]

    credentials_mgr_class: Optional[str] = Field(
        default=None,
        description=textwrap.dedent(
            """
            Fully qualified name of a class used to fetch a password.
            """
        ),
    )  # type: ignore[assignment]

    password: Optional[Password] = Field(
        default=None,
        description=textwrap.dedent(
            """
            Password for the apiurl.
            May be empty if the credentials manager fetches the password from a keyring or ``sshkey`` is used.
            """
        ),
        ini_key="pass",
    )  # type: ignore[assignment]

    sshkey: Optional[str] = Field(
        default=FromParent("sshkey"),
        description=textwrap.dedent(
            """
            A pointer to public SSH key that corresponds with a private SSH used for authentication:

             - keep empty for auto detection
             - path to the public SSH key
             - public SSH key filename (must be placed in ~/.ssh)
             - fingerprint of a SSH key (2nd column of ``ssh-add -l``)

            NOTE: The private key may not be available on disk because it could be in a GPG keyring, on YubiKey or forwarded through SSH agent.

            TIP: To give osc a hint which ssh key from the agent to use during auto detection,
            append ``obs=<apiurl-hostname>`` to the **private** key's comment.
            This will also work nicely during SSH agent forwarding, because the comments get forwarded too.

             - To edit the key, run: ``ssh-keygen -c -f ~/.ssh/<private-key>``
             - To query the key, run: ``ssh-keygen -y -f ~/.ssh/<private-key>``
             - Example comment: ``<username@host> obs=api.example.com obs=api-test.example.com``
            """
        ),
    )  # type: ignore[assignment]

    downloadurl: Optional[str] = Field(
        default=None,
        description=textwrap.dedent(
            """
            Redirect downloads of packages used during build to an alternative location.
            This allows specifying a local mirror or a proxy, which can greatly improve download performance, latency and more.
            """
        ),
    )  # type: ignore[assignment]

    cafile: Optional[str] = Field(
        default=None,
        description=textwrap.dedent(
            """
            The path to a file of concatenated CA certificates in PEM format.
            If specified, the CA certificates from the path will be used to validate other peers' certificates instead of the system-wide certificates.
            """
        ),
    )  # type: ignore[assignment]

    capath: Optional[str] = Field(
        default=None,
        description=textwrap.dedent(
            """
            The path to a directory containing several CA certificates in PEM format.
            If specified, the CA certificates from the path will be used to validate other peers' certificates instead of the system-wide certificates.
            """
        ),
    )  # type: ignore[assignment]

    sslcertck: bool = Field(
        default=True,
        description=textwrap.dedent(
            """
            Whether to validate SSL certificate of the server.
            It is highly recommended to keep this option enabled.
            """
        ),
    )  # type: ignore[assignment]

    allow_http: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Whether to allow plain HTTP connections.
            Using HTTP is insecure because it sends passwords and session cookies in plain text.
            It is highly recommended to keep this option disabled.
            """
        ),
    )  # type: ignore[assignment]

    http_headers: List[HttpHeader] = Field(
        default=[],
        description=textwrap.dedent(
            """
            Additional HTTP headers attached to each HTTP or HTTPS request.
            The format is [(header-name, header-value)].
            """
        ),
        ini_description=textwrap.dedent(
            """
            Additional HTTP headers attached to each request.
            The format is HTTP headers separated with newlines.

            Example::

                http_headers =
                    X-Header1: Value1
                    X-Header2: Value2
            """
        ),
        ini_type="newline-separated-list",
    )  # type: ignore[assignment]

    trusted_prj: List[str] = Field(
        default=[],
        description=textwrap.dedent(
            """
            List of names of the trusted projects.
            The names can contain globs.
            Please note that some repos may contain malicious packages that can compromise the build result or even your system!
            """
        ),
    )  # type: ignore[assignment]

    disable_hdrmd5_check: bool = Field(
        default=FromParent("disable_hdrmd5_check"),
        description=textwrap.dedent(
            """
            Disable hdrmd5 checks of downloaded and cached packages in ``osc build``.
            It is recommended to keep the check enabled.

            OBS builds the noarch packages once per binary arch.
            Such noarch packages are supposed to be nearly identical across all build arches,
            any discrepancy in the payload and dependencies is considered a packaging bug.
            But to guarantee that the local builds work identically to builds in OBS,
            using the arch-specific copy of the noarch package is required.
            Unfortunatelly only one of the noarch packages gets distributed
            and can be downloaded from a local mirror.
            All other noarch packages are available through the OBS API only.
            Since there is currently no information about hdrmd5 checksums of published noarch packages,
            we download them, verify hdrmd5 and re-download the package from OBS API on mismatch.

            The same can also happen for architecture depend packages when someone is messing around
            with the source history or the release number handling in a way that it is not increasing.

            If you want to save some bandwidth and don't care about the exact rebuilds
            you can turn this option on to disable hdrmd5 checks completely.
            """
        ),
    )  # type: ignore[assignment]

    passx: Optional[str] = Field(
        default=None,
        deprecated_text=textwrap.dedent(
            """
            Option 'passx' (oscrc option [$apiurl]/passx) is deprecated.
            You should be using the 'password' option with 'credentials_mgr_class' set to 'osc.credentials.ObfuscatedConfigFileCredentialsManager' instead.
            """
        ),
    )  # type: ignore[assignment]

    realname: Optional[str] = Field(
        default=FromParent("realname"),
        description=textwrap.dedent(
            """
            Name of the user passed to the ``vc`` tool via ``VC_REALNAME`` env variable.
            """
        ),
    )  # type: ignore[assignment]

    email: Optional[str] = Field(
        default=FromParent("email"),
        description=textwrap.dedent(
            """
            Email of the user passed to the ``vc`` tool via ``VC_MAILADDR`` env variable.
            """
        ),
    )  # type: ignore[assignment]


class Options(OscOptions):
    """
    Main configuration options.
    """

    # for internal use
    conffile: Optional[str] = Field(
        default=None,
        exclude=True,
    )  # type: ignore[assignment]

    api_host_options: Dict[str, HostOptions] = Field(
        default={},
        description=textwrap.dedent(
            """
            A dictionary that maps ``apiurl`` to ``HostOptions``.
            """
        ),
        ini_exclude=True,
    )  # type: ignore[assignment]

    @property
    def apiurl_aliases(self):
        """
        Compute and return a dictionary that maps ``alias`` to ``apiurl``.
        """
        result = {}
        for apiurl, opts in self.api_host_options.items():
            result[apiurl] = apiurl
            for alias in opts.aliases:
                result[alias] = apiurl
        return result

    section_generic: str = Field(
        default="Generic options",
        exclude=True,
        section=True,
    )  # type: ignore[assignment]

    apiurl: str = Field(
        default="https://api.opensuse.org",
        description=textwrap.dedent(
            """
            Default URL to the API server.
            Credentials and other ``apiurl`` specific settings must be configured
            in a ``[$apiurl]`` config section or via API in an ``api_host_options`` entry.
            """
        ),
    )  # type: ignore[assignment]

    section_auth: str = Field(
        default="Authentication options",
        exclude=True,
        section=True,
    )  # type: ignore[assignment]

    username: Optional[str] = Field(
        default=None,
        ini_key="user",
        deprecated_text=textwrap.dedent(
            """
            Option 'username' (oscrc option [global]/user) is deprecated.
            You should be using username for each apiurl instead.
            """
        ),
    )  # type: ignore[assignment]

    password: Optional[Password] = Field(
        default=None,
        ini_key="pass",
        deprecated_text=textwrap.dedent(
            """
            Option 'password' (oscrc option [global]/pass) is deprecated.
            You should be using password for each apiurl instead.
            """
        ),
    )  # type: ignore[assignment]

    passx: Optional[str] = Field(
        default=None,
        deprecated_text=textwrap.dedent(
            """
            Option 'passx' (oscrc option [global]/passx) is deprecated.
            You should be using password for each apiurl instead.
            """
        ),
    )  # type: ignore[assignment]

    sshkey: Optional[str] = Field(
        default=None,
        description=HostOptions.__fields__["sshkey"].description,
    )  # type: ignore[assignment]

    use_keyring: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Enable keyring as an option for storing passwords.
            """
        ),
    )  # type: ignore[assignment]

    section_verbosity: str = Field(
        default="Verbosity options",
        exclude=True,
        section=True,
    )  # type: ignore[assignment]

    quiet: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Reduce amount of printed information to bare minimum.
            If enabled, automatically sets ``verbose`` to ``False``.
            """
        ),
    )  # type: ignore[assignment]

    verbose: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Increase amount of printed information to stdout.
            Automatically set to ``False`` when ``quiet`` is enabled.
            """
        ),
        get_callback=lambda conf, value: False if conf.quiet else value,
    )  # type: ignore[assignment]

    debug: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Print debug information to stderr.
            """
        ),
    )  # type: ignore[assignment]

    http_debug: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Print HTTP traffic to stderr.
            Automatically set to ``True`` when``http_full_debug`` is enabled.
            """
        ),
        get_callback=lambda conf, value: True if conf.http_full_debug else value,
    )  # type: ignore[assignment]

    http_full_debug: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            [CAUTION!] Print HTTP traffic incl. authentication data to stderr.
            If enabled, automatically sets ``http_debug`` to ``True``.
            """
        ),
    )  # type: ignore[assignment]

    post_mortem: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Jump into a debugger when an unandled exception occurs.
            """
        ),
    )  # type: ignore[assignment]

    traceback: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Print full traceback to stderr when an unandled exception occurs.
            """
        ),
    )  # type: ignore[assignment]

    show_download_progress: bool = Field(
        default=True,
        description=textwrap.dedent(
            """
            Show download progressbar.
            """
        ),
    )  # type: ignore[assignment]

    section_connection: str = Field(
        default="Connection options",
        exclude=True,
        section=True,
    )  # type: ignore[assignment]

    http_retries: int = Field(
        default=3,
        description=textwrap.dedent(
            """
            Number of retries on HTTP error.
            """
        ),
    )  # type: ignore[assignment]

    cookiejar: str = Field(
        default=os.path.join(xdg.XDG_STATE_HOME, "osc", "cookiejar"),
        description=textwrap.dedent(
            """
            Path to a cookie jar that stores session cookies.
            """
        ),
    )  # type: ignore[assignment]

    section_scm: str = Field(
        default="SCM options",
        exclude=True,
        section=True,
    )  # type: ignore[assignment]

    realname: Optional[str] = Field(
        default=None,
        description=HostOptions.__fields__["realname"].description,
    )  # type: ignore[assignment]

    email: Optional[str] = Field(
        default=None,
        description=HostOptions.__fields__["email"].description,
    )  # type: ignore[assignment]

    local_service_run: bool = Field(
        default=True,
        description=textwrap.dedent(
            """
            Run local services during commit.
            """
        ),
    )  # type: ignore[assignment]

    getpac_default_project: str = Field(
        default="openSUSE:Factory",
        description=textwrap.dedent(
            """
            The default project for ``osc getpac`` and ``osc bco``.
            The value is a space separated list of strings.
            """
        ),
    )  # type: ignore[assignment]

    exclude_glob: List[str] = Field(
        default=[".osc", "CVS", ".svn", ".*", "_linkerror", "*~", "#*#", "*.orig", "*.bak", "*.changes.vctmp.*"],
        description=textwrap.dedent(
            """
            Space separated list of files ignored by SCM.
            The files can contain globs.
            """
        ),
    )  # type: ignore[assignment]

    exclude_files: List[str] = Field(
        default=[],
        description=textwrap.dedent(
            """
            Files that match the listed glob patterns get skipped during checkout.
            """
        ),
    )  # type: ignore[assignment]

    include_files: List[str] = Field(
        default=[],
        description=textwrap.dedent(
            """
            Files that do not match the listed glob patterns get skipped during checkout.
            The ``exclude_files`` option takes priority over ``include_files``.
            """
        ),
    )  # type: ignore[assignment]

    checkout_no_colon: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Use '/' as project separator instead the default ':' and create corresponding subdirs.
            If enabled, it takes priority over the ``project_separator`` option.
            """
        ),
    )  # type: ignore[assignment]

    project_separator: str = Field(
        default=":",
        description=textwrap.dedent(
            """
            Use the specified string to separate projects.
            """
        ),
    )  # type: ignore[assignment]

    check_filelist: bool = Field(
        default=True,
        description=textwrap.dedent(
            """
            Check for untracked files and removed files before commit.
            """
        ),
    )  # type: ignore[assignment]

    do_package_tracking: bool = Field(
        default=True,
        description=textwrap.dedent(
            """
            Track packages in parent project's .osc/_packages.
            """
        ),
    )  # type: ignore[assignment]

    checkout_rooted: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Prevent checking out projects inside other projects or packages.
            """
        ),
    )  # type: ignore[assignment]

    status_mtime_heuristic: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Consider a file with a modified mtime as modified.
            """
        ),
    )  # type: ignore[assignment]

    linkcontrol: bool = Field(
        default=False,
        description=textwrap.dedent(
            # TODO: explain what linkcontrol does
            """
            """
        ),
    )  # type: ignore[assignment]

    section_build: str = Field(
        default="Build options",
        exclude=True,
        section=True,
    )  # type: ignore[assignment]

    build_repository: str = Field(
        default="openSUSE_Factory",
        description=textwrap.dedent(
            """
            The default repository used when the ``repository`` argument is omitted from ``osc build``.
            """
        ),
    )  # type: ignore[assignment]

    buildlog_strip_time: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Strip the build time from the build logs.
            """
        ),
    )  # type: ignore[assignment]

    package_cache_dir: str = Field(
        default="/var/tmp/osbuild-packagecache",
        description=textwrap.dedent(
            """
            The directory where downloaded packages are stored. Must be writable by you.
            """
        ),
        ini_key="packagecachedir",
    )  # type: ignore[assignment]

    no_verify: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Disable signature verification of packages used for build.
            """
        ),
    )  # type: ignore[assignment]

    builtin_signature_check: bool = Field(
        default=True,
        description=textwrap.dedent(
            """
            Use the RPM's built-in package signature verification.
            """
        ),
    )  # type: ignore[assignment]

    disable_hdrmd5_check: bool = Field(
        default=False,
        description=HostOptions.__fields__["disable_hdrmd5_check"].description,
    )  # type: ignore[assignment]

    section_request: str = Field(
        default="Request options",
        exclude=True,
        section=True,
    )  # type: ignore[assignment]

    include_request_from_project: bool = Field(
        default=True,
        description=textwrap.dedent(
            """
            When querying requests, show also those that originate in the specified projects.
            """
        ),
    )  # type: ignore[assignment]

    request_list_days: int = Field(
        default=0,
        description=textwrap.dedent(
            """
            Limit the age of requests shown with ``osc req list`` to the given number of days.

            This is only the default that can be overridden with ``osc request list -D <VALUE>``.
            Use ``0`` for unlimited.
            """
        ),
    )  # type: ignore[assignment]

    check_for_request_on_action: bool = Field(
        default=True,
        description=textwrap.dedent(
            """
            Check for pending requests after executing an action (e.g. checkout, update, commit).
            """
        ),
    )  # type: ignore[assignment]

    request_show_interactive: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Show requests in the interactive mode by default.
            """
        ),
    )  # type: ignore[assignment]

    print_web_links: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Print links to Web UI that can be directly pasted to a web browser where possible.
            """
        ),
    )  # type: ignore[assignment]

    request_show_source_buildstatus: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Print the buildstatus of the source package.
            Works only with ``osc request show`` and the interactive review.
            """
        ),
    )  # type: ignore[assignment]

    submitrequest_accepted_template: Optional[str] = Field(
        default=None,
        description=textwrap.dedent(
            """
            Template message for accepting a request.

            Supported substitutions: ``%(reqid)s``, ``%(type)s``, ``%(who)s``, ``%(src_project)s``, ``%(src_package)s``, ``%(src_rev)s``, ``%(tgt_project)s``, ``%(tgt_package)s``

            Example::

                Hi %(who)s, your request %(reqid)s (type: %(type)s) for %(tgt_project)s/%(tgt_package)s has been accepted. Thank you for your contribution.
            """
        ),
    )  # type: ignore[assignment]

    submitrequest_declined_template: Optional[str] = Field(
        default=None,
        description=textwrap.dedent(
            """
            Template message for declining a request.

            Supported substitutions: ``%(reqid)s``, ``%(type)s``, ``%(who)s``, ``%(src_project)s``, ``%(src_package)s``, ``%(src_rev)s``, ``%(tgt_project)s``, ``%(tgt_package)s``

            Example::

                Hi %(who)s, your request %(reqid)s (type: %(type)s) for %(tgt_project)s/%(tgt_package)s has been declined because ...
            """
        ),
    )  # type: ignore[assignment]

    request_show_review: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Review requests interactively.
            """
        ),
    )  # type: ignore[assignment]

    review_inherit_group: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            If a review was accepted in interactive mode and a group was specified,
            the review will be accepted for this group.
            """
        ),
    )  # type: ignore[assignment]

    submitrequest_on_accept_action: Optional[str] = Field(
        default=None,
        description=textwrap.dedent(
            """
            What to do with the source package if the request has been accepted.
            If nothing is specified the API default is used.

            Choices: cleanup, update, noupdate
            """
        ),
    )  # type: ignore[assignment]

    # XXX: let's hide attributes from documentation as it is not clear if anyone uses them and should them change from their defaults
    # section_obs_attributes: str = Field(
    #     default="OBS attributes",
    #     exclude=True,
    #     section=True,
    # )  # type: ignore[assignment]

    maintained_attribute: str = Field(
        default="OBS:Maintained",
    )  # type: ignore[assignment]

    maintenance_attribute: str = Field(
        default="OBS:MaintenanceProject",
    )  # type: ignore[assignment]

    maintained_update_project_attribute: str = Field(
        default="OBS:UpdateProject",
    )  # type: ignore[assignment]

    section_build_tool: str = Field(
        default="Build tool options",
        exclude=True,
        section=True,
    )  # type: ignore[assignment]

    build_jobs: Optional[int] = Field(
        default=os.cpu_count,
        description=textwrap.dedent(
            """
            The number of parallel processes during the build.
            Defaults to the number of available CPU threads.

            If the value is greater than ``0`` then it is passed as ``--jobs`` to the build tool.
            """
        ),
        ini_key="build-jobs",
    )  # type: ignore[assignment]

    vm_type: Optional[str] = Field(
        default=None,
        description=textwrap.dedent(
            """
            Type of the build environment passed the build tool as the ``--vm-type`` option:

             - <empty>   chroot build
             - kvm       KVM VM build (rootless, needs build-device, build-swap, build-memory)
             - xen       XEN VM build (needs build-device, build-swap, build-memory)
             - qemu      [EXPERIMENTAL] QEMU VM build
             - lxc       [EXPERIMENTAL] LXC build
             - uml
             - zvm
             - openstack
             - ec2
             - docker
             - podman    (rootless)
             - pvm
             - nspawn

            See ``build --help`` for more details about supported options.
            """
        ),
        ini_key="build-type",
    )  # type: ignore[assignment]

    build_memory: Optional[int] = Field(
        default=None,
        description=textwrap.dedent(
            """
            The amount of RAM (in MiB) assigned to a build VM.
            """
        ),
        ini_key="build-memory",
    )  # type: ignore[assignment]

    build_root: str = Field(
        default="/var/tmp/build-root%(dash_user)s/%(repo)s-%(arch)s",
        description=textwrap.dedent(
            """
            Path to the build root directory.

            Supported substitutions: ``%(repo)s``, ``%(arch)s``, ``%(project)s``, ``%(package)s``, ``%(apihost)s``, ``%(user)s``, ``%(dash_user)s``
            where::

                - ``apihost`` is the hostname extracted from the currently used ``apiurl``.
                - ``dash_user`` is the username prefixed with a dash. If ``user`` is empty, ``dash_user`` is also empty.

            NOTE: The configuration holds the original unexpanded string. Call ``osc.build.get_build_root()`` with proper arguments to retrieve an actual path.

            Passed as ``--root <VALUE>`` to the build tool.
            """
        ),
        ini_key="build-root",
    )  # type: ignore[assignment]

    build_shell_after_fail: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Start a shell prompt in the build environment if a build fails.

            Passed as ``--shell-after-fail`` to the build tool.
            """
        ),
        ini_key="build-shell-after-fail",
    )  # type: ignore[assignment]

    build_uid: Optional[str] = Field(
        default=None,
        description=textwrap.dedent(
            """
            Numeric uid:gid to use for the abuild user.
            Neither of the values should be 0.
            This is useful if you are hacking in the buildroot.
            This must be set to the same value if the buildroot is re-used.

            Passed as ``--uid <VALUE>`` to the build tool.
            """
        ),
        ini_key="build-uid",
    )  # type: ignore[assignment]

    build_vm_kernel: Optional[str] = Field(
        default=None,
        description=textwrap.dedent(
            """
            The kernel used in a VM build.
            """
        ),
        ini_key="build-kernel",
    )  # type: ignore[assignment]

    build_vm_initrd: Optional[str] = Field(
        default=None,
        description=textwrap.dedent(
            """
            The initrd used in a VM build.
            """
        ),
        ini_key="build-initrd",
    )  # type: ignore[assignment]

    build_vm_disk: Optional[str] = Field(
        default=None,
        description=textwrap.dedent(
            """
            The disk image used as rootfs in a VM build.

            Passed as ``--vm-disk <VALUE>`` to the build tool.
            """
        ),
        ini_key="build-device",
    )  # type: ignore[assignment]

    build_vm_disk_filesystem: Optional[str] = Field(
        default=None,
        description=textwrap.dedent(
            """
            The file system type of the disk image used as rootfs in a VM build.
            Supported values: ext3 (default), ext4, xfs, reiserfs, btrfs.

            Passed as ``--vm-disk-filesystem <VALUE>`` to the build tool.
            """
        ),
        ini_key="build-vmdisk-filesystem",
    )  # type: ignore[assignment]

    build_vm_disk_size: Optional[int] = Field(
        default=None,
        description=textwrap.dedent(
            """
            The size of the disk image (in MiB) used as rootfs in a VM build.

            Passed as ``--vm-disk-size`` to the build tool.
            """
        ),
        ini_key="build-vmdisk-rootsize",
    )  # type: ignore[assignment]

    build_vm_swap: Optional[str] = Field(
        default=None,
        description=textwrap.dedent(
            """
            Path to the disk image used as a swap for VM builds.

            Passed as ``--swap`` to the build tool.
            """
        ),
        ini_key="build-swap",
    )  # type: ignore[assignment]

    build_vm_swap_size: Optional[int] = Field(
        default=None,
        description=textwrap.dedent(
            """
            The size of the disk image (in MiB) used as swap in a VM build.

            Passed as ``--vm-swap-size`` to the build tool.
            """
        ),
        ini_key="build-vmdisk-swapsize",
    )  # type: ignore[assignment]

    build_vm_user: Optional[str] = Field(
        default=None,
        description=textwrap.dedent(
            """
            The username of a user used to run QEMU/KVM process.
            """
        ),
        ini_key="build-vm-user",
    )  # type: ignore[assignment]

    icecream: int = Field(
        default=0,
        description=textwrap.dedent(
            """
            Use Icecream distributed compiler.
            The value represents the number of parallel build jobs.

            Passed as ``--icecream <VALUE>`` to the build tool.
            """
        ),
    )  # type: ignore[assignment]

    ccache: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Enable compiler cache (ccache) in build roots.

            Passed as ``--ccache`` to the build tool.
            """
        ),
    )  # type: ignore[assignment]

    sccache: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Enable shared compilation cache (sccache) in build roots. Conflicts with ``ccache``.

            Passed as ``--sccache`` to the build tool.
            """
        ),
    )  # type: ignore[assignment]

    sccache_uri: Optional[str] = Field(
        default=None,
        description=textwrap.dedent(
            """
            Optional URI for sccache storage.

            Supported URIs depend on the sccache configuration.
            The URI allows the following substitutions:

             - ``{pkgname}``: name of the package to be build

            Examples:

             - file:///var/tmp/osbuild-sccache-{pkgname}.tar.lzop
             - file:///var/tmp/osbuild-sccache-{pkgname}.tar
             - redis://127.0.0.1:6379

            Passed as ``--sccache-uri <VALUE>`` to the build tool.
            """
        ),
    )  # type: ignore[assignment]

    no_preinstallimage: bool = Field(
        default=False,
        description=textwrap.dedent(
            """
            Do not use preinstall images to initialize build roots.
            """
        ),
    )  # type: ignore[assignment]

    extra_pkgs: List[str] = Field(
        default=[],
        description=textwrap.dedent(
            """
            Extra packages to install into the build root when building packages locally with ``osc build``.

            This corresponds to ``osc build -x pkg1 -x pkg2 ...``.
            The configured values can be overriden from the command-line with ``-x ''``.

            This global setting may leads to dependency problems when the base distro is not providing the package.
            Therefore using server-side ``cli_debug_packages`` option instead is recommended.

            Passed as ``--extra-packs <VALUE>`` to the build tool.
            """
        ),
        ini_key="extra-pkgs",
    )  # type: ignore[assignment]

    section_programs: str = Field(
        default="Paths to programs",
        exclude=True,
        section=True,
    )  # type: ignore[assignment]

    build_cmd: str = Field(
        default=
            shutil.which("build", path="/usr/bin:/usr/lib/build:/usr/lib/obs-build")
            or shutil.which("obs-build", path="/usr/bin:/usr/lib/build:/usr/lib/obs-build")
            or "/usr/bin/build",
        description=textwrap.dedent(
            """
            Path to the 'build' tool.
            """
        ),
        ini_key="build-cmd",
    )  # type: ignore[assignment]

    download_assets_cmd: str = Field(
        default=
            shutil.which("download_assets", path="/usr/lib/build:/usr/lib/obs-build")
            or "/usr/lib/build/download_assets",
        description=textwrap.dedent(
            """
            Path to the 'download_assets' tool used for downloading assets in SCM/Git based builds.
            """
        ),
        ini_key="download-assets-cmd",
    )  # type: ignore[assignment]

    obs_scm_bridge_cmd: str = Field(
        default=
            shutil.which("obs_scm_bridge", path="/usr/lib/obs/service")
            or "/usr/lib/obs/service/obs_scm_bridge",
        description=textwrap.dedent(
            """
            Path to the 'obs_scm_bridge' tool used for cloning scmsync projects and packages.
            """
        ),
        ini_key="obs-scm-bridge-cmd",
    )  # type: ignore[assignment]

    vc_cmd: str = Field(
        default=shutil.which("vc", path="/usr/lib/build:/usr/lib/obs-build") or "/usr/lib/build/vc",
        description=textwrap.dedent(
            """
            Path to the 'vc' tool.
            """
        ),
        ini_key="vc-cmd",
    )  # type: ignore[assignment]

    su_wrapper: str = Field(
        default="sudo",
        description=textwrap.dedent(
            """
            The wrapper to call build tool as root (sudo, su -, ...).
            If empty, the build tool runs under the current user wich works only with KVM at this moment.
            """
        ),
        ini_key="su-wrapper",
    )  # type: ignore[assignment]


# Generate rst from a model. Use it to generate man page in sphinx.
# This IS NOT a public API.
def _model_to_rst(cls, title=None, description=None, sections=None, output_file=None):
    def header(text, char="-"):
        result = f"{text}\n"
        result += f"{'':{char}^{len(text)}}"
        return result

    def bold(text):
        text = text.replace(r"*", r"\*")
        return f"**{text}**"

    def italic(text):
        text = text.replace(r"*", r"\*")
        return f"*{text}*"

    def get_type(name, field):
        ini_type = field.extra.get("ini_type", None)
        if ini_type:
            return ini_type
        if field.origin_type.__name__ == "list":
            return "space-separated-list"
        return field.origin_type.__name__

    def get_default(name, field):
        if field.default is None:
            return None

        if field.default_is_lazy:
            # lazy default may return different results under different circumstances -> return nothing
            return None

        ini_type = field.extra.get("ini_type", None)
        if ini_type:
            return None

        if isinstance(field.default, FromParent):
            return None

        origin_type = field.origin_type

        if origin_type == bool:
            return str(int(field.default))

        if origin_type == int:
            return str(field.default)

        if origin_type == list:
            if not field.default:
                return None
            default_str = " ".join(field.default)
            return f'"{default_str}"'

        if origin_type == str:
            return f'"{field.default}"'

        # TODO:
        raise Exception(f"{name} {field}, {origin_type}")

    result = []

    if title:
        result.append(header(title, char="="))
        result.append("")

    if description:
        result.append(description)
        result.append("")

    for name, field in cls.__fields__.items():
        extra = field.extra

        is_section_header = extra.get("section", False)
        if is_section_header:
            result.append(header(field.default))
            result.append("")
            continue

        exclude = extra.get("ini_exclude", False) or field.exclude
        exclude |= field.description is None
        if exclude:
            continue

        ini_key = extra.get("ini_key", name)

        x = f"{bold(ini_key)} : {get_type(name, field)}"
        default = get_default(name, field)
        if default:
            x += f" = {italic(default)}"
        result.append(x)
        result.append("")
        desc = extra.get("ini_description", None) or field.description or ""
        for line in desc.splitlines():
            result.append(f"    {line}")
        result.append("")

    sections = sections or {}
    for section_name, section_class in sections.items():
        result.append(header(section_name))
        result.append(_model_to_rst(section_class))

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(result))

    return "\n".join(result)


# being global to this module, this object can be accessed from outside
# it will hold the parsed configuration
config = Options()


general_opts = [field.extra.get("ini_key", field.name) for field in Options.__fields__.values() if not field.exclude]
api_host_options = [field.extra.get("ini_key", field.name) for field in HostOptions.__fields__.values() if not field.exclude]


# HACK: Proxy object that modifies field defaults in the Options class; needed for compatibility with the old DEFAULTS dict; prevents breaking osc-plugin-collab
# This IS NOT a public API.
class Defaults:
    def _get_field(self, name):
        if hasattr(Options, name):
            return getattr(Options, name)

        for i in dir(Options):
            field = getattr(Options, i)
            if field.extra.get("ini_key", None) == name:
                return field

        return None

    def __getitem__(self, name):
        field = self._get_field(name)
        result = field.default
        if field.type is List[str]:
            # return list as a string so we can append another string to it
            return ", ".join(result)
        return result

    def __setitem__(self, name, value):
        obj = Options()
        obj.set_value_from_string(name, value)
        field = self._get_field(name)
        field.default = obj[name]


DEFAULTS = Defaults()


new_conf_template = """
# see oscrc(5) man page for the full list of available options

[general]

# Default URL to the API server.
# Credentials and other `apiurl` specific settings must be configured in a `[$apiurl]` config section.
apiurl=%(apiurl)s

[%(apiurl)s]
# aliases=
# user=
# pass=
# credentials_mgr_class=osc.credentials...
"""


account_not_configured_text = """
Your user account / password are not configured yet.
You will be asked for them below, and they will be stored in
%s for future use.
"""

config_incomplete_text = """

Your configuration file %s is not complete.
Make sure that it has a [general] section.
(You can copy&paste the below. Some commented defaults are shown.)

"""

config_missing_apiurl_text = """
The apiurl \'%s\' does not exist in the config file. Please enter
your credentials for this apiurl.
"""


def sanitize_apiurl(apiurl):
    """
    Sanitize apiurl:
    - add https:// schema if apiurl contains none
    - strip trailing slashes
    """
    return urljoin(*parse_apisrv_url(None, apiurl))


def parse_apisrv_url(scheme, apisrv):
    if apisrv.startswith('http://') or apisrv.startswith('https://'):
        url = apisrv
    elif scheme is not None:
        url = scheme + apisrv
    else:
        url = f"https://{apisrv}"
    scheme, url, path = urlsplit(url)[0:3]
    return scheme, url, path.rstrip('/')


def urljoin(scheme, apisrv, path=''):
    return f"{scheme}://{apisrv}" + path


def is_known_apiurl(url):
    """returns ``True`` if url is a known apiurl"""
    apiurl = sanitize_apiurl(url)
    return apiurl in config['api_host_options']


def extract_known_apiurl(url):
    """
    Return longest prefix of given url that is known apiurl,
    None if there is no known apiurl that is prefix of given url.
    """
    scheme, host, path = parse_apisrv_url(None, url)
    p = path.split('/')
    while p:
        apiurl = urljoin(scheme, host, '/'.join(p))
        if apiurl in config['api_host_options']:
            return apiurl
        p.pop()
    return None


def get_apiurl_api_host_options(apiurl):
    """
    Returns all apihost specific options for the given apiurl, ``None`` if
    no such specific options exist.
    """
    # FIXME: in A Better World (tm) there was a config object which
    # knows this instead of having to extract it from a url where it
    # had been mingled into before.  But this works fine for now.

    apiurl = sanitize_apiurl(apiurl)
    if is_known_apiurl(apiurl):
        return config['api_host_options'][apiurl]
    raise oscerr.ConfigMissingApiurl(f'missing credentials for apiurl: \'{apiurl}\'',
                                     '', apiurl)


def get_apiurl_usr(apiurl):
    """
    returns the user for this host - if this host does not exist in the
    internal api_host_options the default user is returned.
    """
    # FIXME: maybe there should be defaults not just for the user but
    # for all apihost specific options.  The ConfigParser class
    # actually even does this but for some reason we don't use it
    # (yet?).

    try:
        return get_apiurl_api_host_options(apiurl)['user']
    except KeyError:
        print('no specific section found in config file for host of [\'%s\'] - using default user: \'%s\''
              % (apiurl, config['user']), file=sys.stderr)
        return config['user']


def get_configParser(conffile=None, force_read=False):
    """
    Returns an ConfigParser() object. After its first invocation the
    ConfigParser object is stored in a method attribute and this attribute
    is returned unless you pass force_read=True.
    """
    if not conffile:
        conffile = identify_conf()

    conffile = os.path.expanduser(conffile)
    if 'conffile' not in get_configParser.__dict__:
        get_configParser.conffile = conffile
    if force_read or 'cp' not in get_configParser.__dict__ or conffile != get_configParser.conffile:
        get_configParser.cp = OscConfigParser.OscConfigParser()
        get_configParser.cp.read(conffile)
        get_configParser.conffile = conffile
    return get_configParser.cp


def write_config(fname, cp):
    """write new configfile in a safe way"""
    # config file is behind a symlink
    # resolve the symlink and continue writing the config as usual
    if os.path.islink(fname):
        fname = os.path.realpath(fname)

    if os.path.exists(fname) and not os.path.isfile(fname):
        # only write to a regular file
        return

    # create directories to the config file (if they don't exist already)
    fdir = os.path.dirname(fname)
    if fdir:
        try:
            os.makedirs(fdir, mode=0o700)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    with open(f"{fname}.new", 'w') as f:
        cp.write(f, comments=True)
    try:
        os.rename(f"{fname}.new", fname)
        os.chmod(fname, 0o600)
    except:
        if os.path.exists(f"{fname}.new"):
            os.unlink(f"{fname}.new")
        raise


def config_set_option(section, opt, val=None, delete=False, update=True, creds_mgr_descr=None, **kwargs):
    """
    Sets a config option. If val is not specified the current/default value is
    returned. If val is specified, opt is set to val and the new value is returned.
    If an option was modified get_config is called with ``**kwargs`` unless update is set
    to ``False`` (``override_conffile`` defaults to ``config['conffile']``).
    If val is not specified and delete is ``True`` then the option is removed from the
    config/reset to the default value.
    """
    cp = get_configParser(config['conffile'])

    if section != 'general':
        section = config.apiurl_aliases.get(section, section)
        scheme, host, path = \
            parse_apisrv_url(config.get('scheme', 'https'), section)
        section = urljoin(scheme, host, path)

    sections = {}
    for url in cp.sections():
        if url == 'general':
            sections[url] = url
        else:
            scheme, host, path = \
                parse_apisrv_url(config.get('scheme', 'https'), url)
            apiurl = urljoin(scheme, host, path)
            sections[apiurl] = url

    section = sections.get(section.rstrip('/'), section)
    if section not in cp.sections():
        raise oscerr.ConfigError(f'unknown section \'{section}\'', config['conffile'])
    if section == 'general' and opt not in general_opts or \
       section != 'general' and opt not in api_host_options:
        raise oscerr.ConfigError(f'unknown config option \'{opt}\'', config['conffile'])

    if not val and not delete and opt == 'pass' and creds_mgr_descr is not None:
        # change password store
        creds_mgr = _get_credentials_manager(section, cp)
        user = _extract_user_compat(cp, section, creds_mgr)
        val = creds_mgr.get_password(section, user, defer=False)

    run = False
    if val:
        if opt == 'pass':
            creds_mgr = _get_credentials_manager(section, cp)
            user = _extract_user_compat(cp, section, creds_mgr)
            old_pw = creds_mgr.get_password(section, user, defer=False)
            try:
                creds_mgr.delete_password(section, user)
                if creds_mgr_descr:
                    creds_mgr_new = creds_mgr_descr.create(cp)
                else:
                    creds_mgr_new = creds_mgr
                creds_mgr_new.set_password(section, user, val)
                write_config(config['conffile'], cp)
                opt = credentials.AbstractCredentialsManager.config_entry
                old_pw = None
            finally:
                if old_pw is not None:
                    creds_mgr.set_password(section, user, old_pw)
                    # not nice, but needed if the Credentials Manager will change
                    # something in cp
                    write_config(config['conffile'], cp)
        else:
            cp.set(section, opt, val)
            write_config(config['conffile'], cp)
        run = True
    elif delete and (cp.has_option(section, opt) or opt == 'pass'):
        if opt == 'pass':
            creds_mgr = _get_credentials_manager(section, cp)
            user = _extract_user_compat(cp, section, creds_mgr)
            creds_mgr.delete_password(section, user)
        else:
            cp.remove_option(section, opt)
        write_config(config['conffile'], cp)
        run = True
    if run and update:
        kw = {
            'override_conffile': config['conffile'],
            'override_no_keyring': config['use_keyring'],
        }
        kw.update(kwargs)
        get_config(**kw)
    if cp.has_option(section, opt):
        return (opt, cp.get(section, opt, raw=True))
    return (opt, None)


def _extract_user_compat(cp, section, creds_mgr):
    """
    This extracts the user either from the ConfigParser or
    the creds_mgr. Only needed for deprecated Gnome Keyring
    """
    user = cp.get(section, 'user')
    if user is None and hasattr(creds_mgr, 'get_user'):
        user = creds_mgr.get_user(section)
    return user


def write_initial_config(conffile, entries, custom_template='', creds_mgr_descriptor=None):
    """
    write osc's intial configuration file. entries is a dict which contains values
    for the config file (e.g. { 'user' : 'username', 'pass' : 'password' } ).
    custom_template is an optional configuration template.
    """
    conf_template = custom_template or new_conf_template
    config = globals()["config"].dict()
    config.update(entries)
    sio = StringIO(conf_template.strip() % config)
    cp = OscConfigParser.OscConfigParser()
    cp.read_file(sio)
    cp.set(config['apiurl'], 'user', config['user'])
    if creds_mgr_descriptor:
        creds_mgr = creds_mgr_descriptor.create(cp)
    else:
        creds_mgr = _get_credentials_manager(config['apiurl'], cp)
    creds_mgr.set_password(config['apiurl'], config['user'], config['pass'])
    write_config(conffile, cp)


def add_section(filename, url, user, passwd, creds_mgr_descriptor=None, allow_http=None):
    """
    Add a section to config file for new api url.
    """
    global config
    cp = get_configParser(filename)
    try:
        cp.add_section(url)
    except OscConfigParser.configparser.DuplicateSectionError:
        # Section might have existed, but was empty
        pass
    cp.set(url, 'user', user)
    if creds_mgr_descriptor:
        creds_mgr = creds_mgr_descriptor.create(cp)
    else:
        creds_mgr = _get_credentials_manager(url, cp)
    creds_mgr.set_password(url, user, passwd)
    if allow_http:
        cp.set(url, 'allow_http', "1")
    write_config(filename, cp)


def _get_credentials_manager(url, cp):
    if cp.has_option(url, credentials.AbstractCredentialsManager.config_entry):
        creds_mgr = credentials.create_credentials_manager(url, cp)
        if creds_mgr is None:
            msg = f'Unable to instantiate creds mgr (section: {url})'
            conffile = get_configParser.conffile
            raise oscerr.ConfigMissingCredentialsError(msg, conffile, url)
        return creds_mgr
    if config['use_keyring'] and GENERIC_KEYRING:
        return credentials.get_keyring_credentials_manager(cp)
    elif cp.get(url, "passx", fallback=None) is not None:
        return credentials.ObfuscatedConfigFileCredentialsManager(cp, None)
    return credentials.PlaintextConfigFileCredentialsManager(cp, None)


def get_config(override_conffile=None,
               override_apiurl=None,
               override_debug=None,
               override_http_debug=None,
               override_http_full_debug=None,
               override_traceback=None,
               override_post_mortem=None,
               override_quiet=None,
               override_no_keyring=None,
               override_verbose=None,
               overrides=None
               ):
    """
    Configure osc.

    The configuration options are loaded with the following priority:
        1. environment variables: ``OSC_<uppercase_option>`` or ``OSC_<uppercase_host_alias>_<uppercase_host_option>``
        2. override arguments provided to ``get_config()``
        3. oscrc config file
    """

    if overrides:
        overrides = overrides.copy()
    else:
        overrides = {}

    if override_apiurl is not None:
        overrides["apiurl"] = override_apiurl

    if override_debug is not None:
        overrides["debug"] = override_debug

    if override_http_debug is not None:
        overrides["http_debug"] = override_http_debug

    if override_http_full_debug is not None:
        overrides["http_full_debug"] = override_http_full_debug

    if override_traceback is not None:
        overrides["traceback"] = override_traceback

    if override_post_mortem is not None:
        overrides["post_mortem"] = override_post_mortem

    if override_no_keyring is not None:
        overrides["use_keyring"] = not override_no_keyring

    if override_quiet is not None:
        overrides["quiet"] = override_quiet

    if override_verbose is not None:
        overrides["verbose"] = override_verbose

    if override_conffile is not None:
        conffile = override_conffile
    else:
        conffile = identify_conf()

    if conffile in ["", "/dev/null"]:
        cp = OscConfigParser.OscConfigParser()
        cp.add_section("general")
    else:
        conffile = os.path.expanduser(conffile)
        if not os.path.exists(conffile):
            raise oscerr.NoConfigfile(conffile, account_not_configured_text % conffile)

        cp = get_configParser(conffile)

        if not cp.has_section("general"):
            # FIXME: it might be sufficient to just assume defaults?
            msg = config_incomplete_text % conffile
            defaults = Options().dict()
            msg += new_conf_template % defaults
            raise oscerr.ConfigError(msg, conffile)

        has_password = False
        for section in cp.sections():
            keys = ["pass", "passx"]
            for key in keys:
                value = cp.get(section, key, fallback="").strip()
                if value:
                    has_password = True
                    break

        # make sure oscrc is not world readable, it may contain a password
        conffile_stat = os.stat(conffile)
        # applying 0o7777 mask because we want to ignore the file type bits
        if conffile_stat.st_mode & 0o7777 != 0o600:
            try:
                os.chmod(conffile, 0o600)
            except OSError as e:
                if e.errno in (errno.EROFS, errno.EPERM):
                    if has_password:
                        print(f"Warning: Configuration file '{conffile}' may have insecure file permissions.", file=sys.stderr)
                else:
                    raise e


    global config

    config = Options()
    config.conffile = conffile

    # read 'debug' value before it gets properly stored into Options for early debug messages
    if override_debug:
        debug_str = str(override_debug)
    elif "OSC_DEBUG" in os.environ:
        debug_str = os.environ["OSC_DEBUG"]
    elif "debug" in cp["general"]:
        debug_str = cp["general"]["debug"]
    else:
        debug_str = "0"
    debug = True if debug_str.strip().lower() in ("1", "yes", "true", "on") else False

    # read host options first in order to populate apiurl aliases
    urls = [i for i in cp.sections() if i != "general"]
    for url in urls:
        apiurl = sanitize_apiurl(url)
        # the username will be overwritten later while reading actual config values
        username = cp[url].get("user", "")
        host_options = HostOptions(apiurl=apiurl, username=username, _parent=config)

        known_ini_keys = set()
        for name, field in host_options.__fields__.items():
            # the following code relies on interating through fields in a given order: aliases, username, credentials_mgr_class, password

            ini_key = field.extra.get("ini_key", name)
            known_ini_keys.add(ini_key)
            known_ini_keys.add(name)

            # iterate through aliases and store the value of the the first env that matches OSC_HOST_{ALIAS}_{NAME}
            env_value = None
            for alias in host_options.aliases:
                alias = alias.replace("-", "_")
                env_key = f"OSC_HOST_{alias.upper()}_{name.upper()}"
                env_value = os.environ.get(env_key, None)
                if env_value is not None:
                    break

            if env_value is not None:
                value = env_value
            elif ini_key in cp[url]:
                value = cp[url][ini_key]
            else:
                value = None

            if name == "credentials_mgr_class":
                # HACK: inject credentials_mgr_class back in case we have specified it from env to have it available for reading password
                if value:
                    cp[url][credentials.AbstractCredentialsManager.config_entry] = value
            elif name == "password":
                creds_mgr = _get_credentials_manager(url, cp)
                if env_value is None:
                    value = creds_mgr.get_password(url, host_options.username, defer=True, apiurl=host_options.apiurl)

            if value is not None:
                host_options.set_value_from_string(name, value)

        for key, value in cp[url].items():
            if key.startswith("_"):
                continue
            if key in known_ini_keys:
                continue
            if debug:
                print(f"DEBUG: Config option '[{url}]/{key}' doesn't map to any HostOptions field", file=sys.stderr)
            host_options[key] = value

        scheme = urlsplit(apiurl)[0]
        if scheme == "http" and not host_options.allow_http:
            msg = "The apiurl '{apiurl}' uses HTTP protocol without any encryption.\n"
            msg += "All communication incl. sending your password IS NOT ENCRYPTED!\n"
            msg += "Add 'allow_http=1' to the [{apiurl}] config file section to mute this message.\n"
            print(msg.format(apiurl=apiurl), file=sys.stderr)

        config.api_host_options[apiurl] = host_options

    # read the main options
    known_ini_keys = set()
    for name, field in config.__fields__.items():
        ini_key = field.extra.get("ini_key", name)
        known_ini_keys.add(ini_key)
        known_ini_keys.add(name)
        env_key = f"OSC_{name.upper()}"

        # priority: env, overrides, config
        if env_key in os.environ:
            value = os.environ[env_key]
            # remove any matching records from overrides because they are checked for emptiness later
            overrides.pop(name, None)
            overrides.pop(ini_key, None)
        elif name in overrides:
            value = overrides.pop(name)
        elif ini_key in overrides:
            value = overrides.pop(ini_key)
        elif ini_key in cp["general"]:
            value = cp["general"][ini_key]
        else:
            continue

        if name == "apiurl":
            # resolve an apiurl alias to an actual apiurl
            apiurl = config.apiurl_aliases.get(value, None)
            if not apiurl:
                # no alias matched, try again with a sanitized apiurl (with https:// prefix)
                # and if there's no match again, just use the sanitized apiurl
                apiurl = sanitize_apiurl(value)
                apiurl = config.apiurl_aliases.get(apiurl, apiurl)
            value = apiurl

        config.set_value_from_string(name, value)

    # BEGIN: override credentials for the default apiurl

    # OSC_APIURL is handled already because it's a regular field
    env_username = os.environ.get("OSC_USERNAME", "")
    env_credentials_mgr_class = os.environ.get("OSC_CREDENTIALS_MGR_CLASS", None)
    env_password = os.environ.get("OSC_PASSWORD", None)

    if config.apiurl not in config.api_host_options:
        host_options = HostOptions(apiurl=config.apiurl, username=env_username, _parent=config)
        config.api_host_options[config.apiurl] = host_options
        # HACK: inject section so we can add credentials_mgr_class later
        cp.add_section(config.apiurl)

    host_options = config.api_host_options[config.apiurl]
    if env_username:
        host_options.set_value_from_string("username", env_username)

    if env_credentials_mgr_class:
        host_options.set_value_from_string("credentials_mgr_class", env_credentials_mgr_class)
        # HACK: inject credentials_mgr_class in case we have specified it from env to have it available for reading password
        cp[config.apiurl]["credentials_mgr_class"] = env_credentials_mgr_class

    if env_password:
        password = Password(env_password)
        host_options.password = password
    elif env_credentials_mgr_class:
        creds_mgr = _get_credentials_manager(config.apiurl, cp)
        password = creds_mgr.get_password(config.apiurl, host_options.username, defer=True, apiurl=host_options.apiurl)
        host_options.password = password

    # END: override credentials for the default apiurl

    for apiurl, host_options in config.api_host_options.items():
        if not host_options.username:
            raise oscerr.ConfigMissingCredentialsError(f"No user configured for apiurl {apiurl}", conffile, apiurl)

        if host_options.password is None:
            raise oscerr.ConfigMissingCredentialsError(f"No password configured for apiurl {apiurl}", conffile, apiurl)

    for key, value in cp["general"].items():
        if key.startswith("_"):
            continue
        if key in known_ini_keys:
            continue
        if debug:
            print(f"DEBUG: Config option '[general]/{key}' doesn't map to any Options field", file=sys.stderr)
        config[key] = value

    if overrides:
        unused_overrides_str = ", ".join((f"'{i}'" for i in overrides))
        raise oscerr.ConfigError(f"Unknown config options: {unused_overrides_str}", "<command-line>")

    # XXX unless config['user'] goes away (and is replaced with a handy function, or
    # config becomes an object, even better), set the global 'user' here as well,
    # provided that there _are_ credentials for the chosen apiurl:
    try:
        config['user'] = get_apiurl_usr(config['apiurl'])
    except oscerr.ConfigMissingApiurl as e:
        e.msg = config_missing_apiurl_text % config['apiurl']
        e.file = conffile
        raise e

    # enable connection debugging after all config options are set
    from .connection import enable_http_debug
    enable_http_debug(config)


def identify_conf():
    # needed for compat reasons(users may have their oscrc still in ~
    if 'OSC_CONFIG' in os.environ:
        return os.environ.get('OSC_CONFIG')

    conffile = os.path.join(xdg.XDG_CONFIG_HOME, "osc", "oscrc")

    if os.path.exists(os.path.expanduser("~/.oscrc")) or os.path.islink(os.path.expanduser("~/.oscrc")):
        if "XDG_CONFIG_HOME" in os.environ:
            print(f"{tty.colorize('WARNING', 'yellow,bold')}: Ignoring XDG_CONFIG_HOME env, loading an existing config from '~/.oscrc' instead", file=sys.stderr)
            print("         To fix this, move the existing '~/.oscrc' to XDG location such as '~/.config/osc/oscrc'", file=sys.stderr)
        elif os.path.exists(os.path.expanduser(conffile)):
            print(f"{tty.colorize('WARNING', 'yellow,bold')}: Ignoring config '{conffile}' in XDG location, loading an existing config from ~/.oscrc instead", file=sys.stderr)
            print("         To fix this, remove '~/.oscrc'", file=sys.stderr)
        return '~/.oscrc'

    return conffile


def interactive_config_setup(conffile, apiurl, initial=True):
    if not apiurl:
        apiurl = Options()["apiurl"]

    scheme = urlsplit(apiurl)[0]
    http = scheme == "http"
    if http:
        msg = "The apiurl '{apiurl}' uses HTTP protocol without any encryption.\n"
        msg += "All communication incl. sending your password WILL NOT BE ENCRYPTED!\n"
        msg += "Do you really want to continue with no encryption?\n"
        print(msg.format(apiurl=apiurl), file=sys.stderr)
        yes = raw_input("Type 'YES' to continue: ")
        if yes != "YES":
            raise oscerr.UserAbort()
        print()

    apiurl_no_scheme = urlsplit(apiurl)[1] or apiurl
    user_prompt = f"Username [{apiurl_no_scheme}]: "
    user = raw_input(user_prompt)
    pass_prompt = f"Password [{user}@{apiurl_no_scheme}]: "
    passwd = getpass.getpass(pass_prompt)
    creds_mgr_descr = select_credentials_manager_descr()
    if initial:
        config = {'user': user, 'pass': passwd}
        if apiurl:
            config['apiurl'] = apiurl
        if http:
            config['allow_http'] = 1
        write_initial_config(conffile, config, creds_mgr_descriptor=creds_mgr_descr)
    else:
        add_section(conffile, apiurl, user, passwd, creds_mgr_descriptor=creds_mgr_descr, allow_http=http)


def select_credentials_manager_descr():
    if not credentials.has_keyring_support():
        print('To use keyrings please install python%d-keyring.' % sys.version_info.major)
    creds_mgr_descriptors = credentials.get_credentials_manager_descriptors()

    rows = []
    for i, creds_mgr_descr in enumerate(creds_mgr_descriptors, 1):
        rows += [str(i), creds_mgr_descr.name(), creds_mgr_descr.description()]

    from .core import build_table
    headline = ('NUM', 'NAME', 'DESCRIPTION')
    table = build_table(len(headline), rows, headline)
    print()
    for row in table:
        print(row)

    i = raw_input('Select credentials manager [default=1]: ')
    if not i:
        i = "1"
    if not i.isdigit():
        sys.exit('Invalid selection')
    i = int(i) - 1
    if i < 0 or i >= len(creds_mgr_descriptors):
        sys.exit('Invalid selection')
    return creds_mgr_descriptors[i]

# vim: sw=4 et
