import html
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree


class LocalDocumentParser:
    def parse(self, filename: str, content: bytes) -> tuple[str, str]:
        suffix = Path(filename).suffix.lower()

        if suffix == ".pdf":
            text = self._parse_pdf(content)
        elif suffix == ".docx":
            text = self._parse_docx(content)
        elif suffix in {".txt", ".md"}:
            text = content.decode("utf-8", errors="ignore")
        elif suffix in {".html", ".htm", ".xml"}:
            text = self._strip_markup(content.decode("utf-8", errors="ignore"))
        elif suffix == ".rtf":
            text = self._strip_rtf(content.decode("utf-8", errors="ignore"))
        else:
            text = content.decode("utf-8", errors="ignore")

        normalized = self._normalize_text(text)
        return normalized, self._summarize(normalized)

    def _parse_pdf(self, content: bytes) -> str:
        from io import BytesIO

        from pypdf import PdfReader

        reader = PdfReader(BytesIO(content))
        pages = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(page_text.strip())
        return "\n\n<!-- PageBreak -->\n\n".join(pages)

    def _parse_docx(self, content: bytes) -> str:
        from io import BytesIO

        with zipfile.ZipFile(BytesIO(content)) as archive:
            xml_bytes = archive.read("word/document.xml")
        root = ElementTree.fromstring(xml_bytes)
        paragraphs: list[str] = []
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        for paragraph in root.findall(".//w:p", namespace):
            texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
            line = "".join(texts).strip()
            if line:
                paragraphs.append(line)
        return "\n\n".join(paragraphs)

    def _strip_markup(self, raw: str) -> str:
        stripped = re.sub(r"<[^>]+>", " ", raw)
        return html.unescape(stripped)

    def _strip_rtf(self, raw: str) -> str:
        without_controls = re.sub(r"\\[a-zA-Z]+\d* ?", " ", raw)
        without_groups = re.sub(r"[{}]", " ", without_controls)
        return without_groups

    def _normalize_text(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line).strip()

    def _summarize(self, text: str) -> str:
        if not text:
            return ""
        sentences = re.split(r"(?<=[.!?。！？])\s+", text)
        summary = " ".join(sentence.strip() for sentence in sentences[:3] if sentence.strip())
        return summary[:500]
