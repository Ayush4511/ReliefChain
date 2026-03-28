import sqlite3, os, sys, traceback
os.chdir(r'c:\Users\Dell\OneDrive\Desktop\reliefchain')

db = sqlite3.connect('database.db')
db.row_factory = sqlite3.Row
c = db.cursor()

c.execute('PRAGMA table_info(beneficiaries)')
print('BEN COLS:', [r[1] for r in c.fetchall()])

c.execute('PRAGMA table_info(campaigns)')
print('CAMP COLS:', [r[1] for r in c.fetchall()])

c.execute('PRAGMA table_info(donations)')
print('DON COLS:', [r[1] for r in c.fetchall()])

c.execute('PRAGMA table_info(ledger)')
print('LEDGER COLS:', [r[1] for r in c.fetchall()])

queries = [
    ('flagged col', "SELECT COUNT(*) FROM beneficiaries WHERE flagged=1"),
    ('status col', "SELECT COUNT(*) FROM beneficiaries WHERE status='verified'"),
    ('campaigns', "SELECT * FROM campaigns WHERE status='active' LIMIT 1"),
    ('donations', "SELECT SUM(amount) as total, COUNT(*) as cnt FROM donations"),
    ('region', "SELECT state, SUM(aid_amount) as total, COUNT(*) as cnt FROM beneficiaries GROUP BY state"),
]
for name, q in queries:
    try:
        c.execute(q)
        row = c.fetchone()
        print(f'OK {name}: {dict(row) if row else None}')
    except Exception as e:
        print(f'FAIL {name}: {e}')

db.close()
