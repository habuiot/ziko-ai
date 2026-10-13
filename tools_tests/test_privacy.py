from test_query import module


def test_nested_credentials_and_bearer_tokens_are_masked():
    p = module('privacy')
    result = p.sanitize({'password': 'secret-value', 'message': 'Authorization: Bearer abc.def.ghi',
                         'safe': {'temperature': 27, 'access_token': 'tok-value'}})
    assert 'secret-value' not in str(result)
    assert 'abc.def.ghi' not in str(result)
    assert 'tok-value' not in str(result)
    assert result['safe']['temperature'] == 27


def test_trace_summary_omits_variables_config_and_context():
    p = module('privacy')
    raw = {'run_id': 'run', 'state': 'stopped', 'config': {'secret': 'private'},
           'context': {'user_id': 'owner'},
           'trace': {'action/0': [{'path': 'action/0', 'changed_variables': {'private': 'value'},
                                   'timestamp': '2026-10-12T00:00:00Z', 'result': {'result': True}}]}}
    result = p.trace_summary(raw)
    assert 'changed_variables' not in str(result)
    assert 'private' not in str(result)
    assert 'config' not in result and 'context' not in result
    assert result['steps'][0]['result'] == {'result': True}


def test_header_quoted_and_uri_credentials_are_masked():
    p = module('privacy')
    cases = [
        ('Authorization: Basic dXNlcjpwYXNz', 'dXNlcjpwYXNz'),
        ('Cookie: session=abc123; other=private', 'abc123'),
        ('password="multi word private" next=ok', 'word private'),
        ('mysql://username:myprivatepass@database/test', 'myprivatepass'),
    ]
    for text, secret in cases:
        assert secret not in p.sanitize(text)


def test_quoted_json_and_python_repr_secret_fields_are_masked():
    p = module('privacy')
    for message in ('{"access_token": "FAKE_PRIVATE_VALUE", "password": "FAKE_PASSWORD"}',
                    "{'refresh_token': 'FAKE_PRIVATE_VALUE', 'api_key': 'FAKE_PASSWORD'}"):
        result = p.sanitize(message)
        assert 'FAKE_PRIVATE_VALUE' not in result and 'FAKE_PASSWORD' not in result
