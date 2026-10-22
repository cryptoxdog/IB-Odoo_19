"""Merge ERP notes into an Odoo Html comment without dropping later paragraphs."""

from __future__ import annotations

from html import escape
from html.parser import HTMLParser

_COMMENT_BLOCK_TAGS = frozenset({"p", "div", "li", "blockquote", "pre", "tr", "h1", "h2", "h3", "h4", "h5", "h6"})


class _CommentBlocks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._parts: list[str] = []

    def flush(self) -> None:
        text = " ".join("".join(self._parts).split())
        if text:
            self.blocks.append(text)
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag in _COMMENT_BLOCK_TAGS:
            self.flush()
        elif tag == "br":
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _COMMENT_BLOCK_TAGS:
            self.flush()

    def handle_data(self, data):
        self._parts.append(data)


def comment_with_erp_notes(comment, notes: str):
    """``comment`` holding the ERP notes and every other paragraph. ``None`` means no write.

    The CRM sync appends its notes to the same partner comment. When the ERP
    notes are already there as one paragraph, or a run of adjacent paragraphs,
    nothing is written. Otherwise they go first and the existing paragraphs stay.
    """
    text = " ".join((notes or "").split())
    if not text:
        return None
    parser = _CommentBlocks()
    parser.feed(str(comment or ""))
    parser.close()
    parser.flush()
    blocks = parser.blocks
    for start in range(len(blocks)):
        joined = ""
        for block in blocks[start:]:
            joined = f"{joined} {block}" if joined else block
            if joined == text:
                return None
            if len(joined) >= len(text):
                break
    if not blocks:
        return notes
    return f"<p>{escape(notes.strip(), quote=False)}</p>{comment}"
