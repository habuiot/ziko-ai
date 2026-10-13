import pytest
from ziko.scope import approved_devices


def test_public_source_has_no_house_device_defaults(monkeypatch):
    monkeypatch.delenv('ZIKO_APPROVED_DEVICE_IDS',raising=False)
    assert approved_devices()==frozenset()


def test_scope_comes_only_from_local_configuration(monkeypatch):
    allowed='a'*32
    monkeypatch.setenv('ZIKO_APPROVED_DEVICE_IDS','["'+allowed+'"]')
    assert approved_devices()==frozenset({allowed})


@pytest.mark.parametrize('value',['bad','{}','[null]','["*"]','["no"]'])
def test_invalid_scope_fails_closed(monkeypatch,value):
    monkeypatch.setenv('ZIKO_APPROVED_DEVICE_IDS',value)
    with pytest.raises(ValueError):approved_devices()
