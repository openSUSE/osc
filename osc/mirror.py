import sys
import os.path
from shutil import copyfile

try:
    from urllib.request import urlopen, HTTPError, url2pathname
except ImportError:
    from urllib2 import urlopen, HTTPError, url2pathname

class MGError(IOError):
    def __init__(self, *args):
        IOError.__init__(self, *args)

class OscMirrorGroup:
    def __init__(self, grabber, mirrors, **kwargs):
        self.grabber = grabber
        self.mirrors = mirrors

    def urlgrab(self, url, filename=None, **kwargs):
        max_m = len(self.mirrors)
        tries = 0
        for mirror in self.mirrors:
            try:
                if mirror.startswith('file'):
                    path = mirror.replace('file:/', '')
                    if not os.path.exists(path):
                        tries += 1
                        continue
                    else:
                        copyfile(path,filename)
                        break
                u = urlopen(mirror)
                h = u.info()
                totalSize = int(h["Content-Length"])
                f = open(filename, 'wb')
                blockSize = 8192
                file_size_dl = 0
                count = 0
                while True:
                    chunk = u.read(blockSize)
                    if not chunk: break
                    f.write(chunk)
                    file_size_dl += len(chunk)
                    done = int(50 * file_size_dl / totalSize)
                    sys.stdout.write('[%s%s] %s\r' % ('=' * done, ' ' * (50-done), url)) 
                    sys.stdout.flush()
                print('\n')
                f.flush
                f.close
                break
            except HTTPError, e:
                if e.code == 414:
                    raise MGError
                tries += 1
                continue

        if max_m == tries:
            print('No mirror left to check. We now need to use the api')
            raise MGError(256, 'No mirrors left')
