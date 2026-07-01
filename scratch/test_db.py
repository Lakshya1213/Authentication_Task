import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import init_db
import logging

logging.basicConfig(level=logging.INFO)

try:
    init_db()
    print("Database tables initialized successfully!")
except Exception as e:
    print(f"Error initializing database: {e}", file=sys.stderr)
    sys.exit(1)
