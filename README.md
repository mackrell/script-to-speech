# Script-to-Speech CLI

Convert multi-speaker text scripts into MP3 audio using the ElevenLabs text-to-dialogue API.

## Setup

**Prerequisites:** Python 3.10+ and [ffmpeg](https://ffmpeg.org/) (`brew install ffmpeg`).

```bash
cd script-to-speech
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your ElevenLabs API key:

```bash
cp .env.example .env
# Edit .env and replace your_key_here with your actual key
```

Your API key needs **Text to Speech** (Access) and **Voices** (Read) permissions.

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
python script_to_speech.py -l

# Preview without generating audio
python script_to_speech.py my_script.txt -d

# Generate audio
python script_to_speech.py my_script.txt -o output.mp3

# Use a specific model
python script_to_speech.py my_script.txt -m eleven_v3
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `-o`, `--output` | `output.mp3` | Output file path |
| `-m`, `--model` | `eleven_v3` | ElevenLabs model ID |
| `-l`, `--list-voices` | — | List voices and exit |
| `-d`, `--dry-run` | — | Show plan without generating |

## How It Works

The app uses the ElevenLabs **text-to-dialogue** API, which handles multiple speakers in a single API call with natural speaker transitions and pacing. For longer scripts (over ~1800 characters), the script is automatically split into chunks and the resulting audio is seamlessly joined.

## API Limits

- ~2,000 characters per API call (the app chunks automatically)
- Up to 10 unique voices per call
- Concurrency limits vary by ElevenLabs plan
