# be careful when debugging this code:
# don't add print statements when setting sys.stdout = SafeWriter(sys.stdout)...
class SafeWriter:
    """
    Safely write an (unicode) str. In case of an "UnicodeEncodeError" the
    the str is encoded with the "encoding" encoding.
    All getattr, setattr calls are passed through to the "writer" instance.
    """
    def __init__(self, writer, encoding='unicode_escape'):
        self.__dict__['writer'] = writer
        self.__dict__['encoding'] = encoding

    def __get_writer(self):
        return self.__dict__['writer']

    def __get_encoding(self):
        return self.__dict__['encoding']

    def write(self, s):
        try:
            self.__get_writer().write(s)
        except UnicodeEncodeError as e:
            self.__get_writer().write(s.encode(self.__get_encoding()))

    def __getattr__(self, name):
        return getattr(self.__get_writer(), name)

    def __setattr__(self, name, value):
        setattr(self.__get_writer(), name, value)
