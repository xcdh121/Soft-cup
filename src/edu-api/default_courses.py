"""Provision the two built-in demo courses for application users."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from edu_db.models import Course
from edu_db.session import get_session_factory, init_db


DEFAULT_COURSE_SCRIPTS = {
    "DSA-MVP": "seed_dsa_course.py",
    "ML-DEMO": "seed_ml_demo_course.py",
}


def _get_session_factory():
    try:
        return get_session_factory()
    except RuntimeError:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL is required to provision default courses")
        init_db(database_url)
        return get_session_factory()


def ensure_default_courses(user_id: str) -> None:
    """Create any missing built-in courses for ``user_id``.

    The seed scripts are idempotent. Running them in isolated subprocesses keeps
    their environment-based owner selection safe when registrations overlap.
    """

    session_factory = _get_session_factory()
    with session_factory() as db:
        existing_codes = {
            code
            for (code,) in (
                db.query(Course.code)
                .filter(
                    Course.owner_id == user_id,
                    Course.code.in_(DEFAULT_COURSE_SCRIPTS),
                )
                .all()
            )
        }

    missing_codes = set(DEFAULT_COURSE_SCRIPTS) - existing_codes
    if not missing_codes:
        return

    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    child_env = os.environ.copy()
    child_env["SEED_OWNER_ID"] = user_id

    for course_code in DEFAULT_COURSE_SCRIPTS:
        if course_code not in missing_codes:
            continue
        script_path = scripts_dir / DEFAULT_COURSE_SCRIPTS[course_code]
        if not script_path.is_file():
            raise RuntimeError(f"Default course seed script missing: {script_path}")
        subprocess.run(
            [sys.executable, str(script_path)],
            check=True,
            env=child_env,
            capture_output=True,
            text=True,
            timeout=120,
        )
