import hmac

INGRESS_IP = '172.30.32.2'
USER_HEADER = 'X-Remote-User-Id'

def require_operator(peer_ip: str, forwarded_user_id: str | None, configured_user_id: str) -> None:
    if peer_ip != INGRESS_IP or not forwarded_user_id or not configured_user_id:
        raise PermissionError('Hozzáférés megtagadva')
    if not hmac.compare_digest(forwarded_user_id, configured_user_id):
        raise PermissionError('Hozzáférés megtagadva')
