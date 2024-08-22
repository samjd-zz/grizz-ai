import whisper
import pyaudio
import numpy as np
import torch
from config import load_config

# Load configuration
config = load_config()

# Initialize the Whisper model
# Tiny model: ~1 GB VRAM
# Base model: ~2 GB VRAM
# Small model: ~3 GB VRAM
# Medium model: ~5 GB VRAM
# Large model: ~10-12 GB VRAM
whisper_model = whisper.load_model(api_key = config.WHISPER_MODEL_SIZE, device="cuda" if torch.cuda.is_available() else "cpu")

# PyAudio configuration
CHUNK = 1024
FORMAT = pyaudio.paFloat32
CHANNELS = 1
RATE = 16000

def is_listen_voice_enabled():
    return config.LISTEN_VOICE_ENABLED.lower() == 'true'

def listen_to_user(duration=config.LISTEN_VOICE_DURATION_SHORT):
    if not is_listen_voice_enabled():
        return None

    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print(f"Listening {duration} seconds...")

    frames = []
    for _ in range(0, int(RATE / CHUNK * duration)):  # Record for 5 seconds
        data = stream.read(CHUNK)
        frames.append(data)

    print("Processing...")

    stream.stop_stream()
    stream.close()
    p.terminate()

    audio_data = np.frombuffer(b''.join(frames), dtype=np.float32)
    result = whisper_model.transcribe(audio_data)
    
    return result['text'].strip().lower()

def toggle_voice():
    current_state = is_listen_voice_enabled()
    new_state = 'true' if not current_state else 'false'
    
    # Read the current .env file
    with open('.env', 'r') as file:
        lines = file.readlines()
    
    # Update the LISTEN_VOICE_ENABLED line
    for i, line in enumerate(lines):
        if line.startswith('LISTEN_VOICE_ENABLED='):
            lines[i] = f'LISTEN_VOICE_ENABLED={new_state}\n'
            break
    
    # Write the updated content back to .env
    with open('.env', 'w') as file:
        file.writelines(lines)
    
    print(f"Voice recognition {'enabled' if new_state == 'true' else 'disabled'}")