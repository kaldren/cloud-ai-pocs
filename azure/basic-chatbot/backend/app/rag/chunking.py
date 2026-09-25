"""Markdown-aware chunking by token count.

The document is split into blocks (paragraphs, tables, lists, headings), which are packed into
chunks of at most `max_tokens`. Consecutive chunks within a section share up to `overlap_tokens`
of trailing blocks. A chunk that starts mid-section is prefixed with its section path, so every
chunk carries its own context.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

import tiktoken

# The tokenizer used by the text-embedding-3 models.
ENCODING_NAME = "cl100k_base"
DEFAULT_MAX_TOKENS = 500
DEFAULT_OVERLAP_TOKENS = 75

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


@lru_cache(maxsize=1)
def get_encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(ENCODING_NAME)


def count_tokens(text: str) -> int:
    return len(get_encoding().encode(text))


@dataclass(frozen=True)
class Block:
    text: str
    section: str  # heading path in effect, e.g. "4. Time Off and Leave > 4.1 Annual leave"
    tokens: int
    is_heading: bool = False


def extract_title(markdown: str) -> str | None:
    """The text of the first level-1 heading, if any."""
    for line in markdown.splitlines():
        match = _HEADING.match(line)
        if match and len(match.group(1)) == 1:
            return match.group(2)
    return None


def split_blocks(markdown: str) -> list[Block]:
    """Blank-line separated blocks; each heading is its own block. The H1 is not part of paths."""
    blocks: list[Block] = []
    stack: list[tuple[int, str]] = []
    lines: list[str] = []

    def section() -> str:
        return " > ".join(text for level, text in stack if level > 1)

    def flush() -> None:
        text = "\n".join(lines).strip()
        lines.clear()
        if text:
            blocks.append(Block(text=text, section=section(), tokens=count_tokens(text)))

    for line in markdown.splitlines():
        match = _HEADING.match(line)
        if match:
            flush()
            level = len(match.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, match.group(2)))
            heading = line.strip()
            blocks.append(
                Block(
                    text=heading, section=section(), tokens=count_tokens(heading), is_heading=True
                )
            )
        elif line.strip():
            lines.append(line)
        else:
            flush()
    flush()
    return blocks


def _split_oversized(block: Block, limit: int) -> list[Block]:
    """Hard-split a block longer than `limit` tokens into token windows."""
    if block.tokens <= limit:
        return [block]
    encoding = get_encoding()
    ids = encoding.encode(block.text)
    parts: list[Block] = []
    for start in range(0, len(ids), limit):
        window = ids[start : start + limit]
        parts.append(Block(text=encoding.decode(window), section=block.section, tokens=len(window)))
    return parts


def _render(blocks: list[Block]) -> str:
    body = "\n\n".join(block.text for block in blocks)
    first = blocks[0]
    if first.is_heading or not first.section:
        return body
    return f"Section: {first.section}\n\n{body}"


def chunk_markdown(
    markdown: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[str]:
    """Split markdown into chunks of about `max_tokens` with `overlap_tokens` of overlap."""
    if max_tokens <= 0 or not 0 <= overlap_tokens < max_tokens:
        raise ValueError("need max_tokens > 0 and 0 <= overlap_tokens < max_tokens")

    block_limit = max_tokens - overlap_tokens
    blocks = [
        part for block in split_blocks(markdown) for part in _split_oversized(block, block_limit)
    ]

    chunks: list[str] = []
    current: list[Block] = []
    size = 0
    has_new = False  # does `current` hold any block not already emitted?

    for block in blocks:
        if current and has_new and size + block.tokens > max_tokens:
            # Headings at the end of a chunk belong to the next one.
            carried: list[Block] = []
            while current and current[-1].is_heading:
                carried.insert(0, current.pop())
            if current:
                chunks.append(_render(current))
            if not carried and not block.is_heading:
                # Same section continues: overlap with the trailing blocks.
                for previous in reversed(current):
                    if sum(b.tokens for b in carried) + previous.tokens > overlap_tokens:
                        break
                    carried.insert(0, previous)
            current = carried
            size = sum(b.tokens for b in current)
            has_new = any(b.is_heading for b in current)
        current.append(block)
        size += block.tokens
        has_new = True

    if current and has_new:
        chunks.append(_render(current))
    return chunks
