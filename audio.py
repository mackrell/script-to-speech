"""
Audio assembler for the Script-to-Speech CLI.

Uses pydub to concatenate MP3 audio segments into a single output file
with configurable silence gaps between segments.
"""

import io
from pydub import AudioSegment


DEFAULT_GAP_MS = 300


def assemble(
    audio_segments: list[bytes],
    output_path: str,
    gap_ms: int = DEFAULT_GAP_MS,
) -> float:
    """
    Concatenate MP3 audio segments into a single MP3 file.

    Args:
        audio_segments: List of raw MP3 bytes, one per dialogue segment.
        output_path: File path for the output MP3.
        gap_ms: Silence duration in milliseconds between segments.

    Returns:
        Total duration of the final MP3 in seconds.

    Raises:
        ValueError: If no audio segments are provided.
    """
    if not audio_segments:
        raise ValueError("No audio segments to assemble.")

    print("Assembling final MP3...")

    # Create silence gap
    silence = AudioSegment.silent(duration=gap_ms)

    # Load and concatenate segments
    combined = AudioSegment.empty()

    for i, mp3_bytes in enumerate(audio_segments):
        segment = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")

        if i > 0:
            combined += silence

        combined += segment

    # Export
    combined.export(output_path, format="mp3")

    duration_seconds = len(combined) / 1000.0
    return duration_seconds


def format_duration(seconds: float) -> str:
    """Format a duration in seconds to a human-readable string."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes > 0:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"
