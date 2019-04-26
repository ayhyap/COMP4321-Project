import re
import sys
import urllib.request
import urllib.parse
import numpy as np
import dateutil.parser
import datetime as dt
import pickle
from collections import defaultdict
from sqlitedict import SqliteDict
from nltk.tokenize import word_tokenize
from nltk.stem import snowball, wordnet
from nltk.corpus import stopwords
from bs4 import BeautifulSoup as bs
from time import sleep

website_extensions = ['asp', 'aspx', 'axd', 'asx', 'asmx', 'ashx', 'html', 'htm', 'xhtml', 'jhtml', 'jsp', 'jspx', 'wss', 'js', 'pl', 'php', 'php4', 'php3', 'phtml', 'py', 'rb', 'rhtml', 'shtml', 'xml', 'rss', 'svg', 'cgi', 'dll', 'txt']

sys.setrecursionlimit(int(1e5))
stopwords = stopwords.words('english')
snowball = snowball.EnglishStemmer()
wordnet = wordnet.WordNetLemmatizer()


import threading
try:
    import thread
except ImportError:
    import _thread as thread

def quit_function(fn_name):
    print('timed out!')
    thread.interrupt_main()

def exit_after(s):
    '''
    use as decorator to exit process if 
    function takes longer than s seconds
    '''
    def outer(fn):
        def inner(*args, **kwargs):
            timer = threading.Timer(s, quit_function, args=[fn.__name__])
            timer.start()
            try:
                result = fn(*args, **kwargs)
            finally:
                timer.cancel()
            return result
        return inner
    return outer


@exit_after(60)
def scrape_page(page_url):
    global page2id, token2id
    _page_url = page_url
    # check for redirect!
    redirect = 5
    while redirect > 0:
        # get html file
        html = urllib.request.urlopen(page_url)
        # parse html file using beautiful soup package
        # see: https://www.crummy.com/software/BeautifulSoup/bs4/doc
        page = bs(html, 'html.parser')
        
        refresh = False
        for tag in page('meta'):
            try:
                if 'refresh' in str(tag.attrs['http-equiv']).lower():
                    refresh = True
                    redirect -= 1
                    temp = re.findall('[(URL)(url)(Url)]=\S+', tag.attrs['content'])[0]
                    temp = re.sub('[(URL)(url)(Url)]=', '', temp, count=1)
                    if temp.startswith('/'):
                        page_url = '/'.join(page_url.split('/')[:3]) + temp
                    elif not temp.startswith('http'):
                        src_has_extension = False
                        for file_extension in website_extensions:
                            if page_url.endswith('.' + file_extension):
                                src_has_extension = True
                                break
                        if src_has_extension:
                            # remove file part of page_url then add to end
                            page_url = '/'.join(page_url.split('/')[:-1]) + '/' + temp
                        else:
                            # just add to end
                            page_url = page_url + '/' + temp
                    else:
                        page_url = temp
                    page_url = page_url.strip()
                    
                    # remove /./././././
                    page_url = re.sub('/(\./)+','/',page_url)
                    
                    # this removes anchors from valid pages
                    page_url = re.sub('[#\?].*$','',page_url)
                    
                    valid = False
                    for file_extension in website_extensions:
                        if page_url.endswith('.' + file_extension):
                            valid = True
                            break
                    
                    # /folder1/file../file -> /file
                    page_url = re.sub('[^/]*/[^/]+\.\./', '', page_url)
                    
                    # /folder1/../folder2 -> /folder2
                    while re.search('/[^/]*/\.\./', page_url):
                        page_url = re.sub('/[^/]*/\.\./', '/', page_url, count = 1)
                    
                    # for consistency, remove ending slashes
                    if page_url.endswith('/'):
                        page_url = page_url[:-1]
                    
                    # for consistency, remove doubled slashes (except for http://) and use http:// (not https://)
                    page_url = re.sub('/+','/',page_url).replace('https', 'http').replace('http:/', 'http://')
                    
                    page_url = urllib.parse.unquote(page_url).replace(' ', '%20')
                    
                    print('redirected! trying:', page_url)
                    
                    if not valid or page_url in page2id.keys() or len(page_url) > 300:
                        raise urllib.error.URLError('')
                    break
            except:
                continue
        if not refresh:
            break
    
    
    # try to get last modified date from html header
    # to do date comparisons, first convert back to datetime object with dt.datetime.fromtimestamp()
    # then you can do: date1 > date2 (returns true if date1 comes after date2)
    try:
        last_modified = dateutil.parser.parse(dict(html.info()._headers)['Last-Modified']).timestamp()
    except:
        last_modified = dt.datetime.now(tz= dt.timezone.utc).timestamp()
        
    # this gets a naiive size of the page based solely on the html size, prior to javascript calls and stuff
    page_size = sys.getsizeof(str(page))

    # remove scripts and styles which interfere with html parsing
    for element in page(['script','style']):
        element.decompose()

    # get title
    try:
        page_title = page.title.contents[0]
    except:
        page_title = ''

    # get all links
    a_tags = page('a')
    link_urls = []
    link_texts = []
    for i, tag in enumerate(a_tags):
        try:
            link_url = str(tag.attrs['href'])
        except:
            # <a> tag without hyperlink
            continue

        link_text = ''
        while True:
            try:
                link_text = str(tag.attrs['title'])
                break
            except:
                pass

            try:
                # try acessing image alt text content
                link_text = str(tag.find('img').attrs['alt'])
                break
            except:
                pass

            try:
                link_text = str(tag.contents[0])
                assert ('<' not in link_text) and ('/>' not in link_text)
                break
            except:
                # no content (or just give up): no link text
                link_text = ''
                break
        
        link_url = link_url.strip()
        
        # check relative url
        if link_url.startswith('/'):
            link_url = '/'.join(page_url.split('/')[:3]) + link_url
        # skip anchors, HTML GET and javascript calls to same page
        elif link_url.startswith('#') or link_url.startswith('?') or link_url.startswith('javascript'):
            continue
        elif not link_url.startswith('http'):
            # either it's a lazy url without protocol like 'course.cse.ust.hk'
            # what if it's 'ust.hk'?
            # or it's a relative url like 'ust' or 'ust.html'
            
            if link_url.split('/')[0].count('.') > 1:
                link_url = 'http://' + link_url
            else:
                src_has_extension = False
                for file_extension in website_extensions:
                    if page_url.endswith('.' + file_extension):
                        src_has_extension = True
                        break
                if src_has_extension:
                    # remove file part of page_url then add to end
                    link_url = '/'.join(page_url.split('/')[:-1]) + '/' + link_url
                else:
                    # just add to end
                    link_url = page_url + '/' + link_url
        
        if '<script>' in link_url or 'mailto:' in link_url or 'tel:' in link_url:
            continue
        
        # remove /./././././
        link_url = re.sub('/(\./)+','/',link_url)
        
        
        # this removes anchors from valid pages
        link_url = re.sub('[#\?].*$','',link_url)
        
        # check if the link has a file extension
        # this returns true if there is a file extension like "file.???"
        if re.search('/[^/]*\.[^/]+$',link_url):
            # check it is a valid text-like file extension
            valid = False
            for file_extension in website_extensions:
                if link_url.endswith('.' + file_extension):
                    valid = True
                    break
            if not valid:
                continue
        
        # resolve relative parent directory addressing
        # /folder1/file../file -> /file
        link_url = re.sub('[^/]*/[^/]+\.\./', '', link_url)
        
        # /folder1/../folder2 -> /folder2
        while re.search('/[^/]*/\.\./', link_url):
            link_url = re.sub('/[^/]*/\.\./', '/', link_url, count = 1)
        
        # for consistency, remove ending slashes
        if link_url.endswith('/'):
            link_url = link_url[:-1]
        
        # for consistency, remove doubled slashes (except for http://) and use http:// (not https://)
        link_url = re.sub('/+','/',link_url).replace('https', 'http').replace('http:/', 'http://')
        
        link_url = urllib.parse.unquote(link_url).replace(' ', '%20')
        
        if len(link_url) > 300:
            continue
        
        link_texts.append(link_text)
        link_urls.append(link_url)
        # print(link_url)
    

    # get all text
        # plain text:
    full_site_string = ' ... '.join(page.strings)
        # image alt text
    images = page('img')
    image_text = []
    for image in images:
        try:
            image_text.append(image.attrs['alt'])
        except:
            # no alt text
            continue
        # do something

    full_image_string = ' ... '.join(image_text)
    full_string = full_site_string + ' ... ' + full_image_string

    # tokenize string
    tokens = word_tokenize(full_string)
    
    # remove stopwords
    tokens = [token for token in tokens if token.lower() not in stopwords]
    
    
    # split up hyphenated tokens
    # temp = []
    # for token in tokens:
        # temp += token.split('-')
    # tokens = temp
    # ACTUALLY, leave hyphenated tokens as they are because handling different spellings is too much trouble
    
    # ACTUALLY, replace invalid tokens with <unk> token to keep positions handy
    for i in range(len(tokens)-1, -1, -1):
        if not re.fullmatch('[a-zA-Z0-9\-/]+', tokens[i]) or re.fullmatch('[\-/]+', tokens[i]):
            tokens[i] = '<unk>'
        elif len(tokens[i]) <= 1:
            del tokens[i]
    
    # lemmatize
    tokens = [wordnet.lemmatize(token) for token in tokens]
    # stem words
    stemmed_tokens = [snowball.stem(token) for token in tokens]

    keyword_count = len(stemmed_tokens)

    # update vocabulary dict
    page_vocab = np.unique(stemmed_tokens)
    for word in page_vocab:
        try:
            temp = token2id[word]
        except:
            # the id increments for each new token
            token2id[word] = len(token2id)
    
    # translate processed text into ids
    stemmed_tokenids = [token2id[token] for token in stemmed_tokens]
    
    # count the keywords
    # tokens, counts = np.unique(stemmed_tokens, return_counts = True)
    # token_counts = dict(zip(tokens, counts))
    
    # or count the ids
    # tokens, counts = np.unique(stemmed_tokenids, return_counts = True)
    # tokenid_counts = dict(zip(tokens, counts))
    # ACTUALLY, keep the positions of the tokens instead of the counts
    
    token_positions = defaultdict(list)
    for i in range(len(stemmed_tokenids)):
        token_positions[stemmed_tokenids[i]].append(i)
    
    token_maxfreq = 1
    max_token = 0
    for key, value in token_positions.items():
        if key == 0:
            continue
        # token_maxfreq = max(token_maxfreq, len(value))
        if token_maxfreq < len(value):
            token_maxfreq = len(value)
            max_token = key
    id2token = dict((v,k) for k,v in token2id.items())
    # print('\t\t\t', token_maxfreq, '\t', id2token[max_token])
    
    # tokenize page title
    page_title_tokens = word_tokenize(page_title)
    page_title_tokens = [token for token in page_title_tokens if token not in stopwords]
    for i in range(len(page_title_tokens)-1, -1, -1):
        if not re.fullmatch('[a-zA-Z0-9\-/]+', page_title_tokens[i]) or re.fullmatch('[\-/]+', page_title_tokens[i]):
            page_title_tokens[i] = '<unk>'
        elif len(page_title_tokens[i]) <= 1:
            del page_title_tokens[i]
    # lemmatize
    page_title_tokens = [wordnet.lemmatize(token) for token in page_title_tokens]
    # stem words
    page_title_tokens = [snowball.stem(token) for token in page_title_tokens]
    page_title_vocab = np.unique(page_title_tokens)
    for word in page_title_vocab:
        try:
            temp = token2id[word]
        except:
            # the id increments for each new token
            token2id[word] = len(token2id)
    page_title_tokenids = [token2id[token] for token in page_title_tokens]
    page_title_token_positions = defaultdict(list)
    for i in range(len(page_title_tokenids)):
        page_title_token_positions[page_title_tokenids[i]].append(i)
    
    title_token_maxfreq = 1
    for key, value in page_title_token_positions.items():
        if key == 0:
            continue
        title_token_maxfreq = max(title_token_maxfreq, len(value))
    
    output = {}
    output['page_title'] = page_title
    output['page_url'] = _page_url
    output['page_size'] = page_size
    output['last_modified'] = last_modified
    output['token_positions'] = token_positions
    output['token_maxfreq'] = token_maxfreq
    
    output['keyword_count'] = keyword_count
    output['link_urls'] = link_urls
    
    output['page_title_token_positions'] = page_title_token_positions
    output['page_title_token_maxfreq'] = title_token_maxfreq
    # output['link_texts'] = np.array(link_texts)
    
    return output

def crawl(website, limit = 1000000, pages_to_scrape = None, url_check = None):
    if pages_to_scrape is None:
        pages_to_scrape = [website]
    
    if url_check is None:
        url_check = website
    
    # check if already in mapping
    try:
        temp = page2id[website]
    except:
        page2id[website] = len(page2id)
    
    try:
        failed_pages = np.loadtxt('failed_pages.txt', dtype=str).tolist()
    except:
        failed_pages = []
    
    
    scraped_pages = 0
    while scraped_pages < limit:
        while True:
            try:
                np.savetxt('pages_to_scrape.txt', pages_to_scrape, fmt = '%s', encoding='utf-8')
                break
            except:
                pass
        while True:
            try:
                np.savetxt('pages_to_scrape2.txt', pages_to_scrape, fmt = '%s', encoding='utf-8')
                break
            except:
                pass
        
        page_url = pages_to_scrape.pop(0)
        pageID = int(page2id[page_url])
        try:
            print(pageID, '(queued:', len(pages_to_scrape),')\t',page_url)
            page_dict = scrape_page(page_url)
            
            # page_dict['link_urls']: list of urls
            for i in range(len(page_dict['link_urls'])-1, -1, -1):
                url = page_dict['link_urls'][i]
                if url_check in url:
                    # print('\t\tO', url)
                    try:
                        temp = page2id[url]
                    except:
                        pages_to_scrape.append(url)
                        page2id[url] = len(page2id)
                else:
                    # print('\t\t-', url)
                    del page_dict['link_urls'][i]
            
            page_dict['link_ids'] = np.unique([page2id[url] for url in page_dict['link_urls']]).tolist()
            try:
                temp = linksDB[pageID]
            except KeyError:
                temp = {'out':[], 'in':[]}
            temp['out'] = page_dict['link_ids']
            linksDB[pageID] = temp
            
            token_positionsDB[pageID] = page_dict['token_positions']
            page_title_token_positionsDB[pageID] = page_dict['page_title_token_positions']
            
            for token, positions in page_dict['token_positions'].items():
                try:
                    tokensinpage = tokenid2page[int(token)]
                    # dict of pageid -> positions
                except:
                    tokensinpage = {}
                tokensinpage[pageID] = positions
                tokenid2page[int(token)] = tokensinpage
            
            for token, positions in page_dict['page_title_token_positions'].items():
                try:
                    tokensinpage = page_title_tokenid2page[int(token)]
                    # dict of pageid -> positions
                except:
                    tokensinpage = {}
                tokensinpage[pageID] = positions
                page_title_tokenid2page[int(token)] = tokensinpage
            
            metadata = np.array([page_dict['page_title'],page_dict['page_url'],page_dict['last_modified'],page_dict['page_size'],page_dict['keyword_count'], page_dict['token_maxfreq']])
            metadataDB[pageID] = metadata
            
            scraped_pages += 1

        except (urllib.error.URLError, KeyboardInterrupt, UnicodeEncodeError, urllib.error.HTTPError) as e:
            print("*********** Url doesn't work ***********")
            failed_pages.append(page_url)
            np.savetxt('failed_pages.txt', failed_pages, fmt = '%s', encoding='utf-8')
            np.savetxt('failed_pages2.txt', failed_pages, fmt = '%s', encoding='utf-8')
            
        if len(pages_to_scrape) == 0:
            print('ran out of pages to scrape!')
            break
    
    
    print('building in-links')
    for i, pageID in enumerate(linksDB.keys()):
        pageID = int(pageID)
        print('\r',i+1,'/',len(metadataDB),end='')
        
        # get out-links of page
        links = linksDB[pageID]['out']
        
        # loop over out-links
        for child in links:
            try:
                temp = linksDB[int(child)]
            except KeyError:
                temp = {'out':[], 'in':[]}
            
            if pageID not in temp['in']:
                temp['in'].append(pageID)
                linksDB[int(child)] = temp
    print('')

if __name__ == '__main__':
    # this is the database file
    # token_countsDB = SqliteDict('phase2-token_counts.sqlite', autocommit=True)
    token_positionsDB = SqliteDict('phase2-token_positions.sqlite', autocommit=True)
    page_title_token_positionsDB = SqliteDict('phase2-page_title_token_positions.sqlite', autocommit=True)
    metadataDB = SqliteDict('phase2-metadata.sqlite', autocommit=True)
    linksDB = SqliteDict('phase2-links.sqlite', autocommit=True)
    tokenid2page = SqliteDict('phase2-inverted_index.sqlite', autocommit=True)
    page_title_tokenid2page = SqliteDict('phase2-page_title_inverted_index.sqlite', autocommit=True)
    page2id = SqliteDict('phase2-page2id.sqlite', autocommit=True)
    token2id = SqliteDict('phase2-token2id.sqlite', autocommit=True)
    token2id['<unk>'] = 0
    
    try:
        pages_to_scrape = np.loadtxt('pages_to_scrape.txt', dtype=str).tolist()
    except:
        pages_to_scrape = None
    # crawl('http://www.cse.ust.hk', pages_to_scrape = pages_to_scrape, url_check = 'cse.ust.hk')
    crawl('http://www.cse.ust.hk', pages_to_scrape = pages_to_scrape, url_check = 'cse.ust.hk', limit = 30)