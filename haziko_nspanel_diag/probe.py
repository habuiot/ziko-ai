"""One-shot, allowlisted, no-credential, non-mutating network diagnostics."""
import json
import re
import socket
import time
from datetime import datetime, timezone

TARGETS = {
    "nspanel_pro_last_known": ("192.168.10.207", [80, 443, 8080]),
    "home_assistant_broker": ("192.168.10.118", [1883]),
}
TIMEOUT = 1.8


def tcp_connect(host, port):
    t0 = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT):
            return {"reachable": True, "connect_ms": round((time.monotonic() - t0) * 1000, 1)}
    except OSError as exc:
        return {"reachable": False, "reason": type(exc).__name__}


def http_identity(host, port):
    """Only non-authenticated GET /; no response body is logged, just status and title."""
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT) as sock:
            sock.settimeout(TIMEOUT)
            sock.sendall(("GET / HTTP/1.0\\r\\nHost: " + host +
                          "\\r\\nConnection: close\\r\\n\\r\\n").replace("\\r", "\r").replace("\\n", "\n").encode("ascii"))
            buf = b""
            while len(buf) < 3072:
                part = sock.recv(min(1024, 3072 - len(buf)))
                if not part:
                    break
                buf += part
            head, sep, body = buf.partition(b"\r\n\r\n")
            line = head.split(b"\r\n", 1)[0].decode("ascii", "replace")[:100]
            if not line.startswith("HTTP/"):
                return {"protocol": "not_http"}
            title = re.search(rb"<title[^>]*>([^<]{1,100})</title\s*>", body, re.I)
            return {"status_line": line, "html_title": title.group(1).decode("utf-8", "replace") if title else None}
    except OSError as exc:
        return {"error": type(exc).__name__}


def main():
    result = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "checks": []}
    for name, (ip, ports) in TARGETS.items():
        for port in ports:
            status = tcp_connect(ip, port)
            item = {"target": name, "ip": ip, "tcp_port": port, **status}
            if status.get("reachable") and name == "nspanel_pro_last_known" and port in (80, 8080):
                item["http"] = http_identity(ip, port)
            result["checks"].append(item)
    try:
        result["nspanelpro_local_dns"] = [x[4][0] for x in socket.getaddrinfo("nspanelpro.local", 80, type=socket.SOCK_STREAM)]
    except OSError as exc:
        result["nspanelpro_local_dns"] = type(exc).__name__
    print("HAZIKO_NSPANEL_DIAGNOSTIC_RESULT=" + json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
