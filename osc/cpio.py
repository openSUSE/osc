import struct, sys

class Cpio:
    """cpio archive small files in memory, using new style portable header format"""

    def __init__(self):
        self.cpio = ''

    def add(self, name=None, content=None):
        namesize = len(name) + 1
        if namesize % 2:
            name += '\0'
        filesize = len(content)

        c = []
        c.append('070701') # magic
        c.append('%08X' % 0) # inode
        c.append('%08X' % 0) # mode
        c.append('%08X' % 0) # uid
        c.append('%08X' % 0) # gid
        c.append('%08X' % 0) # nlink
        c.append('%08X' % 0) # mtime
        c.append('%08X' % filesize)
        c.append('%08X' % 0) # major
        c.append('%08X' % 0) # minor
        c.append('%08X' % 0) # rmajor
        c.append('%08X' % 0) # rminor
        c.append('%08X' % namesize)
        c.append('%08X' % 0) # checksum

        c.append(name + '\0')
        c.append('\0' * (len(''.join(c)) % 4))

        c.append(content)
    
        c = ''.join(c)
        sys.stderr.write('%s\n' % len(c))
        if len(c) % 4:
            c += '\0' * (4 - len(c) % 4)
        sys.stderr.write('%s\n\n' % len(c))

        self.cpio += c
    
    def add_padding(self):
        if len(self.cpio) % 512:
            self.cpio += '\0' * (512 - len(self.cpio) % 512)

    def get(self):
        self.add('TRAILER!!!', '')
        self.add_padding()
        return ''.join(self.cpio)
        

def main():
    cpio = Cpio()
    cpio.add(name='asdf', content='123\n')
    cpio.add(name='bar', content='foo1\n')
    cpio.add(name='services', content=open('/etc/services').read())
    sys.stdout.write(cpio.get())



if __name__ == '__main__':
    main()
