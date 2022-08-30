from __future__ import print_function

import importlib
import bz2
import base64
import getpass
import sys

try:
    from urllib.parse import urlsplit
except ImportError:
    from urlparse import urlsplit

try:
    import keyring
except ImportError:
    keyring = None
except BaseException as e:
    # catch and report any exceptions raised in the 'keyring' module
    msg = "Warning: Unable to load the 'keyring' module due to an internal error:"
    print(msg, e, file=sys.stderr)
    keyring = None

try:
    import gnomekeyring
except ImportError:
    gnomekeyring = None
except BaseException as e:
    # catch and report any exceptions raised in the 'gnomekeyring' module
    msg = "Warning: Unable to load the 'gnomekeyring' module due to an internal error:"
    print(msg, e, file=sys.stderr)
    gnomekeyring = None

from . import oscerr


class _LazyPassword(object):
    def __init__(self, pwfunc):
        self._pwfunc = pwfunc
        self._password = None

    def __str__(self):
        if self._password is None:
            password = self._pwfunc()
            if callable(password):
                print('Warning: use of a deprecated credentials manager API.',
                      file=sys.stderr)
                password = password()
            if password is None:
                raise oscerr.OscIOError(None, 'Unable to retrieve password')
            self._password = password
        return self._password

    def __len__(self):
        return len(str(self))

    def __add__(self, other):
        return str(self) + other

    def __radd__(self, other):
        return other + str(self)

    def __getattr__(self, name):
        return getattr(str(self), name)


class AbstractCredentialsManagerDescriptor(object):
    def name(self):
        raise NotImplementedError()

    def description(self):
        raise NotImplementedError()

    def priority(self):
        # priority determines order in the credentials managers list
        # higher number means higher priority
        raise NotImplementedError()

    def create(self, cp):
        raise NotImplementedError()

    def __lt__(self, other):
        return (-self.priority(), self.name()) < (-other.priority(), other.name())


class AbstractCredentialsManager(object):
    config_entry = 'credentials_mgr_class'

    def __init__(self, cp, options):
        super(AbstractCredentialsManager, self).__init__()
        self._cp = cp
        self._process_options(options)

    @classmethod
    def create(cls, cp, options):
        return cls(cp, options)

    def _get_password(self, url, user):
        raise NotImplementedError()

    def get_password(self, url, user, defer=True):
        if defer:
            return _LazyPassword(lambda: self._get_password(url, user))
        else:
            return self._get_password(url, user)

    def set_password(self, url, user, password):
        raise NotImplementedError()

    def delete_password(self, url, user):
        raise NotImplementedError()

    def _qualified_name(self):
        return qualified_name(self)

    def _process_options(self, options):
        pass


class PlaintextConfigFileCredentialsManager(AbstractCredentialsManager):
    def get_password(self, url, user, defer=True):
        return self._cp.get(url, 'pass', raw=True)

    def set_password(self, url, user, password):
        self._cp.set(url, 'pass', password)
        self._cp.set(url, self.config_entry, self._qualified_name())

    def delete_password(self, url, user):
        self._cp.remove_option(url, 'pass')

    def _process_options(self, options):
        if options is not None:
            raise RuntimeError('options must be None')


class PlaintextConfigFileDescriptor(AbstractCredentialsManagerDescriptor):
    def name(self):
        return 'Config'

    def description(self):
        return 'Store the password in plain text in the osc config file [insecure, persistent]'

    def priority(self):
        return 1

    def create(self, cp):
        return PlaintextConfigFileCredentialsManager(cp, None)


class ObfuscatedConfigFileCredentialsManager(
        PlaintextConfigFileCredentialsManager):
    def get_password(self, url, user, defer=True):
        if self._cp.has_option(url, 'passx', proper=True):
            passwd = self._cp.get(url, 'passx', raw=True)
        else:
            passwd = super(self.__class__, self).get_password(url, user)
        return self.decode_password(passwd)

    def set_password(self, url, user, password):
        compressed_pw = bz2.compress(password.encode('ascii'))
        password = base64.b64encode(compressed_pw).decode("ascii")
        super(self.__class__, self).set_password(url, user, password)

    def delete_password(self, url, user):
        self._cp.remove_option(url, 'passx')
        super(self.__class__, self).delete_password(url, user)

    @classmethod
    def decode_password(cls, password):
        if password is None:
            # avoid crash on encoding None when 'pass' is not specified in the config
            return None
        compressed_pw = base64.b64decode(password.encode("ascii"))
        return bz2.decompress(compressed_pw).decode("ascii")


class ObfuscatedConfigFileDescriptor(AbstractCredentialsManagerDescriptor):
    def name(self):
        return 'Obfuscated config'

    def description(self):
        return 'Store the password in obfuscated form in the osc config file [insecure, persistent]'

    def priority(self):
        return 2

    def create(self, cp):
        return ObfuscatedConfigFileCredentialsManager(cp, None)


class TransientCredentialsManager(AbstractCredentialsManager):
    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self._password = None

    def _process_options(self, options):
        if options is not None:
            raise RuntimeError('options must be None')

    def _get_password(self, url, user):
        if self._password is None:
            self._password = getpass.getpass('Password: ')
        return self._password

    def set_password(self, url, user, password):
        self._password = password
        self._cp.set(url, self.config_entry, self._qualified_name())

    def delete_password(self, url, user):
        self._password = None


class TransientDescriptor(AbstractCredentialsManagerDescriptor):
    def name(self):
        return 'Transient'

    def description(self):
        return 'Do not store the password and always ask for it [secure, in-memory]'

    def priority(self):
        return 3

    def create(self, cp):
        return TransientCredentialsManager(cp, None)


class KeyringCredentialsManager(AbstractCredentialsManager):
    def _process_options(self, options):
        if options is None:
            raise RuntimeError('options may not be None')
        self._backend_cls_name = options

    def _load_backend(self):
        try:
            keyring_backend = keyring.core.load_keyring(self._backend_cls_name)
        except ModuleNotFoundError:
            msg = "Invalid credentials_mgr_class: {}".format(self._backend_cls_name)
            from . import conf
            raise oscerr.ConfigError(msg, conf.config['conffile'])
        keyring.set_keyring(keyring_backend)

    @classmethod
    def create(cls, cp, options):
        if not has_keyring_support():
            return None
        return super(cls, cls).create(cp, options)

    def _get_password(self, url, user):
        self._load_backend()
        return keyring.get_password(urlsplit(url)[1], user)

    def set_password(self, url, user, password):
        self._load_backend()
        keyring.set_password(urlsplit(url)[1], user, password)
        config_value = self._qualified_name() + ':' + self._backend_cls_name
        self._cp.set(url, self.config_entry, config_value)

    def delete_password(self, url, user):
        self._load_backend()
        keyring.delete_password(urlsplit(url)[1], user)


class KeyringCredentialsDescriptor(AbstractCredentialsManagerDescriptor):
    def __init__(self, keyring_backend, name=None, description=None, priority=None):
        self._keyring_backend = keyring_backend
        self._name = name
        self._description = description
        self._priority = priority

    def name(self):
        if self._name:
            return self._name
        if hasattr(self._keyring_backend, 'name'):
            return self._keyring_backend.name
        return self._keyring_backend.__class__.__name__

    def description(self):
        if self._description:
            return self._description
        return 'Backend provided by python-keyring'

    def priority(self):
        if self._priority is not None:
            return self._priority
        return 0

    def create(self, cp):
        qualified_backend_name = qualified_name(self._keyring_backend)
        return KeyringCredentialsManager(cp, qualified_backend_name)


class GnomeKeyringCredentialsManager(AbstractCredentialsManager):
    @classmethod
    def create(cls, cp, options):
        if gnomekeyring is None:
            return None
        return super(cls, cls).create(cp, options)

    def _get_password(self, url, user):
        gk_data = self._keyring_data(url, user)
        if gk_data is None:
            return None
        return gk_data['password']

    def set_password(self, url, user, password):
        scheme, host, path = self._urlsplit(url)
        gnomekeyring.set_network_password_sync(
            user=user,
            password=password,
            protocol=scheme,
            server=host,
            object=path)
        self._cp.set(url, self.config_entry, self._qualified_name())

    def delete_password(self, url, user):
        gk_data = self._keyring_data(url, user)
        if gk_data is None:
            return
        gnomekeyring.item_delete_sync(gk_data['keyring'], gk_data['item_id'])

    def get_user(self, url):
        gk_data = self._keyring_data(url, None)
        if gk_data is None:
            return None
        return gk_data['user']

    def _keyring_data(self, url, user):
        scheme, host, path = self._urlsplit(url)
        try:
            entries = gnomekeyring.find_network_password_sync(protocol=scheme,
                                                              server=host,
                                                              object=path)
        except gnomekeyring.NoMatchError:
            return None

        for entry in entries:
            if 'user' not in entry or 'password' not in entry:
                continue
            if user is None or entry['user'] == user:
                return entry
        return None

    def _urlsplit(self, url):
        splitted_url = urlsplit(url)
        return splitted_url.scheme, splitted_url.netloc, splitted_url.path


class GnomeKeyringCredentialsDescriptor(AbstractCredentialsManagerDescriptor):
    def name(self):
        return 'GNOME Keyring Manager (deprecated)'

    def description(self):
        return 'Deprecated GNOME Keyring Manager. If you use \
                this we will send you a Dial-In modem'

    def priority(self):
        return 0

    def create(self, cp):
        return GnomeKeyringCredentialsManager(cp, None)


# we're supporting only selected python-keyring backends in osc
SUPPORTED_KEYRING_BACKENDS = {
    "keyutils.osc.OscKernelKeyringBackend": {
        "name": "Kernel keyring",
        "description": "Store password in user session keyring in kernel keyring [secure, in-memory, per-session]",
        "priority": 10,
    },
    "keyring.backends.SecretService.Keyring": {
        "name": "Secret Service",
        "description": "Store password in Secret Service (GNOME Keyring backend) [secure, persistent]",
        "priority": 9,
    },
    "keyring.backends.kwallet.DBusKeyring": {
        "name": "KWallet",
        "description": "Store password in KWallet [secure, persistent]",
        "priority": 8,
    },
}


def get_credentials_manager_descriptors():
    descriptors = []

    if has_keyring_support():
        for backend in keyring.backend.get_all_keyring():
            qualified_backend_name = qualified_name(backend)
            data = SUPPORTED_KEYRING_BACKENDS.get(qualified_backend_name, None)
            if not data:
                continue
            descriptor = KeyringCredentialsDescriptor(
                backend,
                data["name"],
                data["description"],
                data["priority"]
            )
            descriptors.append(descriptor)
    if gnomekeyring:
        descriptors.append(GnomeKeyringCredentialsDescriptor())
    descriptors.append(PlaintextConfigFileDescriptor())
    descriptors.append(ObfuscatedConfigFileDescriptor())
    descriptors.append(TransientDescriptor())
    descriptors.sort()
    return descriptors


def get_keyring_credentials_manager(cp):
    keyring_backend = keyring.get_keyring()
    return KeyringCredentialsManager(cp, qualified_name(keyring_backend))


def create_credentials_manager(url, cp):
    config_entry = cp.get(url, AbstractCredentialsManager.config_entry)
    if ':' in config_entry:
        creds_mgr_cls, options = config_entry.split(':', 1)
    else:
        creds_mgr_cls = config_entry
        options = None
    mod, cls = creds_mgr_cls.rsplit('.', 1)
    try:
        creds_mgr = getattr(importlib.import_module(mod), cls).create(cp, options)
    except ModuleNotFoundError:
        msg = "Invalid credentials_mgr_class: {}".format(creds_mgr_cls)
        from . import conf
        raise oscerr.ConfigError(msg, conf.config['conffile'])
    return creds_mgr


def qualified_name(obj):
    return obj.__module__ + '.' + obj.__class__.__name__


def has_keyring_support():
    return keyring is not None
