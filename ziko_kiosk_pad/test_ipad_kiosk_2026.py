import sys, os, json, threading, tempfile, http.client, datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import secure
from http.server import ThreadingHTTPServer

LOCK="lock.eloszoba_bejarati_ajto_also_zar"
DOOR="binary_sensor.ewelink_snzb_04p_contact"
GUARD="automation.haziko_kulcs_belepes_ajtofigyeles_es_automatikus_visszazaras"
TIMER="timer.haziko_kulcs_belepesi_idoablak"
PHASE="input_select.haziko_kulcs_belepesi_folyamat"
class FakeHA:
    def __init__(self):
        self.state={DOOR:"off",LOCK:"locked",GUARD:"on",TIMER:"idle",PHASE:"nyugalmi"}
        self.calls=[]
    def states(self):
        return [{"entity_id":k,"state":v,"attributes":{}} for k,v in self.state.items()]
    def request(self,url):
        if url.startswith("/states/"):return {"state":self.state.get(url[len("/states/"):],"unknown")}
        raise RuntimeError("Unexpected request")
    def service(self,domain,action,entity_id):
        self.calls.append((domain,action,entity_id))
        if domain=="lock" and entity_id==LOCK:
            self.state[LOCK]="unlocked" if action=="unlock" else "locked"
class FakeBridge:
    def __init__(self):
        self.ha=FakeHA();self.last_read=42
bridge=FakeBridge()
s=secure.Security.__new__(secure.Security)
s.bridge=bridge
s.unlock_mutex=threading.Lock()
s.last_swipe_unlock={}
s.swipe_without_pin=lambda: True
s.identity=lambda cookie,ip=None: "KIOSK-01" if cookie=="zkp_tls=FAKE-NONSECRET" else None
s.data=Path(tempfile.mkdtemp(prefix="ziko-kiosk-test-"))
def expect(label,condition):
    if not condition:raise AssertionError(label)
    print("PASS",label)
code,snap=s.ipad_entry_state()
expect("fresh-state-lock",code==200 and snap["lock"]=="locked" and snap["door"]=="off" and snap["guard"]=="on")
code,reply=s.ipad_entry_action("KIOSK-02","127.0.0.1","unlock","hold")
expect("deny-wrong-pad",code==403 and not bridge.ha.calls)
code,reply=s.ipad_entry_action("KIOSK-01","127.0.0.1","unlock","tap")
expect("deny-wrong-gesture",code==403 and not bridge.ha.calls)
bridge.ha.state[DOOR]="on"
code,reply=s.ipad_entry_action("KIOSK-01","127.0.0.1","unlock","hold")
expect("deny-door-open",code==423 and not bridge.ha.calls)
bridge.ha.state[DOOR]="unknown"
code,reply=s.ipad_entry_action("KIOSK-01","127.0.0.1","lock","tap")
expect("deny-door-unknown",code==423 and not bridge.ha.calls)
bridge.ha.state[DOOR]="off"
bridge.ha.state[GUARD]="off"
code,reply=s.ipad_entry_action("KIOSK-01","127.0.0.1","unlock","hold")
expect("deny-guard-off",code==423 and not bridge.ha.calls)
bridge.ha.state[GUARD]="on"
bridge.ha.state[TIMER]="unknown"
code,reply=s.ipad_entry_action("KIOSK-01","127.0.0.1","unlock","hold")
expect("deny-timer-unknown",code==423 and not bridge.ha.calls)
bridge.ha.state[TIMER]="idle"
code,reply=s.ipad_entry_action("KIOSK-01","127.0.0.1","unlock","hold")
expect("safe-mock-hold-unlock",code==200 and bridge.ha.calls==[("lock","unlock",LOCK)] and bridge.ha.state[LOCK]=="unlocked")
code,reply=s.ipad_entry_action("KIOSK-01","127.0.0.1","lock","hold")
expect("deny-lock-with-hold",code==403 and len(bridge.ha.calls)==1)
code,reply=s.ipad_entry_action("KIOSK-01","127.0.0.1","lock","tap")
expect("safe-mock-tap-lock",code==200 and bridge.ha.calls[-1]==("lock","lock",LOCK) and bridge.ha.state[LOCK]=="locked")
code,reply=s.ipad_entry_action("KIOSK-01","127.0.0.1","lock","tap")
expect("already-locked-no-new-command",code==200 and len(bridge.ha.calls)==2)
s.bridge.ha.state.pop(DOOR)
code,reply=s.ipad_entry_action("KIOSK-01","127.0.0.1","unlock","hold")
expect("failclosed-missing-contact",code==423 and len(bridge.ha.calls)==2)
s.bridge.ha.state[DOOR]="off"
s.swipe_without_pin=lambda: False
code,reply=s.ipad_entry_action("KIOSK-01","127.0.0.1","unlock","hold")
expect("failclosed-pin-mode",code==423 and len(bridge.ha.calls)==2)
s.swipe_without_pin=lambda: True
server=ThreadingHTTPServer(("127.0.0.1",0),secure.secure_handler(s,b"old"))
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
def req(method,path,body=None,headers=None):
    c=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=5)
    c.request(method,path,body=body,headers=headers or {})
    r=c.getresponse();raw=r.read();ct=r.getheader("Content-Type")
    c.close();return r.status,raw,ct
code,body,ct=req("GET","/kiosk-2026")
expect("new-route-html",code==200 and b"ZIKO KIOSK" in body and len(body)>10000)
code,body,ct=req("GET","/api/entry")
expect("entry-anonymous-401",code==401)
code,body,ct=req("GET","/api/entry",headers={"Cookie":"zkp_tls=FAKE-NONSECRET"})
expect("entry-paired-readonly-200",code==200 and json.loads(body)["lock"]=="locked")
code,body,ct=req("POST","/api/entry",body=b'{"action":"unlock","confirm":"hold"}',headers={"Content-Type":"application/json","Cookie":"zkp_tls=FAKE-NONSECRET"})
expect("csrf-reject-without-custom-header",code==403 and len(bridge.ha.calls)==2)
server.shutdown();server.server_close()
print("MOCK_TESTS_PASS 15+ / 0 REAL HA COMMANDS")
