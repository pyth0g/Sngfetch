import os
import requests
from resources import userError, debug, DISABLE_STDOUT, finish, LOG_PATH, stripNonAlphaNum
import resources
from sys import platform
import subprocess
import base64
import urllib.parse
import bs4
import re

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

class Lyrics:
    def ensureAPIcreds(file_path: str):
        if not os.path.exists(file_path):
            debug(f'File {file_path} does not exist. Creating file.')
            with open(file_path, 'w') as f:
                f.write('Access-Token:')

        # Read the access token
        with open(file_path, 'r') as f:
            debug(f'Reading credentials from {file_path}.')
            access_token = None
            for line in f.read().splitlines():
                if line.startswith('Access-Token:'):
                    access_token = line.split(':', 1)[1].strip()
                    debug(f'Found access token.')

        if not access_token:
            debug(f'Missing Genius API access token in the file {file_path}.')
            if input(f"Missing Genius API access token in the file '{file_path}'. Open the file [y/N]? ").lower() == 'y':
                try:
                    debug(f'Opening text file {file_path}.')
                    if platform == 'win32':
                        os.startfile(file_path)
                    elif platform == 'darwin':
                        subprocess.run(['open', file_path])
                    else:
                        subprocess.run(['xdg-open', file_path])
                except Exception as e:
                    userError(f"Error opening file: {e}")
            else:
                debug('Doing nothing.')
                db_print('Doing nothing.')
            finish()
        
        return access_token

    def truncate(lst):
        result = []
        
        for i, item in enumerate(lst):
            if item != '\n' or (i > 0 and lst[i-1] != '\n'):
                result.append(item)
        
        return result

    def getFromUrl(song_url: str):
        debug(f'Fetching lyrics from url: {song_url}.')
        response = requests.get(song_url)
        debug(f'Got response from url: {song_url}.')
        html = response.text
        soup = bs4.BeautifulSoup(html, 'html.parser')

        divs = soup.find_all('div', class_=re.compile('^Lyrics-sc'))
        debug(f'{divs=}', level=2)
        for div in divs:
            debug(f'Finding lyrics in div.')
            debug(f'{div=}', level=2)
            unfiltered_lyrics = div.get_text(separator='\n', strip=True).splitlines()
            debug(f'Found lyrics in div.')
            debug(f'{unfiltered_lyrics=}', level=2)
            for c, line in enumerate(unfiltered_lyrics):
                if line == '[Intro]' or 'Lyrics' in line:
                    if '[' not in '\n'.join(unfiltered_lyrics[c:]):
                        debug("The lyrics don't have any [section] indicators, splitting by <br> tags (less effective).")
                        div = str(div).replace('<br/><br/>', '\n\n')
                        div = bs4.BeautifulSoup(div, 'html.parser')
                        unfiltered_lyrics = div.get_text(separator='\n', strip=True).splitlines()
                    else:
                        debug("Splitting lyrics by [sections].")
                        
            debug(f'{unfiltered_lyrics=}', level=2)
            lyrics = []

            debug(f'Filtering lyrics.')
            song_started = False
            unclosed_angle_bracket = False
            unclosed_bracket = False
            unclosed_bracket_string = ''
            rm_next_line = False
            for line in unfiltered_lyrics:
                line = line.strip()

                if rm_next_line:
                    rm_next_line = False
                    debug(f'Got instruction to skip this line: {line}')
                    continue

                if unclosed_angle_bracket:
                    debug(f'Unclosed angle bracket on line: {line}')
                    if ']' in line:
                        debug('Angle bracket closed.')
                        unclosed_angle_bracket = False

                    continue

                if unclosed_bracket:
                    debug(f'Unclosed bracket on line: {line}')
                    unclosed_bracket_string += line

                    if ')' in line:
                        debug('Bracket closed.')
                        unclosed_bracket = False
                        lyrics.append(unclosed_bracket_string)
                        unclosed_bracket_string = ''

                    continue

                if line == '[Intro]' or 'Lyrics' in line:
                    debug(f'Found line after which song starts.')
                    debug(f'{line}', level=1)
                    song_started = True

                if not song_started:
                    debug(f'Skipping line: {line}, because it appears before the song has started.', level=1)
                    continue

                if line.startswith('[') and line.endswith(']'):
                    debug(f'Skipping line and  adding blank line: {line}, because it is a section.', level=1)
                    lyrics.append('\n') # New verse (double '\n')
                    continue

                elif line.startswith('['):
                    debug(f'Found unclosed angle bracket on line: {line}')
                    unclosed_angle_bracket = True
                    continue

                if '(' in line and not line.endswith(')'):
                    debug(f'Found unclosed bracket on line: {line}')
                    unclosed_bracket = True
                    unclosed_bracket_string += '(' + line.split('(', 1)[1]
                    continue
                
                if line == 'Embed':
                    debug(f'Skipping line: {line}, because it is an embed.', level=1)
                    continue

                elif line == 'You might also like':
                    debug(f'Skipping line: {line}')
                    continue

                if line.startswith('See') and line.endswith('Live'):
                    debug(f'Promo line removed it: {line}')
                    rm_next_line = True
                    continue

                lyrics.append(line)
                debug(f'Added line to lyrics: {line}.')
            
            if '\n'.join(lyrics[1:]).strip():
                debug(f'Lyrics found.')
                break
        
        debug(f'Lyrics: {lyrics[1:-1]}.', level=2)
        return '\n'.join(Lyrics.truncate(lyrics[1:-1])).strip()
    
    def getFromTitle(search_string: str, title:str, file_path: str):
        db_print('Fetching lyrics...\x1b[1A')
        debug(f'Fetching lyrics for {title=} with {search_string=}.')
        
        # Define the file path for the access token
        debug(f'Checking for Genius API credentials in file: {file_path}.')

        access_token = Lyrics.ensureAPIcreds(file_path)

        # Make the search request to the Genius API
        search_url = f'https://api.genius.com/search?q={urllib.parse.quote(search_string)}'
        debug(f'{search_url=}', level=2)

        search_headers = {
            'Authorization': f'Bearer {access_token}',
        }
        debug(f'{search_headers=}', level=2)

        debug(f'Sending GET request to {search_url} with headers.')
        response = requests.get(search_url, headers=search_headers)
        debug('Got response.')
        debug(f'{response=}', level=2)
        song_url = None
        i = 0

        debug(f'Status code: {response.status_code}', level=2)
        if response.status_code == 200:
            search_results = response.json().get('response', {}).get('hits', [])
            debug(f'Got search results.')
            debug(f'{search_results=}', level=2)
            while not song_url and i < len(search_results):
                debug(f'Checking search result {i}.')
                song_url = search_results[i].get('result', {}).get('url', '')
                debug(f'{song_url=}', level=2)
                song_title = search_results[i].get('result', {}).get('title', '')
                debug(f'{song_title=}', level=2)
                debug(f'{title=}', level=2)
                clear_title = stripNonAlphaNum(title.lower())
                clear_song_title = stripNonAlphaNum(song_title.lower())
                debug(f'{clear_song_title=}', level=2)
                debug(f'{clear_title=}', level=2)
                if song_url and (clear_title in clear_song_title) or (clear_song_title in clear_title):
                    debug(f'Found song url, getting lyrics from url.')
                    return Lyrics.getFromUrl(song_url), song_url
                i += 1
        
        db_print(f"Unable to fetch lyrics for '{title}'.")