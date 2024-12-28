import requests
from resources import sampleAudio, userError, getIndex, debug, DISABLE_STDOUT, LOG_PATH
import resources
from shazamio import Shazam
import os
import base64

if LOG_PATH:
    debug('Logging to file enabled.')
    def db_print(*values: object, sep: str | None = " ", end: str | None = "\n", file: str | None = None, flush: bool = False):
        print(*values, end=end, sep=sep, file=file, flush=flush)
        resources.LOG.append(sep.join(values))

else:
    debug('Logging to file disabled.')
    def db_print(*values: object, sep: str | None = " ", end: str | None = "\n", file: str | None = None, flush: bool = False):
        print(*values, end=end, sep=sep, file=file, flush=flush)

if DISABLE_STDOUT:
    debug('Disabled print.')
    def db_print(*values, sep = None, end = None, file = None, flush = False): ... # Disable print

class Data:
    def __init__(self, timeout: int = 20, duration: int = 2, increase: int = 0):
        self.isinfinite = timeout == -1
        self.threshold = timeout // duration 
        self.threshold += increase * self.threshold
        self.duration = duration
        self.inc = increase
        debug(f'Initialized Data object with timeout {timeout}, duration {duration}, increase {increase}.', level=1)

    async def get(self):
        r = {'matches': []}
        result = None
        itr = 0
        
        # Loop until a match is found
        debug(f'Listening for a song with a timeout of {self.threshold * self.duration} seconds.')
        debug(f'Duration: {self.duration}, Threshold: {self.threshold}.', level=1)
        db_print(f'\x1b[2K({itr}{('/' + str(self.threshold)) if not self.isinfinite else ''}) Listening...\x1b[1A\x1b[999999999D')
        while not (r['matches']):
            db_print(f'\x1b[2K({itr}{('/' + str(self.threshold)) if not self.isinfinite else ''}) Listening...\x1b[1A\x1b[999999999D')
            if (itr == self.threshold - 1) and (not self.isinfinite):
                debug(f'Last try, with a longer duration ({self.duration}).')
                # Last try; with a longer duration
                db_print(f'\x1b[2K({itr}/{self.threshold}) Last try...\x1b[1A\x1b[999999999D')
                self.duration += 3

            elif (itr >= self.threshold - 4) and (not self.isinfinite):
                debug(f'Trying harder, with a longer duration ({self.duration}).')
                # Trying harder; with longer durations
                db_print(f'\x1b[2K({itr}/{self.threshold}) Trying harder...\x1b[1A\x1b[999999999D')
                self.duration += 1
            
            # Get the audio sample
            debug(f'Getting audio for sample of duration {self.duration}.')
            audio_bin = sampleAudio(self.duration)

            # Get the song data
            shazam = Shazam()
            debug(f'Initialized Shazam.')
            debug(f'Recognizing audio sample.')
            result = await shazam.recognize(audio_bin)
            debug(f'Got result.')

            r = result
            itr += 1
            debug(f'New iteration ({itr}).')

            if (itr >= self.threshold) and (not self.isinfinite):
                debug(f'Exceeded threshold of {self.threshold} attempts.')
                userError(f"Sorry couldn't recognize this song after {self.threshold} attempts.\x1b[K")

        debug(f'Got a match after {itr} iterations.')
        debug('Parsing result.')

        return self._parse(r['track'])

    def isrcLookup(self, isrc: str):
        debug(f'Looking up ISRC {isrc}.')
        deezer_api = f'https://api.deezer.com/track/isrc:{isrc}'

        # Get the song data from Deezer
        try:
            debug(f'Getting data from the Deezer API.')
            response = requests.get(deezer_api).json()
            debug('Got response')
        except requests.exceptions.RequestException as e:
            userError(f"An Error occurred: {e}\x1b[K")
            response = {'error': e}

        return response

    def _parse(self, track_data: dict, nohistoryadd: bool = False):
        debug(f'Parsing track data.')
        result = {
            'artists': track_data.get('subtitle', 'Unknown').split(' '),
            'title': track_data.get('title', 'Unknown'),
            'cover': track_data.get('images', {}).get('coverart'),
            'duration': 'Unknown',
            'popularity': 'Unknown',
            'explicit': track_data['hub'].get('explicit') == "True",
            'album': (getIndex(0, getIndex(0, track_data.get('sections'), {}).get('metadata'), {}).get('text', 'Unknown')),
            'release_date': getIndex(2, getIndex(0, track_data['sections'], {}).get('metadata'), {}).get('text', 'Unknown'),
            'label': getIndex(1, getIndex(0, track_data.get('sections'), {}).get('metadata'), {}).get('text', 'Unknown'),
            'link': track_data.get('url', 'Unknown'),
            'isrc': track_data.get('isrc', 'Unknown'),
            'genre': track_data['genres'].get('primary', 'Unknown'),
            'bpm': 'Unknown',
            'gain': 'Unknown',
        }

        debug(f'{result=}', level=2)
        
        response = self.isrcLookup(result['isrc'])
        debug(f'Got response from ISRC lookup.')

        if response.get('error', ''):
            deezer_api = f'https://api.deezer.com/search?q=artist:"{track_data.get('subtitle')}",track:"{track_data.get("title")}"'
            debug(f'No data found for ISRC. Searching Deezer for the song.', 'warning', '\x1b[33m')
            response = requests.get(deezer_api).json()
            debug(f'Got response from Deezer search.')
            if response['total'] == 0:
                userError(f"Sorry unable to get data on the song '{result['title']}'.\x1b[K")

            debug(f'Parsing Deezer response.')
            for i in response.get('data'):
                debug(f'Checking if it is the correct track.', level=1)
                if (track_data.get('subtitle').strip() in i['artist']['name']):
                    debug(f'Found a correct track.')
                    response = i
                    break
        
        if not response.get('error', '') and response:
            debug(f'Got necessary data.')
            deezer_data = response

            duration = deezer_data.get('duration')
            minutes = duration // 60
            seconds = duration % 60
            debug(f'{minutes=}, {seconds=}', level=2)
            
            artists = 'Unknown'
            if deezer_data.get('contributors'):
                artists = ', '.join([i['name'] for i in deezer_data.get('contributors')])
            
            elif deezer_data.get('artist'):
                artists = deezer_data.get('artist').get('name')

            debug(f'{artists=}.', level=2)

            result.update({
                'artists': artists,
                'cover': deezer_data.get('album').get('cover'),
                'album': deezer_data.get('album').get('title'),
                'duration': f'{minutes}:{str(seconds).rjust(2, '0')}',
                'link': deezer_data.get('link', result['link']),
                'bpm': deezer_data.get('bpm') if deezer_data.get('bpm') else 'Unknown',
                'gain': deezer_data.get('gain') if deezer_data.get('gain') else 'Unknown',
                'explicit': deezer_data.get('explicit_lyrics', result['explicit']),
                'popularity': f'{deezer_data.get('rank', '')}',
            })

            debug(f'Updated result with Deezer data.')
            debug(f'{result=}', level=2)

        else:
            debug(f'Could only get limited data on song.', 'warning', '\x1b[33m')
        
        if not nohistoryadd and result['title'] != 'Unknown':
            debug(f'Adding track data to history.')
            History().add(result)

        return result

    
class History:
    def __init__(self):
        self.tracks = []
        self.history_loc = f'{os.path.expanduser("~")}/.sngfetch_history'
        debug(f'Initialized History object with location {self.history_loc}.')

        if os.path.exists(self.history_loc):
            debug(f'History file exists.')
            with open(self.history_loc, 'r') as f:
                self.tracks = list(map(lambda i: eval(base64.b64decode(i).decode('utf-8')), f.read().splitlines()))
                debug(f'Loaded {len(self.tracks)} tracks into memory.')

        else:
            debug(f'History file does not exist. Creating one.')
            with open(self.history_loc, 'w') as f:
                f.write('')

            debug(f'Successfully created history file.')

    def add(self, track_data: dict):
        debug(f'Adding track data to history.')
        if not self.exists(track_data):
            debug(f'Track data does not exist in history. Adding.')
            self.tracks.append(track_data)
            debug(f'Added track data to local history (variable).')
            with open(self.history_loc, 'a') as f:
                f.write(f'{base64.b64encode(bytes(str(track_data), 'utf-8')).decode('utf-8')}\n')
            
            debug(f'Added track data to history file.')
        
        else:
            debug(f'Track data already exists in history. Not adding.')

    def exists(self, track_data: dict):
        if track_data in self.tracks:
            return True
        
        return False

    def get(self):
        debug(f'Returning history of fetched songs.')
        return self.tracks
    
    def clear(self):
        debug(f'Clear history confirm.')
        confirm = input(f"Are you sure to clear the history? [y/n]: ").lower()
        while confirm not in ['y', 'n']:
            debug(f'Invalid input.')
            confirm = input(f"Are you sure to clear the history? [y/n]: ").lower()
                
        if confirm == 'y':
            debug(f'Clearing history.')
            self.tracks = []
            with open(self.history_loc, 'w') as f:
                f.write('')

            debug(f'History cleared.')
            db_print('History cleared.')
            return
            
        debug(f'No changes were made.')
        db_print('No changes were made.')

    def remove(self, title: str):
        debug(f'Trying to remove song with title {title}.')
        found_any = False
        debug(f'Checking if song exists in history and if found asking for deletion conformation.')
        for i in self.tracks:
            debug(f'{i["title"]=}', level=1)
            debug(f'{i=}', level=2)
            if title.lower() in i['title'].lower():
                debug(f'Found song in history, asking for conformation.')
                confirm = input(f"Remove '{i['title']}'? [y/n]: ").lower()
                while confirm not in ['y', 'n']:
                    debug(f'Invalid input.')
                    confirm = input(f"Remove '{i['title']}'? [y/n]: ").lower()
                
                if confirm == 'y':
                    debug(f'Removing song from history.')
                    self.tracks.remove(i)
                    debug('Removed song from local history (variable).')
                    with open(self.history_loc, 'w') as f:
                        f.write('\n'.join(self.tracks))
                    debug(f'Removed song from history file.')

                    db_print(f"Removed '{i['title']}' from history.")
                    found_any = True
                    continue
                
                debug(f'No changes were made.')
                db_print('No changes were made.')
                found_any = True
            
        if not found_any:
            userError(f"Could not find any song matching the title '{title}'.")