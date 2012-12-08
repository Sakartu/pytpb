#!/usr/bin/env python
# encoding: utf-8

#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 2 of the License, or
#       (at your option) any later version.
#
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.

import datetime
import sys
from urllib import quote_plus
from urlparse import urljoin
import urllib2

import lxml.html


class SearchResultParser:
    def __init__(self, html):
        self.doc = lxml.html.parse(html).getroot()

    def parse(self):
        row_data = []
        try:
            table = self.doc.xpath('//*[@id="searchResult"]')[0]
            rows = [row for row in table.iterchildren() if row.tag == 'tr']
            for row in rows:
                columns = row.getchildren()[1:]
                row_data.append(self.parse_row_columns(columns))
        except:
            pass
        return row_data

    def parse_row_columns(self, columns):
        """Parse the columns of a table row.

        *Returns*
            a dictionary with parsed data.
        """
        data = {}
        data["user_type"] = "standard"
        for ele in columns[0].iterchildren():
            if ele.tag == 'div' and ele.get('class') == 'detName':
                a = ele.find('a')
                data["torrent_info_url"] = urljoin(ele.base, a.get('href'))
                data["name"] = a.text_content()
            elif ele.tag == 'a':
                if ele.get('title') == "Download this torrent":
                    data["torrent_url"] = ele.get("href")
                elif ele.get('title') == "Download this torrent using magnet":
                    data["magnet_url"] = ele.get("href")
                elif ele[0].tag == 'img':
                    if ele[0].get('title') == "VIP":
                        data["user_type"] = "VIP"
                    elif ele[0].get('title') == "Trusted":
                        data["user_type"] = "trusted"
            elif ele.tag == 'font':
                a = ele.find('a')
                if a is None:
                    data['user'] = "Anonymous"
                else:
                    data['user'] = urljoin(ele.base, a.get('href'))
                data["uploaded_at"], data["size_of"] = \
                        self.process_datetime_string(ele.text_content())
        data['seeders'] = int(columns[1].text_content().strip())
        data['leechers'] = int(columns[2].text_content().strip())
        return data

    def process_datetime_string(self, string):
        """Process the datetime string from a torrent upload.

        *Returns*
            Tuple with (datetime, (size, unit))
        """
        def process_datetime(part):
            if part.startswith("Today"):
                h, m = part.split()[1].split(':')
                return datetime.datetime.now().replace(
                    hour=int(h), minute=int(m))
            elif part.startswith("Y-day"):
                h, m = part.split()[1].split(':')
                d = datetime.datetime.now()
                return d.replace(
                    hour=int(h), minute=int(m),
                    day=d.day - 1
                )
            elif part.endswith("ago"):
                amount, unit = part.split()[:2]
                d = datetime.datetime.now()
                if unit == "mins":
                    d = d.replace(minute=d.minute - int(amount))
                return d
            else:
                d = datetime.datetime.now()
                if ':' in part:
                    current_date, current_time = part.split()
                    h, m = current_time.split(':')
                    month, day = current_date.split('-')
                    d = d.replace(hour=int(h), minute=int(m),
                            month=int(month), day=int(day))
                else:
                    current_date, year = part.split()
                    month, day = current_date.split('-')
                    d = d.replace(year=int(year), month=int(month),
                            day=int(day))
                return d

        def process_size(part):
            units = {'MiB': 1048576, 'GiB': 1073741824}
            size, unit = part.split()[1:]
            size = float(size) * units[unit]
            return int(size)
        string = string.replace(u"\xa0", " ")
        results = [x.strip() for x in string.split(',')]
        date = process_datetime(' '.join(results[0].split()[1:]))
        size = process_size(results[1])
        return (date, size)


class ThePirateBay:
    """Api for the Pirate Bay"""

    name = 'The Pirate Bay'

    searchUrl = 'https://thepiratebay.org/search/%s/0/7/%d'

    def __init__(self):
        pass

    def search(self, term, cat=None):
        if not cat:
            cat = 0
        url = self.searchUrl % (quote_plus(term), cat)

        req = urllib2.Request(url)
        html = urllib2.urlopen(req)
        parser = SearchResultParser(html)
        return parser.parse()

if __name__ == '__main__':
    def prettySize(size):
        suffixes = [("B", 2 ** 10), ("K", 2 ** 20), ("M", 2 ** 30),
                ("G", 2 ** 40), ("T", 2 ** 50)]
        for suf, lim in suffixes:
            if size > lim:
                continue
            else:
                return round(size / float(lim / 2 ** 10), 2).__str__() + suf

    def magnet_to_torrent(uri):
        return "d10:magnet-uri" + str(len(uri)) + ':' + uri + 'e'

    t = ThePirateBay()
    if sys.argv[1:]:
        term = ' '.join(sys.argv[1:])
    else:
        term = 'the walking dead'
    print 'Searching for "{0}"'.format(term)

    torrents = t.search(term)
    if not torrents:
        print u'No torrents found!'
        sys.exit(1)
    maxlen = max(len(x['name']) for x in torrents) + 3

    print u'{i:>2s}.  {uploaded_at:17s} {name:>{maxlen}} {size:10} : {seeders}'.format(
            i='#', uploaded_at='Uploaded at', maxlen=maxlen, name='Name', size='Size',
            seeders='Seeders')
    for i, t in enumerate(torrents):
        print u'{i:2d}.  {uploaded_at} {name:>{maxlen}} {size:10} : {seeders}'.format(i=i,
                uploaded_at=t['uploaded_at'].strftime('%x %X'), maxlen=maxlen, name=t['name'], size='(' +
                prettySize(t['size_of']) + ')', seeders=t['seeders'])

    try:
        for num in raw_input(("Please provide a comma separated list of "
        "torrents you want to get: ")).split(','):
            try:
                t = torrents[int(num)]
                print num, ':', t['magnet_url']
                outname = t['torrent_info_url'][t['torrent_info_url'].rfind(
                    '/') + 1:] + '.torrent'
                with open(outname, 'w') as out:
                    out.write(magnet_to_torrent(t['magnet_url']))
                    print 'Written magnet URI to file "{name}"'.format(
                            name=outname)
            except Exception, e:
                print 'Something went wrong:', e
                sys.exit()
    except KeyboardInterrupt:
        print u'\nExitting'
        sys.exit(-1)
