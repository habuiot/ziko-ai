#!/usr/bin/env python3
"""Run on the same computer as the browser. Never run in HA Terminal & SSH."""
import argparse
import asyncio
import hmac
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sys
import threading
from urllib.parse import parse_qs, urlsplit
import webbrowser

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ziko_ai'/'src'))
import httpx
from ziko.credentials import CredentialStore, atomic_json
from ziko.oauth import begin_login, complete_login

def save_registration(directory: Path,record: dict):
    atomic_json(directory/'registration.json',{k:record[k] for k in ('client_id','subject','id_token')})

def load_registration(directory: Path):
    path=directory/'registration.json'
    if not path.exists():return None
    record=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(record,dict) or not isinstance(record.get('client_id'),str) or not record['client_id'].startswith('oaiapp_'):
        raise ValueError('Hibás helyi regisztráció')
    if any(not isinstance(record.get(k),str) or not record[k] for k in ('subject','id_token')):
        raise ValueError('Hiányos helyi regisztráció')
    return record

def main():
    parser=argparse.ArgumentParser(description='Ziko AI bejelentkező segéd. Ugyanazon számítógépen fusson, mint a böngésző; a távoli HA-terminál nem megfelelő.')
    parser.add_argument('--output',type=Path,help='Védett kapcsolati fájl helye; alapértelmezés: a saját profil ziko-login könyvtára')
    parser.add_argument('--state-dir',type=Path,default=Path.home()/'.config/ziko-login',help='A segéd helyi hostazonosítója')
    args=parser.parse_args()
    args.output=args.output or args.state_dir/'ziko-connection.json'
    if args.output.exists():
        print('A kimeneti fájl már létezik. Töröld az előző import után, vagy válassz másik --output fájlnevet.',file=sys.stderr)
        return 1
    store=CredentialStore(args.state_dir)
    try:registration=load_registration(args.state_dir)
    except (ValueError,OSError):
        print('A helyi regisztráció nem olvasható. Használj új saját --state-dir könyvtárat.',file=sys.stderr)
        return 1
    callback={};done=threading.Event();pending=None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            url=urlsplit(self.path)
            expected_host=f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host')!=expected_host or url.path!='/auth/callback' or url.netloc:
                self.send_error(404);return
            try:
                query=parse_qs(url.query,max_num_fields=20)
                if any(len(v)!=1 for v in query.values()):raise ValueError()
                received={k:v[0] for k,v in query.items()}
                if not hmac.compare_digest(received.get('state',''),pending.state) or done.is_set():raise ValueError()
            except ValueError:
                self.send_response(400);self.end_headers();self.wfile.write(b'Invalid sign-in attempt.');return
            callback.update(received)
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.end_headers()
            self.wfile.write('<!doctype html><html lang="hu"><meta charset="utf-8"><title>Ziko AI</title><h1>Ziko AI</h1><p>A böngészős lépés lezárult. Térj vissza a bejelentkező segédhez az ellenőrzés eredményéért.</p></html>'.encode())
            done.set()

    server=HTTPServer(('127.0.0.1',0),Handler)
    server.timeout=1
    pending=begin_login(store.host_id(),server.server_port,registration)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        print('Ziko AI: megnyitom a helyi böngészőt. Válaszd ki a saját fiókodat és engedélyezd a ChatGPT-plan használatát.')
        if not webbrowser.open(pending.url):raise ValueError('Nem sikerült megnyitni a helyi böngészőt. Ezt a segédet böngészővel rendelkező számítógépen indítsd.')
        if not done.wait(600):raise ValueError('A bejelentkezés időkorlátja lejárt. Indítsd újra a segédet.')
        async def exchange():
            async with httpx.AsyncClient(timeout=30,follow_redirects=False) as client:
                return await complete_login(pending,callback,client)
        record=asyncio.run(exchange())
        if args.output.exists():raise ValueError('A kimeneti fájl már létezik. Válassz új --output fájlnevet.')
        atomic_json(args.output.resolve(),record)
        save_registration(args.state_dir,record)
        print('Bejelentkezés ellenőrizve. A kapcsolati fájl elkészült: '+str(args.output.resolve()))
        print('Importáld a Ziko HA-felületén. Import után a HA kezeli a frissítést. A kapcsolati fájlt töröld a számítógépről és a telefonról; ne küldd chatbe.')
        return 0
    except (ValueError,httpx.HTTPError):
        print('A bejelentkezés nem fejeződött be. Ellenőrizd, hogy a böngésző és a segéd ugyanazon számítógépen fut-e, illetve engedélyezted-e a ChatGPT-plan használatát. Új próbához indítsd újra a segédet.',file=sys.stderr)
        return 1
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)

if __name__=='__main__':raise SystemExit(main())
