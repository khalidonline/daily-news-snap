"""Source-first image discovery and small, expiring source-outcome memory."""
import hashlib
import ipaddress
import json
import re
import socket
import time
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

OWNER_DECISION = 'owner-source-editorial-use-2026-09-22'
PUBLISHERS = {'aawsat.com','www.aawsat.com','www.alyaum.com','bbc.com','www.bbc.com','www.bbc.co.uk','bbc.co.uk'}


def public_url(url):
    p=urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in (None,443) or p.fragment:
        raise ValueError('primary_url_rejected')
    # This publisher CDN is source-verified and also works behind DNS proxies.
    if p.hostname in {'static.srpcdigital.com','images-assets.nasa.gov'}:
        return url
    addresses=socket.getaddrinfo(p.hostname,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('primary_private_network_rejected')
    return url


class SameSiteRedirect(HTTPRedirectHandler):
    def __init__(self):
        self.hops=0
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        old=urlsplit(req.full_url).hostname.removeprefix('www.')
        new=(urlsplit(newurl).hostname or '').removeprefix('www.')
        if new!=old or self.hops>=2:
            raise ValueError('primary_redirect_rejected')
        public_url(newurl);self.hops+=1
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def primary_bytes(url, *, limit=16*1024*1024):
    public_url(url)
    with build_opener(SameSiteRedirect()).open(Request(url,headers={'User-Agent':'DailyNewsSnap/2.0'}),timeout=10) as response:
        data=response.read(limit+1)
    if len(data)>limit:raise ValueError('primary_too_large')
    return data


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images=[];self.links=[];self.script=None;self.article=0;self.figure=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='article':self.article+=1
        if tag=='figure' and self.article:self.figure+=1
        if tag=='img' and self.article and self.figure:
            self.images.append((a.get('data-src') or a.get('src',''),a.get('alt','')))
        if tag=='meta' and (a.get('property') or a.get('name')) in {'og:image','og:image:secure_url','twitter:image'}:
            self.images.append((a.get('content',''),''))
        if tag=='a' and a.get('href'):self.links.append(a['href'])
        if tag=='script' and a.get('type')=='application/ld+json':self.script=[]
    def handle_data(self,data):
        if self.script is not None:self.script.append(data)
    def handle_endtag(self,tag):
        if tag=='article':self.article=max(0,self.article-1)
        if tag=='figure':self.figure=max(0,self.figure-1)
        if tag=='script' and self.script is not None:
            try:self.structured(json.loads(''.join(self.script)))
            except (ValueError,TypeError,RecursionError):pass
            self.script=None
    def structured(self,value,depth=0):
        if depth>8:return
        if isinstance(value,list):
            for v in value[:30]:self.structured(v,depth+1)
        elif isinstance(value,dict):
            types=value.get('@type',[])
            if isinstance(types,str):types=[types]
            if set(types)&{'NewsArticle','Article','ReportageNewsArticle','Product','Organization'}:
                images=value.get('image',[])
                if not isinstance(images,list):images=[images]
                for im in images[:10]:
                    if isinstance(im,str):self.images.append((im,''))
                    elif isinstance(im,dict):self.images.append((im.get('contentUrl') or im.get('url',''),im.get('caption','')))
            self.structured(value.get('@graph',[]),depth+1)


def identity(source,url):
    return 'primary:'+hashlib.sha256((source+'\n'+url).encode()).hexdigest()[:24]


def page_images(html,source,subject,*,kind,entity=None,official_site=None):
    parser=Page();parser.feed(html)
    rows=[];seen=set()
    for url,caption in parser.images:
        url=urljoin(source,url)
        if url in seen or urlsplit(url).scheme!='https':continue
        seen.add(url)
        row={'provider':'primary_media','asset_id':identity(source,url),'original_url':url,'download_url':url,
             'source_url':source,'source_kind':kind,'title':str(caption or (subject + ': source illustration; identity unverified'))[:250],
             'description':str(caption or subject)[:900],'collection_subject':subject,
             'credit':urlsplit(source).hostname,'license':'All rights reserved','licensing_verified':False,
             'owner_use_decision':OWNER_DECISION,'rights_status':'owner_accepted_editorial_use',
             'image_role':'source-page illustration, not proof of the depicted person/building identity; review pixels and card context'}
        if kind=='official':row.update(website_entity=entity,official_site=official_site)
        if owner_primary_use(row):rows.append(row)
        if len(rows)>=8:break
    return rows


def owner_primary_use(row):
    if isinstance(row,dict) and row.get('provider')=='nasa':
        try:
            return bool(row.get('owner_use_decision')==OWNER_DECISION
                and row.get('rights_status')=='owner_accepted_editorial_use'
                and row.get('license')=='review_required'
                and row.get('source_url')=='https://images.nasa.gov/details/'+quote(row['asset_id'],safe='')
                and urlsplit(row['original_url']).netloc=='images-assets.nasa.gov'
                and urlsplit(row['original_url']).scheme=='https'
                and not urlsplit(row['original_url']).fragment
                and row.get('download_url')==row['original_url'])
        except (KeyError,TypeError,ValueError):return False
    try:
        source=urlsplit(row['source_url']);image=urlsplit(row['original_url'])
        if any(p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in (None,443) or p.fragment for p in (source,image)):return False
        bound=(row.get('source_kind')=='article' and source.hostname in PUBLISHERS)
        if row.get('source_kind')=='official':
            bound=bool(re.fullmatch(r'Q[1-9][0-9]*',row.get('website_entity','')) and urlsplit(row.get('official_site','')).netloc==source.netloc)
        return bool(bound and row.get('provider')=='primary_media' and row.get('download_url')==row['original_url']
            and row.get('asset_id')==identity(row['source_url'],row['original_url'])
            and row.get('owner_use_decision')==OWNER_DECISION and row.get('rights_status')=='owner_accepted_editorial_use'
            and row.get('license')=='All rights reserved')
    except (KeyError,TypeError,ValueError):return False


def official_site_images(site,entity,subject,*,fetch=primary_bytes):
    """Site originates from the resolved encyclopedia entity's P856, never a model URL."""
    root=fetch(site,limit=2*1024*1024).decode('utf-8',errors='replace')
    rows=page_images(root,site,subject,kind='official',entity=entity,official_site=site)
    parser=Page();parser.feed(root)
    links=[]
    for href in parser.links:
        url=urljoin(site,href);p=urlsplit(url)
        if p.netloc==urlsplit(site).netloc and re.search(r'news|media|press',p.path,re.I) and not p.fragment and not p.query and url not in links:links.append(url)
    for url in links[:2]:
        try:
            html=fetch(url,limit=2*1024*1024).decode('utf-8',errors='replace')
            rows+=page_images(html,url,subject,kind='official',entity=entity,official_site=site)
        except (OSError,ValueError):continue
    return list({r['original_url']:r for r in rows}.values())[:10]


class ImageMemory:
    """Per-entity outcomes expire after a week; no permanent global blacklist."""
    def __init__(self,store=None,clock=time.time):
        self.store,self.clock=store,clock
        self.rows=(store.read() if store else {}).get('images',{})
    def key(self,subject,row):
        return hashlib.sha256((subject.casefold()+'\n'+str(row.get('original_url') or row['asset_id'])).encode()).hexdigest()
    def rejected(self,subject,row):
        old=self.rows.get(self.key(subject,row),{})
        return old.get('okay') is False and self.clock()-old.get('at',0)<7*86400
    def preferred(self,subject):
        return {r['provider'] for r in self.rows.values() if r.get('subject')==subject.casefold() and r.get('okay') is True and self.clock()-r.get('at',0)<7*86400}
    def record(self,subject,row,okay):
        self.rows[self.key(subject,row)]={'subject':subject.casefold(),'provider':row.get('provider'),'okay':bool(okay),'at':self.clock()}
    def save(self):
        self.rows=dict(sorted(self.rows.items(),key=lambda item:item[1]['at'],reverse=True)[:300])
        if self.store:self.store.save({'version':1,'images':self.rows})
