import requests
from resources import sampleAudio, userError, getIndex
from shazamio import Shazam
import os
import base64

class Data:
    def __init__(self, timeout: int = 20, duration: int = 2, increase: int = 0):
        self.isinfinite = timeout == -1
        self.threshold = timeout // duration 
        self.threshold += increase * self.threshold
        self.duration = duration
        self.inc = increase

    async def get(self):
        r = {'matches': []}
        result = None
        itr = 0
        
        # Loop until a match is found
        print(f'\x1b[2K({itr}{('/' + str(self.threshold)) if not self.isinfinite else ''}) Listening...\x1b[1A\x1b[999999999D')
        while not (r['matches']):
            print(f'\x1b[2K({itr}{('/' + str(self.threshold)) if not self.isinfinite else ''}) Listening...\x1b[1A\x1b[999999999D')
            if (itr == self.threshold - 1) and (not self.isinfinite):
                # Last try; with a longer duration
                print(f'\x1b[2K({itr}{self.threshold}) Last try...\x1b[1A\x1b[999999999D')
                self.duration += 3

            elif (itr >= self.threshold - 4) and (not self.isinfinite):
                # Trying harder; with longer durations
                print(f'\x1b[2K({itr}/{self.threshold}) Trying harder...\x1b[1A\x1b[999999999D')
                self.duration += 1
            
            # Get the audio sample
            audio_bin = sampleAudio(self.duration)

            # Get the song data
            shazam = Shazam()
            result = await shazam.recognize(audio_bin)

            r = result
            itr += 1

            if (itr >= self.threshold) and (not self.isinfinite):
                userError(f"Sorry couldn't recognize this song after {self.threshold} attempts.\x1b[K")

        return self._parse(r['track'])

    def isrcLookup(self, isrc: dict):
        deezer_api = f'https://api.deezer.com/track/isrc:{isrc}'

        # Get the song data from Deezer
        try:
            response = requests.get(deezer_api).json()
        except requests.exceptions.RequestException as e:
            userError(f"Network error occurred: {e}\x1b[K")
            response = {'error': 'Network error occurred'}
        
        return response

    def _parse(self, track_data: dict, nohistoryadd: bool = False):
        result = {
            'artists': track_data.get('subtitle', 'Unknown').split(' '),
            'title': track_data.get('title', 'Unknown'),
            'cover': track_data.get('images', {}).get('coverart'),
            'duration': 'Unknown',
            'popularity': 'Unknown',
            'explicit': track_data['hub'].get('explicit') == "True",
            'album': (getIndex(0, getIndex(0, track_data.get('sections'), {}).get('metadata'), {}).get('text', 'Unknown')),
            'release_date': getIndex(2, getIndex(0, track_data['sections'], {}).get('metadata'), {}).get('text', 'Unknown'),
            'label': track_data['sections'][0]['metadata'][1].get('text', 'Unknown'),
            'link': track_data.get('url', 'Unknown'),
            'isrc': track_data.get('isrc', 'Unknown'),
            'genre': track_data['genres'].get('primary', 'Unknown'),
            'bpm': 'Unknown',
            'gain': 'Unknown',
        }
        
        response = self.isrcLookup(result['isrc'])

        if response.get('error', ''):
            deezer_api = f'https://api.deezer.com/search?q=artist:"{track_data.get('subtitle')}",track:"{track_data.get("title")}"'
            response = requests.get(deezer_api).json()
            if response['total'] == 0:
                userError(f"Sorry unable to get data on the song '{result['title']}'.\x1b[K")

            for i in response.get('data'):
                if (track_data.get('subtitle').strip() in i['artist']['name']):
                    response = i

        if not response.get('error', '') and response:
            deezer_data = response

            duration = deezer_data.get('duration')
            minutes = duration // 60
            seconds = duration % 60
            
            artists = 'Unknown'
            if deezer_data.get('contributors'):
                artists = ', '.join([i['name'] for i in deezer_data.get('contributors')])
            
            elif deezer_data.get('artist'):
                artists = deezer_data.get('artist').get('name')

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
        
        if not nohistoryadd and result['title'] != 'Unknown':
            History().add(result)

        return result
    
class History:
    def __init__(self):
        self.tracks = []
        self.history_loc = f'{os.path.expanduser("~")}/.sngfetch_history'

        if os.path.exists(self.history_loc):
            with open(self.history_loc, 'r') as f:
                self.tracks = list(map(lambda i: eval(base64.b64decode(i).decode('utf-8')), f.read().splitlines()))

        else:
            with open(self.history_loc, 'w') as f:
                f.write('')

    def add(self, track_data: dict):
        if not self.exists(track_data):
            self.tracks.append(track_data)
            with open(self.history_loc, 'a') as f:
                f.write(f'{base64.b64encode(bytes(str(track_data), 'utf-8')).decode('utf-8')}\n')

    def exists(self, track_data: dict):
        if track_data in self.tracks:
            return True
        
        return False

    def get(self):
        return self.tracks
    
    def clear(self):
        confirm = input(f"Are you sure to clear the history? [y/n]: ").lower()
        while confirm not in ['y', 'n']:
            confirm = input(f"Are you sure to clear the history? [y/n]: ").lower()
                
        if confirm == 'y':
            self.tracks = []
            with open(self.history_loc, 'w') as f:
                f.write('')

            print('History cleared.')
            return
            
        print('No changes were made.')

    def remove(self, title: str):
        found_any = False
        for i in self.tracks:
            if title.lower() in i['title'].lower():
                confirm = input(f"Remove '{i['title']}'? [y/n]: ").lower()
                while confirm not in ['y', 'n']:
                    confirm = input(f"Remove '{i['title']}'? [y/n]: ").lower()
                
                if confirm == 'y':
                    self.tracks.remove(i)
                    with open(self.history_loc, 'w') as f:
                        f.write('\n'.join(self.tracks))

                    print(f"Removed '{i['title']}' from history.")
                    found_any = True
                    continue

                print('No changes were made.')
                found_any = True
            
        if not found_any:
            print(f"Could not find any song matching the title '{title}'.")