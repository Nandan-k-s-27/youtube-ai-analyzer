"""
Cache Statistics and Management Script

Run this to view cache status and perform maintenance operations.
"""
import os
import sys
from cache_manager import CacheManager, MAX_DB_SIZE_MB

def print_header(text):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def format_size(bytes_size):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"

def main():
    print_header("📊 CACHE STATISTICS & MANAGEMENT")
    
    cache = CacheManager()
    stats = cache.get_cache_stats()
    
    # Configuration
    print("\n🔧 Configuration:")
    print(f"   TTL (Time to Live):     {stats['ttl_days']} days")
    print(f"   Max Entries Limit:      {stats['max_entries']}")
    print(f"   Max Size Warning:       {MAX_DB_SIZE_MB} MB")
    
    # Database Stats
    print_header("💾 DATABASE STATUS")
    print(f"   Database Size:          {stats['database_size_mb']} MB")
    print(f"   Total Entries:          {stats['total_entries']}")
    print(f"   Total Accesses:         {stats['total_accesses']}")
    
    if stats['oldest_entry_days'] is not None:
        print(f"   Oldest Entry:           {stats['oldest_entry_days']} days ago")
    
    # Health Indicators
    print("\n🏥 Health Indicators:")
    
    # Size check
    size_usage = (stats['database_size_mb'] / MAX_DB_SIZE_MB) * 100
    if size_usage > 80:
        print(f"   ⚠️  Size Warning:         {size_usage:.1f}% of limit")
    else:
        print(f"   ✅ Size:                  {size_usage:.1f}% of limit")
    
    # Entry count check
    entry_usage = (stats['total_entries'] / stats['max_entries']) * 100
    if entry_usage > 80:
        print(f"   ⚠️  Entry Warning:        {entry_usage:.1f}% of limit")
    else:
        print(f"   ✅ Entries:               {entry_usage:.1f}% of limit")
    
    # Age check
    if stats['oldest_entry_days'] and stats['oldest_entry_days'] > stats['ttl_days']:
        print(f"   ⚠️  Old Data:             Entries older than TTL found")
    else:
        print(f"   ✅ Freshness:             All entries within TTL")
    
    # Cache efficiency
    if stats['total_accesses'] > 0 and stats['total_entries'] > 0:
        avg_hits = stats['total_accesses'] / stats['total_entries']
        print(f"   💡 Avg Hits/Entry:        {avg_hits:.1f}x")
    
    # Top Videos
    if stats['top_videos']:
        print_header("🔥 TOP 5 MOST ACCESSED VIDEOS")
        for i, video in enumerate(stats['top_videos'], 1):
            print(f"   {i}. {video['video_id']} - {video['access_count']} hits")
    
    # Management Options
    print_header("🛠️  MANAGEMENT OPTIONS")
    print("\n1. Clear old cache (older than TTL)")
    print("2. Clear ALL cache")
    print("3. Clear cache older than X days")
    print("4. Exit")
    
    choice = input("\nSelect option (1-4): ").strip()
    
    if choice == "1":
        print(f"\n🗑️  Clearing entries older than {stats['ttl_days']} days...")
        deleted = cache.clear_old_cache(stats['ttl_days'])
        print(f"✅ Deleted {deleted} entries")
        
    elif choice == "2":
        confirm = input("⚠️  Are you sure you want to delete ALL cache? (yes/no): ")
        if confirm.lower() == 'yes':
            import shutil
            if os.path.exists(cache.db_path):
                os.remove(cache.db_path)
                print("✅ All cache cleared!")
                print("💡 Run the app again to recreate the database")
        else:
            print("❌ Cancelled")
            
    elif choice == "3":
        days = input("Enter number of days: ").strip()
        try:
            days = int(days)
            print(f"\n🗑️  Clearing entries older than {days} days...")
            deleted = cache.clear_old_cache(days)
            print(f"✅ Deleted {deleted} entries")
        except ValueError:
            print("❌ Invalid number")
            
    elif choice == "4":
        print("👋 Goodbye!")
    else:
        print("❌ Invalid option")
    
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
