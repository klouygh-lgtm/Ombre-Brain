# ============================================================
# Module: Snapshot Store (snapshot_store.py)
# 模块：写前快照存储
#
# 每次 trace 修改 content 前，保存旧版本到 SQLite。
# 提供按桶 ID 查询历史版本的能力。
# ============================================================

import os
import sqlite3
import logging
from datetime import datetime, timezone

logger = logging.getLogger("ombre_brain.snapshot")


class SnapshotStore:
    """写前快照存储 —— 在覆盖/追加前保留旧 content。"""

    def __init__(self, state_dir: str):
        self.db_path = os.path.join(state_dir, "snapshots.db")
        self._ensure_table()

    def _ensure_table(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bucket_id TEXT NOT NULL,
                content TEXT NOT NULL,
                operation TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_bucket
            ON snapshots(bucket_id, timestamp DESC)
        """)
        conn.commit()
        conn.close()

    def save(self, bucket_id: str, content: str, operation: str = "trace"):
        """保存写前快照。"""
        ts = datetime.now(timezone.utc).isoformat()
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO snapshots (bucket_id, content, operation, timestamp) VALUES (?, ?, ?, ?)",
                (bucket_id, content, operation, ts),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"快照保存失败 {bucket_id}: {e}")

    def list_versions(self, bucket_id: str, limit: int = 10) -> list:
        """列出指定桶的历史快照（最新在前）。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, operation, timestamp FROM snapshots WHERE bucket_id = ? ORDER BY timestamp DESC LIMIT ?",
            (bucket_id, limit),
        ).fetchall()
        conn.close()
        return [{"id": r["id"], "operation": r["operation"], "timestamp": r["timestamp"]} for r in rows]

    def get_version(self, snapshot_id: int) -> dict | None:
        """读取指定快照的完整内容。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
        conn.close()
        if row:
            return {
                "id": row["id"],
                "bucket_id": row["bucket_id"],
                "content": row["content"],
                "operation": row["operation"],
                "timestamp": row["timestamp"],
            }
        return None

    def prune(self, keep_per_bucket: int = 20):
        """清理旧快照，每桶最多保留 keep_per_bucket 条。"""
        conn = sqlite3.connect(self.db_path)
        bucket_ids = [r[0] for r in conn.execute("SELECT DISTINCT bucket_id FROM snapshots").fetchall()]
        for bid in bucket_ids:
            conn.execute("""
                DELETE FROM snapshots WHERE bucket_id = ? AND id NOT IN (
                    SELECT id FROM snapshots WHERE bucket_id = ? ORDER BY timestamp DESC LIMIT ?
                )
            """, (bid, bid, keep_per_bucket))
        conn.commit()
        conn.close()
