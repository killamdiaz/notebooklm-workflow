"""Stub implementation for extracting content from Kindle-compatible files.

This module is intentionally lightweight for the MVP. It focuses on EPUB
parsing using the standard library and provides a very naive MOBI fallback.
It is designed so that future work can plug in proper DRM-aware extraction as
illustrated in https://github.com/Xetera/kindle-api.
"""

from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Dict, List
from zipfile import ZipFile


@dataclass
class Chapter:
    chapter: int
    text: str


@dataclass
class KindleBook:
    title: str
    author: str
    chapters: List[Chapter]

    def to_dict(self) -> Dict[str, object]:
        return {
            "title": self.title,
            "author": self.author,
            "chapters": [chapter.__dict__ for chapter in self.chapters],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: List[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self._chunks.append(text)

    def get_text(self) -> str:
        return " ".join(self._chunks)


def _strip_html(content: bytes) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(content.decode("utf-8", errors="ignore"))
    return parser.get_text()


def _extract_epub(file_path: pathlib.Path) -> KindleBook:
    title = file_path.stem
    author = "Unknown"
    chapters: List[Chapter] = []

    with ZipFile(file_path) as archive:
        opf_path = next((name for name in archive.namelist() if name.endswith(".opf")), None)
        if opf_path:
            import xml.etree.ElementTree as ET

            root = ET.fromstring(archive.read(opf_path))
            ns = {"dc": "http://purl.org/dc/elements/1.1/"}
            title_elem = root.find(".//dc:title", ns)
            creator_elem = root.find(".//dc:creator", ns)
            if title_elem is not None and title_elem.text:
                title = title_elem.text.strip()
            if creator_elem is not None and creator_elem.text:
                author = creator_elem.text.strip()

        html_files = [name for name in archive.namelist() if name.endswith((".xhtml", ".html", ".htm"))]
        for idx, name in enumerate(sorted(html_files), start=1):
            text = _strip_html(archive.read(name))
            if text:
                chapters.append(Chapter(chapter=idx, text=text))

    if not chapters:
        chapters.append(Chapter(chapter=1, text=""))

    return KindleBook(title=title, author=author, chapters=chapters)


def _extract_mobi(file_path: pathlib.Path) -> KindleBook:
    # MOBI is a proprietary format; for the MVP we perform a very naive extraction
    # by attempting to decode the binary file into UTF-8 and splitting on common
    # chapter markers. This should be replaced with a proper parser such as the
    # one provided by https://github.com/Xetera/kindle-api.
    data = file_path.read_bytes().decode("utf-8", errors="ignore")
    title = file_path.stem
    author = "Unknown"

    chunks = re.split(r"\n\s*chapter\s+\d+\s*\n", data, flags=re.IGNORECASE)
    chapters: List[Chapter] = []

    for idx, chunk in enumerate(chunks, start=1):
        text = chunk.strip()
        if text:
            chapters.append(Chapter(chapter=idx, text=text))

    if not chapters:
        chapters.append(Chapter(chapter=1, text=data.strip()))

    return KindleBook(title=title, author=author, chapters=chapters)


def extract_kindle_book(file_path: str | pathlib.Path) -> Dict[str, object]:
    """Extract the contents of an EPUB or MOBI book into structured JSON."""

    path = pathlib.Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()
    if suffix == ".epub":
        book = _extract_epub(path)
    elif suffix == ".mobi":
        book = _extract_mobi(path)
    else:
        raise ValueError("Unsupported file format. Expected .epub or .mobi")

    return book.to_dict()


__all__ = ["extract_kindle_book", "KindleBook", "Chapter"]
