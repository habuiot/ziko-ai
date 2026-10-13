import asyncio
import pytest
from ziko.storage import Storage
from ziko.chat import ChatService

async def completed(*args):
    yield dict(type='delta',text='Szia, Mesterem!')
    yield dict(type='completed')

async def test_success_saved_only_after_completed(tmp_path):
    s=Storage(tmp_path/'db');cid=s.create_conversation();chat=ChatService(s,completed)
    run=chat.begin(cid,'Szia','model');out=[e async for e in chat.events(run)]
    assert out[-1]['type']=='completed';assert s.messages(cid)[-1]['status']=='completed'

async def test_partial_reply_not_saved_as_completed(tmp_path):
    async def bad(*args):
        yield dict(type='delta',text='rész');yield dict(type='failed',code='limit',message='Keret elfogyott')
    s=Storage(tmp_path/'db');cid=s.create_conversation();chat=ChatService(s,bad)
    run=chat.begin(cid,'Szia','model');out=[e async for e in chat.events(run)]
    assert out[-1]['type']=='failed';assert s.messages(cid)[-1]['text']=='rész'
    assert s.context(cid)==[]

async def test_concurrent_request_returns_busy(tmp_path):
    gate=asyncio.Event()
    async def waiting(*args):
        await gate.wait();yield dict(type='completed')
    s=Storage(tmp_path/'db');cid=s.create_conversation();chat=ChatService(s,waiting)
    run=chat.begin(cid,'Első','m')
    with pytest.raises(ValueError,match='folyamatban'):chat.begin(cid,'Második','m')
    gate.set();await chat.task

async def test_model_cannot_create_persistent_memory(tmp_path):
    async def reply(*args):
        yield dict(type='delta',text='Ezt megjegyzem: zöld a szobád.');yield dict(type='completed')
    s=Storage(tmp_path/'db');cid=s.create_conversation();chat=ChatService(s,reply)
    run=chat.begin(cid,'Szia','m');await chat.task
    assert s.memories()==[]

async def test_cancel_closes_request_and_marks_cancelled(tmp_path):
    started=asyncio.Event();closed=asyncio.Event()
    async def waiting(*args):
        try:
            started.set();yield dict(type='delta',text='rész');await asyncio.Event().wait()
        finally:closed.set()
    s=Storage(tmp_path/'db');cid=s.create_conversation();chat=ChatService(s,waiting)
    run=chat.begin(cid,'Szia','m');await started.wait();await chat.cancel(run.request_id)
    assert closed.is_set();assert s.messages(cid)[-1]['status']=='cancelled'
    assert not chat.busy

async def test_cancel_before_worker_starts_is_persisted(tmp_path):
    s=Storage(tmp_path/'db');cid=s.create_conversation();chat=ChatService(s,completed)
    run=chat.begin(cid,'Szia','m')
    await chat.cancel(run.request_id)
    assert s.messages(cid)[-1]['status']=='cancelled'
    assert not chat.busy

async def test_completed_provider_is_closed_before_terminal(tmp_path):
    closed=asyncio.Event()
    async def provider(*args):
        try:yield dict(type='completed')
        finally:closed.set()
    s=Storage(tmp_path/'db');cid=s.create_conversation();chat=ChatService(s,provider)
    run=chat.begin(cid,'Szia','m');await chat.task
    assert closed.is_set()
