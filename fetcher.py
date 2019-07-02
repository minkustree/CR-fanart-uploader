from bs4 import BeautifulSoup
from urllib.parse import urlparse
import os.path
import requests
from requests_oauthlib import OAuth2Session
import webbrowser
import pickle
from time import time
import json


def fetch(path):
    headers = { 'User-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'}
    response = requests.get('https://critrole.com/fan-art-gallery-reflection/', headers=headers)
    soup = BeautifulSoup(response.content.decode(), 'html.parser')
    img_srcs = [a['href'] for a in soup.find_all('a', class_='wpgridlightbox')]
    for src in img_srcs:
        resp = requests.get(src, headers=headers)
        filename = urlparse(src).path.split('/')[-1]
        print(filename)
        open(os.path.join(path, filename), 'wb').write(resp.content)
    print(img_srcs)

def upload(path):
    # TODO: Upload to archive
    pass

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

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

def main():
    test_google_client()
    # path = 'out'
    # # fetch(path)
    # upload(path)
    
    # p = GooglePhotos()
    # p.get_albums()


if __name__=='__main__':
    main()