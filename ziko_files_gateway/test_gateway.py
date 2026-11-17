import unittest
from email.message import Message
import gateway

def headers(**kw):
    h = Message()
    for key, val in kw.items():
        h[key.replace('_', '-')] = val
    return h

class PolicyTests(unittest.TestCase):
    def test_valid_and_invalid_peer(self):
        h = headers(X_Remote_User_Id='ha-user')
        self.assertTrue(gateway.ingress_identity('172.30.32.2', h))
        self.assertFalse(gateway.ingress_identity('127.0.0.1', h))
        self.assertFalse(gateway.ingress_identity('172.30.32.2', headers()))
    def test_invalid_identifiers(self):
        for uid in ('', 'a\nb', 'a\tb', 'x'*129):
            self.assertFalse(gateway.ingress_identity('172.30.32.2', headers(X_Remote_User_Id=uid)))
    def test_prefix(self):
        self.assertEqual(gateway.ingress_prefix(headers(X_Ingress_Path='/api/hassio_ingress/TOKEN123456/')), '/api/hassio_ingress/TOKEN123456/')
        self.assertIsNone(gateway.ingress_prefix(headers(X_Ingress_Path='/evil')))
    def test_path_security(self):
        for good in ('/', '/api/me', '/static/app.js'):
            self.assertTrue(gateway.allowed_upstream_path(good))
        for bad in ('//evil','/evil','/api/../secret','/api/%2e%2e/secret','/api/%5csecret'):
            self.assertFalse(gateway.allowed_upstream_path(bad))
    def test_cookie_scope(self):
        src = 'ziko_session=a.b.c; HttpOnly; Secure; SameSite=None; Partitioned; Path=/; Max-Age=43200'
        out = gateway.rewritten_cookie(src, '/api/hassio_ingress/TOKEN123456/', True)
        self.assertIn('Path=/api/hassio_ingress/TOKEN123456/', out)
        self.assertIn('SameSite=Lax', out)
        self.assertNotIn('Partitioned', out)
        self.assertNotIn('Secure', gateway.rewritten_cookie(src, '/api/hassio_ingress/TOKEN123456/', False))
        self.assertIsNone(gateway.rewritten_cookie('other=1', '/', True))

if __name__ == '__main__':
    unittest.main()
