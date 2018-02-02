import sys
import os.path
import urllib
import pycurl

class OscMirrorGroup:
    def __init__(self, grabber, mirrors, **kwargs):

        self.grabber = grabber
        self.mirrors = mirrors

    #def _parse_mirrors(self, mirrors):
    #    parsed_mirrors = []
    #    for m in mirrors:
    #        if isinstance(m, str):
    #            m = {'mirror': _to_utf8(m)}
    #        parsed_mirrors.append(m)
    #    return parsed_mirrors 


    def urlgrab(self, url, filename=None, **kwargs):
        print(self.mirrors)
        for mirror in self.mirrors:
            if mirror.startswith('file://'):
                next
            print('using mirror ' + mirror)
            try: 
                urllib.urlretrieve(mirror, filename)
                #fo = PyCurlFileObject(mirror, filename
                print('saved ' + url + ' to ' + filename)
            except Exception, e:
                print('We have an exception!')
                print(e)
                raise(123,'This error')
