from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import db as dbmod
from scripts.import_mdb import connect, init_schema, seed_user


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "catholic.db"
    monkeypatch.setattr(dbmod, "DB_PATH", db_path)
    import scripts.import_mdb as importer

    monkeypatch.setattr(importer, "DB_PATH", db_path)
    conn = connect()
    init_schema(conn)
    seed_user(conn)
    conn.execute(
        """INSERT INTO parish_settings (id, church_th, church_en, father, id_prefix, religion, sen, prefix)
           VALUES (1, 'วัดทดสอบ', 'Test Church', 'บาทหลวงทดสอบ', '070104-', 'คาทอลิก', 'เรียน', 'คุณ')"""
    )
    conn.execute(
        """INSERT INTO members (id, num, saint_name, first_name, last_name, gang, sex, religion, family_no, birth_date)
           VALUES (1, '070104-1987-B9', 'ยอห์นบอสโก', 'จอมพล', 'แสนสุข', '3A', 'ชาย', 'คาทอลิก', '525', '1982-02-02')"""
    )
    conn.execute(
        """INSERT INTO churches (id, name, gen_name, is_header) VALUES ('070104', 'นักบุญยอแซฟ', 'วัดบ้านโป่ง', 0)"""
    )
    conn.commit()
    conn.close()

    from importlib import reload
    import app.main as mainmod

    reload(mainmod)
    monkeypatch.setattr(mainmod, "get_db", dbmod.get_db)
    with TestClient(mainmod.app) as c:
        yield c
