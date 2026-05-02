"""
TTS engine for the Script-to-Speech CLI.

Wraps ElevenLabs text-to-speech API calls with retry/backoff logic
and progress reporting.
"""

import io
import sys
import time
from elevenlabs import ElevenLabs


DEFAULT_MODEL = "eleven_v3"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"
MAX_RETRIES = 5
BASE_DELAY = 1.0  # seconds
INTER_REQUEST_DELAY = 0.3  # seconds between sequential requests


def generate_segment(
    client: ElevenLabs,
    text: str,
    voice_id: str,
    model_id: str = DEFAULT_MODEL,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
) -> bytes:
    """
    Generate TTS audio for a single text segment.

    Args:
        client: ElevenLabs client instance.
        text: The text to convert to speech.
        voice_id: The ElevenLabs voice ID to use.
        model_id: The model to use for generation.
        output_format: Audio output format.

    Returns:
        MP3 audio bytes.

    Raises:
        RuntimeError: If all retries are exhausted.
    """
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            audio_generator = client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id=model_id,
                output_format=output_format,
            )

            # Collect bytes from the generator
            audio_bytes = b""
            for chunk in audio_generator:
                audio_bytes += chunk

            return audio_bytes

        except Exception as e:
            last_error = e
            error_str = str(e).lower()

            # Check for rate limit errors
            if "429" in str(e) or "too_many" in error_str or "rate" in error_str:
                delay = BASE_DELAY * (2 ** attempt)
                print(f"  Rate limited. Retrying in {delay:.1f}s "
                      f"(attempt {attempt + 1}/{MAX_RETRIES})...",
                      file=sys.stderr)
                time.sleep(delay)
                continue

            # Check for transient server errors
            if "500" in str(e) or "502" in str(e) or "503" in str(e):
                delay = BASE_DELAY * (2 ** attempt)
                print(f"  Server error. Retrying in {delay:.1f}s "
                      f"(attempt {attempt + 1}/{MAX_RETRIES})...",
                      file=sys.stderr)
                time.sleep(delay)
                continue

            # Non-retryable error
            raise

    raise RuntimeError(
        f"Failed to generate audio after {MAX_RETRIES} attempts. "
        f"Last error: {last_error}"
    )


def generate_all_segments(
    client: ElevenLabs,
    segments: list[tuple[str, str]],
    voice_mapping: dict[str, str],
    model_id: str = DEFAULT_MODEL,
) -> list[bytes]:
    """
    Generate TTS audio for all dialogue segments.

    Args:
        client: ElevenLabs client instance.
        segments: List of (speaker_name, dialogue_text) tuples.
        voice_mapping: Dict of {speaker_name: voice_id}.
        model_id: The model to use for generation.

    Returns:
        List of MP3 audio bytes, one per segment.
    """
    total = len(segments)
    audio_segments = []

    print(f"\nGenerating audio for {total} segments...")

    for i, (speaker, text) in enumerate(segments, 1):
        voice_id = voice_mapping[speaker]

        # Progress indicator
        bar_width = 30
        filled = int(bar_width * i / total)
        bar = "█" * filled + "░" * (bar_width - filled)
        preview = text[:40] + "..." if len(text) > 40 else text
        print(f"\r  [{bar}] {i}/{total} {speaker}: {preview}", end="", flush=True)

        audio_bytes = generate_segment(client, text, voice_id, model_id)
        audio_segments.append(audio_bytes)

        # Small delay between requests to avoid hitting concurrency limits
        if i < total:
            time.sleep(INTER_REQUEST_DELAY)

    print()  # Newline after progress bar
    return audio_segments
