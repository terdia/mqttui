"""Tests for UX features: topic favorites/bookmarks and retained message indicator."""
import json


class TestTopicFavorites:
    """Tests for topic bookmark/favorite functionality."""

    def test_bookmark_creates_favorite(self, auth_client, app):
        """POST /api/v1/topics/<topic>/bookmark creates a favorite (201)."""
        r = auth_client.post('/api/v1/topics/home%2Fsensor/bookmark')
        assert r.status_code == 201
        data = json.loads(r.data)
        assert data['status'] == 'success'
        assert data['data']['bookmarked'] is True

    def test_bookmark_toggle_removes_favorite(self, auth_client, app):
        """POST /api/v1/topics/<topic>/bookmark again removes the favorite (200)."""
        # First call creates
        auth_client.post('/api/v1/topics/home%2Fsensor/bookmark')
        # Second call removes (toggle)
        r = auth_client.post('/api/v1/topics/home%2Fsensor/bookmark')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data['status'] == 'success'
        assert data['data']['bookmarked'] is False

    def test_get_favorites_returns_bookmarked_topics(self, auth_client, app):
        """GET /api/v1/topics/favorites returns list of bookmarked topics."""
        # Bookmark two topics
        auth_client.post('/api/v1/topics/home%2Fsensor/bookmark')
        auth_client.post('/api/v1/topics/home%2Flight/bookmark')

        r = auth_client.get('/api/v1/topics/favorites')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data['status'] == 'success'
        favorites = data['data']['favorites']
        assert len(favorites) == 2
        topics = [f['topic'] for f in favorites]
        assert 'home/sensor' in topics
        assert 'home/light' in topics

    def test_topics_includes_is_favorite(self, auth_client, app):
        """GET /api/v1/topics includes is_favorite=true for bookmarked topics."""
        # Bookmark a topic
        auth_client.post('/api/v1/topics/home%2Fsensor/bookmark')

        r = auth_client.get('/api/v1/topics')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data['status'] == 'success'
        # The topics list should have is_favorite field
        topics = data['data']['topics']
        for t in topics:
            assert 'is_favorite' in t

    def test_unauthenticated_bookmark_rejected(self, client):
        """Unauthenticated bookmark request returns 401 or redirect."""
        r = client.post('/api/v1/topics/home%2Fsensor/bookmark')
        # Flask-Login redirects to login page (302) by default
        assert r.status_code in (302, 401)
