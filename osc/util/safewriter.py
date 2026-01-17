import io

# be careful when debugging this code:
# don't add print statements when setting sys.stdout = SafeWriter(sys.stdout)...
class SafeWriter(io.TextIOBase):
    """
    Safely write an (unicode) str. In case of an "UnicodeEncodeError" the
    the str is encoded with the "encoding" encoding.
    All getattr, setattr calls are passed through to the "writer" instance.
    """

    def __init__(self, writer, encoding='unicode_escape'):
        super().__init__()
        self._writer = writer
        self._encoding = encoding

    # TextIOBase requires overriding the following stub methods: detach, read, readline, and write

    def detach(self, *args, **kwargs):
        return self._writer.detach(*args, **kwargs)

    def read(self, *args, **kwargs):
        return self._writer.read(args, **kwargs)

    def readline(self, *args, **kwargs):
        return self._writer.readline(args, **kwargs)

    def write(self, s):
        try:
            self._writer.write(s)
        except UnicodeEncodeError as e:
            self._writer.write(s.encode(self._encoding))

    def fileno(self, *args, **kwargs):
        return self._writer.fileno(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._writer, name)

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
