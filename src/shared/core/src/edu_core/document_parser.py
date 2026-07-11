from dataclasses import dataclass
import html
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class ParsedDocument:
    pages: list[ParsedPage]
    full_text: str
    summary: str


class LocalDocumentParser:
    def parse(self, filename: str, content: bytes) -> ParsedDocument:
        suffix = Path(filename).suffix.lower()

        if suffix == ".pdf":
            pages = self._parse_pdf(content)
            full_text = "\n\n<!-- PageBreak -->\n\n".join(
                page.text for page in pages if page.text.strip()
            )
        elif suffix == ".docx":
            text = self._parse_docx(content)
            full_text = self._normalize_text(text)
            pages = self._single_text_page(full_text)
        elif suffix in {".txt", ".md"}:
            text = content.decode("utf-8", errors="ignore")
            full_text = self._normalize_text(text)
            pages = self._single_text_page(full_text)
        elif suffix in {".html", ".htm", ".xml"}:
            text = self._strip_markup(content.decode("utf-8", errors="ignore"))
            full_text = self._normalize_text(text)
            pages = self._single_text_page(full_text)
        elif suffix == ".rtf":
            text = self._strip_rtf(content.decode("utf-8", errors="ignore"))
            full_text = self._normalize_text(text)
            pages = self._single_text_page(full_text)
        else:
            text = content.decode("utf-8", errors="ignore")
            full_text = self._normalize_text(text)
            pages = self._single_text_page(full_text)

        return ParsedDocument(
            pages=pages,
            full_text=full_text,
            summary=self._summarize(full_text),
        )

    def _parse_pdf(self, content: bytes) -> list[ParsedPage]:
        from io import BytesIO

        from pypdf import PdfReader

        reader = PdfReader(BytesIO(content))
        pages = []
        for index, page in enumerate(reader.pages):
            page_text = self._normalize_text(page.extract_text() or "")
            if page_text.strip():
                pages.append(ParsedPage(page_number=index + 1, text=page_text))
        return pages

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

    def _single_text_page(self, text: str) -> list[ParsedPage]:
        if not text.strip():
            return []
        return [ParsedPage(page_number=1, text=text)]

    def _summarize(self, text: str) -> str:
        if not text:
            return ""
        sentences = re.split(r"(?<=[.!?。！？])\s+", text)
        summary = " ".join(sentence.strip() for sentence in sentences[:3] if sentence.strip())
        return summary[:500]
