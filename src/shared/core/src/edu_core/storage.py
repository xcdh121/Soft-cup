from pathlib import Path


class LocalStorageService:
    def __init__(self, root_dir: str) -> None:
        self.root = Path(root_dir).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def build_document_path(
        self, project_id: str, document_id: str, filename: str
    ) -> str:
        extension = Path(filename).suffix
        return f"projects/{project_id}/documents/{document_id}{extension}"

    def build_processed_text_path(self, project_id: str, document_id: str) -> str:
        return f"projects/{project_id}/processed/{document_id}.contents.txt"

    def build_chat_file_path(
        self, project_id: str, chat_id: str, filename: str, unique_prefix: str
    ) -> str:
        return f"projects/{project_id}/chat-files/{chat_id}/{unique_prefix}-{filename}"

    def resolve(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if self.root not in path.parents and path != self.root:
            raise ValueError(f"Path escapes storage root: {relative_path}")
        return path

    def write_bytes(self, relative_path: str, data: bytes) -> str:
        path = self.resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return relative_path

    def write_text(self, relative_path: str, data: str) -> str:
        path = self.resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return relative_path

    def read_bytes(self, relative_path: str) -> bytes:
        return self.resolve(relative_path).read_bytes()

    def read_text(self, relative_path: str) -> str:
        return self.resolve(relative_path).read_text(encoding="utf-8")

    def exists(self, relative_path: str) -> bool:
        return self.resolve(relative_path).exists()

    def delete(self, relative_path: str) -> None:
        path = self.resolve(relative_path)
        if path.exists():
            path.unlink()
