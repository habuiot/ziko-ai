import http.client,threading,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import secure
from http.server import ThreadingHTTPServer
fake_calls=[]
class FakeHA:
 def states(self):
  return [{"entity_id":"light.awox_eglo_zm_rgb_tw","state":"off","attributes":{"brightness":200}},
          {"entity_id":"lock.eloszoba_bejarati_ajto_also_zar","state":"locked","attributes":{}},
          {"entity_id":"secret.private","state":"not_exposed","attributes":{}}]
 def request(self,p,body=None):
  fake_calls.append((p,body))
  return {"ok":True,"state":"off"}
class FakeBridge:
 ha=FakeHA()
bridge=FakeBridge()
class FakeSecurity:
 def __init__(self):
  self.bridge=bridge
 def identity(self,cookie,ip):
  return "KIOSK-01" if cookie=="zkp_tls=TEST-FAKE-NONSECRET" else None
sec=FakeSecurity()
server=ThreadingHTTPServer(("127.0.0.1",0),secure.secure_handler(sec,b"legacy"))
threading.Thread(target=server.serve_forever,daemon=True).start()
def req(method,path,data=None,headers=None):
 c=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=6)
 c.request(method,path,body=None if data is None else json.dumps(data).encode(),headers=headers or {})
 res=c.getresponse();status=res.status;body=res.read();respheaders=dict(res.getheaders());c.close();return status,body,respheaders
def check(label,condition):
 if not condition:raise AssertionError(label)
 print("PASS",label)
for path in ("/kiosk-pad","/kiosk-pad/thermostat","/kiosk-pad/lights","/kiosk-pad/vilagitasok","/kiosk-pad/attekintes"):
 status,body,heads=req("GET",path)
 check("page_"+path,status==200 and b"kiosk-pad/assets" in body and b"apple-mobile-web-app-capable" in body)
for name in ("webcomponents-bundle.js","core-js-bundle.js","dom4.js","pep.js","kiosk-thermostat-copy.es5.js","kiosk-lights-copy.es5.js","kiosk-v1.2.9.css","kiosk-lights-v1.2.15.css","pad-copy-adapter.js"):
 status,body,heads=req("GET","/kiosk-pad/assets/"+name)
 check("asset_"+name,status==200 and len(body)>1000)
status,body,_=req("GET","/api/padcopy/states")
check("states_anon_401",status==401)
cookie={"Cookie":"zkp_tls=TEST-FAKE-NONSECRET"}
status,body,_=req("GET","/api/padcopy/states",headers=cookie)
data=json.loads(body)
check("states_auth_real_whitelist",status==200 and data["states"]["light.awox_eglo_zm_rgb_tw"]["state"]=="off" and "secret.private" not in data["states"])
headers=dict(cookie,**{"X-ZIKO-Request":"1","Content-Type":"application/json","Origin":"https://127.0.0.1:%d"%server.server_port})
status,body,_=req("POST","/api/padcopy/service",{"domain":"lock","service":"unlock","data":{"entity_id":"lock.eloszoba_bejarati_ajto_also_zar"}},headers)
check("lock_general_proxy_denied",status==403 and not fake_calls)
status,body,_=req("POST","/api/padcopy/service",{"domain":"switch","service":"turn_on","data":{"entity_id":"switch.nagyszoba_fokapcsolo_1_aljzat"}},headers)
check("safe_fake_whitelisted_switch",status==200 and len(fake_calls)==1 and fake_calls[-1][0]=="/services/switch/turn_on")
status,body,_=req("POST","/api/padcopy/service",{"domain":"switch","service":"turn_on","data":{"entity_id":"switch.malicious_unknown"}},headers)
check("reject_unknown_switch",status==403 and len(fake_calls)==1)
status,body,_=req("POST","/api/padcopy/service",{"domain":"climate","service":"set_temperature","data":{"entity_id":"lock.eloszoba_bejarati_ajto_also_zar","temperature":40}},headers)
check("reject_cross_domain",status==403 and len(fake_calls)==1)
status,body,_=req("POST","/api/padcopy/service",{"domain":"light","service":"turn_on","data":{"entity_id":"light.awox_eglo_zm_rgb_tw"}},cookie)
check("reject_no_csrf_header",status==403 and len(fake_calls)==1)
status,body,_=req("GET","/api/padcopy/ha?path=states%2Flight.awox_eglo_zm_rgb_tw",headers=cookie)
check("allowed_ha_entity",status==200 and len(fake_calls)==2)
status,body,_=req("GET","/api/padcopy/ha?path=states%2Flock.eloszoba_bejarati_ajto_also_zar",headers=cookie)
check("allowed_known_lock_state",status==200)
status,body,_=req("GET","/api/padcopy/ha?path=states%2Fsecret.private",headers=cookie)
check("reject_ha_unknown",status==403)
status,body,_=req("GET","/api/padcopy/ha?path=services%2Flock%2Funlock",headers=cookie)
check("reject_ha_command",status==403)
status,body,_=req("GET","/kiosk-pad/assets/../../secure.py")
check("reject_path_traversal",status==404)
status,body,_=req("GET","/api/padcopy/states",headers={"Cookie":"zkp_tls=INVALID"})
check("invalid_cookie_401",status==401)
server.shutdown();server.server_close()
print("TOTAL_MOCK_AND_HTTP_PASS, FAKE_HA_ONLY")
