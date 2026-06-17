import os
from pathlib import Path

# Paths to search
search_dirs = ["agents", "config", "dashboard", "ml", "pipeline", "."]

replacements = [
    ("config.tickers", "config.tickers"),
    ("ACTIVE_STOCKS", "ACTIVE_STOCKS")
]

for d in search_dirs:
    p = Path(d)
    if not p.is_dir(): continue
    for py_file in p.glob("**/*.py"):
        # skip virtual env or unwanted dirs
        if "venv" in str(py_file) or ".conda" in str(py_file):
            continue
            
        content = py_file.read_text(encoding='utf-8')
        new_content = content
        
        for old, new in replacements:
            new_content = new_content.replace(old, new)
            
        if new_content != content:
            py_file.write_text(new_content, encoding='utf-8')
            print(f"Updated {py_file}")

print("Refactoring complete.")
