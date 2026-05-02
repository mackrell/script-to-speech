"""
Script parser for the Script-to-Speech CLI.

Reads a .txt script file and extracts:
- An optional voice mapping header (enclosed in --- fences)
- Dialogue segments as (speaker_name, dialogue_text) pairs
"""

import re
import sys
from dataclasses import dataclass, field


@dataclass
class ParseResult:
    """Result of parsing a script file."""
    voice_map: dict[str, str] = field(default_factory=dict)
    segments: list[tuple[str, str]] = field(default_factory=list)
    speakers: list[str] = field(default_factory=list)


def _parse_header(lines: list[str]) -> tuple[dict[str, str], int]:
    """
    Extract the optional --- header block from the top of the file.

    Returns:
        A tuple of (voice_map dict, index of first line after header).
        If no header is found, returns ({}, 0).
    """
    if not lines or lines[0].strip() != "---":
        return {}, 0

    voice_map = {}
    end_index = 0

    for i, line in enumerate(lines[1:], start=1):
        stripped = line.strip()
        if stripped == "---":
            end_index = i + 1
            break

        # Skip blank lines and comments in the header
        if not stripped or stripped.startswith("#"):
            continue

        if "=" in stripped:
            speaker, voice_value = stripped.split("=", 1)
            speaker = speaker.strip()
            voice_value = voice_value.strip()
            if speaker and voice_value:
                voice_map[speaker.lower()] = voice_value
        else:
            print(f"Warning: Ignoring invalid header line: {stripped}",
                  file=sys.stderr)
            print(f"  Voice mappings must use '=' (e.g. Alice = Rachel)",
                  file=sys.stderr)
    else:
        # No closing --- found; treat entire content as dialogue (no header)
        print("Warning: Opening '---' found but no closing '---'. "
              "Treating entire file as dialogue.", file=sys.stderr)
        return {}, 0

    return voice_map, end_index


def _parse_dialogue_line(line: str) -> tuple[str, str] | None:
    """
    Parse a single dialogue line in 'Speaker: Text' format.

    Returns:
        (speaker_name, dialogue_text) or None if the line isn't valid dialogue.
    """
    if ":" not in line:
        return None

    speaker, text = line.split(":", 1)
    speaker = speaker.strip()
    text = text.strip()

    if not speaker or not text:
        return None

    # Reject speaker names that look like they contain dialogue punctuation
    # (e.g., a line that's just a sentence with a colon in it)
    if " " in speaker and len(speaker.split()) > 4:
        return None

    return speaker, text


def parse_script(filepath: str) -> ParseResult:
    """
    Parse a script file into voice mappings and dialogue segments.

    Args:
        filepath: Path to the .txt script file.

    Returns:
        ParseResult with voice_map, segments, and unique speakers list.

    Raises:
        FileNotFoundError: If the script file doesn't exist.
        ValueError: If the script contains no valid dialogue lines.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Strip trailing newlines
    lines = [line.rstrip("\n") for line in lines]

    # Parse optional header
    voice_map, start_index = _parse_header(lines)

    # Parse dialogue lines
    segments = []
    speakers_seen = {}
    speakers_ordered = []

    for line_num, line in enumerate(lines[start_index:], start=start_index + 1):
        stripped = line.strip()

        # Skip blank lines
        if not stripped:
            continue

        # Skip comments
        if stripped.startswith("#"):
            continue

        # Try to parse as dialogue
        result = _parse_dialogue_line(stripped)
        if result is None:
            print(f"Warning: Skipping unparseable line {line_num}: {stripped[:60]}",
                  file=sys.stderr)
            continue

        speaker, text = result
        segments.append((speaker, text))

        # Track unique speakers in order of first appearance
        speaker_key = speaker.lower()
        if speaker_key not in speakers_seen:
            speakers_seen[speaker_key] = speaker
            speakers_ordered.append(speaker)

    if not segments:
        raise ValueError(f"No valid dialogue lines found in '{filepath}'.")

    return ParseResult(
        voice_map=voice_map,
        segments=segments,
        speakers=speakers_ordered,
    )
