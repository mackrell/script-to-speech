"""
Voice resolver for the Script-to-Speech CLI.

Handles:
- Fetching available voices from ElevenLabs
- Resolving voice names/IDs from script header mappings
- Interactive voice selection for unmapped speakers
"""

import re
import sys
from elevenlabs import ElevenLabs


def get_client(api_key: str) -> ElevenLabs:
    """Create an ElevenLabs client."""
    return ElevenLabs(api_key=api_key)


def fetch_voices(client: ElevenLabs) -> list[dict]:
    """
    Fetch all available voices from ElevenLabs.

    Returns:
        List of dicts with 'voice_id', 'name', and 'category' keys.
    """
    response = client.voices.get_all()
    voices = []
    for voice in response.voices:
        voices.append({
            "voice_id": voice.voice_id,
            "name": voice.name,
            "category": getattr(voice, "category", "unknown"),
        })
    return sorted(voices, key=lambda v: v["name"].lower())


def print_voices(voices: list[dict]) -> None:
    """Print a formatted list of available voices."""
    print(f"\nAvailable voices ({len(voices)}):\n")
    max_name_len = max(len(v["name"]) for v in voices) if voices else 10
    for v in voices:
        print(f"  {v['name']:<{max_name_len}}  {v['category']:<12}  {v['voice_id']}")
    print()


def _parse_voice_value(value: str) -> tuple[str | None, str | None]:
    """
    Parse a voice mapping value from the script header.

    Supports two formats:
        - "Rachel"                           -> (name="Rachel", voice_id=None)
        - "Adam Stone (auq43ws1oslv0tO4BDa7)" -> (name="Adam Stone", voice_id="auq43ws1oslv0tO4BDa7")

    Returns:
        (name_or_none, voice_id_or_none)
    """
    match = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", value)
    if match:
        name = match.group(1).strip()
        voice_id = match.group(2).strip()
        return name, voice_id
    return value.strip(), None


def resolve_voice(value: str, voices: list[dict]) -> str:
    """
    Resolve a voice mapping value to a voice_id.

    If the value contains an explicit ID in parentheses, use it directly.
    Otherwise, search available voices by name (case-insensitive).

    Args:
        value: Voice mapping value (e.g. "Rachel" or "Adam Stone (abc123)")
        voices: List of available voice dicts.

    Returns:
        The resolved voice_id.

    Raises:
        ValueError: If the voice name can't be matched.
    """
    name, explicit_id = _parse_voice_value(value)

    if explicit_id:
        return explicit_id

    # Search by name (case-insensitive)
    name_lower = name.lower()
    for voice in voices:
        if voice["name"].lower() == name_lower:
            return voice["voice_id"]

    # Try partial match
    partial_matches = [v for v in voices if name_lower in v["name"].lower()]
    if len(partial_matches) == 1:
        match = partial_matches[0]
        print(f"  Matched '{name}' to '{match['name']}' (partial match)", file=sys.stderr)
        return match["voice_id"]

    # No match found
    suggestion = ""
    if partial_matches:
        names = ", ".join(v["name"] for v in partial_matches[:5])
        suggestion = f" Partial matches: {names}"
    raise ValueError(
        f"Voice '{name}' not found among available voices.{suggestion}\n"
        f"Use --list-voices to see all available voices."
    )


def interactive_select(speaker: str, voices: list[dict]) -> str:
    """
    Prompt the user to select a voice for a speaker interactively.

    Args:
        speaker: The speaker name to assign a voice to.
        voices: List of available voice dicts.

    Returns:
        The selected voice_id.
    """
    print(f"\n  Select a voice for '{speaker}':")
    for i, voice in enumerate(voices, 1):
        print(f"    {i:3d}) {voice['name']} ({voice['category']})")

    while True:
        try:
            choice = input(f"  Enter number (1-{len(voices)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(voices):
                selected = voices[idx]
                print(f"  {speaker} -> {selected['name']}")
                return selected["voice_id"]
            else:
                print(f"  Please enter a number between 1 and {len(voices)}.")
        except ValueError:
            print(f"  Please enter a valid number.")
        except (EOFError, KeyboardInterrupt):
            print("\n  Aborted.")
            sys.exit(1)


def resolve_all_voices(
    speakers: list[str],
    voice_map: dict[str, str],
    voices: list[dict],
) -> dict[str, str]:
    """
    Resolve voice_ids for all speakers in the script.

    Uses pre-defined mappings from the script header where available,
    falling back to interactive selection for unmapped speakers.

    Args:
        speakers: List of unique speaker names from the script.
        voice_map: Dict of {speaker_lower: voice_value} from the script header.
        voices: List of available voice dicts from ElevenLabs.

    Returns:
        Dict of {speaker_name: voice_id} for every speaker.
    """
    resolved = {}

    for speaker in speakers:
        speaker_key = speaker.lower()

        if speaker_key in voice_map:
            value = voice_map[speaker_key]
            try:
                voice_id = resolve_voice(value, voices)
                name, explicit_id = _parse_voice_value(value)
                source = "from script header"
                if explicit_id:
                    source += ", explicit ID"
                print(f"  {speaker} -> {name} ({source})")
                resolved[speaker] = voice_id
            except ValueError as e:
                print(f"  Error resolving voice for '{speaker}': {e}", file=sys.stderr)
                print(f"  Falling back to interactive selection.", file=sys.stderr)
                resolved[speaker] = interactive_select(speaker, voices)
        else:
            resolved[speaker] = interactive_select(speaker, voices)

    return resolved
