import time
import re
from datetime import timedelta


global static_urls
static_urls = []

try:
    from HTMLParser import HTMLParser
    from urlparse import urljoin, urldefrag
except ImportError:
    from html.parser import HTMLParser
    from urllib.parse import urljoin, urldefrag
from tornado import httpclient, gen, ioloop, queues
base_url = 'http://127.0.0.1:65412'
concurrency = 10
@gen.coroutine
def get_links_from_url(url):
    try:
        response = yield httpclient.AsyncHTTPClient().fetch(url)
        #print(' [+]fetched %s' % url)

        html = response.body if isinstance(response.body, str) \
            else response.body.decode()
        urls = [urljoin(url, remove_fragment(new_url))
                for new_url in get_links(html)]
    except Exception as e:
        #print(' \n[!]Exception: %s %s' % (e, url))
        raise gen.Return([])

    raise gen.Return(urls)

def remove_fragment(url):
    pure_url, frag = urldefrag(url)
    return pure_url


def get_links(html):
    class URLSeeker(HTMLParser):
        def __init__(self):
            HTMLParser.__init__(self)
            self.urls = []

        def handle_starttag(self, tag, attrs):
            href = dict(attrs).get('href')
            if href and tag == 'a':
                self.urls.append(href)

    url_seeker = URLSeeker()
    url_seeker.feed(html)
    return url_seeker.urls


@gen.coroutine
def main():
    q = queues.Queue()
    start = time.time()
    fetching, fetched = set(), set()

    @gen.coroutine
    def fetch_url():
        current_url = yield q.get()
        try:
            if current_url in fetching:
                return

            #print('fetching %s' % current_url)
            fetching.add(current_url)
            urls = yield get_links_from_url(current_url)
            fetched.add(current_url)
            for new_url in urls:
                if new_url.startswith(base_url):
                    static_urls.append(new_url)
                    yield q.put(new_url)

        finally:
            q.task_done()

    @gen.coroutine
    def worker():
        while True:
            yield fetch_url()

    q.put(base_url)
    for _ in range(concurrency):
        worker()
    yield q.join(timeout=timedelta(seconds=300))
    assert fetching == fetched
    print('Done in %d seconds, fetched %s URLs.' % (
        time.time() - start, len(fetched)))

def static_url(urls):
    param1 = set()
    params = []
    line_date = []
    links = []
    for i in urls:
        if re.search('.(html|shtml)', i):
            if re.search(r"\d{4}\/\d{1,2}\/\d{1,2}|\d{4}-\d{1,2}-\d{1,2}", i):
                m = re.sub("\d{4}\/\d{1,2}\/\d{1,2}|\d{4}-\d{1,2}-\d{1,2}", '{int}', i)
                if m in line_date:
                    continue
                else:
                    line_date.append(m)
            elif re.match(r'\d+', i):
                n = re.findall(r'\d+', i)
                if len(n) in params:
                    continue
                else:
                    params.append(len(n))

            links.append(i)

        else:
            line = i.split('/')[3:]
            if len(line) > 0:
                line.pop()
                key = set(line)
                if key <= param1:
                    continue
                else:
                    param1 = param1.union(key)
                    links.append(i)
    return links
if __name__ == '__main__':
    import logging
    logging.basicConfig()
    io_loop = ioloop.IOLoop.current()
    io_loop.run_sync(main)
    links=static_url(static_urls)
    print("-----------------------[*]去重后----------------------")
    for i in links:
        print(i)