import json
import sys
import unittest
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
for source in (
    ROOT / "src" / "shared" / "core" / "src",
    ROOT / "src" / "shared" / "db" / "src",
):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from edu_core.services.admin import AdminService  # noqa: E402


class RecordingSession:
    def __init__(self) -> None:
        self.added = []

    def add(self, value) -> None:
        self.added.append(value)


class AdminAuditSerializationTest(unittest.TestCase):
    def test_audit_snapshots_are_json_serializable(self):
        session = RecordingSession()
        created_at = datetime(2026, 8, 4, 7, 30, tzinfo=UTC)

        AdminService._audit(
            session,
            "admin-1",
            "course.create",
            "course",
            "course-1",
            {},
            {
                "created_at": created_at,
                "published_on": date(2026, 8, 4),
                "price": Decimal("59.90"),
                "owner_id": UUID("00000000-0000-0000-0000-000000000001"),
                "nested": [{"updated_at": created_at}],
            },
            "创建平台课程",
        )

        audit = session.added[0]
        self.assertEqual(audit.after_snapshot["created_at"], created_at.isoformat())
        self.assertEqual(audit.after_snapshot["published_on"], "2026-08-04")
        self.assertEqual(audit.after_snapshot["price"], "59.90")
        self.assertEqual(
            audit.after_snapshot["owner_id"],
            "00000000-0000-0000-0000-000000000001",
        )
        json.dumps(audit.before_snapshot)
        json.dumps(audit.after_snapshot)


if __name__ == "__main__":
    unittest.main()
