import pytest
from ziko.access import require_operator

def test_rejects_untrusted_peer_even_with_spoofed_forwarded_headers():
    with pytest.raises(PermissionError): require_operator('127.0.0.1', 'owner', 'owner')

def test_unconfigured_operator_cannot_chat_or_import():
    with pytest.raises(PermissionError): require_operator('172.30.32.2', 'owner', '')

def test_different_user_is_denied():
    with pytest.raises(PermissionError): require_operator('172.30.32.2', 'other', 'owner')
    with pytest.raises(PermissionError): require_operator('172.30.32.2', None, 'owner')

def test_operator_allowed():
    require_operator('172.30.32.2', 'owner', 'owner')
