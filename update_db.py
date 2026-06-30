from sqlalchemy import create_engine, text
engine = create_engine('postgresql://postgres:dcs%40123@localhost/code_review_platform')
with engine.connect() as conn:
    try:
        conn.execute(text('ALTER TABLE projects ADD COLUMN github_token VARCHAR'))
    except Exception as e:
        print(e)
    try:
        conn.execute(text('ALTER TABLE projects ADD COLUMN github_repo_url VARCHAR'))
    except Exception as e:
        print(e)
    conn.commit()
