import requests
from resources import sampleAudio, userError
from shazamio import Shazam

class Data:
    def __init__(self, timeout: int = 20, duration: int = 2):
        self.threshold = timeout // duration
        self.duration = duration

    async def get(self):
        r = {'matches': []}
        result = None
        itr = 0
        
        print(f'\x1b[2K({itr}/{self.threshold}) Listening...\x1b[1A\x1b[999999999D')
        while not (r['matches']):
            print(f'\x1b[2K({itr}/{self.threshold}) Listening...\x1b[1A\x1b[999999999D')
            if (itr == self.threshold - 1):
                print(f'\x1b[2K({itr}/{self.threshold}) Last try...\x1b[1A\x1b[999999999D')
                self.duration += 3

            elif (itr >= self.threshold - 4):
                print(f'\x1b[2K({itr}/{self.threshold}) Trying harder...\x1b[1A\x1b[999999999D')
                self.duration += 1
            
            audio_bin = sampleAudio(self.duration)

            shazam = Shazam()
            result = await shazam.recognize(audio_bin)

            r = result
            itr += 1

            if (itr >= self.threshold):
                userError(f"Sorry couldn't recognize this song after {self.threshold} attempts.\x1b[K")

        return self._parse(r)
    
    def _parse(self, song_data):
        result = {
            'artists': song_data['track'].get('subtitle').split(' '),
            'title': song_data['track'].get('title', 'Unknown'),
            'cover': song_data['track']['images'].get('coverart'),
            'duration': 'Unknown',
            'popularity': 'Unknown',
            'explicit': song_data['track']['hub'].get('explicit') == "True",
            'album': song_data['track']['sections'][0]['metadata'][0].get('text', 'Unknown'),
            'release_date': song_data['track']['sections'][0]['metadata'][2].get('text', 'Unknown'),
            'label': song_data['track']['sections'][0]['metadata'][1].get('text', 'Unknown'),
            'link': song_data['track'].get('url', 'Unknown'),
            'isrc': song_data['track'].get('isrc', 'Unknown'),
            'genre': song_data['track']['genres'].get('primary', 'Unknown'),
            'bpm': 'Unknown',
            'gain': 'Unknown',
        }

        deezer_api = f'https://api.deezer.com/track/isrc:{result["isrc"]}'

        response = requests.get(deezer_api).json()
        if response.get('error', ''):
            deezer_api = f'https://api.deezer.com/search?q=artist:"{song_data['track'].get('subtitle')}",track:"{song_data["track"].get("title")}"'
            response = requests.get(deezer_api).json()
            if response['total'] == 0:
                userError(f"Sorry unable to get data on this song '{song_data['track']}'.\x1b[K")

            for i in response.get('data'):
                if (song_data['track'].get('subtitle').strip() in i['artist']['name']):
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
        
        return result