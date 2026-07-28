"""일회성 마이그레이션: K:\\claude\\events.db -> Neon Postgres.

로컬에서 DATABASE_URL 환경변수(Neon pooled connection string)를 설정하고
events_store.init_db()가 이미 한 번 실행된(테이블이 생성된) 상태에서 한 번만 실행.
(이번 프로젝트는 events.db에 실데이터가 없어 실행 없이 넘어갔지만, 참고용으로 남겨둠.)
"""
import os
import sqlite3

import psycopg2

SQLITE_PATH = r"K:\claude\events.db"
DATABASE_URL = os.environ["DATABASE_URL"]

src = sqlite3.connect(SQLITE_PATH)
src.row_factory = sqlite3.Row
dst = psycopg2.connect(DATABASE_URL)
cur = dst.cursor()

for row in src.execute("SELECT * FROM manual_events"):
    cur.execute(
        """INSERT INTO manual_events
           (id, title, organizer, start_at, end_at, time, location, description, created_at, updated_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        tuple(row),
    )
for row in src.execute("SELECT * FROM event_review"):
    cur.execute(
        "INSERT INTO event_review (event_id, status, overrides_json, updated_at) VALUES (%s,%s,%s,%s)",
        tuple(row),
    )
for row in src.execute("SELECT * FROM tags"):
    cur.execute("INSERT INTO tags (id, name) VALUES (%s,%s)", tuple(row))
for row in src.execute("SELECT * FROM event_tags"):
    cur.execute("INSERT INTO event_tags (event_id, tag_id) VALUES (%s,%s)", tuple(row))

# Postgres identity 시퀀스를 마이그레이션된 최대 id 이후로 재설정
cur.execute(
    "SELECT setval(pg_get_serial_sequence('manual_events','id'), "
    "COALESCE((SELECT MAX(id) FROM manual_events), 1))"
)
cur.execute(
    "SELECT setval(pg_get_serial_sequence('tags','id'), "
    "COALESCE((SELECT MAX(id) FROM tags), 1))"
)

dst.commit()
print("migration done")
