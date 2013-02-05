'''
Created on Jan 18, 2013

@author: jason
'''

import requests, logging
from lxml import etree
from StringIO import StringIO
from urllib import urlencode
from json import load

logging.basicConfig(level=logging.INFO)
try:
    ks_auth_json = open('ks_auth.json')
    ks_auth = load(ks_auth_json)
except IOError:
    logging.error('Could not load auth file!')

def parse_response(response):
    return etree.parse(StringIO(response.text), etree.HTMLParser(encoding = 'UTF-8'))

s = requests.Session()
r = s.get('https://www.kickstarter.com/login')
t = parse_response(r)
e = t.xpath("//div[@id='login']//input[@name='authenticity_token']")[0]
authenticity_token = e.attrib['value']
logging.info('authenticity_token: ' + authenticity_token)

# generate the authentication payload for posting
data = {'utf8': '\xe2\x9c\x93',
        'authenticity_token': authenticity_token,
        'email': None,
        'password': None,
        'remember_me': '1',
        'commit': 'Log me in!'}
data.update(ks_auth)
uedata = urlencode(data)

# post the payload to authenticate the session
r = s.post('https://www.kickstarter.com/session', data = uedata)

# get info about a backing tier on a sample project
r = s.get('http://www.kickstarter.com/projects/weaver/empires-collide/pledge/edit')
assert('LEGACY' in r.text)
t = parse_response(r)
e = t.xpath("//input[@id='backing_backer_reward_id_1310707']")[0]
logging.info(e.attrib)