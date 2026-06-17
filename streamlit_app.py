import sys
import os

# Ensure the root folder is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the actual dashboard entrypoint
from dashboard.app import *
