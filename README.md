# Script-to-Speech CLI

Convert multi-speaker text scripts into MP3 audio using the ElevenLabs API.

## Setup

**Prerequisites:** Python 3.10+ and [ffmpeg](https://ffmpeg.org/) (`brew install ffmpeg`).

```bash
cd script-to-speech
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your ElevenLabs API key:

```bash
cp .env.example .env
# Edit .env and replace your_key_here with your actual key
```

## Script Format

Write your script as a plain `.txt` file with `Speaker: Dialogue` lines:

```
Alice: Welcome to the show, everyone.
Bob: Thanks for having me, Alice.
```

Blank lines and `#` comments are ignored.

### Voice Mapping (optional)

Add a `---` header block to map speakers to ElevenLabs voices:

```
---
Alice = Rachel
Bob = Adam Stone (auq43ws1oslv0tO4BDa7)
---
Alice: Welcome to the show.
Bob: Glad to be here.
```

Voices can be specified by name or by name with an explicit voice ID in parentheses. Any unmapped speakers will trigger an interactive voice selection prompt.

## Usage

```bash
# List available voices
python script_to_speech.py --list-voices

# Preview without generating audio
python script_to_speech.py my_script.txt --dry-run

# Generate audio
python script_to_speech.py my_script.txt -o output.mp3

# Custom gap between segments (milliseconds)
python script_to_speech.py my_script.txt -o output.mp3 --gap 500

# Use a specific model
python script_to_speech.py my_script.txt --model eleven_v3
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `-o`, `--output` | `output.mp3` | Output file path |
| `--gap` | `300` | Silence between segments (ms) |
| `--model` | `eleven_v3` | ElevenLabs model ID |
| `--list-voices` | — | List voices and exit |
| `--dry-run` | — | Show plan without generating |
