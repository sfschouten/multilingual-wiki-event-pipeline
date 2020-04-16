from collections import Counter
from collections import defaultdict
import urllib
import http
import ast
import socket
from urllib.parse import urlencode
import urllib3

import classes

from newsplease import NewsPlease

WAYBACK_CDX_SERVER = 'http://web.archive.org/cdx/search/cdx?'

def generate_wayback_uri(url,
                         last_n=-5,
                         format='json',
                         verbose=0):
    """
    call the https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server#basic-usage
    API to obtain the last snapshots of the wayback machine for a specific URL.

    :param str url: a URL
    :param int last_n: -5 indicates the 5 latest snapshots and 5 the first 5 snapshots
    :param str format: supported: 'json'

    :rtype: tuple
    :return: (status, URL or None)
    """
    http = urllib3.PoolManager()
    wb_url = None

    params = {'url': url,
              'output' : format,
              'limit' : last_n}

    encoded_uri = WAYBACK_CDX_SERVER + urlencode(params)
    r = http.request('GET', encoded_uri)

    if r.status != 200:
        status = 'status code not 200'
        if verbose >= 4:
            print(f'status code: {r.status_code}')

    data_as_string = r.data.decode('utf-8')
    snapshots = ast.literal_eval(data_as_string[:-1])

    for (urlkey,
         timestamp,
         original,
         mimetype,
         statuscode,
         digest,
         length) in snapshots[1:]:

        if statuscode == '-':
            continue 

        if int(statuscode) == 200:
            wb_url = f'http://web.archive.org/web/{timestamp}/{original}'
            status = 'succes'

    if wb_url is None:
        status = 'Wayback Machine URL not found'

    if status == 'succes':
        if verbose >= 3:
            print()
            print(f'Wayback machine: {wb_url} for url {url}')
            print(f'used the following query: {encoded_uri}')

    return status, wb_url


def run_newsplease(url,
                   timeout,
                   startswith=None,
                   accepted_languages=set(),
                   excluded_domains=set(),
                   title_required=True,
                   num_chars_range=False,
                   verbose=0):
    """
    apply newsplease on a url

    :param str url: a url to crawl
    :param int timeout: timeout in seconds
    :param startswith: if provided, the url has to start with this prefix, e.g., http
    :param set accepted_languages: set of languages that are accepted
    (https://en.wikipedia.org/wiki/ISO_639-1)
    :param bool title_required: the article.title value can not be None
    :param num_chars_range: if of type range, an article will only be included
    if the number of characters falls within the specified range.

    :rtype: tuple
    :return (status, None of dict with all NewsPlease information)
    """
    status = 'succes'
    wb_url = None
    news_please_info = None

    if startswith:
        if not url.startswith(startswith):
            status = 'not a valid url'

    for excluded_domain in excluded_domains:
        if excluded_domain in url:
            status = 'excluded domain'

    if status == 'succes':
        if 'web.archive.org/web/' not in url:
            status, wb_url = generate_wayback_uri(url, verbose=verbose)
        else:
            status = 'succes'
            wb_url = url

    # TODO: what if url is not the same as the one crawler (via redirects?)

    if status == 'succes':
        try:
            article = NewsPlease.from_url(wb_url, timeout=timeout)

            if article is None:
                status = 'crawl error'
            elif article.text is None:
                status = 'crawl error'

        except (urllib.error.URLError,
                ValueError,
                http.client.RemoteDisconnected,
                socket.timeout) as e:
            article = None
            status = 'URL error'

    if status == 'succes':

        # validate attributes based on settings
        news_please_info = article.get_dict()

        if accepted_languages:
            if news_please_info['language'] not in accepted_languages:
                status = 'not in accepted languages'

        if num_chars_range:
            num_chars = len(news_please_info['text'])
            if num_chars not in num_chars_range:
                status = 'outside of accepted number of characters range'

        if title_required:
            if news_please_info['title'] is None:
                status = 'no title'

    if verbose >= 3:
        if status == 'succes':
            print()
            print(f'{status} {url}')
            if status == 'succes':
                attrs = ['title',
                         'url',
                         'date_publish',
                         'source_domain',
                         'language']

            for attr in attrs:
                print(f'ATTR {attr}: {getattr(article, attr)}')

            print('num chars', len(news_please_info['text']))
        else:
            print()
            print(status, wb_url, url)

    return status, news_please_info

status, article = run_newsplease(url='https://www.aasdfjsoidfj.nl',
                                 timeout=10)
assert status == 'Wayback Machine URL not found'

status, article = run_newsplease(url='https://www.rt.com/news/203203-ukraine-russia-troops-border/',
                                 timeout=10)
assert status == 'succes'

def get_ref_text_obj_of_primary_reference_texts(urls,
                                                timeout,
                                                startswith=None,
                                                accepted_languages=set(),
                                                excluded_domains=set(),
                                                title_required=True,
                                                num_chars_range=False,
                                                verbose=0):
    """
    crawl urls using newsplease and represent succesful crawls
    using the classes.ReferenceText object

    :param urls:
    :param timeout: see function "run_newsplease"
    :param startswith: see function "run_newsplease"
    :param accepted_languages: see function "run_newsplease"
    :param excluded_domains: see function "run_newsplease"
    :param title_required: see function "run_newsplease"
    :param num_chars_range: see function "run_newsplease"

    :rtype: dict
    :return: mapping from uri ->
    classes.ReferenceText object
    """
    url_to_info = {}
    stati = defaultdict(int)

    for url in urls:
        status, result = run_newsplease(url,
                                        timeout=timeout,
                                        startswith=startswith,
                                        excluded_domains=excluded_domains,
                                        accepted_languages=accepted_languages,
                                        title_required=title_required,
                                        num_chars_range=num_chars_range,
                                        verbose=verbose)

        info = {
            'status' : status,
            'web_archive_uri' : None,
            'name' : None,
            'creation_date' : None,
            'language' : None,
            'found_by' : None,
            'content' : None,
        }

        if status == 'succes':
            info['web_archive_uri']  = result['url']
            info['name'] = result['title']
            info['creation_date'] = result['date_publish']
            info['language'] = result['language']
            info['found_by'] = 'Wikipedia source'
            info['content'] = result['text']
        url_to_info[url] = info


    url_to_ref_text_obj = {}
    for url, info in url_to_info.items():
        stati[info['status']] += 1
        if info['status'] == 'succes':
            ref_text_obj = classes.ReferenceText(
                uri=url,
                web_archive_uri=info['web_archive_uri'],
                name=info['name'],
                content=info['content'],
                language=info['language'],
                creation_date=info['creation_date'],
                found_by=[info['found_by']],
            )

            url_to_ref_text_obj[url] = ref_text_obj

    if verbose >= 2:
        print()
        print(f'processed {len(urls)} urls')
        print(f'represented {len(url_to_ref_text_obj)} as ReferenceText object')
        print(stati)
        

    return url_to_ref_text_obj


if __name__ == '__main__':

    urls = ['http://www.tvweeklogieawards.com.au/logie-history/2000s/2005/',
            'http://www.australiantelevision.net/awards/logie2005.html',
            'https://www.smh.com.au/entertainment/once-twice-three-times-a-gold-logie-20050502-gdl8io.html',
            'https://www.imdb.com/event/ev0000401/2005/',
            'https://web.archive.org/web/20140126184012/http://www.tvweeklogieawards.com.au/logie-history/2000s/2005/']

    exluded_domains = {'jstor.org'}
    accepted_languages = {'en'}
    title_required = True
    num_chars_range = range(100, 10001)
    startswith = 'http'
    timeout = 2

    url_to_info = get_ref_text_obj_of_primary_reference_texts(urls,
                                                              timeout,
                                                              startswith=startswith,
                                                              accepted_languages=accepted_languages,
                                                              excluded_domains=exluded_domains,
                                                              title_required=True,
                                                              num_chars_range=num_chars_range,
                                                              verbose=2)