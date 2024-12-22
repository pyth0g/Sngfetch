import song
from io import BytesIO
from resources import coverArtToText
import requests
from typing import Callable
import asyncio

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

    width = 20

    # Cover art
    cover, dc = coverArtToText(BytesIO(response.content), density, width)
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

    w = width * 2 + 1

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
    for _ in range(width - md.count - 2):
        printNext('', w)

# Get the data about a song via the microphone
try:
    data = asyncio.run(song.Data(20, 2).get())
    display(data)
except KeyboardInterrupt:
    print('\nExiting...')