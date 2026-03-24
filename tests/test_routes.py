def test_index_returns_200(client):
    response = client.get('/')
    assert response.status_code == 200


def test_stats_returns_json(client):
    response = client.get('/stats')
    assert response.status_code == 200
    data = response.get_json()
    assert 'connection_count' in data
    assert 'topic_count' in data
    assert 'message_count' in data
    assert 'errors' in data


def test_version_returns_json(client):
    response = client.get('/version')
    assert response.status_code == 200
    data = response.get_json()
    assert 'version' in data


def test_api_messages_returns_json(client):
    response = client.get('/api/messages')
    assert response.status_code == 200
    data = response.get_json()
    assert 'messages' in data


def test_api_topics_returns_json(client):
    response = client.get('/api/topics')
    assert response.status_code == 200
    data = response.get_json()
    assert 'topics' in data


def test_database_stats(client):
    response = client.get('/api/database/stats')
    assert response.status_code == 200
    data = response.get_json()
    assert 'enabled' in data
