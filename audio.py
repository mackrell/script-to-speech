"""
Audio assembler for the Script-to-Speech CLI.

Uses ffmpeg to decode all segments to raw PCM, concatenate with silence
gaps, and re-encode to MP3 in a single pass. This avoids MP3 frame
alignment glitches that occur with the concat demuxer.
"""

import json
import os
import subprocess
import shutil
import struct
import tempfile


DEFAULT_GAP_MS = 300
SAMPLE_RATE = 44100
CHANNELS = 2
SAMPLE_WIDTH = 2  # 16-bit


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


def _mp3_to_pcm(mp3_bytes: bytes) -> bytes:
    """Decode MP3 bytes to raw PCM (s16le, 44100Hz, stereo) using ffmpeg."""
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
    return result.stdout


def _generate_silence_pcm(duration_ms: int) -> bytes:
    """Generate raw PCM silence bytes for a given duration."""
    num_samples = int(SAMPLE_RATE * duration_ms / 1000) * CHANNELS
    return b"\x00\x00" * num_samples


def _trim_silence(samples: list[int], threshold: int = 80) -> list[int]:
    """
    Trim leading and trailing near-silent samples from a PCM sample list.

    Looks at sample frames (pairs for stereo) and trims from both ends
    where the absolute sample value stays below the threshold. This removes
    tiny noise bursts that ElevenLabs sometimes adds at segment edges.

    Args:
        samples: List of 16-bit signed PCM samples (interleaved stereo).
        threshold: Amplitude below which samples are considered silent.

    Returns:
        Trimmed sample list.
    """
    frame_size = CHANNELS  # samples per frame

    # Find first non-silent frame
    start = 0
    for i in range(0, len(samples) - frame_size + 1, frame_size):
        frame = samples[i:i + frame_size]
        if any(abs(s) > threshold for s in frame):
            start = i
            break

    # Find last non-silent frame
    end = len(samples)
    for i in range(len(samples) - frame_size, -1, -frame_size):
        frame = samples[i:i + frame_size]
        if any(abs(s) > threshold for s in frame):
            end = i + frame_size
            break

    return samples[start:end]


def _apply_fade(pcm: bytes, fade_ms: int = 30) -> bytes:
    """
    Trim silence and apply a linear fade-in/fade-out to a PCM segment.

    Trims any near-silent noise at the edges, then applies fades to
    eliminate clicks or artifacts at the start/end of TTS audio.

    Args:
        pcm: Raw PCM bytes (s16le, stereo).
        fade_ms: Fade duration in milliseconds.

    Returns:
        PCM bytes, trimmed and faded.
    """
    samples = list(struct.unpack(f"<{len(pcm) // 2}h", pcm))

    # Trim leading/trailing noise
    samples = _trim_silence(samples)

    if not samples:
        return b""

    fade_samples = int(SAMPLE_RATE * fade_ms / 1000) * CHANNELS
    fade_samples = min(fade_samples, len(samples) // 2)

    # Fade in
    for i in range(fade_samples):
        factor = i / fade_samples
        samples[i] = int(samples[i] * factor)

    # Fade out
    for i in range(fade_samples):
        factor = i / fade_samples
        samples[-(i + 1)] = int(samples[-(i + 1)] * factor)

    return struct.pack(f"<{len(samples)}h", *samples)


def assemble(
    audio_segments: list[bytes],
    output_path: str,
    gap_ms: int = DEFAULT_GAP_MS,
) -> float:
    """
    Concatenate MP3 audio segments into a single MP3 file.

    Decodes all segments to raw PCM, concatenates with silence gaps,
    then re-encodes to MP3 in one pass. This eliminates frame-boundary
    glitches.

    Args:
        audio_segments: List of raw MP3 bytes, one per dialogue segment.
        output_path: File path for the output MP3.
        gap_ms: Silence duration in milliseconds between segments.

    Returns:
        Total duration of the final MP3 in seconds.

    Raises:
        ValueError: If no audio segments are provided.
        RuntimeError: If ffmpeg fails.
    """
    if not audio_segments:
        raise ValueError("No audio segments to assemble.")

    print("Assembling final MP3...")

    # Decode all segments to PCM and apply fades
    pcm_segments = []
    for i, mp3_bytes in enumerate(audio_segments):
        pcm = _mp3_to_pcm(mp3_bytes)
        pcm = _apply_fade(pcm)
        pcm_segments.append(pcm)

    # Build combined PCM with silence gaps
    silence = _generate_silence_pcm(gap_ms)
    combined_pcm = bytearray()

    for i, pcm in enumerate(pcm_segments):
        if i > 0:
            combined_pcm.extend(silence)
        combined_pcm.extend(pcm)

    # Encode combined PCM to MP3 in a single pass
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

    duration = _get_duration(output_path)
    return duration


def format_duration(seconds: float) -> str:
    """Format a duration in seconds to a human-readable string."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes > 0:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"
