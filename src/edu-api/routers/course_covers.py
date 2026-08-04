"""Public delivery endpoint for administrator-managed course covers."""

import re
from pathlib import Path

from config import get_settings
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/v1/course-covers", tags=["course-covers"])

COURSE_COVER_NAME = re.compile(r"^[0-9a-f]{32}\.(?:jpg|png|webp)$")
COURSE_COVER_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


@router.get("/{filename}", include_in_schema=False)
def get_course_cover(filename: str):
    if not COURSE_COVER_NAME.fullmatch(filename):
        raise HTTPException(status_code=404, detail="课程封面不存在")

    path = Path(get_settings().storage_root) / "course-covers" / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="课程封面不存在")

    return FileResponse(
        path,
        media_type=COURSE_COVER_MEDIA_TYPES[path.suffix],
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
