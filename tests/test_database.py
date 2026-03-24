from datetime import datetime


def test_wal_mode(test_db):
    conn = test_db.get_connection()
    mode = conn.execute('PRAGMA journal_mode').fetchone()[0]
    assert mode == 'wal'


def test_busy_timeout(test_db):
    conn = test_db.get_connection()
    timeout = conn.execute('PRAGMA busy_timeout').fetchone()[0]
    assert timeout == 5000


def test_store_and_retrieve(test_db):
    now = datetime.now()
    test_db.store_message(
        topic='test/topic',
        payload='hello world',
        timestamp=now,
        qos=0,
        retain=False
    )
    messages = test_db.get_messages(limit=10)
    assert len(messages) >= 1
    assert messages[0]['topic'] == 'test/topic'
    assert messages[0]['payload'] == 'hello world'


def test_get_topics(test_db):
    test_db.store_message(topic='sensor/temp', payload='22.5', timestamp=datetime.now())
    test_db.store_message(topic='sensor/humidity', payload='45', timestamp=datetime.now())
    topics = test_db.get_topics()
    topic_names = [t['topic'] for t in topics]
    assert 'sensor/temp' in topic_names
    assert 'sensor/humidity' in topic_names


def test_message_count(test_db):
    for i in range(5):
        test_db.store_message(topic='count/test', payload=str(i), timestamp=datetime.now())
    count = test_db.get_message_count(topic_filter='count/test')
    assert count == 5
