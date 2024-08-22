import whisper
import pyaudio
import os
import numpy as np
import torch
from dotenv import load_dotenv

load_dotenv()

# Check if CUDA is available
device = "cuda" if torch.cuda.is_available() else "cpu"

# Initialize the Whisper model
# Tiny model: ~1 GB VRAM
# Base model: ~2 GB VRAM
# Small model: ~3 GB VRAM
# Medium model: ~5 GB VRAM
# Large model: ~10-12 GB VRAM
model = whisper.load_model("large").to(device)

# PyAudio configuration
CHUNK = 1024
FORMAT = pyaudio.paFloat32
CHANNELS = 1
RATE = 16000

def is_voice_enabled():
    return os.getenv('VOICE_ENABLED', 'false').lower() == 'true'

def listen_for_command():
    if not is_voice_enabled():
        return None

    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print("Listening... (Say your command)")

    frames = []
    for _ in range(0, int(RATE / CHUNK * 5)):  # Record for 5 seconds
        data = stream.read(CHUNK)
        frames.append(data)

    print("Processing...")

    stream.stop_stream()
    stream.close()
    p.terminate()

    audio_data = np.frombuffer(b''.join(frames), dtype=np.float32)
    result = model.transcribe(audio_data)
    
    return result['text'].strip().lower()

def toggle_voice():
    current_state = is_voice_enabled()
    new_state = 'true' if not current_state else 'false'
    
    # Read the current .env file
    with open('.env', 'r') as file:
        lines = file.readlines()
    
    # Update the VOICE_ENABLED line
    for i, line in enumerate(lines):
        if line.startswith('VOICE_ENABLED='):
            lines[i] = f'VOICE_ENABLED={new_state}\n'
            break
    
    # Write the updated content back to .env
    with open('.env', 'w') as file:
        file.writelines(lines)
    
    print(f"Voice recognition {'enabled' if new_state == 'true' else 'disabled'}")