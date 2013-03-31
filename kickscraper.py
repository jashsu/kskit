'''
Kickstarter scraper to help mine info about a project's backers
Usage:
python ./kickscraper.py http://www.kickstarter.com/projects/2093540459/msj-the-musical-0 2
'''

import requests, time, json, sys, gzip, operator
from sys import stdout
from lxml import etree
from StringIO import StringIO
from urllib import urlencode
from random import random
from HTMLParser import HTMLParser

def scrape_project_backers(creator, project, sleep=.5, spread=.5):
    session = requests.Session()
    params = {}
    last_page = False
    project_backers = []
    project_backers_url = 'http://www.kickstarter.com/projects/{}/{}/backers'.format(creator, project)

    stdout.write('\nScraping project backer list\n')
    while(not last_page):
        response = session.get('{}?{}'.format(project_backers_url, urlencode(params)))
        response_tree = etree.parse(StringIO(response.text), etree.HTMLParser(encoding = 'UTF-8'))
        page = response_tree.xpath("//li[@class='page']")[0]
        last_page = {'false': False, 'true': True}[page.attrib['data-last_page']]
        project_backers.extend(page.getchildren())
        params['cursor'] = project_backers[-1].attrib['data-cursor']
        stdout.write('.')
        stdout.flush()
        if not last_page: time.sleep(sleep + random() * spread)

    session.close()
    return project_backers

def scrape_user_info(user_slug, session, sleep=.5, spread=.5):
    params = {}
    last_page = False
    user_profile_url = 'http://www.kickstarter.com/profile/{}'.format(user_slug)
    user_info = {'timestamp': time.time(),
                 'user_slug': user_slug,
                 'user_profile_url': user_profile_url,
                 'user_backed_projects': []}

    while(not last_page):
        response = session.get('{}?{}'.format(user_profile_url, urlencode(params)))
        response_tree = etree.parse(StringIO(response.text), etree.HTMLParser(encoding = 'UTF-8'))
        page = response_tree.xpath("//li[@class='page']")[0]
        last_page = {'false': False, 'true': True}[page.attrib['data-last_page']]
        backed_projects = [tuple(project_url.split('/')[-2:]) for project_url in page.xpath('./a/@href')]
        user_info['user_backed_projects'].extend(backed_projects)
        params['page'] = int(page.attrib['data-page_number']) + 1
        if not last_page: time.sleep(sleep + random() * spread)

    wishlist = [('user_name', "//meta[@property='kickstarter:name']/@content"),
                ('user_joined', "//meta[@property='kickstarter:joined']/@content"),
                ('user_image_large', "//meta[@property='og:image']/@content")]
    for item in wishlist:
        user_info[item[0]] = response_tree.xpath(item[1])[0]

    return user_info

def process_project_backers(project_backers):
    session = requests.Session()
    project_backers_processed = []

    stdout.write('\nScraping users backed projects lists\n')
    for user in project_backers:
        user_slug = user.xpath("./a/@href")[0].split('/')[2]
        project_backers_processed.append(scrape_user_info(user_slug, session))
        stdout.write('.')
        stdout.flush()

    session.close()
    return project_backers_processed

def initialize_project_cache_v1():
    f = gzip.open('project_cache_v1.json.gz', 'wb')
    f.write(json.dumps({}))
    f.close()

def update_project_cache_v1(creator, project, force=False):
    sanitizer = [('\\\\"', "'"),]

    while True:
        try:
            f = gzip.open('project_cache_v1.json.gz', 'rb')
            project_cache_v1 = json.loads(f.read())
        except:
            stdout.write('\nUnable to read project cache; attempting to regenerate')
            initialize_project_cache_v1()
            continue
        break

    f.close()
    if project in project_cache_v1 and force == False:
        return

    f = gzip.open('project_cache_v1.json.gz', 'wb')
    stdout.write('\nUpdating project_cache: {}'.format(project))
    project_url = 'http://www.kickstarter.com/projects/{}/{}'.format(creator, project)
    session = requests.Session()
    try:
        response = session.get(project_url)
        response_tree = etree.parse(StringIO(response.text), etree.HTMLParser(encoding = 'UTF-8'))
        current_project = HTMLParser().unescape(response_tree.xpath('//head/script[contains(text(), "window.current_project")]')[0].text.split('"')[1])
        for rule in sanitizer:
            current_project = current_project.replace(*rule)
        project_cache_v1[project] = json.loads(current_project)
    finally:
        f.write(json.dumps(project_cache_v1))
        session.close()
        f.close()

def query_project_cache_v1(project):
    f = gzip.open('project_cache_v1.json.gz', 'rb')
    project_cache_v1 = json.loads(f.read())
    f.close()
    return project_cache_v1[project]

def print_similarity_statistics(project_backers_processed, project_threshold):
    count = {}

    for user in project_backers_processed:
        for creator_project in user['user_backed_projects']:
            update_project_cache_v1(creator_project[0], creator_project[1])
            if creator_project[1] in count:
                count[creator_project[1]] += 1
            else:
                count[creator_project[1]] = 1

    sorted_count = sorted(count.iteritems(), key=operator.itemgetter(1), reverse=True)
    stdout.write('\n')
    for project in sorted_count:
        if project[1] >= int(project_threshold):
            current_project = query_project_cache_v1(project[0])
            stdout.write('\n{}\n    {} backers in common\n    {} ({})'.format(project[0], project[1], current_project['category']['name'], current_project['category']['id']))

def main(args):
    project_url, project_threshold = args[1:]
    creator, project = project_url.split('/')[4:6]

    project_backers = scrape_project_backers(creator, project)
    project_backers_processed = process_project_backers(project_backers)
    f = open('{}_{}.json'.format(project, int(time.time())), 'wb')
    f.write(json.dumps(project_backers_processed))
    f.close()
    print_similarity_statistics(project_backers_processed, project_threshold)

    raw_input('\n\nPress any key to exit...\n')

if __name__ == '__main__':
    sys.exit(main(sys.argv))