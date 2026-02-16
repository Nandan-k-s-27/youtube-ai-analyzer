"""Cache Manager Module

Provides intelligent caching for video processing results:
- SQLite-based persistent storage
- Automatic TTL management
- Cache size monitoring
- Performance analytics
- Thread-safe operations
"""
import sqlite3
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
import os

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────
# Can be overridden via environment variables
DEFAULT_CACHE_TTL_DAYS = int(os.getenv('CACHE_TTL_DAYS', 7))  # Auto-delete entries older than 7 days
MAX_CACHE_ENTRIES = int(os.getenv('CACHE_MAX_ENTRIES', 500))  # Maximum number of cached entries
MAX_DB_SIZE_MB = int(os.getenv('CACHE_MAX_SIZE_MB', 100))  # Maximum database size in MB


class CacheManager:
    def __init__(self, db_path: str = "./cache/summaries.db", 
                 auto_cleanup: bool = True,
                 ttl_days: int = DEFAULT_CACHE_TTL_DAYS):
        """Initialize cache manager with SQLite database
        
        Args:
            db_path: Path to SQLite database file
            auto_cleanup: Automatically cleanup old entries on init
            ttl_days: Days to keep cache entries (default: 7)
        """
        self.db_path = db_path
        self.ttl_days = ttl_days
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_database()
        
        if auto_cleanup:
            self._auto_cleanup_on_startup()
    
    def _init_database(self):
        """Create database tables if they don't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS summaries (
                    cache_key TEXT PRIMARY KEY,
                    video_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT,
                    full_text TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    method TEXT,
                    percentage REAL,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 1
                )
            """)
            
            # Create indexes for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON summaries(created_at)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_video_id 
                ON summaries(video_id)
            """)
            
            conn.commit()
            conn.close()
            logger.info(f"Cache database initialized at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Error initializing cache database: {str(e)}")
            raise
    
    def _get_video_hash(self, video_id: str, percentage: float) -> str:
        """Generate hash for video ID and percentage combination"""
        key = f"{video_id}_{percentage}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def get_cached_summary(self, video_id: str, percentage: float) -> Optional[Dict]:
        """Retrieve cached summary if it exists (considering both video_id AND percentage)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Use cache_key that includes percentage
            cache_key = self._get_video_hash(video_id, percentage)
            
            cursor.execute("""
                SELECT url, title, full_text, summary, method, percentage, source, created_at
                FROM summaries
                WHERE cache_key = ?
            """, (cache_key,))
            
            result = cursor.fetchone()
            
            if result:
                # Update access statistics
                cursor.execute("""
                    UPDATE summaries
                    SET accessed_at = CURRENT_TIMESTAMP,
                        access_count = access_count + 1
                    WHERE cache_key = ?
                """, (cache_key,))
                conn.commit()
                
                logger.info(f"✅ Cache HIT for video: {video_id} (percentage: {percentage*100:.0f}%)")
                
                return {
                    'url': result[0],
                    'title': result[1],
                    'text': result[2],
                    'summary': result[3],
                    'method': result[4],
                    'percentage': result[5],
                    'source': result[6],
                    'cached': True,
                    'cached_at': result[7]
                }
            
            logger.info(f"❌ Cache MISS for video: {video_id}")
            conn.close()
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving from cache: {str(e)}")
            return None
    
    def save_summary(self, video_id: str, url: str, title: str, full_text: str, 
                    summary: str, method: str, percentage: float, source: str):
        """Save summary to cache (with unique key for video_id + percentage combination)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Generate unique cache key
            cache_key = self._get_video_hash(video_id, percentage)
            
            cursor.execute("""
                INSERT OR REPLACE INTO summaries 
                (cache_key, video_id, url, title, full_text, summary, method, percentage, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (cache_key, video_id, url, title, full_text, summary, method, percentage, source))
            
            conn.commit()
            conn.close()
            
            logger.info(f"💾 Saved summary to cache for video: {video_id} (percentage: {percentage*100:.0f}%)")
            
        except Exception as e:
            logger.error(f"Error saving to cache: {str(e)}")
    
    def clear_old_cache(self, days: int = 30):
        """Remove cache entries older than specified days"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            cursor.execute("""
                DELETE FROM summaries
                WHERE created_at < ?
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"🗑️ Cleared {deleted_count} old cache entries (older than {days} days)")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error clearing old cache: {str(e)}")
            return 0
    
    def _auto_cleanup_on_startup(self):
        """Automatically cleanup old cache entries on startup"""
        try:
            deleted = self.clear_old_cache(self.ttl_days)
            if deleted > 0:
                logger.info(f"🧹 Auto-cleanup: Removed {deleted} expired entries")
            
            # Check if we exceed max entries
            self._enforce_max_entries()
            
            # Check database size
            self._check_database_size()
            
        except Exception as e:
            logger.warning(f"Auto-cleanup warning: {str(e)}")
    
    def _enforce_max_entries(self):
        """Remove oldest entries if cache exceeds MAX_CACHE_ENTRIES"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM summaries")
            total_entries = cursor.fetchone()[0]
            
            if total_entries > MAX_CACHE_ENTRIES:
                excess = total_entries - MAX_CACHE_ENTRIES
                
                # Delete oldest accessed entries
                cursor.execute("""
                    DELETE FROM summaries
                    WHERE cache_key IN (
                        SELECT cache_key FROM summaries
                        ORDER BY accessed_at ASC
                        LIMIT ?
                    )
                """, (excess,))
                
                conn.commit()
                logger.info(f"🗑️ Removed {excess} oldest entries (max: {MAX_CACHE_ENTRIES})")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Error enforcing max entries: {str(e)}")
    
    def _check_database_size(self):
        """Check and report database size"""
        try:
            if os.path.exists(self.db_path):
                size_bytes = os.path.getsize(self.db_path)
                size_mb = size_bytes / (1024 * 1024)
                
                logger.info(f"📊 Cache database size: {size_mb:.2f} MB")
                
                if size_mb > MAX_DB_SIZE_MB:
                    logger.warning(
                        f"⚠️ Database size ({size_mb:.2f} MB) exceeds limit ({MAX_DB_SIZE_MB} MB). "
                        "Consider clearing cache or reducing TTL."
                    )
                    # Auto-cleanup more aggressively
                    deleted = self.clear_old_cache(days=3)  # Clear entries older than 3 days
                    logger.info(f"🧹 Emergency cleanup: Removed {deleted} entries")
                    
        except Exception as e:
            logger.error(f"Error checking database size: {str(e)}")
    
    def get_cache_stats(self) -> Dict:
        """Get comprehensive cache statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM summaries")
            total_entries = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(access_count) FROM summaries")
            total_accesses = cursor.fetchone()[0] or 0
            
            cursor.execute("""
                SELECT video_id, url, access_count 
                FROM summaries 
                ORDER BY access_count DESC 
                LIMIT 5
            """)
            top_videos = cursor.fetchall()
            
            # Get database size
            db_size_mb = 0
            if os.path.exists(self.db_path):
                db_size_mb = os.path.getsize(self.db_path) / (1024 * 1024)
            
            # Get oldest entry age
            cursor.execute("""
                SELECT MIN(created_at) FROM summaries
            """)
            oldest = cursor.fetchone()[0]
            oldest_age_days = None
            if oldest:
                oldest_date = datetime.fromisoformat(oldest)
                oldest_age_days = (datetime.now() - oldest_date).days
            
            conn.close()
            
            return {
                'total_entries': total_entries,
                'total_accesses': total_accesses,
                'database_size_mb': round(db_size_mb, 2),
                'max_entries': MAX_CACHE_ENTRIES,
                'ttl_days': self.ttl_days,
                'oldest_entry_days': oldest_age_days,
                'top_videos': [
                    {'video_id': v[0], 'url': v[1], 'access_count': v[2]} 
                    for v in top_videos
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {'total_entries': 0, 'total_accesses': 0, 'top_videos': []}
