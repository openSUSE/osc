import importlib
import bz2
import base64
import getpass
try:
    from urllib.parse import urlsplit
except ImportError:
    from urlparse import urlsplit
try:
    import keyring
except ImportError:
    keyring = None
try:
    import gnomekeyring
except ImportError:
    gnomekeyring = None


class AbstractCredentialsManagerDescriptor(object):
    def name(self):
        raise NotImplementedError()

    def description(self):
        raise NotImplementedError()

    def create(self, cp):
        raise NotImplementedError()

    def __lt__(self, other):
        return self.name() < other.name()


class AbstractCredentialsManager(object):
    config_entry = 'credentials_mgr_class'

    def __init__(self, cp, options):
        super(AbstractCredentialsManager, self).__init__()
        self._cp = cp
        self._process_options(options)

    @classmethod
    def create(cls, cp, options):
        return cls(cp, options)

    def get_password(self, url, user, defer=True):
        # If defer is True a callable can be returned
        # and the password is retrieved if the callable
        # is called. Implementations are free to ignore
        # defer parameter and can directly return the password.
        # If defer is False the password is directly returned.
        raise NotImplementedError()

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
        return 'Config file credentials manager'

    def description(self):
        return 'Store the credentials in the config file (plain text)'

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
        compressed_pw = base64.b64decode(password.encode("ascii"))
        return bz2.decompress(compressed_pw).decode("ascii")


class ObfuscatedConfigFileDescriptor(AbstractCredentialsManagerDescriptor):
    def name(self):
        return 'Obfuscated Config file credentials manager'

    def description(self):
        return 'Store the credentials in the config file (obfuscated)'

    def create(self, cp):
        return ObfuscatedConfigFileCredentialsManager(cp, None)


class TransientCredentialsManager(AbstractCredentialsManager):
    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self._password = None

    def _process_options(self, options):
        if options is not None:
            raise RuntimeError('options must be None')

    def get_password(self, url, user, defer=True):
        if defer:
            return self
        return self()

    def set_password(self, url, user, password):
        self._password = password
        self._cp.set(url, self.config_entry, self._qualified_name())

    def delete_password(self, url, user):
        self._password = None

    def __call__(self):
        if self._password is None:
            self._password = getpass.getpass('Password: ')
        return self._password


class TransientDescriptor(AbstractCredentialsManagerDescriptor):
    def name(self):
        return 'Transient password store'

    def description(self):
        return 'Do not store the password and always ask for the password'

    def create(self, cp):
        return TransientCredentialsManager(cp, None)


class KeyringCredentialsManager(AbstractCredentialsManager):
    def _process_options(self, options):
        if options is None:
            raise RuntimeError('options may not be None')
        self._backend_cls_name = options

    def _load_backend(self):
        keyring_backend = keyring.core.load_keyring(self._backend_cls_name)
        keyring.set_keyring(keyring_backend)

    @classmethod
    def create(cls, cp, options):
        if not has_keyring_support():
            return None
        return super(cls, cls).create(cp, options)

    def get_password(self, url, user, defer=True):
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
    def __init__(self, keyring_backend):
        self._keyring_backend = keyring_backend

    def name(self):
        return self._keyring_backend.name

    def description(self):
        return 'Backend provided by python-keyring'

    def create(self, cp):
        qualified_backend_name = qualified_name(self._keyring_backend)
        return KeyringCredentialsManager(cp, qualified_backend_name)


class GnomeKeyringCredentialsManager(AbstractCredentialsManager):
    @classmethod
    def create(cls, cp, options):
        if gnomekeyring is None:
            return None
        return super(cls, cls).create(cp, options)

    def get_password(self, url, user, defer=True):
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

    def create(self, cp):
        return GnomeKeyringCredentialsManager(cp, None)


def get_credentials_manager_descriptors():
    if has_keyring_support():
        backend_list = keyring.backend.get_all_keyring()
    else:
        backend_list = []
    descriptors = []
    for backend in backend_list:
        descriptors.append(KeyringCredentialsDescriptor(backend))
    descriptors.sort()
    if gnomekeyring:
        descriptors.append(GnomeKeyringCredentialsDescriptor())
    descriptors.append(PlaintextConfigFileDescriptor())
    descriptors.append(ObfuscatedConfigFileDescriptor())
    descriptors.append(TransientDescriptor())
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
    return getattr(importlib.import_module(mod), cls).create(cp, options)


def qualified_name(obj):
    return obj.__module__ + '.' + obj.__class__.__name__


def has_keyring_support():
    return keyring is not None
