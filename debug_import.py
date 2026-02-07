
import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "league_system.settings")
django.setup()

try:
    import analysis.urls
    print("SUCCESS: analysis.urls imported")
except ImportError as e:
    print(f"FAILURE: {e}")
    # Inspect sys.path
    print("sys.path:", sys.path)
