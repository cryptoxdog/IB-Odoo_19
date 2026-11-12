"""Deterministic reference extraction from an email. No ORM, no fuzzy matching.

A number format is never written here. It is built from an ``ir.sequence``
definition (prefix, suffix, padding) that the caller reads from the database:

* ``plasticos.transaction``  plasticos_transaction/data/sequence.xml:8-9  ``SM-%(y)s-`` + 5 digits
* ``plasticos.load``         plasticos_logistics/data/sequence.xml:7-8    ``LD-%(y)s-`` + 5 digits
* ``sale.order``             native sale/data/ir_sequence_data.xml:7-8    ``S`` + 5 digits
* ``purchase.order``         native purchase/data/purchase_data.xml:25-26 ``P`` + 5 digits
* ``stock.picking``          the outgoing picking type's own sequence (warehouse code + ``/OUT/``)

A sequence whose prefix or suffix uses a placeholder this module does not know
yields no pattern. A sequence with no literal prefix yields no pattern: a bare
number is not a reference.
"""

import re

from lxml import html as lxml_html

# ir.sequence interpolation keys (odoo/addons/base/models/ir_sequence.py
# ``_get_prefix_suffix``) and the digit count strftime produces for each.
_PLACEHOLDER_DIGITS = dict(
    (
        ("year", 4),
        ("isoyear", 4),
        ("doy", 3),
        ("weekday", 1),
        ("month", 2),
        ("day", 2),
        ("y", 2),
        ("isoy", 2),
        ("woy", 2),
        ("isoweek", 2),
        ("h24", 2),
        ("h12", 2),
        ("min", 2),
        ("sec", 2),
    )
)
_PLACEHOLDER_RE = re.compile(r"%\((?:range_|current_)?([a-z0-9]+)\)s")
_ANY_PERCENT_RE = re.compile(r"%(?!%)")

_QUOTE_MARKERS = (
    re.compile(r"^\s*-{2,}\s*Original Message\s*-{2,}\s*$", re.IGNORECASE),
    re.compile(r"^\s*-{2,}\s*Forwarded message\s*-{2,}\s*$", re.IGNORECASE),
    re.compile(r"^\s*Begin forwarded message:\s*$", re.IGNORECASE),
    re.compile(r"^\s*On .{1,300} wrote:\s*$"),
)
_HEADER_FROM_RE = re.compile(r"^\s*From:\s+\S")
_HEADER_SENT_RE = re.compile(r"^\s*(Sent|Date):\s+\S")
# Outlook marks the start of the older message with one of these element ids.
_OUTLOOK_HEADER_IDS = frozenset(("divRplyFwdMsg", "appendonsend"))
_QUOTE_XPATH = (
    "//blockquote"
    " | //*[contains(concat(' ', normalize-space(@class), ' '), ' gmail_quote ')]"
    " | //*[@id='divRplyFwdMsg']"
    " | //*[@id='appendonsend']"
)


def _affix_regex(text):
    """Regex source for one prefix or suffix. None when it cannot be built exactly."""
    out = []
    position = 0
    for found in _PLACEHOLDER_RE.finditer(text):
        literal = text[position : found.start()]
        if _ANY_PERCENT_RE.search(literal.replace("%%", "")):
            return None
        digits = _PLACEHOLDER_DIGITS.get(found.group(1))
        if digits is None:
            return None
        out.append(re.escape(literal.replace("%%", "%")))
        out.append(rf"\d{{{digits}}}")
        position = found.end()
    tail = text[position:]
    if _ANY_PERCENT_RE.search(tail.replace("%%", "")):
        return None
    out.append(re.escape(tail.replace("%%", "%")))
    return "".join(out)


def number_pattern(prefix, suffix, padding):
    """Compiled exact-format pattern for one sequence, or None.

    ``padding`` is the minimum digit count: a sequence past 99999 keeps counting.
    """
    prefix = prefix or ""
    suffix = suffix or ""
    if not _PLACEHOLDER_RE.sub("", prefix).replace("%%", "%").strip():
        return None
    head = _affix_regex(prefix)
    tail = _affix_regex(suffix)
    if head is None or tail is None:
        return None
    digits = max(int(padding or 0), 1)
    return re.compile(r"(?<![A-Za-z0-9])" + head + rf"\d{{{digits},}}" + tail + r"(?![A-Za-z0-9])")


def extract_tokens(text, patterns):
    """Ordered, de-duplicated ``(model, token)`` pairs found in ``text``.

    ``patterns`` is an iterable of ``(model, compiled_pattern)``.
    """
    found = []
    seen = set()
    if not text:
        return found
    for model, pattern in patterns:
        for match in pattern.finditer(text):
            pair = (model, match.group(0))
            if pair not in seen:
                seen.add(pair)
                found.append(pair)
    return found


def _split_text(text):
    fresh = []
    quoted = []
    lines = (text or "").splitlines()
    for index, line in enumerate(lines):
        cut = any(marker.match(line) for marker in _QUOTE_MARKERS)
        if not cut and _HEADER_FROM_RE.match(line):
            cut = any(_HEADER_SENT_RE.match(following) for following in lines[index + 1 : index + 6])
        if cut:
            quoted.extend(lines[index:])
            break
        if line.lstrip().startswith(">"):
            quoted.append(line)
        else:
            fresh.append(line)
    return "\n".join(fresh), "\n".join(quoted)


def split_email_body(body):
    """``(fresh_text, quoted_text)`` for an HTML or plain-text email body.

    Quoted text is a reply or forward of an older message: ``<blockquote>``,
    the Gmail and Outlook quote containers, ``>`` lines, and everything after a
    reply or forward header line.
    """
    if not body or not body.strip():
        return "", ""
    quoted_parts = []
    text = body
    if "<" in body and ">" in body:
        try:
            root = lxml_html.fromstring(f"<div>{body}</div>")
        except (ValueError, lxml_html.etree.ParserError):
            root = None
        if root is not None:
            for node in root.xpath(_QUOTE_XPATH):
                if node.getparent() is None:
                    continue
                quoted_parts.append(node.text_content())
                # Outlook puts the older message after its header block, not inside it.
                if node.get("id") in _OUTLOOK_HEADER_IDS:
                    for sibling in list(node.itersiblings()):
                        quoted_parts.append(sibling.text_content())
                        sibling.drop_tree()
                node.drop_tree()
            for breaker in root.xpath("//br"):
                breaker.tail = "\n" + (breaker.tail or "")
            for block in root.xpath("//p | //div | //tr | //li"):
                block.tail = "\n" + (block.tail or "")
            text = root.text_content()
    fresh, quoted_text = _split_text(text)
    quoted_parts.append(quoted_text)
    return fresh, "\n".join(part for part in quoted_parts if part)
