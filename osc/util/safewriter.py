# be careful when debugging this code:
# don't add print statements when setting sys.stdout = SafeWriter(sys.stdout)...
class SafeWriter:
    """
    Safely write an (unicode) str. In case of an "UnicodeEncodeError" the
    the str is encoded with the "encoding" encoding.
    All getattr, setattr calls are passed through to the "writer" instance.
    """

    def __init__(self, writer, encoding='unicode_escape'):
        self._writer = writer
        self._encoding = encoding

    def write(self, s):
        try:
            self._writer.write(s)
        except UnicodeEncodeError as e:
            self._writer.write(s.encode(self._encoding))

    def __getattr__(self, name):
        return getattr(self._writer, name)

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
