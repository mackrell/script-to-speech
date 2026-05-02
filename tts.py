"""
TTS engine for the Script-to-Speech CLI.

Uses the ElevenLabs text-to-dialogue API to generate multi-speaker
audio in a single call, with automatic chunking for longer scripts.
"""

import sys
import time
from elevenlabs import ElevenLabs, DialogueInput


DEFAULT_MODEL = "eleven_v3"
MAX_CHARS_PER_CHUNK = 1800  # stay under the ~2000 char limit with margin
MAX_VOICES_PER_CHUNK = 10
MAX_RETRIES = 5
BASE_DELAY = 1.0


def _build_chunks(
    segments: list[tuple[str, str]],
    voice_mapping: dict[str, str],
) -> list[list[DialogueInput]]:
    """
    Split dialogue segments into chunks that fit within API limits.

    Each chunk stays under MAX_CHARS_PER_CHUNK total characters and
    MAX_VOICES_PER_CHUNK unique voices.

    Args:
        segments: List of (speaker_name, dialogue_text) tuples.
        voice_mapping: Dict of {speaker_name: voice_id}.

    Returns:
        List of chunks, where each chunk is a list of DialogueInput.
    """
    chunks = []
    current_chunk = []
    current_chars = 0
    current_voices = set()

    for speaker, text in segments:
        voice_id = voice_mapping[speaker]
        text_len = len(text)

        # Check if adding this segment would exceed limits
        new_voices = current_voices | {voice_id}
        would_exceed_chars = (current_chars + text_len) > MAX_CHARS_PER_CHUNK
        would_exceed_voices = len(new_voices) > MAX_VOICES_PER_CHUNK

        if current_chunk and (would_exceed_chars or would_exceed_voices):
            chunks.append(current_chunk)
            current_chunk = []
            current_chars = 0
            current_voices = set()

        current_chunk.append(DialogueInput(text=text, voice_id=voice_id))
        current_chars += text_len
        current_voices.add(voice_id)

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _generate_chunk(
    client: ElevenLabs,
    inputs: list[DialogueInput],
    model_id: str,
) -> bytes:
    """
    Generate audio for a single chunk via the text-to-dialogue API.

    Includes retry logic with exponential backoff.

    Args:
        client: ElevenLabs client instance.
        inputs: List of DialogueInput for this chunk.
        model_id: The model to use.

    Returns:
        MP3 audio bytes.

    Raises:
        RuntimeError: If all retries are exhausted.
    """
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            audio_generator = client.text_to_dialogue.convert(
                inputs=inputs,
                model_id=model_id,
            )

            # Collect bytes from the generator
            audio_bytes = b""
            for chunk in audio_generator:
                audio_bytes += chunk

            return audio_bytes

        except Exception as e:
            last_error = e
            error_str = str(e).lower()

            if "429" in str(e) or "too_many" in error_str or "rate" in error_str:
                delay = BASE_DELAY * (2 ** attempt)
                print(f"  Rate limited. Retrying in {delay:.1f}s "
                      f"(attempt {attempt + 1}/{MAX_RETRIES})...",
                      file=sys.stderr)
                time.sleep(delay)
                continue

            if "500" in str(e) or "502" in str(e) or "503" in str(e):
                delay = BASE_DELAY * (2 ** attempt)
                print(f"  Server error. Retrying in {delay:.1f}s "
                      f"(attempt {attempt + 1}/{MAX_RETRIES})...",
                      file=sys.stderr)
                time.sleep(delay)
                continue

            raise

    raise RuntimeError(
        f"Failed to generate audio after {MAX_RETRIES} attempts. "
        f"Last error: {last_error}"
    )


def generate_dialogue(
    client: ElevenLabs,
    segments: list[tuple[str, str]],
    voice_mapping: dict[str, str],
    model_id: str = DEFAULT_MODEL,
) -> list[bytes]:
    """
    Generate TTS audio for all dialogue segments using text-to-dialogue.

    Automatically chunks the script if it exceeds API limits.

    Args:
        client: ElevenLabs client instance.
        segments: List of (speaker_name, dialogue_text) tuples.
        voice_mapping: Dict of {speaker_name: voice_id}.
        model_id: The model to use.

    Returns:
        List of MP3 audio bytes (one per chunk).
    """
    chunks = _build_chunks(segments, voice_mapping)
    total_segments = len(segments)

    if len(chunks) == 1:
        print(f"\nGenerating dialogue ({total_segments} segments, 1 API call)...")
    else:
        print(f"\nGenerating dialogue ({total_segments} segments, "
              f"{len(chunks)} chunks)...")

    audio_chunks = []

    for i, chunk in enumerate(chunks, 1):
        if len(chunks) > 1:
            print(f"  Chunk {i}/{len(chunks)} "
                  f"({len(chunk)} segments)...", end=" ", flush=True)
        else:
            print(f"  Calling text-to-dialogue API...", end=" ", flush=True)

        audio_bytes = _generate_chunk(client, chunk, model_id)
        audio_chunks.append(audio_bytes)
        print("done.")

    return audio_chunks
