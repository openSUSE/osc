import oauth
import urlparse
import urllib2
import sys

class OAuthHandler(urllib2.BaseHandler):
    def __init__(self, password_mgr = None):
        if password_mgr is None:
            password_mgr = urllib2.HTTPPasswordMgr()
        self.passwd = password_mgr
        self.add_password = self.passwd.add_password

    def http_error_401(self, req, fp, code, msg, headers):
        # XXX: desktop clients etc. won't have a consumer token + secret => unknown + unknown will be used
        auth_req = headers.get('www-authenticate', None)
        scheme = None
        if auth_req:
            mo = urllib2.AbstractBasicAuthHandler.rx.search(auth_req)
            if mo:
                scheme = mo.groups()[0]
        if not auth_req or scheme != 'oauth':
            return None
        # default consumer key + secret for desktop clients
        consumer = oauth.OAuthConsumer('desktop', 'desktop')
        atoken, secret = self.passwd.find_user_password(None, req.get_full_url())
        token = oauth.OAuthToken(atoken, secret)
        query = dict(urlparse.parse_qsl(urlparse.urlsplit(req.get_full_url())[3]))
        if query.has_key('oauth_token') or req.headers.get('Authorization', '').startswith('OAuth'):
            return None
        # XXX: pass the full url - it'll be converted by the oauth module
        oauthreq = oauth.OAuthRequest.from_consumer_and_token(consumer, token=token,
             http_method=req.get_method(), http_url=req.get_full_url(), parameters=query)
        print consumer, token
        oauthreq.sign_request(oauth.OAuthSignatureMethod_HMAC_SHA1(), consumer, token)
        req.add_header(*oauthreq.to_header().items()[0])
        return self.parent.open(req)

    def get_handler(config, password_mgr = None):
        return OAuthHandler(password_mgr)
    get_handler = staticmethod(get_handler)
