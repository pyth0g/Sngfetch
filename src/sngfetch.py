import song
from io import BytesIO
from resources import coverArtToText, formatBytes
import requests
from typing import Callable
import asyncio
import argparse
from sys import exit
import os

# Versioning
# Major revision (new UI, lots of new features, conceptual change, etc.), Minor revision (maybe a change to a search box, 1 feature added, collection of bug fixes), Bug fix release
VERSION = '2.0.0'

parser = argparse.ArgumentParser(description='Sngfetch: get song details in the command line.')
parser.add_argument('-v', '--version', action='version', version=f'%(prog)s v{VERSION}')
parser.add_argument('-hi', '--history', action='store_true', help='Show the history of fetched songs.')
parser.add_argument('-hic', '--history-clear', action='store_true', help='Clear all the history of fetched songs.')
parser.add_argument('-r', '--remove', help="Remove a song from the history by it's title.")
parser.add_argument('-d', '--duration', type=int, help='The default duration of each audio sample to be taken in seconds.', default=3)
parser.add_argument('-t', '--total', type=int, help='The total amount of time to listen for in seconds.', default=30)
parser.add_argument('-inc', '--increase', type=int, help='Increase the duration of each audio sample to be taken in seconds.', default=0)
parser.add_argument('-i', '--infinite', action='store_true', help='Keep trying until interrupted.')
args = parser.parse_args()

cover_size = 20

# Lambda call counter
def lambdaCounter(func: Callable):
    def wrapper(*args, **kwargs):
        wrapper.count += 1
        
        return func(*args, **kwargs)
    
    wrapper.count = 0
    return wrapper

# Display with all info available
def display(data):
    response = requests.get(data['cover'])
    
    density = {
            'Ñ': 255,
            '@': 245,
            '#': 235,
            'W': 225, 
            '$': 215, 
            '9': 205, 
            '8': 195, 
            '7': 185, 
            '6': 175, 
            '5': 165, 
            '4': 155, 
            '3': 145, 
            '2': 135, 
            '1': 125, 
            '0': 115, 
            '?': 105, 
            '!': 95, 
            'a': 85, 
            'b': 75, 
            'c': 65, 
            ';': 55, 
            ':': 50, 
            '+': 45, 
            '=': 40, 
            '-': 35,
            '*': 20,
            ',': 10,
            '.': 5,
            }

    # Cover art
    cover, dc = coverArtToText(BytesIO(response.content), density, cover_size)
    print(cover)

    # Get ready to print the other stuff
    # Put the cursor back up
    print(f'\x1b[{len(cover.splitlines()) + 1}A')

    def printNext(s: str, w: int, end: str = '\n') -> None:
        # Go as far to the left as possible then go to the right for the correct amount
        print(f'\x1b[99999999D\x1b[{w}C{s}', end=end)

    def color(s: str, rgb: tuple, bold: bool = True, fg: bool = True) -> str:
        r, g, b = rgb

        return f'{"\x1b[1m" if bold else ""}\x1b[{"38" if fg else "48"};2;{r};{g};{b}m{s}\x1b[0m'

    w = cover_size * 2 + 1

    # Title
    printNext(color(data['title'], dc), w)
    printNext('-' * len(data['title']), w)

    # Metadata
    md = lambda n, s: printNext(f'{color(n, dc)}: {s}', w)
    md = lambdaCounter(md) # Call count wrapper

    md(f'Artist', data['artists'])
    md('Album', data['album'])
    md('Label', data['label'])
    md('Genre', data['genre'])
    # md('Composer', data['composer'])
    md('Duration', data['duration'])
    md('Popularity', f'#{int(data['popularity']):,}' if data['popularity'] else 'Unknown')
    md('Released', data['release_date'] if data['release_date'] else 'Unknown')
    md('Explicit', 'Yes' if data['explicit'] else 'No')
    md('ISRC', data['isrc'])
    md('BPM', data['bpm'])
    md('Gain', data['gain'])
    md('Link', data['link'])

    # Fill the rest of the space with empty lines
    for _ in range(cover_size - md.count - 2):
        printNext('', w)

# Get the history of fetched songs
if args.history:
    try:
        data = song.History().get()
        for each in data:
            display(each)
    except KeyboardInterrupt:
        print('\nExiting...')

    print(f'\n{len(data)} songs. ({formatBytes(os.path.getsize(song.History().history_loc))})')
    exit()

elif args.remove:
    try:
        song.History().remove(args.remove)
    except KeyboardInterrupt:
        print('\nExiting...')
    exit()

elif args.history_clear:
    try:
        song.History().clear()
    except KeyboardInterrupt:
        print('\nExiting...')
    exit()

# Get the data about a song via the microphone
try:
    data = asyncio.run(song.Data(args.total, args.duration, args.increase).get() if not args.infinite else song.Data(-1, args.duration, args.increase).get())
    display(data)
except KeyboardInterrupt:
    print('\nExiting...')