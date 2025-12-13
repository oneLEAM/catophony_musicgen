import json
import os
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

APP_VERSION = "0.1.1b"

AVAILABLE_MODELS = ["facebook/musicgen-small", "facebook/musicgen-medium", "facebook/musicgen-large"]

OS = "Linux" # Write there "Windows" instead of "Linux" if you use it

if OS == "Linux":
    CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".local", "share", "catophony", "config")
    MODELS_DIR = os.path.join(os.path.expanduser("~"), ".local", "share", "catophony", "models")
elif OS == "Windows":
    CONFIG_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "catophony", "config")
    MODELS_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "catophony", "models")
else:
    raise ValueError("constant OS must be \"Linux\" or \"Windows\"")

Path(CONFIG_DIR).mkdir(parents=True, exist_ok=True)
Path(MODELS_DIR).mkdir(parents=True, exist_ok=True)

if not Path(os.path.join(CONFIG_DIR, "settings.json")).exists():
    Path(os.path.join(CONFIG_DIR, "settings.json")).touch()
    default_settings = {"music_model": "facebook/musicgen-small"}
    
    with open(os.path.join(CONFIG_DIR, "settings.json"), "w", encoding="utf-8") as json_file:
        json.dump(default_settings, json_file, indent=4, ensure_ascii=False)

with open(os.path.join(CONFIG_DIR, "settings.json"), "r", encoding="utf-8") as json_file:
    music_model = json.load(json_file)["music_model"]
    if music_model in AVAILABLE_MODELS:
        MUSIC_MODEL = music_model
    else:
        raise ValueError(f"constant MUSIC_MODEL must be in {AVAILABLE_MODELS}")

TEXT_MODEL = "Qwen/Qwen3-1.7B"

with open(os.path.join(BASE_DIR, "fake_logs.json"), "r", encoding="utf-8") as json_file:
    FAKE_LOGS = json.load(json_file)["fake_logs"]
    if not isinstance(FAKE_LOGS, list):
        raise ValueError(f"constant FAKE_LOGS must be a list type, not a {type(FAKE_LOGS)}")

REFINE_PROMPT = """You are an expert prompt engineer for text-to-music models such as Facebook MusicGen. Your task is to rewrite the user's input into a single, clear, production-ready music description in English that can be used directly as a prompt for a text-to-music model.

Guidelines:
- Preserve the original idea, style, and mood; do not change the genre or emotional intent.
- Make the description more specific: mention genre and subgenre, mood adjectives, main instruments, approximate tempo (BPM or “slow / medium / fast”), rhythm or groove, sound design and production style (for example: “lo‑fi”, “cinematic”, “orchestral”, “EDM”, “retro 8‑bit”).
- If the user mentions a reference artist, band, track, game, film, or era, keep that reference but do not invent new ones.
- If the user does not clearly ask for vocals, assume the track is instrumental and explicitly say “instrumental, no vocals”. If they ask for vocals, briefly describe the vocal type and language.
- Avoid vague words like “cool”, “nice”, “epic” without context; replace them with precise musical terms.
- The final answer must be 1–3 sentences, with no bullet points, no explanations, no quotation marks, and no extra commentary. Output only the improved prompt.
"""

TRANSLATE_PROMPT = """You are a translator specialized in prompts for text-to-music models. The user will give you a prompt in any language.

Your task:
- Translate the prompt into natural, neutral English while preserving the musical meaning, mood, genre, and all important details.
- Do not change the user’s intent and do not add new instruments, genres, or references that are not present in the original text.
- You may slightly reorder words if needed to sound natural in English, but do not significantly shorten or expand the content.
- Output only the translated prompt in English, with no explanations, notes, or the original text.
"""