import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app.database import engine
from sqlalchemy import inspect, text

inspector = inspect(engine)
cols = [c['name'] for c in inspector.get_columns('code_reviews')]
print("code_reviews columns:", cols)

needed = ['bad_practices', 'performance_improvements', 'generated_comments']
missing = [c for c in needed if c not in cols]
print("Missing:", missing)

if missing:
    with engine.begin() as conn:
        for col in missing:
            conn.execute(text(f"ALTER TABLE code_reviews ADD COLUMN IF NOT EXISTS {col} TEXT"))
            print(f"Added column: {col}")
    print("Migration done.")
else:
    print("All columns present.")
