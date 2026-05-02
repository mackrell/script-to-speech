"""
Audio assembler for the Script-to-Speech CLI.

Handles saving audio and concatenating chunks when a script is split
across multiple API calls. Uses ffmpeg for chunk concatenation.
"""

import json
import os
import shutil
import subprocess
import tempfile


def _get_duration(filepath: str) -> float:
    """Get the duration of an audio file in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", filepath,
        ],
        capture_output=True, text=True,
    )
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


def save_audio(
    audio_chunks: list[bytes],
    output_path: str,
) -> float:
    """
    Save audio chunks to a single MP3 file.

    If there's only one chunk, writes it directly. If multiple chunks,
    decodes each to PCM, concatenates, and re-encodes to avoid
    frame-boundary glitches.

    Args:
        audio_chunks: List of MP3 bytes (one per API call chunk).
        output_path: File path for the output MP3.

    Returns:
        Total duration of the final MP3 in seconds.

    Raises:
        ValueError: If no audio chunks are provided.
        RuntimeError: If ffmpeg fails.
    """
    if not audio_chunks:
        raise ValueError("No audio chunks to save.")

    print("Saving audio...")

    if len(audio_chunks) == 1:
        # Single chunk — write directly, no processing needed
        with open(output_path, "wb") as f:
            f.write(audio_chunks[0])
        return _get_duration(output_path)

    # Multiple chunks — decode to PCM, concatenate, re-encode
    SAMPLE_RATE = 44100
    CHANNELS = 2

    combined_pcm = bytearray()

    for mp3_bytes in audio_chunks:
        result = subprocess.run(
            [
                "ffmpeg", "-v", "quiet",
                "-i", "pipe:0",
                "-f", "s16le",
                "-acodec", "pcm_s16le",
                "-ar", str(SAMPLE_RATE),
                "-ac", str(CHANNELS),
                "pipe:1",
            ],
            input=mp3_bytes,
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError("ffmpeg decode failed")
        combined_pcm.extend(result.stdout)

    # Encode combined PCM to MP3
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-v", "quiet",
            "-f", "s16le",
            "-ar", str(SAMPLE_RATE),
            "-ac", str(CHANNELS),
            "-i", "pipe:0",
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            output_path,
        ],
        input=bytes(combined_pcm),
        capture_output=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg encode failed: {result.stderr.decode()}")

    return _get_duration(output_path)


def format_duration(seconds: float) -> str:
    """Format a duration in seconds to a human-readable string."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes > 0:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"
