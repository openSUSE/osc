import base64
import bz2
import getpass
import importlib
import sys
from urllib.parse import urlsplit

try:
    import keyring
except ImportError:
    keyring = None
except BaseException as e:
    # catch and report any exceptions raised in the 'keyring' module
    msg = "Warning: Unable to load the 'keyring' module due to an internal error:"
    print(msg, e, file=sys.stderr)
    keyring = None

from . import conf
from . import oscerr


class AbstractCredentialsManagerDescriptor:
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


class AbstractCredentialsManager:
    config_entry = 'credentials_mgr_class'

    def __init__(self, cp, options):
        super().__init__()
        self._cp = cp
        self._process_options(options)

    @classmethod
    def create(cls, cp, options):
        return cls(cp, options)

    def _get_password(self, url, user, apiurl=None):
        raise NotImplementedError()

    def get_password(self, url, user, defer=True, apiurl=None):
        if defer:
            return conf.Password(lambda: self._get_password(url, user, apiurl=apiurl))
        else:
            return conf.Password(self._get_password(url, user, apiurl=apiurl))

    def set_password(self, url, user, password):
        raise NotImplementedError()

    def delete_password(self, url, user):
        raise NotImplementedError()

    def _qualified_name(self):
        return qualified_name(self)

    def _process_options(self, options):
        pass


class PlaintextConfigFileCredentialsManager(AbstractCredentialsManager):
    def get_password(self, url, user, defer=True, apiurl=None):
        password = self._cp.get(url, "pass", fallback=None, raw=True)
        if password is None:
            return None
        return conf.Password(password)

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


class ObfuscatedConfigFileCredentialsManager(PlaintextConfigFileCredentialsManager):
    def get_password(self, url, user, defer=True, apiurl=None):
        if self._cp.has_option(url, 'passx', proper=True):
            passwd = self._cp.get(url, 'passx', raw=True)
        else:
            passwd = super().get_password(url, user, apiurl=apiurl)
        password = self.decode_password(passwd)
        return conf.Password(password)

    def set_password(self, url, user, password):
        compressed_pw = bz2.compress(password.encode('ascii'))
        password = base64.b64encode(compressed_pw).decode("ascii")
        super().set_password(url, user, password)

    def delete_password(self, url, user):
        self._cp.remove_option(url, 'passx')
        super().delete_password(url, user)

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
        super().__init__(*args, **kwargs)
        self._password = None

    def _process_options(self, options):
        if options is not None:
            raise RuntimeError('options must be None')

    def _get_password(self, url, user, apiurl=None):
        if self._password is None:
            if apiurl:
                # strip scheme from apiurl because we don't want to display it to the user
                apiurl_no_scheme = urlsplit(apiurl)[1]
                msg = f'Password [{user}@{apiurl_no_scheme}]: '
            else:
                msg = 'Password: '
            self._password = getpass.getpass(msg)
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._password = None

    def _process_options(self, options):
        if options is None:
            raise RuntimeError('options may not be None')
        self._backend_cls_name = options

    def _load_backend(self):
        try:
            keyring_backend = keyring.core.load_keyring(self._backend_cls_name)
        except ModuleNotFoundError:
            msg = f"Invalid credentials_mgr_class: {self._backend_cls_name}"
            raise oscerr.ConfigError(msg, conf.config['conffile'])
        keyring.set_keyring(keyring_backend)

    @classmethod
    def create(cls, cp, options):
        if not has_keyring_support():
            return None
        return super().create(cp, options)

    def _get_password(self, url, user, apiurl=None):
        if self._password is None:
            self._load_backend()
            self._password = keyring.get_password(urlsplit(url)[1], user)
            # TODO: this works fine on the command-line but a long-running process using osc library would start failing after changing the password in the keyring
            # TODO: implement retrieving the password again after basic auth fails; sufficiently inform user about what's being done
        return self._password

    def set_password(self, url, user, password):
        self._load_backend()
        keyring.set_password(urlsplit(url)[1], user, password)
        config_value = f"{self._qualified_name()}:{self._backend_cls_name}"
        self._cp.set(url, self.config_entry, config_value)
        self._password = password

    def delete_password(self, url, user):
        self._load_backend()
        service = urlsplit(url)[1]
        data = keyring.get_password(service, user)
        if data is None:
            return
        keyring.delete_password(service, user)


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
        msg = f"Invalid credentials_mgr_class: {creds_mgr_cls}"
        raise oscerr.ConfigError(msg, conf.config['conffile'])
    return creds_mgr


def qualified_name(obj):
    return f"{obj.__module__}.{obj.__class__.__name__}"


def has_keyring_support():
    return keyring is not None
