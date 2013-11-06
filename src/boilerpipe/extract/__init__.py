# coding=utf8

import jpype
import urllib2
import socket
import charade
import threading
import re

socket.setdefaulttimeout(15)
lock = threading.Lock()

InputSource        = jpype.JClass('org.xml.sax.InputSource')
StringReader       = jpype.JClass('java.io.StringReader')
HTMLHighlighter    = jpype.JClass('de.l3s.boilerpipe.sax.HTMLHighlighter')
BoilerpipeSAXInput = jpype.JClass('de.l3s.boilerpipe.sax.BoilerpipeSAXInput')

re_enc_error = re.compile(r";?\sdir=.*")
re_enc_error2 = re.compile(r"text/html;\s+")
re_enc_win = re.compile(r"cp-1251")
re_enc_def = re.compile(r"default_charset")
re_http = re.compile(r"http://")
re_slash = re.compile(r"/.*")
re_rus = re.compile(ur"[а-я]",re.U|re.I)
DEFAULT_ENCODING = "utf-8"

def whatisthis(s):
    if isinstance(s, str):
        return "str"
    elif isinstance(s, unicode):
        return "unicode"
    else:
        return "not str"

class Extractor(object):
    """
    Extract text. Constructor takes 'extractor' as a keyword argument,
    being one of the boilerpipe extractors:
    - DefaultExtractor
    - ArticleExtractor
    - ArticleSentencesExtractor
    - KeepEverythingExtractor
    - KeepEverythingWithMinKWordsExtractor
    - LargestContentExtractor
    - NumWordsRulesExtractor
    - CanolaExtractor
    """
    extractor = None
    source    = None
    data      = None
    header_default   = {'User-Agent': 'Mozilla/5.0'}
    headers = ['Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.97 Safari/537.11',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:17.0) Gecko/20100101 Firefox/17.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_2) AppleWebKit/536.26.17 (KHTML, like Gecko) Version/6.0.2 Safari/536.26.17',
    'Mozilla/5.0 (Linux; U; Android 2.2; fr-fr; Desire_A8181 Build/FRF91) App3leWebKit/53.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1',
    'Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; FunWebProducts; .NET CLR 1.1.4322; PeoplePal 6.2)',
    'Mozilla/5.0 (Windows NT 5.1; rv:13.0) Gecko/20100101 Firefox/13.0.1',
    'Opera/9.80 (Windows NT 5.1; U; en) Presto/2.10.289 Version/12.01',
    'Mozilla/5.0 (Windows NT 5.1; rv:5.0.1) Gecko/20100101 Firefox/5.0.1',
    'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.0; Trident/4.0; Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1) ; .NET CLR 3.5.30729)']
    
    def __init__(self, extractor='DefaultExtractor', **kwargs):
        if kwargs.get('url'):
            # Correctly encode url  
            url = unicode(kwargs['url'])
            if re_rus.search(url):
                url = re_http.sub("", url)
                url = re_slash.sub("", url)
                url = url.encode("idna")
                url = "http://" + url

            # Set header 
            h = {'User-Agent':self.headers[0], 'Accept':'*/*'}
            
            # Download the page
            request     = urllib2.Request(url, headers=h)
            connection  = urllib2.urlopen(request)
            self.data   = connection.read()
            encoding    = connection.headers['content-type'].lower().split('charset=')[-1]

            # Decode the page contents in the correct encoding
            if self.data is None: 
		raise Exception('Html data cannot be extracted.')
            if encoding.lower() == 'text/html':
                encoding = charade.detect(self.data)['encoding']
            old = encoding
            encoding = re_enc_error.sub("", encoding)
	    encoding = re_enc_error2.sub("", encoding)
	    encoding = re_enc_win.sub("windows-1251", encoding)
            if re_enc_def.search(encoding): encoding = DEFAULT_ENCODING
	    self.data = unicode(self.data, encoding, "ignore")

        elif kwargs.get('html'):
            self.data = kwargs['html']
            if not isinstance(self.data, unicode):
                self.data = unicode(self.data, charade.detect(self.data)['encoding'])
        else:
            raise Exception('No text or url provided')

        try:
            # make it thread-safe
            if threading.activeCount() > 1:
                if jpype.isThreadAttachedToJVM() == False:
                    jpype.attachThreadToJVM()
            lock.acquire()
            
            self.extractor = jpype.JClass(
                "de.l3s.boilerpipe.extractors."+extractor).INSTANCE
        finally:
            lock.release()
    
        reader = StringReader(self.data)
        self.source = BoilerpipeSAXInput(InputSource(reader)).getTextDocument()
        self.extractor.process(self.source)
    
    def getText(self):
        return self.source.getContent()
    
    def getHTML(self):
        highlighter = HTMLHighlighter.newExtractingInstance()
        return highlighter.process(self.source, self.data)
    
    def getImages(self):
        extractor = jpype.JClass(
            "de.l3s.boilerpipe.sax.ImageExtractor").INSTANCE
        images = extractor.process(self.source, self.data)
        jpype.java.util.Collections.sort(images)
        images = [
            {
                'src'   : image.getSrc(),
                'width' : image.getWidth(),
                'height': image.getHeight(),
                'alt'   : image.getAlt(),
                'area'  : image.getArea()
            } for image in images
        ]
        return images
