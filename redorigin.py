import html
import io
import json
import os
import re
import requests
import shutil
import stat
import sys
import subprocess
import tempfile
import time
import urllib.parse


headers = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'User-Agent': 'red-origin',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Encoding': 'gzip,deflate,sdch',
    'Accept-Language': 'en-US,en;q=0.8',
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3'}


class RedactedAPIError(Exception):
    def __init__(self, code, message):
        super().__init__()
        self.code = code
        self.message = message

    def __str__(self):
        return self.message


# RedactedAPI code is based off of REDbetter (https://github.com/Mechazawa/REDBetter-crawler).
class RedactedAPI:
    def __init__(self, session_cookie=None):
        self.session = requests.Session()
        self.session.headers.update(headers)
        self.session_cookie = session_cookie.replace('session=', '')
        self.authkey = None
        self._login()

    def _login(self):
        mainpage = 'https://redacted.ch/';
        cookiedict = {"session": self.session_cookie}
        cookies = requests.utils.cookiejar_from_dict(cookiedict)

        self.session.cookies.update(cookies)

        try:
            self.session.get(mainpage)
        except:
            raise RedactedAPIError('login', 'Could not log in to RED. Check your session cookie or try again later.')

        accountinfo = self.request('index')
        self.authkey = accountinfo['authkey']

    def request(self, action, **kwargs):
        ajaxpage = 'https://redacted.ch/ajax.php'
        params = {'action': action}
        if self.authkey:
            params['auth'] = self.authkey
        params.update(kwargs)

        r = self.session.get(ajaxpage, params=params, allow_redirects=False)
        if r.status_code != 200:
            raise RedactedAPIError('request', 'Could not retrieve origin data. Try again later.')

        parsed = json.loads(r.content)
        if parsed['status'] != 'success':
            raise RedactedAPIError('request-json', 'Could not retrieve origin data. Check the torrent ID/hash or try again later.')

        return parsed['response']

    def get_torrent_info(self, hash=None, id=None):
        info = self.request('torrent', hash=hash, id=id)
        group = info['group']
        torrent = info['torrent']

        if group['categoryName'] != 'Music':
            raise RedactedAPIError('music', 'Not a music torrent')

        artists = group['musicInfo']['artists']
        if len(artists) == 1:
            artists = artists[0]['name']
        elif len(artists) == 2:
            artists = '{0} & {1}'.format(artists[0]['name'], artists[1]['name'])
        else:
            artists = 'Various Artists'

        out = [
            ('Artist',         artists),
            ('Name',           group['name']),
            ('Edition',        torrent['remasterTitle']),
            ('Edition year',   torrent['remasterYear']),
            ('Media',          torrent['media']),
            ('Catalog number', torrent['remasterCatalogueNumber']),
            ('Record label',   torrent['remasterRecordLabel']),
            ('Original year',  group['year']),
            ('Format',         torrent['format']),
            ('Encoding',       torrent['encoding']),
            ('Log',            '{0}%'.format(torrent['logScore']) if torrent['hasLog'] else ''),
            ('File count',     torrent['fileCount']),
            ('Size',           torrent['size']),
            ('Info hash',      torrent['infoHash']),
            ('Uploaded',       torrent['time']),
            ('Permalink',      'https://redacted.ch/torrents.php?torrentid={0}'.format(torrent['id'])),
        ]

        files = list((a,b) for b,a in (word.split('{{{') for word in torrent['fileList'].replace('}}}', '').split('|||')))

        result = make_table(out, True)
        result += '\n{0}/\n'.format(html.unescape(torrent['filePath']))
        result += make_table(files, False)
        comment = html.unescape(torrent['description']).strip('\r\n')
        if comment:
            result += '\n{0}\n'.format(comment)

        return result

def make_table(arr, ljust):
    k_width = max(len(html.unescape(k)) for k,v in arr) + (2 if ljust else 0)
    result = ''
    for k,v in arr:
        just = k.ljust if ljust else k.rjust
        result += "".join((html.unescape(just(k_width)), ('    ' if not ljust else ''), html.unescape(str(v) or '-'))) + '\n'
    return result