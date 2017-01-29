# -*- coding: UTF-8 -*-
# /*
# *      Copyright (C) 2016 Jose Riha
# *
# *
# *  This Program is free software; you can redistribute it and/or modify
# *  it under the terms of the GNU General Public License as published by
# *  the Free Software Foundation; either version 2, or (at your option)
# *  any later version.
# *
# *  This Program is distributed in the hope that it will be useful,
# *  but WITHOUT ANY WARRANTY; without even the implied warranty of
# *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# *  GNU General Public License for more details.
# *
# *  You should have received a copy of the GNU General Public License
# *  along with this program; see the file COPYING.  If not, write to
# *  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
# *  http://www.gnu.org/copyleft/gpl.html
# *
# */
import urllib
import util
import base64
import re
import urlresolver
from provider import ContentProvider
from copy import copy


class TopSerialyContentProvider(ContentProvider):
    urls = {'Seriály': 'http://www.topserialy.sk/serialy'}

    def __init__(self, username=None, password=None, filter=None):
        ContentProvider.__init__(self, 'topserialy.sk', self.urls['Seriály'],
                                 username, password, filter)

    def __del__(self):
        util.cache_cookies(self.cache)

    def capabilities(self):
        return ['resolve', 'categories', 'search']

    def categories(self):
        result = []
        for name, url in self.urls.items():
            item = self.dir_item()
            item['title'] = name
            item['url'] = url
            result.append(item)
        return result

    def search(self, keyword):
        return self.list_series('http://www.topserialy.sk' +
                                '/search.php?search=' + urllib.quote_plus(keyword))

    def list(self, url):
        if 'serialy.' in url:
            if 'epizody' in url:
                print "listing episodes.."
                return self.list_episodes(url)
            elif 'topserialy.sk/serialy' in url:
                print "listing series.."
                return self.list_series(url)
            print "listing seasons.."
            return self.list_seasons(url)

    def series_url(self, url):
        return self.urls['Seriály'] + url

    def list_series(self, url):
        result = []
        tree = util.parse_html(url)
        series_list = tree.select('.vysledky-hladania a.single-result')
        if series_list:
            for series in tree.select('.vysledky-hladania a.single-result'):
                item = self.dir_item()
                item['title'] = series.get('data-name')
                item['url'] = 'http://www.topserialy.sk' + series.get('href')
                item['img'] = 'http://www.topserialy.sk' + series.img.get('data-original')
                result.append(item)
        else:
            for series in tree.select('.container a'):
                item = self.dir_item()
                item['title'] = series.findAll('span', 'name-search')[0].text
                item['url'] = 'http:' + series.get('href')
                item['img'] = 'http:' + series.img.get('src')
                result.append(item)
        return sorted(result)

    def list_seasons(self, url):
        result = []
        for season in util.parse_html(url).select('.accordion'):
            item = self.dir_item()
            item['title'] = season.text.strip()
            item['url'] = 'http://www.topserialy.sk' + season.p['data']
            result.append(item)
        return result

    def list_episodes(self, url):
        result = []
        for episode in util.parse_html(url).select('a'):
            item = self.video_item()
            item['url'] = 'http://www.topserialy.sk/' + episode.get('href')
            season_episode = item['url'].split('-')[-1].upper()
            item['title'] = season_episode + ' ' + episode.text.strip()
            item['number'] = int(''.join(re.findall(r'[0-9]', season_episode)))
            result.append(item)
        return sorted(result, key=lambda k: k['number'])

    def resolve(self, item, captcha_cb=None, select_cb=None):
        streams = []
        links = util.parse_html(item['url']).select('script')
        for link in links:
            if 'data = ' in str(link):
                break
        link = re.search(r'data = "([^"]+)".*', str(link)).group(1)
        link = base64.b64decode(link)

        sources = [x.group(1) for x in re.finditer('iframe src="([^"]+)"', link)]
        sources = [x.replace('b3BlbmxvYWRmdWNrZG1jYXRyb2xscw==',
                             'https://openload.co/embed') for x in sources]
        result = []
        subs = []
        for source in sources:
            if 'openload' in str(source):
                provider = 'OPENLOAD'
                metas = util.parse_html(source).select('meta')
                fname = util.request(source)
                for meta in metas:
                    if meta['name'] in 'description':
                        fname = meta['content']
                code = source.split('/')[-2]
                url = 'http://openload.co/f/' + code + '/' + fname.replace(' ', '.')
                for track in util.parse_html(source).select('track'):
                    if track.get('src'):
                        subs.append([track['src'], track['srclang']])
            elif 'flashx' in str(source):
                provider = 'FLASHX'
                code = re.search('embed-([^.-]+)[\.-]', source).group(1)
                url = 'https://www.flashx.tv/embed.php?c=%s' % code
            else:
                continue
            hmf = urlresolver.HostedMediaFile(url=url, include_disabled=True,
                                              include_universal=False)
            part = 'None'
            if hmf.valid_url() is True:
                surl = hmf.resolve()
                item = self.video_item()
                item['title'] = provider
                item['url'] = surl
                result.append(item)
        if subs:
            _result = []
            for sub in subs:
                for item in result:
                    item = copy(item)
                    item['subs'] = sub[0]
                    item['title'] += ' {0}'.format(sub[1])
                    _result.append(item)
            result = _result
        if len(result) == 1:
            return result[0]
        elif len(result) > 1 and select_cb:
            return select_cb(result)
