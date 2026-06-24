import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import sqlite3
from pathlib import Path

db = Path('data/predictions/articles.db')
conn = sqlite3.connect(str(db))
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('Tables:', c.fetchall())

c.execute('SELECT COUNT(*) FROM articles')
total = c.fetchone()[0]
print(f'Total articles in DB: {total}')

c.execute('SELECT DISTINCT substr(fetched_at,1,10) as day, COUNT(*) FROM articles GROUP BY day ORDER BY day DESC LIMIT 10')
print('Articles by date:')
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]} articles')

c.execute('SELECT fetched_at, source, title FROM articles ORDER BY fetched_at DESC LIMIT 5')
print('\nLatest 5 articles:')
for row in c.fetchall():
    print(f'  {row[0][:16]} | {row[1]} | {str(row[2])[:60]}')
conn.close()
