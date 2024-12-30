from spotify_background_color import SpotifyBackgroundColor
import sys
import numpy as np
import struct
import sounddevice as sd
from PIL import Image
from typing import Tuple, Any, Iterable
from datetime import datetime as dt
import inspect
import re

"""
This library is used for small functionality and
for storing global variables.
"""

class userError:
    def __init__(self, err_msg: str):
        debug(err_msg, 'error', '\x1b[31m')
        print(err_msg)
        finish()

# Globals
DEBUG = False
DEBUG_LEVEL = 0
DISABLE_STDOUT = False
LOG = []
LOG_PATH = ''
MINIMALIST_LEVEL = -1

def debug(value: object, status: str | None = 'info', color: str = '', level: int = 0) -> None:
    """
    debug print
    """

    if DEBUG and level <= DEBUG_LEVEL:
        stack = inspect.stack() # Inspect the stack to later find the function who called debug
        debug_msg = f'[{dt.now().strftime("%H:%M:%S")}] [{status.upper()}] [{stack[1].filename.split('/')[-1].split('\\')[-1]} -> {stack[1].function}] {value}'
        print(color + debug_msg + '\x1b[0m')
        LOG.append(debug_msg)

ansi_escape = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')

def db_print(*values: object, sep: str | None = " ", end: str | None = "\n", file: str | None = None, flush: bool = False, no_clear: bool = False):
    """
    Prints values but with some added functionality
    """

    if not DISABLE_STDOUT:
        if not no_clear:
            print("\r\x1b[0K", end="", flush=flush) # Add \x1b[0K to start of values to clear any weird artifacts in front of the string
        
        if MINIMALIST_LEVEL == 2:
            # Remove all ansi escape codes
            values = [ansi_escape.sub('', str(value)) for value in values]
        
        print(*values, end=end, sep=sep, file=file, flush=flush)
        
        if LOG_PATH:
            LOG.append(sep.join(values))


def getIndex(index: int, itr: Iterable, fallback: Any | None = None) -> Any:
    """
    Index lookup with fallback
    """

    try:
        return itr[index]
    except IndexError:
        return fallback

def stripNonAlphaNum(s: str) -> str:
    """
    Removes non alpha numerical characters from string
    """
    
    n_s = ''
    for i in s:
        n_s += i if i.isalnum() else ''

    return n_s

def matching(s1: str, s2: str, split: str = ' ', diff: int = 2) -> bool:
    """
    More tolerant matching function
    used mainly for searching in this program
    """

    s1 = stripNonAlphaNum(s1)
    s2 = stripNonAlphaNum(s2)
    debug(f'Checking for match between {s1=}, {s2=}')
    if (s1 in s2) or (s2 in s1):
        debug('Strings include each other.')
        return True
    
    matches = 0
    s1_split = s1.strip().split(split)
    s2_split = s2.strip().split(split)
    if len(s1_split) != len(s2_split):
        debug("Length doesn't match")
        return False
    
    for c in range(len(s1_split)):
        i = s1_split[c]
        j = s2_split[c]
        debug(f'{i=}, {j=}', level=1)
        debug(f'Char diff: {len(set(i).difference(set(j)))}', level=1)
        debug(f'Len diff: {abs(len(i) - len(j))}')
        if len(set(i).difference(set(j))) <= diff and abs(len(i) - len(j)) < diff:
            debug('Match found.')
            matches += 1
    
    if matches >= diff:
        debug('Match found.')
        return True
    
    debug('Not a match.')
    return False


def formatBytes(size: int) -> Tuple[int, str]:
    """
    Format bytes
    Slightly modified from the first answer: https://stackoverflow.com/questions/12523586
    """
    
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
    """
    Get an audio sample of t seconds with the gain of gain in bytes
    """

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

    # .wav format headers (thanks Chat-GPT)
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
    """
    Convert an image to ascii art with ansi color codes
    """
    
    debug('Getting ascii cover art from image.')
    im = Image.open(image)
    debug('Opened image.')

    try:
        dc = SpotifyBackgroundColor(np.array(im)).best_color()
        debug(f'Got background color: {dc}.')
    except Exception:
        debug('Failed to get background color. Using white as default.', 'error', '\x1b[31m')
        dc = (255, 255, 255)
        
    im = im.resize((s * 2, s), Image.Resampling.LANCZOS) # Resize to 2x width since text characters are about 2x taller than they are wide
    debug('Resized image.')
    mono = im.convert('L') # Get a clone of the image in monochrome (for the density)
    debug('Converted image clone to monochrome.')
    im = im.convert('RGB') # Ensure the image is in RGB
    debug('Converted image to RGB.')
    
    img = []
    tmp = ''
    
    for y in range(im.height):
        for x in range(im.width):
            mono_pixel = mono.getpixel((x, y))
            r, g, b = im.getpixel((x, y))
            
            density_char, _ = min(density.items(), key=lambda i: abs(mono_pixel - i[1])) # The character from the density map
            tmp += f"\x1b[1m\x1b[38;2;{r};{g};{b}m{density_char}\x1b[0m" # Combine the RGB and density character (this is one character)
        
        img.append(tmp)
        debug(f'Converted row {y + 1} to ascii.', level=1)
        tmp = ''
    
    debug('Got ascii cover art from image.')

    return '\n'.join(img), dc

def finish():
    """
    Stop the program and save any log files
    """
    
    if LOG_PATH:
        with open(LOG_PATH, 'w') as f:
            f.write('\n'.join(LOG))
        
        db_print(f'Logs saved in {LOG_PATH}.')
        debug(f'Logs saved in {LOG_PATH}.')
    

    sys.exit()