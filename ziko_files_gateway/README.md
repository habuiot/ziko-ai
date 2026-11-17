# ZikoFiles Home Assistant Ingress gateway v0.1
This is a private transport gateway to the separate ZikoFiles file manager on Proxmox CT104.
It does not implement project management.
The Home Assistant Supervisor authenticates the HA user; only traffic from 172.30.32.2 with X-Remote-User-Id is accepted.
There is no published host port, HA API token, privileged mount or root access.
The connection to CT104 (192.168.10.100:8787) validates its self-signed TLS certificate and exact SHA-256 fingerprint.
The backend retains its own password/session and mount-based read/write authorization; SSO is NOT implemented.
A certificate change requires an update of backend.crt and its SHA-256 pin.
This add-on must not be considered complete without a real HA browser test and permission audit.
Test with python3 -m unittest test_gateway.py -v.
