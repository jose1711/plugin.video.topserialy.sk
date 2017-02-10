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
import bs4
from provider import ContentProvider
from copy import copy


class TopSerialyContentProvider(ContentProvider):
    urls = {'Seriály': 'https://www.topserialy.to/serialy'}

    def __init__(self, username=None, password=None, filter=None):
        ContentProvider.__init__(self, 'topserialy.to', self.urls['Seriály'],
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
        return self.list_series('https://www.topserialy.to' +
                                '/search.php?search=' + urllib.quote_plus(keyword))

    def list(self, url):
        if 'serialy.' in url:
            if 'epizody' in url:
                print "listing episodes.."
                return self.list_episodes(url)
            elif 'topserialy.to/serialy' in url:
                print "listing series.."
                return self.list_series(url)
            print "listing seasons.."
            return self.list_seasons(url)

    def series_url(self, url):
        return self.urls['Seriály'] + url

    def list_series(self, url):
        result = []
        tree = util.parse_html(url)
        series_list = tree.select('.mk-search-page')
        if series_list:
            for series in tree.select('.container a'):
                item = self.dir_item()
                item['title'] = series.select('span .name-search')[0].text
                item['url'] = 'https://www.topserialy.to' + series.get('href')
                item['img'] = 'https://www.topserialy.to' + series.span.img.get('src')
                result.append(item)
        else:
            for series in tree.select('.container a.single-result'):
                item = self.dir_item()
                original_title = series.select('.original')[0].text
                czsk_title = series.select('.cz-sk')[0].text
                title = original_title
                if czsk_title not in '......' and czsk_title != original_title:
                    title += ' (' + czsk_title + ')'
                item['title'] = title
                item['url'] = 'https://www.topserialy.to' + series.get('href')
                item['img'] = 'https://www.topserialy.to' + series.img.get('data-original')
                result.append(item)
        return sorted(result)

    def list_seasons(self, url):
        result = []
        for season in util.parse_html(url).select('.accordion'):
            item = self.dir_item()
            item['title'] = season.text.strip()
            item['url'] = 'https://www.topserialy.to' + season.p['data']
            result.append(item)
        return result

    def list_episodes(self, url):
        result = []
        for episode in util.parse_html(url).select('a'):
            item = self.video_item()
            item['url'] = 'https://www.topserialy.to/' + episode.get('href')
            season_episode = item['url'].split('-')[-1].upper()
            item['title'] = season_episode + ' ' + episode.text.strip()
            try:
                item['number'] = int(''.join(re.findall(r'[0-9]', season_episode)))
            except ValueError:
                item['number'] = 0
            result.append(item)
        return sorted(result, key=lambda k: k['number'])

    def resolve(self, item, captcha_cb=None, select_cb=None):
        streams = []
        links = util.parse_html(item['url']).select('script')
        for link in links:
            if 'data = ' in str(link):
                break
        links = re.search(r'data = "([^"]+)".*', str(link)).group(1)
        links = base64.b64decode(links)
        soup = bs4.BeautifulSoup(links, 'html5lib')

        sources = [x.group(1) for x in re.finditer('iframe src="([^"]+)"',
                                                   links)]
        lang_regex = re.compile(r'[^(]+\(([^)]+)\)')
        sources_lang = [lang_regex.search(x.a.text).group(1) for x in
                        soup.select('li')]
        sources = soup.select('iframe')
        sources = [x['src'] for x in sources]
        sources = [x.replace('b3BlbmxvYWRmdWNrZG1jYXRyb2xscw==',
                             'https://openload.co/embed') for x in sources]
        result = []
        subs = []
        for index, source in enumerate(sources):
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
            elif 'youwatch.org' in str(source):
                provider = 'YOUWATCH'
                url = source
            else:
                # fail on any other hoster
                continue
            hmf = urlresolver.HostedMediaFile(url=url, include_disabled=False,
                                              include_universal=False)
            part = 'None'
            language = sources_lang[index]
            if hmf.valid_url() is True:
                try:
                    surl = hmf.resolve()
                except:
                    continue
                item = self.video_item()
                item['title'] = '{0} ({1})'.format(provider, language)
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
