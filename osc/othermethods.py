#!/usr/bin/python

# Copyright (C) 2006 Peter Poeml / Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.


"""
This file is provided because urllib2 doesn't have support for the DELETE and
PUT methods.

"""

import httplib 
import base64 
import sys 
import os 
import urlparse
from osc.core import __version__

BLOCKSIZE=4096

def request(method, url, username, password, file=None, strbuf=None):
    """call with method = (PUT|DELETE)"""


    if method == 'PUT':
        if file == None and strbuf == None:
            print >>sys.stderr, 'putting a file requires either a filename or a string buffer'
            sys.exit(1)
        if strbuf:
            size = len(strbuf)
        else:
            size = os.path.getsize(file)

    scheme, host, path, params, query, fragment = urlparse.urlparse(url)
    if query:
        path += '?' + query

    if scheme == 'https':
        conn = httplib.HTTPS(host) 
    elif scheme == 'http':
        conn = httplib.HTTP(host) 
    else:
        sys.exit('unknown scheme %s' % scheme)
    #conn.set_debuglevel(10)

    # Headers
    conn.putrequest(method, '%s' % path) 
    conn.putheader('Host', host)
    conn.putheader('User-agent', 'osc/%s' % __version__)
    auth_string = base64.encodestring('%s:%s' % (username, password)).strip()
    conn.putheader('Authorization', 'Basic %s' % auth_string) 
    if method == 'PUT':
        conn.putheader('Content-Type', 'text/plain') 
        conn.putheader('Content-Length', str(size)) 
    conn.endheaders() 

    # Body
    if method == 'PUT':
        if strbuf:
            conn.send(strbuf)
        else:
            fp = open(file, 'rb') 
            #n = 0 
            while 1: 
                buf = fp.read(BLOCKSIZE) 
                #n+=1 
                #if n % 10 == 0: 
                #    print 'upload-sending blocknum=', n 
                #    print '.',

                if not buf: break 

                try:
                    conn.send(buf)
                except:
                    sys.exit('ERROR uploading %s' % file)
            fp.close() 

    reply, msg, headers = conn.getreply() 

    if reply != 200:
        print >>sys.stderr, 'Error: can\'t %s \'%s\'' % (method, url)
        print >>sys.stderr, 'reply:', reply
        print >>sys.stderr, '\nDebugging output follows.\nurl:\n%s\nheaders:\n%s\nresponse:\n%s' % (url, headers, msg)

    #print ''.join(conn.file.read())


def delfile(url, file, username, password):
    return request('DELETE', url, username, password, file=file)


def putfile(url, username, password, file=None, strbuf=None):
    return request('PUT', url, username, password, file=file, strbuf=strbuf)


