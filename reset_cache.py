"""
Reset cache database to implement new schema that respects percentage parameter.
Run this once to clear old cache and recreate with proper structure.
"""
import os
import shutil

cache_dir = "./cache"
cache_db = "./cache/summaries.db"

if os.path.exists(cache_db):
    print(f"🗑️  Removing old cache database: {cache_db}")
    os.remove(cache_db)
    print("✅ Old cache removed successfully!")
else:
    print("ℹ️  No cache database found (this is fine for first run)")

if os.path.exists(cache_dir):
    # Check if directory is empty
    if not os.listdir(cache_dir):
        print(f"📁 Cache directory exists but is empty")
    else:
        print(f"📁 Cache directory exists")
else:
    print("📁 Cache directory will be created on next run")

print("\n✨ Cache reset complete!")
print("Next time you process a video, the cache will use the new schema.")
print("This means different summary percentages will be properly cached separately.\n")
