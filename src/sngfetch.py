import song
from io import BytesIO
import resources # Custom library for small functions and global variables
from resources import debug, finish, db_print
import requests
from typing import Callable
import asyncio
import argparse
import os
from lyrics import Lyrics
from time import sleep
import json

# Versioning
# Major revision (new UI, lots of new features, conceptual change, etc.), Minor revision (maybe a change to a search box, 1 feature added, collection of bug fixes), Bug fix release
VERSION = '2.5.3'

# Add arguments
parser = argparse.ArgumentParser(description='Sngfetch: get song details in the command line.')
parser.add_argument('-v', '--version', action='version', version=f'%(prog)s v{VERSION}')
parser.add_argument('-l', '--lyrics', action='store_true', help='Display the lyrics of the song fetched.')
parser.add_argument('-ls', '--lyrics-setup', action='store_true', help='Setup the access token for the Genius API.')
parser.add_argument('-cd', '--continuous-until-different', type=int, nargs='?', help='Keep searching even after a song is found, you can specify the delay between searches after the flag, stop by keyboard interrupt.', const=0)
parser.add_argument('-c', '--continuous', type=int, nargs='?', help='Keep searching even after a song is found, you can specify the delay between searches after the flag, stop by keyboard interrupt.', const=0)
parser.add_argument('-hi', '--history', type=str, nargs='?', help='Show the history of fetched songs or a specific song by title.', const='')
parser.add_argument('-hic', '--history-clear', action='store_true', help='Clear all the history of fetched songs.')
parser.add_argument('-m', '--minimalist', type=int, nargs='?', help='Display data in a more minimal style the amount of data can be controlled with an integer (0..2) after the flag.', const=0, default=-1)
parser.add_argument('-r', '--remove', help="Remove a song from the history by it's title.")
parser.add_argument('-d', '--duration', type=int, help='The default duration of each audio sample to be taken in seconds.', default=3)
parser.add_argument('-t', '--total', type=int, help='The total amount of time to listen for in seconds.', default=30)
parser.add_argument('-inc', '--increase', type=int, help='Increase the duration of each audio sample to be taken in seconds.', default=0)
parser.add_argument('-i', '--infinite', action='store_true', help='Keep trying until interrupted.')
parser.add_argument('--linear', action='store_true', help='The length of each audio sample stays the same even in the last few tries.')
parser.add_argument('-s', '--size', type=int, help='The size of the cover art.', default=20)
parser.add_argument('--debug', action='store_true', help='Debug mode.')
parser.add_argument('-ve', '--verbosity', type=int, help='Set the verbosity level of debug (will only have affect if debug is on).', default=0)
parser.add_argument('--disable-stdout', action='store_true', help='Disable stdout and remove it from log.')
parser.add_argument('--log', action='store_true', help='Log all the output in sngfetch_i.log in the current directory (recommended to use in conjunction with disable-stdout).')
parser.add_argument('--freeze', type=str, help='Freeze basic song data to specified json file.')
args = parser.parse_args()

# The path to the file that stores the genius api credentials
genius_api_path = os.path.join(os.path.expanduser('~'), 'genius.api')

if args.debug:
    # Turn on debugging and set the debug level
    resources.DEBUG = True
    resources.DEBUG_LEVEL = args.verbosity

else:
    resources.DEBUG = False # Ensure that the debug mode is off (although it should be off already).
    resources.DEBUG_LEVEL = 0

# Control the level of content to be shown (higher level = less content)
resources.MINIMALIST_LEVEL = args.minimalist

debug(f'Initialized arguments.')
debug(args, level=1)

if args.freeze:
    # Write all song history into a json file
    debug(f'Freezing to file {args.freeze}.')

    tracks = song.History().get() # Get all the tracks as a list of dictionaries
    debug(f'Loaded {tracks=}', level=2)
    
    # Put the tracks into key value pairs
    # with the key being the song title
    data = {item['title']: {key: value for key, value in item.items() if key != 'title'} for item in tracks}
    debug(f'Loaded {data=}', level=2)

    # Save json
    with open(args.freeze, 'w') as f:
        debug('Writing to file...')
        json.dump(data, f, indent=4)

    debug(f'Written to {args.freeze} successfully.')

    finish() # A function that exits the program but before doing it saves any log files

if args.log:
    debug('Logging to file enabled.')
    i = 0
    debug('Finding debug log file path.')
    # Find a valid name for the log
    # file, with the format 'sngfetch_int.log'
    while os.path.exists(os.path.join(os.getcwd(), f'sngfetch_{i}.log')):
        i += 1
    
    log = os.path.join(os.getcwd(), f'sngfetch_{i}.log')
    debug(f'Found debug log file path: {log}.')
    resources.LOG_PATH = log
else:
    debug('Logging to file disabled.')

if args.disable_stdout:
    debug('Disabled print.')
    resources.DISABLE_STDOUT = True
    
if args.lyrics_setup:
    debug('Lyrics setup.')
    # Check if the API credentials are
    # present and exit the program if they are
    Lyrics.ensureAPIcreds(genius_api_path)
    # The credentials aren't present since the program hasn't exited
    if input('API credentials already exist, remove them [y/N]: ') == 'y':
        os.remove(genius_api_path)
        Lyrics.ensureAPIcreds(genius_api_path) # Create the file and ask the user to open it

    db_print('Doing nothing.')
    finish()

def printNext(s: str, w: int, end: str = '\n') -> None:
    """
    Print a string next to another; used when
    printing the metadata next to the cover art
    
    It goes as far left as possible to ensure 
    that the correct width is set after going right
    """
    db_print(f'\x1b[99999999D\x1b[{w}C{s}', end=end, no_clear=True)

def color(s: str, rgb: tuple, bold: bool = True, fg: bool = True) -> str:
    """
    Return the string given in a
    specified rgb color using ansi
    """
    
    r, g, b = rgb

    return f'{"\x1b[1m" if bold else ""}\x1b[{"38" if fg else "48"};2;{r};{g};{b}m{s}\x1b[0m'

cover_size = args.size

def lambdaCounter(func: Callable):
    # Works as a wrapper to a lambda function
    # and counts the amount of calls to it

    debug(f'Initializing lambda counter for {func.__name__}.', level=1)
    def wrapper(*args, **kwargs):
        wrapper.count += 1
        debug(f'Count is now {wrapper.count}.', level=1)
        debug(f'Calling {func.__name__} with {args} and {kwargs}.', level=1)
        
        return func(*args, **kwargs)
    
    wrapper.count = 0
    return wrapper

def display(data):
    """
    Displays the data in a nice format; cover art
    with metadata lines next to it
    """

    debug(f'Displaying data for {data["title"]} by {data["artists"]}.')
    debug(f'Getting cover art from {data["cover"]}.')
    debug(f'Using data: {data}', level=1)
    # Set some default values in case any
    # are missing (THESE ARE NEEDED)
    response = None
    w = 0 # Cover art width
    dc = (255, 255, 255) # Dominant color
    cover = '\n' * cover_size # Cover art string
 
    if args.minimalist < 1:
        # Get cover art and dominant color, the cover art will
        # only be displayed when the minimalist level is -1 
        # (or off), but we still need the dominant color for the
        # minimalist level 0

        if data['cover']:
            # data['cover'] holds the url to the cover art
            response = requests.get(data['cover'])
            debug(f'Got cover art from {data["cover"]}.')
        
        else:
            debug('Unable to get cover art.', 'warning', '\x1b[31m')

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
        
        if response.content:
            debug('Converting cover art to text.')
            # Convert the cover art image to an ascii (text) image
            cover, dc = resources.coverArtToText(BytesIO(response.content), density, cover_size) # Returns the cover art string and dominant color of the artwork
            debug('Converted cover art to text.')
        
    if args.minimalist < 0:
        # Display the cover art only when minimalist
        # is off, hence the minimalist level is -1
        db_print(cover)

        # Get ready to print the other stuff
        # Put the cursor back up
        db_print(f'\x1b[{len(cover.splitlines()) + 1}A')

        w = cover_size * 2 + 1

    if args.minimalist >= 0:
        # Clear the line with (i/j) Listening... on it
        # if minimalist is not off (otherwise the cover art clears that)
        db_print('\x1b[2K\x1b[A')

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
    md('Duration', data['duration'])
    md('Popularity', f'#{int(data['popularity']):,}' if data['popularity'] else 'Unknown')
    md('Released', data['release_date'] if data['release_date'] else 'Unknown')
    md('Explicit', 'Yes' if data['explicit'] else 'No')
    md('ISRC', data['isrc'])
    md('BPM', data['bpm'])
    md('Gain', data['gain'])
    md('Link', data['link'])

    if args.minimalist < 0:
        # Fill the rest of the space with empty
        # lines if the cover art was displayed
        for _ in range(cover_size - md.count - 2):
            printNext('', w)   

        debug(f'Displayed {md.count} metadata lines and {cover_size - md.count - 2} empty lines.')
    
    else:
        printNext('', w)
        debug(f'Displayed {md.count} metadata lines.')

    if args.lyrics:
        # Retrieve lyrics
        try:
            debug(f'Getting lyrics.')
            # Try to get the lyrics of the song by its title and
            # main artist since this is what Genius search supports

            # Strip the title by removing any (feat. ...) and get
            # the first artist (main artist), also provide the full
            # title which the user will see if the search fails and
            # the path to the Genius API credentials
            lyrics = Lyrics.getFromTitle(f'{data["title"].split('(')[0].strip()} {''.join(data["artists"]).strip().split(',')[0]}', data["title"], genius_api_path)
            # 'lyrics' is a list containing the full lyrics and the url to the lyrics
            if lyrics:
                debug('Got lyrics successfully.')
                db_print(lyrics[0]) # full lyrics
                db_print(f'({lyrics[1]})\n') # url
        except KeyboardInterrupt:
            debug('Keyboard interrupt.')
            db_print('\nExiting...')

def main():
    # We have to check for an empty string as well
    # since the search string can also be empty
    if args.history or args.history == '':
        debug('Getting whole history of fetched songs.')
        try:
            # Get the history with the search string stored in args.history
            # data is a list of dictionaries which are ready to be passed to display
            data = song.History(args.history).get()
            for each in data:
                display(each)
        except KeyboardInterrupt:
            debug('Keyboard interrupt.')
            db_print('\nExiting...')

        # Display the amount of songs in history and
        # the size of the file that stores the history
        db_print(f'\n{len(data)} songs. ({resources.formatBytes(os.path.getsize(song.History().history_loc))})')
        debug('Displayed history successfully.')
        finish()

    if args.remove:
        # Remove a song from history by title which is stored in args.remove
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

    if args.continuous == 0 or args.continuous:
        # Search for songs until keyboard interrupt
        # wait for args.continuous seconds in between

        debug('Searching continuously.')
        while True:
            try:
                debug(f'Started fetching song data with args {(args.total, args.duration, args.increase, True, args.linear) if not args.infinite else (-1, args.duration, args.increase, True, args.linear)}.')
                # Get data trough microphone
                # for an explanation of arguments look at the bottom (in the default behavior), except the last
                # argument which signals to Data that the program is in continuous mode
                data = asyncio.run(song.Data(args.total, args.duration, args.increase, True, args.linear).get() if not args.infinite else song.Data(-1, args.duration, args.increase, True, args.linear).get())
                if data:
                    debug('Fetched song data successfully.')
                    display(data)
            except KeyboardInterrupt:
                debug('Keyboard interrupt.')
                db_print('\nExiting...')
                finish()
            
            sleep(args.continuous)

    elif args.continuous_until_different == 0 or args.continuous_until_different:
        # Search for songs util keyboard interrupt,
        # but only display songs that are different
        # than the last song fetched wait for args.continuous_until_different
        # seconds in between

        debug('Searching continuously and only showing different songs.')
        last_data = None # Data dict of the last song
        while True:
            try:
                debug(f'Started fetching song data with args {(args.total, args.duration, args.increase, True, args.linear) if not args.infinite else (-1, args.duration, args.increase, True, args.linear)}.')
                # Get data trough microphone
                # for an explanation of arguments look at the bottom (in the default behavior), except the last
                # argument which signals to Data that the program is in continuous mode
                data = asyncio.run(song.Data(args.total, args.duration, args.increase, True, args.linear).get() if not args.infinite else song.Data(-1, args.duration, args.increase, True, args.linear).get())
                if data and data != last_data:
                    last_data = data
                    debug('Fetched song data successfully.')
                    display(data)
            except KeyboardInterrupt:
                debug('Keyboard interrupt.')
                db_print('\nExiting...')
                finish()
            
            sleep(args.continuous_until_different)

    # If there are no special arguments to override behavior
    try:
        debug(f'Started fetching song data with args {(args.total, args.duration, args.increase, False, args.linear) if not args.infinite else (-1, args.duration, args.increase, False, args.linear)}.')
        # Get the data from song.Data trough the microphone with arguments:
        #   - args.total => the total amount of time the program will (at least try to (this is not the exact amount of time because of
        #     args.duration and increases in time at the last few tries, these are avoidable with the --linear flag)) listen for in seconds
        #
        #   - args.duration => is the duration of each audio segment taken in seconds
        #
        #   - args.increase => the amount the duration increases each time in seconds (default=0)

        data = asyncio.run(song.Data(args.total, args.duration, args.increase, False, args.linear).get() if not args.infinite else song.Data(-1, args.duration, args.increase, False, args.linear).get())
        debug('Fetched song data successfully.')
        display(data)
    except KeyboardInterrupt:
        debug('Keyboard interrupt.')
        db_print('\nExiting...')
        finish()

if __name__ == '__main__':
    main()
    finish() # Ensure exit with saving logs