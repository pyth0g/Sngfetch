from spotify_background_color import SpotifyBackgroundColor
import sys
import numpy as np
import struct
import sounddevice as sd
from PIL import Image
from typing import Tuple, Any, Iterable

class userError:
    def __init__(self, err_msg: str):
        print(err_msg)
        sys.exit()

def getIndex(index: int, itr: Iterable, fallback: Any | None = None) -> Any:
    try:
        return itr[index]
    except IndexError:
        return fallback

def formatBytes(size: int) -> Tuple[int, str]:
    power = 2**10
    n = 0
    power_labels = {0 : 'Bytes', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size > power:
        size /= power
        n += 1
    
    try:
        return f'{round(size, 2)} {power_labels[n]}'
    except KeyError:
        return f'{size} {power_labels[0]}'


def sampleAudio(t: int, gain: int = 2) -> bytes:
    CHANNELS = 1
    RATE = 44100
    WIDTH = 2
    RECORD_SECONDS = t

    audio_array = sd.rec(int(RATE * RECORD_SECONDS), samplerate=RATE, channels=CHANNELS, dtype='int16')
    sd.wait()
    
    audio_data = np.clip(audio_array * gain, -32768, 32767).astype(np.int16).tobytes()

    data_size = len(audio_data)
    chunk_size = 36 + data_size
    riff_chunk_size = chunk_size + 8

    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        riff_chunk_size,
        b'WAVE',
        b'fmt ',
        16,
        1,
        CHANNELS,
        RATE,
        RATE * CHANNELS * WIDTH,
        CHANNELS * WIDTH,
        WIDTH * 8,
        b'data',
        data_size
    )

    audio_data = header + audio_data

    return audio_data

def coverArtToText(image: str, density: dict, s: int) -> Tuple[str, tuple]:
    im = Image.open(image)

    try:
        dc = SpotifyBackgroundColor(np.array(im)).best_color()
    except Exception:
        dc = (255, 255, 255)
        
    im = im.resize((s * 2, s), Image.Resampling.LANCZOS)
    mono = im.convert('L')
    im = im.convert('RGB')
    
    img = []
    tmp = ''
    
    for y in range(im.height):
        for x in range(im.width):
            mono_pixel = mono.getpixel((x, y))
            r, g, b = im.getpixel((x, y))
            
            res_key, _ = min(density.items(), key=lambda i: abs(mono_pixel - i[1]))
            tmp += f"\x1b[1m\x1b[38;2;{r};{g};{b}m{res_key}\x1b[0m"
        
        img.append(tmp)
        tmp = ''

    return '\n'.join(img), dc