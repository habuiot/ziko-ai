import http.client
import json
import tempfile
import shutil
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
import importlib.util

SOURCE = Path(__file__).resolve().parents[1] / 'app.py'
spec = importlib.util.spec_from_file_location('zkp', SOURCE)
zkp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zkp)

class FakeHa:
    def __init__(self):
        self.calls=[]
    def states(self):
        return [dict(entity_id=e,state=('locked' if e.startswith('lock.') else 'on'),attributes={'brightness':120}) for e,n in zkp.VISIBLE]
    def service(self,domain,action,entity_id):
        self.calls.append((domain,action,entity_id))

class TestBridge(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.fake=FakeHa()
        self.bridge=zkp.Bridge(data_dir=self.tmp.name,ha=self.fake)
        self.http=ThreadingHTTPServer(('127.0.0.1',0),zkp.make_handler(self.bridge))
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.cookie=None
    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join(timeout=2);self.tmp.cleanup()
    def req(self,method,path,body=None,headers=None):
        h={'X-ZIKO-Request':'1'};h.update(headers or {})
        if self.cookie:h['Cookie']=self.cookie
        if body is not None:h['Content-Type']='application/json'
        c=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=3)
        c.request(method,path,json.dumps(body).encode() if body is not None else None,h)
        r=c.getresponse();d=json.loads(r.read().decode()) if path!='/index.html' else {}
        ck=r.getheader('Set-Cookie');status=r.status;c.close()
        if ck:self.cookie=ck.split(';')[0]
        return status,d
    def pair(self):
        return self.req('POST','/api/pair',{'code':self.bridge.pairing_code,'pad':'KIOSK-01'})
    def test_requires_pairing(self):
        self.assertEqual(self.req('GET','/api/state')[0],401)
        self.assertEqual(self.req('POST','/api/command',{'id':zkp.LIGHTS[0][0],'action':'on'})[0],401)
    def test_pair_and_read_real_allowlist(self):
        self.assertEqual(self.pair()[0],200)
        code,data=self.req('GET','/api/state');self.assertEqual(code,200)
        self.assertEqual(len(data['items']['lights']),5)
        self.assertEqual(len(data['items']['contacts']),8)
        self.assertEqual(data['items']['locks'][0]['state'],'locked')
        self.assertTrue(all('token' not in str(x) for x in data['items']))
    def test_actions_are_restricted(self):
        self.pair()
        self.assertEqual(self.req('POST','/api/command',{'id':'lock.eloszoba_bejarati_ajto_also_zar','action':'unlock'})[0],403)
        self.assertEqual(self.req('POST','/api/command',{'id':zkp.LIGHTS[0][0],'action':'on'})[0],200)
        self.assertEqual(self.fake.calls[-1],('light','turn_on',zkp.LIGHTS[0][0]))
        self.assertEqual(self.req('POST','/api/command',{'id':zkp.MEDIA[0][0],'action':'play_pause'})[0],200)
        self.assertEqual(self.fake.calls[-1],('media_player','media_play_pause',zkp.MEDIA[0][0]))
    def test_csrf_defense(self):
        self.pair()
        self.assertEqual(self.req('POST','/api/command',{'id':zkp.LIGHTS[0][0],'action':'off'}, {'Origin':'http://evil.example'})[0],403)
        self.assertEqual(self.req('POST','/api/command',{'id':zkp.LIGHTS[0][0],'action':'off'}, {'X-ZIKO-Request':'no'})[0],403)
    def test_pair_code_wrong(self):
        self.assertEqual(self.req('POST','/api/pair',{'code':'00000000' if self.bridge.pairing_code != '00000000' else '11111111','pad':'KIOSK-02'})[0],403)
    def test_unlock_swipe_requires_pairing(self):
        self.assertEqual(self.req('POST', '/api/unlock', {'confirm': 'slide'})[0], 401)
    def test_unlock_does_not_operate_hardware(self):
        self.pair()
        status, payload = self.req('POST', '/api/unlock', {'confirm': 'slide'})
        self.assertEqual(status, 423)
        self.assertEqual(self.fake.calls, [])
    def test_session_survives_bridge_restart(self):
        self.pair()
        b=zkp.Bridge(data_dir=self.tmp.name,ha=self.fake)
        self.assertEqual(b.authenticate(self.cookie),'KIOSK-01')


# Security tests: use a fake lock so NO physical door is opened during CI.
SECURE_SOURCE = Path(__file__).resolve().parents[1] / 'secure.py'
sec_spec = importlib.util.spec_from_file_location('ziko_secure', SECURE_SOURCE)
secure = importlib.util.module_from_spec(sec_spec)
sec_spec.loader.exec_module(secure)


class FakeLockHa(FakeHa):
    def __init__(self):
        super().__init__()
        self.lock_state = 'locked'

    def request(self, path):
        if path != '/states/' + secure.LOCK_ENTITY:
            raise AssertionError('Unexpected HA API path: ' + path)
        return {'state': self.lock_state}

    def service(self, domain, action, entity_id):
        super().service(domain, action, entity_id)
        if (domain, action, entity_id) == ('lock', 'unlock', secure.LOCK_ENTITY):
            self.lock_state = 'unlocked'


class TestSecureBridge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fake = FakeLockHa()
        self.bridge = zkp.Bridge(data_dir=self.tmp.name, ha=self.fake)
        self.secure = secure.Security(self.bridge)

    def tearDown(self):
        self.tmp.cleanup()

    def configure_pin(self):
        (Path(self.tmp.name) / 'options.json').write_text('{"unlock_pin":"12345678"}')

    def test_pin_disabled_until_configured(self):
        self.assertEqual(self.secure.expected_pin(), '')
        status, _ = self.secure.unlock('KIOSK-01', '127.0.0.1', '12345678')
        self.assertEqual(status, 423)
        self.assertEqual(self.fake.calls, [])

    def test_https_session_separate_from_legacy_cookie(self):
        legacy = self.bridge.pair(self.bridge.pairing_code, 'KIOSK-01', '127.0.0.1')
        self.assertIsNone(self.secure.identity('zkp_session=' + legacy))
        token = self.secure.pair(self.bridge.pairing_code, 'KIOSK-01', '127.0.0.1')
        self.assertEqual(self.secure.identity('zkp_tls=' + token), 'KIOSK-01')
        self.assertIsNone(self.bridge.authenticate('zkp_tls=' + token))

    def test_wrong_pin_never_unlocks(self):
        self.configure_pin()
        status, _ = self.secure.unlock('KIOSK-01', '127.0.0.1', '00000000')
        self.assertEqual(status, 403)
        self.assertEqual(self.fake.calls, [])

    def test_non_entry_pad_cannot_unlock_even_with_valid_pin(self):
        self.configure_pin()
        status, _ = self.secure.unlock('KIOSK-02', '127.0.0.1', '12345678')
        self.assertEqual(status, 403)
        self.assertEqual(self.fake.calls, [])

    def test_successful_pin_calls_exact_u200_service(self):
        self.configure_pin()
        status, data = self.secure.unlock('KIOSK-01', '127.0.0.1', '12345678')
        self.assertEqual(status, 200)
        self.assertTrue(data['ok'])
        self.assertEqual(self.fake.calls, [('lock', 'unlock', secure.LOCK_ENTITY)])

    def test_lock_already_unlocked_does_not_call_service(self):
        self.configure_pin()
        self.fake.lock_state = 'unlocked'
        status, _ = self.secure.unlock('KIOSK-01', '127.0.0.1', '12345678')
        self.assertEqual(status, 200)
        self.assertEqual(self.fake.calls, [])

    def test_failing_three_times_blocks_valid_pin(self):
        self.configure_pin()
        for _ in range(3):
            self.assertEqual(self.secure.unlock('KIOSK-01', '127.0.0.1', '00000000')[0], 403)
        self.assertEqual(self.secure.unlock('KIOSK-01', '127.0.0.1', '12345678')[0], 403)
        self.assertEqual(self.fake.calls, [])

    def enable_swipe_mode(self):
        (Path(self.tmp.name) / 'options.json').write_text('{"swipe_without_pin": true}')

    def test_pinless_mode_is_off_by_default(self):
        self.assertFalse(self.secure.swipe_without_pin())
        self.assertEqual(self.secure.unlock('KIOSK-01', '127.0.0.1', None)[0], 423)
        self.assertEqual(self.fake.calls, [])

    def test_paired_ip_required_in_pinless_mode(self):
        self.enable_swipe_mode()
        token = self.secure.pair(self.bridge.pairing_code, 'KIOSK-01', '192.168.10.164')
        self.assertIsNotNone(token)
        self.assertEqual(self.secure.identity('zkp_tls=' + token, '192.168.10.164'), 'KIOSK-01')
        self.assertIsNone(self.secure.identity('zkp_tls=' + token, '192.168.10.165'))

    def test_old_unbound_https_session_rejected_in_pinless_mode(self):
        token = self.secure.pair(self.bridge.pairing_code, 'KIOSK-01', '192.168.10.164')
        self.enable_swipe_mode()
        # Emulate a session from previous versions without an IP binding.
        for item in self.secure.sessions.values():
            item.pop('ip', None)
        self.assertIsNone(self.secure.identity('zkp_tls=' + token, '192.168.10.164'))

    def test_pinless_swipe_unlocks_exact_lock_with_fake_ha(self):
        self.enable_swipe_mode()
        self.assertEqual(self.secure.unlock('KIOSK-01', '127.0.0.1', None)[0], 200)
        self.assertEqual(self.fake.calls, [('lock', 'unlock', secure.LOCK_ENTITY)])

    def test_pinless_repeat_is_throttled(self):
        self.enable_swipe_mode()
        self.assertEqual(self.secure.unlock('KIOSK-01', '127.0.0.1', None)[0], 200)
        self.fake.lock_state = 'locked'
        code, _ = self.secure.unlock('KIOSK-01', '127.0.0.1', None)
        self.assertEqual(code, 429)
        self.assertEqual(len(self.fake.calls), 1)

    def test_other_terminal_blocked_in_pinless_mode(self):
        self.enable_swipe_mode()
        self.assertEqual(self.secure.unlock('KIOSK-02', '127.0.0.1', None)[0], 403)
        self.assertEqual(self.fake.calls, [])

    def test_tls_assets_valid_ca_and_profile(self):
        import os
        import plistlib
        import subprocess
        if not shutil.which('openssl'):
            self.skipTest('openssl not installed')
        assets = secure.tls_assets(self.tmp.name)
        profile = plistlib.loads(assets['profile'])
        self.assertEqual(profile['PayloadType'], 'Configuration')
        self.assertTrue(assets['ca_sha256'])
        tls = Path(self.tmp.name) / 'tls'
        subprocess.run(['openssl', 'verify', '-CAfile', str(tls / 'ca.pem'), str(tls / 'server.pem')],
                       check=True, stdout=subprocess.DEVNULL)


if __name__ == '__main__': unittest.main()
