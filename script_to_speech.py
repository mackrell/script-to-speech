#!/usr/bin/env python3
"""
Script-to-Speech CLI

Converts a multi-speaker text script into a single MP3 file
using the ElevenLabs text-to-dialogue API.

Usage:
    python script_to_speech.py <script_file> [options]
    python script_to_speech.py --list-voices
"""

import argparse
import os
import sys

from dotenv import load_dotenv

from parser import parse_script
from voices import get_client, fetch_voices, print_voices, resolve_all_voices
from tts import generate_dialogue, DEFAULT_MODEL
from audio import save_audio, format_duration


def get_api_key() -> str:
    """
    Resolve the ElevenLabs API key.

    Checks in order:
    1. ELEVENLABS_API_KEY environment variable
    2. .env file in the current directory

    Returns:
        The API key string.

    Raises:
        SystemExit: If no API key is found.
    """
    # Load .env file if present (doesn't override existing env vars)
    load_dotenv()

    api_key = os.environ.get("ELEVENLABS_API_KEY")

    if not api_key:
        print("Error: No ElevenLabs API key found.\n", file=sys.stderr)
        print("Set it in one of these ways:", file=sys.stderr)
        print("  1. Environment variable: export ELEVENLABS_API_KEY=your_key_here",
              file=sys.stderr)
        print("  2. Create a .env file with: ELEVENLABS_API_KEY=your_key_here",
              file=sys.stderr)
        print("\nSee .env.example for reference.", file=sys.stderr)
        sys.exit(1)

    return api_key


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    p = argparse.ArgumentParser(
        prog="script_to_speech",
        description="Convert a multi-speaker text script into an MP3 using ElevenLabs text-to-dialogue API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python script_to_speech.py script.txt\n"
            "  python script_to_speech.py script.txt -o podcast.mp3\n"
            "  python script_to_speech.py script.txt --dry-run\n"
            "  python script_to_speech.py --list-voices\n"
        ),
    )

    p.add_argument(
        "script_file",
        nargs="?",
        help="Path to the .txt script file",
    )
    p.add_argument(
        "-o", "--output",
        default="output.mp3",
        help="Output MP3 file path (default: output.mp3)",
    )
    p.add_argument(
        "-m", "--model",
        default=DEFAULT_MODEL,
        help=f"ElevenLabs model ID (default: {DEFAULT_MODEL})",
    )
    p.add_argument(
        "-l", "--list-voices",
        action="store_true",
        help="List all available ElevenLabs voices and exit",
    )
    p.add_argument(
        "-d", "--dry-run",
        action="store_true",
        help="Parse the script and show the plan without generating audio",
    )

    return p


def cmd_list_voices(api_key: str) -> None:
    """List available voices and exit."""
    client = get_client(api_key)
    print("Fetching voices from ElevenLabs...")
    voices = fetch_voices(client)
    print_voices(voices)


def cmd_dry_run(args, api_key: str) -> None:
    """Parse script, resolve voices, and print the plan without calling TTS."""
    # Parse
    print(f"Parsing script: {args.script_file}")
    result = parse_script(args.script_file)

    print(f"  Found {len(result.speakers)} speaker(s): {', '.join(result.speakers)}")
    print(f"  Found {len(result.segments)} dialogue segment(s)")

    if result.voice_map:
        print(f"  Voice mappings from header: {len(result.voice_map)}")

    # Resolve voices
    print("\nResolving voices...")
    client = get_client(api_key)
    voices = fetch_voices(client)
    voice_mapping = resolve_all_voices(result.speakers, result.voice_map, voices)

    # Estimate chunking
    total_chars = sum(len(text) for _, text in result.segments)

    # Print plan
    print(f"\n--- Dry Run Summary ---")
    print(f"Script:    {args.script_file}")
    print(f"Output:    {args.output}")
    print(f"Model:     {args.model}")
    print(f"API:       text-to-dialogue")
    print(f"Segments:  {len(result.segments)}")
    print(f"Total characters: {total_chars}")

    print(f"\nVoice assignments:")
    for speaker in result.speakers:
        voice_id = voice_mapping[speaker]
        voice_name = next(
            (v["name"] for v in voices if v["voice_id"] == voice_id),
            voice_id
        )
        print(f"  {speaker} -> {voice_name} ({voice_id})")

    print(f"\nSegment breakdown:")
    for i, (speaker, text) in enumerate(result.segments, 1):
        preview = text[:60] + "..." if len(text) > 60 else text
        print(f"  {i:3d}. [{speaker}] {preview}")

    print(f"\nDry run complete. No audio was generated.")


def cmd_generate(args, api_key: str) -> None:
    """Full generation pipeline: parse -> resolve -> TTS -> save."""
    # Parse
    print(f"Parsing script: {args.script_file}")
    result = parse_script(args.script_file)

    print(f"  Found {len(result.speakers)} speaker(s): {', '.join(result.speakers)}")
    print(f"  Found {len(result.segments)} dialogue segment(s)")

    # Resolve voices
    print("\nMapping voices...")
    client = get_client(api_key)
    voices = fetch_voices(client)
    voice_mapping = resolve_all_voices(result.speakers, result.voice_map, voices)

    # Generate via text-to-dialogue API
    audio_chunks = generate_dialogue(
        client=client,
        segments=result.segments,
        voice_mapping=voice_mapping,
        model_id=args.model,
    )

    # Save output
    duration = save_audio(audio_chunks, args.output)

    # Summary
    print(f"\nDone! Saved to {args.output} "
          f"({format_duration(duration)}, {len(result.segments)} segments)")


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Handle --list-voices (no script file required)
    if args.list_voices:
        api_key = get_api_key()
        cmd_list_voices(api_key)
        return

    # All other commands require a script file
    if not args.script_file:
        parser.error("the following arguments are required: script_file")

    api_key = get_api_key()

    if args.dry_run:
        cmd_dry_run(args, api_key)
    else:
        cmd_generate(args, api_key)


if __name__ == "__main__":
    main()
