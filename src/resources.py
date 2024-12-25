from spotify_background_color import SpotifyBackgroundColor
import sys
import numpy as np
import struct
import sounddevice as sd
from PIL import Image
from typing import Tuple, Any, Iterable
from datetime import datetime as dt
import inspect

class userError:
    def __init__(self, err_msg: str):
        debug(err_msg, 'error', '\x1b[31m')
        print(err_msg)
        sys.exit()

DEBUG = False
DEBUG_LEVEL = 0
DISABLE_STDOUT = False
LOG = []

def debug(value: object, status: str | None = "info", color: str = "\x1b[0m", level: int = 0) -> None:
    if DEBUG and level <= DEBUG_LEVEL:
        stack = inspect.stack()
        debug_msg = f'{color}[{dt.now().strftime("%H:%M:%S")}] [{status.upper()}] [{stack[1].filename.split('/')[-1].split('\\')[-1]} -> {stack[1].function}] {value}\x1b[0m'
        print(debug_msg)
        LOG.append(debug_msg)

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

    debug(f'Recording audio for {RECORD_SECONDS} seconds.')
    audio_array = sd.rec(int(RATE * RECORD_SECONDS), samplerate=RATE, channels=CHANNELS, dtype='int16')
    sd.wait()
    debug('Recording stopped got audio array.')
    
    audio_data = np.clip(audio_array * gain, -32768, 32767).astype(np.int16).tobytes()
    debug('Converted audio array to bytes.')

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

    debug(f'Audio data size: {formatBytes(len(audio_data))}.')

    return audio_data

def coverArtToText(image: str, density: dict, s: int) -> Tuple[str, tuple]:
    debug('Getting ascii cover art from image.')
    im = Image.open(image)
    debug('Opened image.')

    try:
        dc = SpotifyBackgroundColor(np.array(im)).best_color()
        debug(f'Got background color: {dc}.')
    except Exception:
        debug('Failed to get background color. Using white as default.', 'error', '\x1b[31m')
        dc = (255, 255, 255)
        
    im = im.resize((s * 2, s), Image.Resampling.LANCZOS)
    debug('Resized image.')
    mono = im.convert('L')
    debug('Converted image clone to monochrome.')
    im = im.convert('RGB')
    debug('Converted image to RGB.')
    
    img = []
    tmp = ''
    
    for y in range(im.height):
        for x in range(im.width):
            debug(f'Pixel ({x}, {y}).', level=2)
            mono_pixel = mono.getpixel((x, y))
            debug(f'Got monochrome pixel value: {mono_pixel}.', level=2)
            r, g, b = im.getpixel((x, y))
            debug(f'Got RGB pixel value: ({r}, {g}, {b}).', level=2)
            
            res_key, _ = min(density.items(), key=lambda i: abs(mono_pixel - i[1]))
            tmp += f"\x1b[1m\x1b[38;2;{r};{g};{b}m{res_key}\x1b[0m"
            debug(f'Converted pixel ({x}, {y}) to ascii.', level=2)
        
        img.append(tmp)
        debug(f'Converted row {y + 1} to ascii.', level=1)
        debug(f'Converted row {y + 1}: {tmp}.', level=2)
        tmp = ''
    
    debug('Got ascii cover art from image.')

    return '\n'.join(img), dc