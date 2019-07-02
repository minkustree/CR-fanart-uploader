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


def fetch(path, url):
    headers = { 'User-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content.decode(), 'html.parser')
    img_srcs = [a['href'] for a in soup.find_all('a', class_='wpgridlightbox')]
    for src in img_srcs:
        filename = urlparse(src).path.split('/')[-1]
        print('Requesting ', filename)
        resp = requests.get(src, headers=headers)
        
        full_path = path / filename
        print('Saving to ', full_path)
        if not full_path.exists():
            open(full_path, 'wb').write(resp.content)

def upload(path):
    # TODO: Upload to archive
    pass

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google_auth_oauthlib.helpers import credentials_from_session

def test_google_client():
    flow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', scopes=['https://www.googleapis.com/auth/photoslibrary'])
    flow.run_local_server()
    service = build('photoslibrary', 'v1', credentials=flow.credentials)
    print(service.albums().list().execute())

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

    def get_albums(self):
        self.ensure_token()
        r = self.session.get('https://photoslibrary.googleapis.com/v1/albums')
        r.raise_for_status()
        print(r.text)
    
    def create_album(self, title):
        self.ensure_token()
        # body = json.dumps({"album": })

    def get_albums_gc(self):
        self.ensure_token()
        print(self.api.albums().list().execute())

    def upload_bytes(self, bytez, filename):        
        self.ensure_token()        
        headers = { 
            'Content-type': 'application/octet-stream',
            'X-Goog-Upload-File-Name': quote(filename),
            'X-Goog-Upload-Protocol': 'raw'
        }
        r = self.session.post('https://photoslibrary.googleapis.com/v1/uploads', data=bytez, headers=headers)
        r.raise_for_status()
        uploadToken = r.text
        print(uploadToken)
        results = self.api.mediaItems().batchCreate(body={
            'newMediaItems': [ {'description':'Otter', 
                                'simpleMediaItem': {'uploadToken': uploadToken}}
                            ]
            }).execute()
        print(results)
        pass
        


def main():
    # test_google_client()
    # gallery_name = 'cosplay-gallery-july-2019'
    gallery_name = 'fan-art-gallery-reflection'
    path = Path('.') / 'out' / gallery_name
    
    path.mkdir(parents=True, exist_ok=True)
    # fetch(path, 'https://critrole.com/' + gallery_name + '/')
    # upload(path)
    
    p = GooglePhotos()
    filename = '@EmberWickArt.jpg'
    p.upload_bytes(open(path / filename, 'rb').read(), filename)
    # p.get_albums_gc()


if __name__=='__main__':
    main()