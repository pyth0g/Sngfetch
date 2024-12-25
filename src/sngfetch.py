import song
from io import BytesIO
import resources
from resources import debug, finish
import requests
from typing import Callable
import asyncio
import argparse
import os
from lyrics import Lyrics

# Versioning
# Major revision (new UI, lots of new features, conceptual change, etc.), Minor revision (maybe a change to a search box, 1 feature added, collection of bug fixes), Bug fix release
VERSION = '2.3.0'

parser = argparse.ArgumentParser(description='Sngfetch: get song details in the command line.')
parser.add_argument('-v', '--version', action='version', version=f'%(prog)s v{VERSION}')
parser.add_argument('-l', '--lyrics', action='store_true', help='Display the lyrics of the song fetched.')
parser.add_argument('-hi', '--history', action='store_true', help='Show the history of fetched songs.')
parser.add_argument('-hic', '--history-clear', action='store_true', help='Clear all the history of fetched songs.')
parser.add_argument('-r', '--remove', help="Remove a song from the history by it's title.")
parser.add_argument('-d', '--duration', type=int, help='The default duration of each audio sample to be taken in seconds.', default=3)
parser.add_argument('-t', '--total', type=int, help='The total amount of time to listen for in seconds.', default=30)
parser.add_argument('-inc', '--increase', type=int, help='Increase the duration of each audio sample to be taken in seconds.', default=0)
parser.add_argument('-i', '--infinite', action='store_true', help='Keep trying until interrupted.')
parser.add_argument('-s', '--size', type=int, help='The size of the cover art.', default=20)
parser.add_argument('--debug', action='store_true', help='Debug mode.')
parser.add_argument('-ve', '--verbosity', type=int, help='Set the verbosity level of debug (will only have affect if debug is on).', default=0)
parser.add_argument('--disable-stdout', action='store_true', help='Disable stdout and remove it from log.')
parser.add_argument('--log', action='store_true', help='Log all the output in sngfetch_i.log in the current directory (recommended to use in conjunction with disable-stdout).')
args = parser.parse_args()

if args.debug:
    resources.DEBUG = True
    resources.DEBUG_LEVEL = args.verbosity

else:
    resources.DEBUG = False # Ensure that the debug mode is off (although it should be off already).
    resources.DEBUG_LEVEL = 0

debug(f'Initialized arguments.')
debug(args, level=1)

if args.log:
    debug('Logging to file enabled.')
    i = 0
    debug('Finding debug log file path.')
    while os.path.exists(os.path.join(os.getcwd(), f'sngfetch_{i}.log')):
        i += 1
    
    log = os.path.join(os.getcwd(), f'sngfetch_{i}.log')
    debug(f'Found debug log file path: {log}.')
    resources.LOG_PATH = log

    def db_print(*values: object, sep: str | None = " ", end: str | None = "\n", file: str | None = None, flush: bool = False):
        print(*values, end=end, sep=sep, file=file, flush=flush)
        resources.LOG.append(sep.join(values))

else:
    debug('Logging to file disabled.')
    def db_print(*values: object, sep: str | None = " ", end: str | None = "\n", file: str | None = None, flush: bool = False):
        print(*values, end=end, sep=sep, file=file, flush=flush)

if args.disable_stdout:
    debug('Disabled print.')
    resources.DISABLE_STDOUT = True
    def db_print(*values, sep = None, end = None, file = None, flush = False): ... # Disable print


def printNext(s: str, w: int, end: str = '\n') -> None:
    # Go as far to the left as possible then go to the right for the correct amount
    db_print(f'\x1b[99999999D\x1b[{w}C{s}', end=end)

def color(s: str, rgb: tuple, bold: bool = True, fg: bool = True) -> str:
    r, g, b = rgb

    return f'{"\x1b[1m" if bold else ""}\x1b[{"38" if fg else "48"};2;{r};{g};{b}m{s}\x1b[0m'

cover_size = args.size

# Lambda call counter
def lambdaCounter(func: Callable):
    debug(f'Initializing lambda counter for {func.__name__}.', level=1)
    def wrapper(*args, **kwargs):
        wrapper.count += 1
        debug(f'Count is now {wrapper.count}.', level=1)
        debug(f'Calling {func.__name__} with {args} and {kwargs}.', level=1)
        
        return func(*args, **kwargs)
    
    wrapper.count = 0
    return wrapper

# Display with all info available
def display(data):
    debug(f'Displaying data for {data["title"]} by {data["artists"]}.')
    debug(f'Getting cover art from {data["cover"]}.')
    debug(f'Using data: {data}', level=1)
    response = requests.get(data['cover'])
    debug(f'Got cover art from {data["cover"]}.')
    
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
    debug('Converting cover art to text.')
    cover, dc = resources.coverArtToText(BytesIO(response.content), density, cover_size)
    debug('Converted cover art to text.')
    db_print(cover)

    # Get ready to print the other stuff
    # Put the cursor back up
    db_print(f'\x1b[{len(cover.splitlines()) + 1}A')


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

    debug(f'Displayed {md.count} metadata lines and {cover_size - md.count - 2} empty lines.')

# Get the history of fetched songs
if args.history:
    debug('Getting history of fetched songs.')
    try:
        data = song.History().get()
        for each in data:
            display(each)
    except KeyboardInterrupt:
        debug('Keyboard interrupt.')
        db_print('\nExiting...')

    db_print(f'\n{len(data)} songs. ({resources.formatBytes(os.path.getsize(song.History().history_loc))})')
    debug('Displayed history successfully.')
    finish()

if args.remove:
    try:
        debug(f'Removing song with title {args.remove}.')
        song.History().remove(args.remove)
    except KeyboardInterrupt:
        debug('Keyboard interrupt.')
        db_print('\nExiting...')
    
    debug('Song removal ran successfully.')
    finish()

if args.history_clear:
    try:
        debug('Clearing history of fetched songs.')
        song.History().clear()
    except KeyboardInterrupt:
        debug('Keyboard interrupt.')
        db_print('\nExiting...')
    
    debug('History cleared successfully.')
    finish()

# Get the data about a song via the microphone
try:
    debug(f'Started fetching song data with args {(args.total, args.duration, args.increase) if not args.infinite else (-1, args.duration, args.increase)}.')
    data = asyncio.run(song.Data(args.total, args.duration, args.increase).get() if not args.infinite else song.Data(-1, args.duration, args.increase).get())
    debug('Fetched song data successfully.')
    display(data)
except KeyboardInterrupt:
    debug('Keyboard interrupt.')
    db_print('\nExiting...')

if args.lyrics:
    try:
        debug('Getting lyrics.')
        lyrics = Lyrics.getFromTitle(f'{data["title"]} {''.join(data["artists"])}', data["title"])
        debug('Got lyrics successfully.')
        db_print(lyrics[0])
        db_print(f'({lyrics[1]})')
    except KeyboardInterrupt:
        debug('Keyboard interrupt.')
        db_print('\nExiting...')
    finish()

# Save logs if logging is on an exit
finish()