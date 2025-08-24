"""
Database module for MQTT message persistence
"""
import sqlite3
import threading
import logging
import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union
import os

class MessageDatabase:
    def __init__(self, db_path: str = "mqtt_messages.db", max_messages: int = 10000):
        self.db_path = db_path
        self.max_messages = max_messages
        self._local = threading.local()
        self.init_database()
        
    def get_connection(self):
        """Get thread-local database connection"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path, 
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
            
            # Add REGEXP function for advanced topic filtering
            self._local.connection.create_function("REGEXP", 2, self._regexp)
            
        return self._local.connection
    
    def _regexp(self, pattern, value):
        """Custom REGEXP function for SQLite"""
        try:
            return re.search(pattern, value, re.IGNORECASE) is not None
        except Exception:
            return False
    
    def init_database(self):
        """Initialize database schema"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Messages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    qos INTEGER DEFAULT 0,
                    retain BOOLEAN DEFAULT 0,
                    payload_size INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Topics table for faster topic queries
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS topics (
                    topic TEXT PRIMARY KEY,
                    last_message_at DATETIME NOT NULL,
                    message_count INTEGER DEFAULT 1,
                    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Filter presets table for saved searches
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS filter_presets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    filters TEXT NOT NULL,  -- JSON string of filter parameters
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_used DATETIME
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_topic 
                ON messages(topic)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_timestamp 
                ON messages(timestamp DESC)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_topic_timestamp 
                ON messages(topic, timestamp DESC)
            ''')
            
            conn.commit()
            logging.info("Database initialized successfully")
            
        except Exception as e:
            logging.error(f"Database initialization error: {e}")
            conn.rollback()
            raise
    
    def store_message(self, topic: str, payload: str, timestamp: datetime = None, 
                     qos: int = 0, retain: bool = False) -> bool:
        """Store a message in the database"""
        if timestamp is None:
            timestamp = datetime.now()
            
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Store message
            cursor.execute('''
                INSERT INTO messages (topic, payload, timestamp, qos, retain, payload_size)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (topic, payload, timestamp, qos, retain, len(payload)))
            
            # Update topics table
            cursor.execute('''
                INSERT OR REPLACE INTO topics (topic, last_message_at, message_count, first_seen)
                VALUES (?, ?, 
                    COALESCE((SELECT message_count FROM topics WHERE topic = ?) + 1, 1),
                    COALESCE((SELECT first_seen FROM topics WHERE topic = ?), ?)
                )
            ''', (topic, timestamp, topic, topic, timestamp))
            
            conn.commit()
            
            # Clean up old messages if needed
            self._cleanup_old_messages()
            return True
            
        except Exception as e:
            logging.error(f"Error storing message: {e}")
            conn.rollback()
            return False
    
    def get_messages(self, limit: int = 100, offset: int = 0, 
                    topic_filter: str = None, since: datetime = None,
                    content_search: str = None, regex_topic: str = None,
                    json_path: str = None, json_value: str = None) -> List[Dict]:
        """Retrieve messages from database with enhanced filtering"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            query = '''
                SELECT topic, payload, timestamp, qos, retain, payload_size
                FROM messages 
                WHERE 1=1
            '''
            params = []
            
            # Basic topic filtering (wildcard support)
            if topic_filter:
                if '%' in topic_filter or '_' in topic_filter:
                    query += ' AND topic LIKE ?'
                else:
                    query += ' AND topic = ?'
                params.append(topic_filter)
            
            # Regex topic filtering (more powerful than LIKE)
            if regex_topic:
                query += ' AND topic REGEXP ?'
                params.append(regex_topic)
            
            # Content search (case-insensitive)
            if content_search:
                query += ' AND LOWER(payload) LIKE LOWER(?)'
                params.append(f'%{content_search}%')
            
            # Time filtering
            if since:
                query += ' AND timestamp >= ?'
                params.append(since)
                
            query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            messages = [dict(row) for row in rows]
            
            # Apply Python-based filters that can't be done in SQL
            if json_path or regex_topic:
                messages = self._apply_python_filters(
                    messages, regex_topic, json_path, json_value
                )
            
            return messages
            
        except Exception as e:
            logging.error(f"Error retrieving messages: {e}")
            return []
    
    def _apply_python_filters(self, messages: List[Dict], regex_topic: str = None,
                            json_path: str = None, json_value: str = None) -> List[Dict]:
        """Apply filters that require Python processing"""
        filtered = []
        
        for msg in messages:
            # Regex topic filter (if not handled by SQL REGEXP)
            if regex_topic and not re.search(regex_topic, msg['topic'], re.IGNORECASE):
                continue
                
            # JSON path filtering
            if json_path and json_value:
                try:
                    payload_json = json.loads(msg['payload'])
                    # Simple JSON path support (e.g., "temperature", "sensors.temp")
                    value = self._get_json_path_value(payload_json, json_path)
                    if value is None or str(value).lower() != json_value.lower():
                        continue
                except (json.JSONDecodeError, KeyError):
                    continue
            
            filtered.append(msg)
        
        return filtered
    
    def _get_json_path_value(self, json_obj: dict, path: str):
        """Extract value from JSON using simple dot notation path"""
        try:
            keys = path.split('.')
            current = json_obj
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return None
            return current
        except Exception:
            return None
    
    def get_topics(self) -> List[Dict]:
        """Get all topics with statistics"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT topic, message_count, last_message_at, first_seen
                FROM topics
                ORDER BY last_message_at DESC
            ''')
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            logging.error(f"Error retrieving topics: {e}")
            return []
    
    def get_message_count(self, topic_filter: str = None, since: datetime = None) -> int:
        """Get total message count with optional filtering"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            query = 'SELECT COUNT(*) FROM messages WHERE 1=1'
            params = []
            
            if topic_filter:
                if '%' in topic_filter or '_' in topic_filter:
                    query += ' AND topic LIKE ?'
                else:
                    query += ' AND topic = ?'
                params.append(topic_filter)
            
            if since:
                query += ' AND timestamp >= ?'
                params.append(since)
                
            cursor.execute(query, params)
            return cursor.fetchone()[0]
            
        except Exception as e:
            logging.error(f"Error counting messages: {e}")
            return 0
    
    def _cleanup_old_messages(self):
        """Remove old messages to stay within limit"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Check if we need cleanup
            cursor.execute('SELECT COUNT(*) FROM messages')
            count = cursor.fetchone()[0]
            
            if count > self.max_messages:
                # Delete oldest messages
                messages_to_delete = count - self.max_messages + 1000  # Delete extra to avoid frequent cleanups
                cursor.execute('''
                    DELETE FROM messages 
                    WHERE id IN (
                        SELECT id FROM messages 
                        ORDER BY timestamp ASC 
                        LIMIT ?
                    )
                ''', (messages_to_delete,))
                
                # Update topic counts (this is approximate)
                cursor.execute('''
                    UPDATE topics SET message_count = (
                        SELECT COUNT(*) FROM messages WHERE messages.topic = topics.topic
                    )
                ''')
                
                conn.commit()
                logging.info(f"Cleaned up {messages_to_delete} old messages")
                
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")
            conn.rollback()
    
    def cleanup_old_data(self, days: int = 30):
        """Remove messages older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM messages WHERE timestamp < ?', (cutoff_date,))
            deleted = cursor.rowcount
            
            # Clean up topics with no messages
            cursor.execute('''
                DELETE FROM topics WHERE topic NOT IN (
                    SELECT DISTINCT topic FROM messages
                )
            ''')
            
            conn.commit()
            logging.info(f"Cleaned up {deleted} messages older than {days} days")
            return deleted
            
        except Exception as e:
            logging.error(f"Error during data cleanup: {e}")
            conn.rollback()
            return 0
    
    def get_database_size(self) -> Dict:
        """Get database size information"""
        try:
            size_bytes = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM messages')
            message_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM topics')
            topic_count = cursor.fetchone()[0]
            
            return {
                'size_bytes': size_bytes,
                'size_mb': round(size_bytes / 1024 / 1024, 2),
                'message_count': message_count,
                'topic_count': topic_count
            }
            
        except Exception as e:
            logging.error(f"Error getting database size: {e}")
            return {'size_bytes': 0, 'size_mb': 0, 'message_count': 0, 'topic_count': 0}
    
    def save_filter_preset(self, name: str, filters: Dict, description: str = None) -> bool:
        """Save a filter preset"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO filter_presets (name, description, filters, last_used)
                VALUES (?, ?, ?, ?)
            ''', (name, description, json.dumps(filters), datetime.now()))
            
            conn.commit()
            logging.info(f"Saved filter preset: {name}")
            return True
            
        except Exception as e:
            logging.error(f"Error saving filter preset: {e}")
            conn.rollback()
            return False
    
    def get_filter_presets(self) -> List[Dict]:
        """Get all filter presets"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name, description, filters, created_at, last_used
                FROM filter_presets
                ORDER BY last_used DESC, created_at DESC
            ''')
            rows = cursor.fetchall()
            
            presets = []
            for row in rows:
                preset = dict(row)
                preset['filters'] = json.loads(preset['filters'])
                presets.append(preset)
            
            return presets
            
        except Exception as e:
            logging.error(f"Error getting filter presets: {e}")
            return []
    
    def delete_filter_preset(self, name: str) -> bool:
        """Delete a filter preset"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM filter_presets WHERE name = ?', (name,))
            conn.commit()
            
            if cursor.rowcount > 0:
                logging.info(f"Deleted filter preset: {name}")
                return True
            return False
            
        except Exception as e:
            logging.error(f"Error deleting filter preset: {e}")
            conn.rollback()
            return False
    
    def use_filter_preset(self, name: str) -> Optional[Dict]:
        """Load and mark a filter preset as used"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Get the preset
            cursor.execute('''
                SELECT filters FROM filter_presets WHERE name = ?
            ''', (name,))
            row = cursor.fetchone()
            
            if not row:
                return None
                
            # Update last_used timestamp
            cursor.execute('''
                UPDATE filter_presets SET last_used = ? WHERE name = ?
            ''', (datetime.now(), name))
            
            conn.commit()
            return json.loads(row['filters'])
            
        except Exception as e:
            logging.error(f"Error using filter preset: {e}")
            return None

    def close(self):
        """Close database connection"""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()