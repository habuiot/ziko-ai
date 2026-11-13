"""Read-only ZIKO-branded access portal served through Home Assistant Ingress.

All project records are supplied by the server-side ACL. Nothing about the
current user or project role is trusted from a browser parameter.
"""
from __future__ import annotations

from html import escape
from typing import Sequence, Mapping

ROLE_LABELS = {
    "viewer": ("Megtekintő", "view"),
    "editor": ("Szerkesztő", "edit"),
    "manager": ("Projektkezelő", "manage"),
}


def dashboard(name: str, projects: Sequence[Mapping] | None = None,
              user_id: str = "") -> bytes:
    safe_name = escape(name or "Házikó-felhasználó", quote=True)
    safe_id = escape(user_id, quote=True)
    records = list(projects or [])
    project_markup = []
    for project in records:
        role_label, tone = ROLE_LABELS.get(project.get("role"), ("Ismeretlen", "view"))
        title = escape(str(project.get("title", "")), quote=True)
        slug = escape(str(project.get("slug", "")), quote=True)
        project_markup.append(
            f'<article class="project"><div class="project-icon" aria-hidden="true">◈</div>'
            f'<div><div class="project-name">{title}</div>'
            f'<div class="project-id">{slug}</div></div>'
            f'<span class="role {tone}">{role_label}</span></article>'
        )

    if not project_markup:
        project_html = """<div class="empty">
          <div class="empty-icon" aria-hidden="true">◈</div>
          <h3>Még nincs hozzárendelt projekt</h3>
          <p>Hozzáférést egy ZIKO projektkezelő adhat. A meglévő
          ZikoTodo feladatlistáid ettől függetlenül használhatók a Házikóban.</p>
          </div>"""
    else:
        project_html = "".join(project_markup)

    page = """<!doctype html>
<html lang="hu"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0b1320">
<title>Ziko™ ● Todo · Hozzáférések</title>
<style>
:root{color-scheme:dark;--background:#0b1320;--card:#122336;
--stroke:#28445b;--text:#e5f5fa;--muted:#8faabd;--cyan:#8ceafa}
*{box-sizing:border-box}
body{margin:0;padding:clamp(12px,3vw,34px);font-family:Inter,
system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--text);
background:radial-gradient(ellipse at 10% 0%,#15344a 0%,transparent 48%),
radial-gradient(ellipse at 100% 80%,#201b35 0%,transparent 48%),var(--background)}
main{max-width:1000px;margin:0 auto}
header{display:flex;justify-content:space-between;gap:15px;align-items:center;
border-bottom:1px solid #29465c;padding:0 0 16px;flex-wrap:wrap}
.eyebrow{font-size:10px;text-transform:uppercase;letter-spacing:2px;color:#85cbdd;
font-weight:800}
h1{font-size:clamp(25px,4vw,40px);line-height:1.08;letter-spacing:-1px;
margin:7px 0 3px}
h1 b{background:linear-gradient(95deg,#83e9f7,#bdaaff);background-clip:text;
-webkit-background-clip:text;color:transparent}
.sub{font-size:12px;color:var(--muted)}
.session{display:flex;gap:8px;align-items:center;border:1px solid #317669;
border-radius:8px;padding:9px 11px;background:#102a2a;color:#9cf4d0;font-size:11px;
white-space:nowrap}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;
background:#69e4b5}
.kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;
margin:20px 0}
.stat{padding:15px;border:1px solid var(--stroke);border-radius:12px;
background:linear-gradient(145deg,#172b3d,#101d2d)}
.stat strong{display:block;font-size:28px;letter-spacing:-.8px;color:#b5f1fc}
.stat small{display:block;color:var(--muted);font-size:11px;margin-top:4px}
.stat.privacy strong{font-size:15px;letter-spacing:0;color:#a6efc3;margin-top:9px}
section{border:1px solid var(--stroke);border-radius:13px;background:#101e2c;
padding:clamp(14px,2vw,21px);margin:12px 0}
.section-top{display:flex;align-items:center;gap:10px;flex-wrap:wrap;
justify-content:space-between;margin:0 0 15px}
h2{margin:0;font-size:17px;letter-spacing:-.25px}
.section-top p{color:var(--muted);margin:0;font-size:11px}
.project{display:flex;align-items:center;gap:12px;padding:13px 12px;margin-top:8px;
border-radius:10px;border:1px solid #345269;background:#182d41;min-width:0}
.project-icon{font-size:23px;color:#8de5f6;flex:0 0 26px}
.project>div:nth-child(2){min-width:0;flex:1}
.project-name{font-size:13px;font-weight:800;overflow-wrap:anywhere}
.project-id{font-size:10px;color:#90acbc;overflow-wrap:anywhere;margin-top:4px}
.role{display:inline-flex;padding:6px 8px;white-space:nowrap;font-size:10px;
font-weight:750;border-radius:7px;border:1px solid #345b72;background:#193b52;color:#8de5f4}
.role.edit{background:#343226;border-color:#706547;color:#f5d99b}
.role.manage{background:#2c2745;border-color:#514978;color:#d0c2ff}
.empty{text-align:center;padding:25px 13px;border:1px dashed #39536a;
border-radius:10px;color:#b6cedb;background:#122436}
.empty-icon{font-size:28px;color:#6dacc3}
.empty h3{font-size:15px;margin:9px 0}
.empty p{font-size:12px;line-height:1.6;color:var(--muted);max-width:410px;margin:auto}
.person{display:grid;grid-template-columns:auto 1fr;gap:12px;align-items:center}
.avatar{height:44px;width:44px;display:flex;align-items:center;
justify-content:center;border:1px solid #368ba7;border-radius:12px;
background:#1a465a;color:#a4f2fa;font-size:21px}
.user-name{font-size:14px;font-weight:800;overflow-wrap:anywhere}
.user-id{font-size:10px;color:#91b0c2;overflow-wrap:anywhere;margin-top:5px}
footer{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;
border-top:1px solid #29465c;margin-top:18px;padding-top:13px;
color:#7798ad;font-size:10px;line-height:1.5}
@media(max-width:600px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
.stat.privacy{grid-column:span 2}.stat strong{font-size:25px}
.session{font-size:10px}.project{padding:10px 9px;gap:8px}}
</style></head>
<body><main>
<header><div><div class="eyebrow">ZIKO TECHNOLOGY / WORKSPACE SECURITY</div>
<h1>Ziko™ <b>● Todo</b></h1>
<div class="sub">Hozzáférések · projektek · saját munkaterület</div></div>
<div class="session"><span class="dot"></span> Házikó-hitelesítés aktív</div></header>
<div class="kpis">
<div class="stat"><strong>__COUNT__</strong><small>Hozzárendelt projekt</small></div>
<div class="stat"><strong>3</strong><small>Jogosultsági szint</small></div>
<div class="stat privacy"><strong>◉ Saját hozzáférés</strong>
<small>Mások privát projektjei nem jelennek meg</small></div>
</div>
<section><div class="section-top"><h2>◈ Saját projektjeim</h2>
<p>Megtekintő · Szerkesztő · Projektkezelő</p></div>
__PROJECTS__</section>
<section><div class="section-top"><h2>◉ Belépési adatok</h2>
<p>Home Assistant Ingress</p></div>
<div class="person"><div class="avatar" aria-hidden="true">◉</div>
<div><div class="user-name">__NAME__</div>
<div class="user-id">Házikó-azonosító: __USERID__</div></div></div>
</section>
<footer><span>ZIKO belső kapcsolat · nincs külön Vikunja-bejelentkezés</span>
<span>Projektadatok: helyi ACL · Vikunja-feladatkapcsolat fejlesztés alatt</span></footer>
</main></body></html>"""

    page = (page.replace("__NAME__", safe_name)
                .replace("__USERID__", safe_id)
                .replace("__COUNT__", str(len(records)))
                .replace("__PROJECTS__", project_html))
    return page.encode("utf-8")
