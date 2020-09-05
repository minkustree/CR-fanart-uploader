from bs4 import BeautifulSoup
from urllib.parse import urlparse
import os.path
import requests
from requests_oauthlib import OAuth2Session
import webbrowser
import pickle
from time import time
import json
from pathlib import Path
from urllib.parse import quote
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google_auth_oauthlib.helpers import credentials_from_session

def fetch(path, url, metadata={}):
    headers = { 'User-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content.decode(), 'html.parser')
    img_links = soup.find_all('a', class_='wpgridlightbox')
    for a in img_links:
        src = a['href']
        title = a['data-title']
        filename = urlparse(src).path.split('/')[-1]
        full_path = path / filename
        metadata_path = full_path.with_suffix('.txt')

        print('Checking ' + filename, end='... ')
        if download_needed(full_path, src, headers):
            print('Downloading... ', end='')
            resp = requests.get(src, headers=headers)
            resp.raise_for_status()
            open(full_path, 'wb').write(resp.content)
            print('Done.')
        else:
            print('Unchanged.')
        open(metadata_path, 'wt', encoding='utf-8').write(title)


def download_needed(full_path, src, request_headers):
    if not full_path.exists(): 
        return True
    head = requests.head(src, headers=request_headers)
    head.raise_for_status()
    local_size = full_path.stat().st_size
    remote_size = int(head.headers['Content-Length'])
    return local_size != remote_size
    
    
def test_google_client():
    flow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', scopes=['https://www.googleapis.com/auth/photoslibrary'])
    flow.run_local_server()
    service = build('photoslibrary', 'v1', credentials=flow.credentials)
    print(service.albums().list().execute()) # pylint: disable=no-member 

class GooglePhotos:
    CLIENT_ID = "767079479609-dqsjbm5okn3cssn4579ou9tt7eq9hm4s.apps.googleusercontent.com"
    AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
    TOKEN_URI = "https://oauth2.googleapis.com/token"
    REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
    SCOPE = "https://www.googleapis.com/auth/photoslibrary"
    PROJECT_ID = "cr-fanart-upload-1561909985391"
    
    def __init__(self):
        self.session = OAuth2Session(client_id=GooglePhotos.CLIENT_ID)
        self.token = None

    def _load_token(self):
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token_file:
                self.token = pickle.load(token_file)

    def _save_token(self):
        with open('token.pickle', 'wb') as token_file:
            pickle.dump(self.token, token_file)

    def ensure_token(self):
        if not self.token:
            self._load_token()

        if not self.token:
            self.session.scope = GooglePhotos.SCOPE
            self.session.redirect_uri = GooglePhotos.REDIRECT_URI
            authorization_url, _ = self.session.authorization_url(GooglePhotos.AUTH_URI,
                # offline for refresh token, # force to always make user click authorize                
                    access_type="offline", prompt="select_account")    
            webbrowser.open(authorization_url)
            # Get the authorization verifier code from the callback url
            code = input('Paste the code here:')
            self.token = self.session.fetch_token(GooglePhotos.TOKEN_URI, 
                            client_secret=self._client_secret, code=code)
            self._save_token()

        if self.token['expires_at'] <= time():
            self.session.token = self.token
            self.token = self.session.refresh_token(GooglePhotos.TOKEN_URI, 
                                                    client_secret=self._client_secret,
                                                    client_id=GooglePhotos.CLIENT_ID)                                                    
            self._save_token()

        self.session.token = self.token
        self.api = build('photoslibrary', 'v1', credentials=credentials_from_session(self.session))

    @property
    def _client_secret(self):
        return json.load(open('client-secret.json', 'r'))['client_secret']

    def upload_bytes(self, bytez, filename):        
        self.ensure_token()
        print("Uploading '" + filename, end="'. ")
        headers = { 
            'Content-type': 'application/octet-stream',
            'X-Goog-Upload-File-Name': quote(filename),
            'X-Goog-Upload-Protocol': 'raw'
        }
        r = self.session.post('https://photoslibrary.googleapis.com/v1/uploads', data=bytez, headers=headers)
        r.raise_for_status()
        print ("Done.")
        return r.text

    def upload_image_file(self, file_path):
        bytez = open(file_path, 'rb').read()
        token = self.upload_bytes(bytez, file_path.name)
        metadata = self.get_metadata(file_path) or file_path.name
        return self._build_new_media_item(token, metadata)

    def get_metadata(self, file_path):
        metadata_path = file_path.with_suffix('.txt')
        try:
            return open(metadata_path, 'rt', encoding='utf-8').read()
        except Exception:
            return None

    def upload_image_files(self, file_paths):
        return [self.upload_image_file(file_path) for file_path in file_paths]

    def _build_new_media_item(self, upload_token, description):
        return {
            'description': description,
            'simpleMediaItem': {'uploadToken': upload_token}
        }

    def batch_create_media_items(self, media_items, album_id=None):
        if not media_items:
            return
        self.ensure_token()
        print("Batch-creating media items. Item count =", len(media_items), end='. ')
        for i in range(0, len(media_items), 50):
            print("Next 50 items from", i, end='. ')
            body = {'newMediaItems': media_items[i:i+50]}
            if album_id:
                body['albumId'] = album_id
            self.api.mediaItems().batchCreate(body=body).execute() # pylint: disable=no-member 
        print('Done.')
        
    def upload_and_register_photos(self, gallery_path, album_title, glob_pattern='*.*'):
        album_id = self.find_or_create_album(album_title)
        file_paths = [f for f in gallery_path.glob(glob_pattern) if f.suffix != '.txt']
        media_items = self.upload_image_files(file_paths)
        self.batch_create_media_items(media_items, album_id)

    def delete_photos_in_album_earlier_than_today(self, album_id, delete_before):
        self.ensure_token()
        print("Deleting photos from album (and all online storage) earlier than", delete_before)
        raise NotImplementedError
        # get all media items from album
        # for each media item, check to see if it was created earlier than today, add it to a list if it was
        # batchRemove from Album all items in the list. 
        # Note there's no delete yet

    def find_or_create_album(self, title):
        id = self.find_album(title)
        if not id:
            id = self.create_album(title)
        return id

    def find_album(self, title):
        self.ensure_token()
        print("Searching for existing album:", title, end='. ')
        request = self.api.albums().list() # pylint: disable=no-member 
        while request:
            albums_response = request.execute()
            for album in albums_response['albums']:
                if album.get('title', "") == title:
                    print('Found.')
                    return album['id']
            request = self.api.albums().list_next(request, albums_response) # pylint: disable=no-member 
        print ('Not found.')
        return None

    def create_album(self, title):
        self.ensure_token()
        print("Creating album:", title, end='. ')
        result = self.api.albums().create(body={ # pylint: disable=no-member 
            'album': { 'title': title }
            }).execute()
        print("Done")
        return result['id']

def main():
    names  = get_fanart_gallery_names('https://critrole.com/category/fan-art/')
    source_gallery_name = names[0]
    google_photos_album_title = 'CR Fan Art Gallery'
    gallery_slug = slugify(source_gallery_name)

    path = Path('.') / 'out' / gallery_slug
    
    path.mkdir(parents=True, exist_ok=True)
    fetch(path, 'https://critrole.com/' + gallery_slug + '/')
    
    p = GooglePhotos()
    p.upload_and_register_photos(path, google_photos_album_title)
    

# This code is from https://github.com/django/django/blob/master/django/utils/text.py
# If this is not enough, consider https://github.com/un33k/python-slugify and others

import unicodedata
import re

def slugify(value, allow_unicode=False):
    """
    Convert to ASCII if 'allow_unicode' is False. Convert spaces to hyphens.
    Remove characters that aren't alphanumerics, underscores, or hyphens.
    Convert to lowercase. Also strip leading and trailing whitespace.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '-', value)   


def get_fanart_gallery_names(url):
    names = []
    headers = { 'User-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content.decode(), 'html.parser')
    fan_art_links = soup.select('.tag-fan-art .qt-title a')
    for a in fan_art_links:
        names.append(a.string.strip())
    return names

if __name__=='__main__':
    main()