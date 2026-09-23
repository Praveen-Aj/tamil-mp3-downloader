import requests
import re
import json

url = 'https://open.spotify.com/embed/playlist/37i9dQZF1DXa2hu2twCYvd'
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
r = requests.get(url, headers=headers)
m = re.search(r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>', r.text, re.S)
if m:
    data = json.loads(m.group(1))
    props = data.get('props', {})
    print('props keys:', list(props.keys()))
    pageProps = props.get('pageProps', {})
    print('pageProps keys:', list(pageProps.keys()))
    state = pageProps.get('state', {})
    print('state keys:', list(state.keys()) if isinstance(state, dict) else type(state))
    if isinstance(state, dict):
        d = state.get('data', {})
        print('state.data keys:', list(d.keys()) if isinstance(d, dict) else type(d))
        entity = d.get('entity', {})
        print('entity keys:', list(entity.keys()) if isinstance(entity, dict) else type(entity))
        if isinstance(entity, dict):
            print('entity title/name:', entity.get('name') or entity.get('title'))
            tl = entity.get('trackList')
            print('trackList type and len:', type(tl), len(tl) if isinstance(tl, list) else None)
            if tl and isinstance(tl, list):
                print('First track:', tl[0])
