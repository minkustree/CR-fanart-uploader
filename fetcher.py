from bs4 import BeautifulSoup
from urllib.parse import urlparse
import os.path
import requests


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

def main():
    path = 'out'
    fetch(path)
    upload(path)

if __name__=='__main__':
    main()