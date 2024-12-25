import os
import requests
from resources import userError, debug, DISABLE_STDOUT
from sys import platform, exit
import subprocess
import base64
import urllib.parse
import bs4
import re

if DISABLE_STDOUT:
    debug('Disabled print.')
    def print(*_, end=None, sep=None): ... # Disable print

class Lyrics:
    def getFromUrl(song_url: str):
        debug(f'Fetching lyrics from url: {song_url}.')
        response = requests.get(song_url)
        debug(f'Got response from url: {song_url}.')
        html = response.text
        soup = bs4.BeautifulSoup(html, 'html.parser')
        debug(f'{soup=}', level=2)

        divs = soup.find_all('div', class_=re.compile('^Lyrics-sc'))
        debug(f'{divs=}', level=2)
        for div in divs:
            debug(f'Finding lyrics in div.')
            debug(f'{div=}', level=2)
            div = str(div).replace('<br/><br/>', '\n\n')
            div = bs4.BeautifulSoup(div, 'html.parser')
            unfiltered_lyrics = div.get_text(separator='\n', strip=True).splitlines()
            debug(f'Found lyrics in div.')
            debug(f'{unfiltered_lyrics=}', level=2)
            lyrics = []

            debug(f'Filtering lyrics.')
            song_started = False
            for line in unfiltered_lyrics:
                line = line.strip()
                if line == '[Intro]' or 'Lyrics' in line:
                    debug(f'Found line after which song starts.')
                    debug(f'{line}', level=1)
                    song_started = True

                if not song_started:
                    debug(f'Skipping line: {line}, because it appears before the song has started.', level=1)
                    continue

                if line.startswith('[') and line.endswith(']'):
                    debug(f'Skipping line: {line}, because it is a section.', level=1)
                    continue
                
                if line == 'Embed':
                    debug(f'Skipping line: {line}, because it is an embed.', level=1)
                    continue

                lyrics.append(line)
                debug(f'Added line to lyrics: {line}.')
            
            if '\n'.join(lyrics[1:-1]).strip():
                debug(f'Lyrics found.')
                break
        
        debug(f'Lyrics: {lyrics}.', level=2)
        return '\n'.join(lyrics[1:-1])

    def getFromTitle(search_string: str, title: str = 'song'):
        print('Fetching lyrics...\x1b[1A')
        debug(f'Fetching lyrics for {title=} with {search_string=}.')
        file_path = os.path.join(os.path.expanduser('~'), 'genius.api')
        debug(f'Checking for Genius API credentials in file: {file_path}.')
        if not os.path.exists(file_path):
            debug(f'File {file_path} does not exist. Creating file.')
            with open(file_path, 'w') as f:
                f.write('Client-ID:\nClient-Secret:')

        with open(file_path, 'r') as f:
            debug(f'Reading credentials from {file_path}.')
            for i in f.read().splitlines():
                if i.startswith('Client-ID:'):
                    client_id = i.split(':')[1]
                    debug(f'Found client id.')
                    debug(f'{client_id=}', level=2)

                elif i.startswith('Client-Secret:'):
                    client_secret = i.split(':')[1]
                    debug(f'Found client secret.')
                    debug(f'{client_secret=}', level=2)

        if not client_id or not client_secret:
            debug(f'Missing Genius API credentials in the file {file_path}.')
            if input(f"Missing Genius API credentials in the file '{file_path}'. Open the file [y/N]? ").lower() == 'y':
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
                print('Doing nothing.')

            exit()
        
        debug(f'Authenticating with Genius API.')
        auth_url = 'https://api.genius.com/oauth/token'
        debug('Creating auth headers and data.')
        auth_header_value = base64.b64encode(f"{client_id}:{client_secret}".encode('utf-8')).decode('utf-8')
        debug(f'{auth_header_value=}', level=2)

        auth_headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {auth_header_value}',
        }
        debug(f'{auth_headers=}', level=2)

        auth_data = {
            'grant_type': 'client_credentials',
        }
        debug(f'{auth_data=}', level=2)

        debug(f'Sending post request to {auth_url} with headers and auth_data.')
        response = requests.post(auth_url, headers=auth_headers, data=auth_data)
        debug(f'{response=}', level=2)

        if not response.status_code == 200:
            debug(f'Status code: {response.status_code}', 'error', '\x1b[31m')
            userError('Failed to authenticate with Genius API. Check your credentials, network connection and try again.')

        auth_token = response.json().get('access_token')
        debug(f'Got auth token.')
        debug(f'{auth_token=}', level=2)

        search_string = search_string.strip().split('-')[0].split('(')[0]
        debug(f'Formatted {search_string=}', level=2)
        search_url = f'https://api.genius.com/search?q={urllib.parse.quote(search_string)}'
        debug(f'{search_url=}', level=2)

        search_headers = {
            'Authorization': f'Bearer {auth_token}',
        }
        debug(f'{search_headers=}', level=2)

        debug(f'Sending get request to {search_url} with headers.')
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
                song_url = search_results[0].get('result', {}).get('url', '')
                debug(f'{song_url=}', level=2)
                song_title = search_results[0].get('result', {}).get('title', '')
                debug(f'{song_title=}', level=2)
                if song_url and title.lower() in song_title.lower():
                    debug(f'Found song url, getting lyrics from url.')
                    return Lyrics.getFromUrl(song_url), song_url
                
                i += 1
    
        
        userError(f"Unable to fetch lyrics for '{title}'.")