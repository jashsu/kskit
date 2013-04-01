#!/usr/bin/env python
""" kickscraper.py: A simple Kickstarter project and user data scraping tool.
    Usage: python ./kickscraper.py <project url> <backer threshold> <category threshold>
        backer threshold: minimum integer number of backers to display project in common
        category threshold: minimum decimal percentage to display category"""

import requests, time, json, sys, gzip, operator
from sys import stdout
from lxml import etree
from StringIO import StringIO
from urllib import urlencode
from urlparse import urlparse
from random import random
from HTMLParser import HTMLParser

__author__ = 'Jason Hsu'
__version__ = '1'

class DeletedUserError(Exception):
    pass

class ProgressBar(object):
    def __init__(self):
        self.counter = 0

    def increment(self, n=1):
        self.counter += n

    def draw(self, tick='.'):
        draw_out = ''
        if self.counter % 50 == 0:  draw_out += '\n[{}] '.format(time.ctime())
        if self.counter % 10 == 0:  draw_out += tick # For optional fancier gfx
        else:                       draw_out += tick
        stdout.write(draw_out)
        stdout.flush()

class ProjectCacheV1(object):
    """Simple object for caching project information. Todo: upgrade to db."""

    __version__ = 1
    project_cache_path = './project_cache/v1.json.gz'
    project_cache = {}
    session = requests.Session()

    def __init__(self):
        """Initialize project cache from disk copy."""

        while True:
            try:
                fh = gzip.open(self.project_cache_path, 'rb')
            except:
                stdout.write('\n[{}] Unable to read project cache, regenerating'.format(time.ctime()))
                fh = gzip.open(self.project_cache_path, 'w+')
                fh.write(json.dumps({}))
                fh.close()
                continue
            break
        self.project_cache = json.loads(fh.read())
        fh.close()

    def refresh(self):
        """Scan through the project cache and refresh all project information."""

        # todo: implement this
        pass

    def update(self, creator, project, progress_bar, force=False):
        """Adds a project to the project cache if it hasn't already been cached."""

        sanitizer = [('\\\\"', "'"),]
        project_url = 'http://www.kickstarter.com/projects/{}/{}'.format(creator, project)

        if project in self.project_cache and force == False:
            return  # Exit quickly if we can
        else:
            response = self.session.get(project_url)
            response_tree = etree.parse(StringIO(response.text), etree.HTMLParser(encoding = 'UTF-8'))
            current_project = HTMLParser().unescape(response_tree.xpath('//head/script[contains(text(), "window.current_project")]')[0].text.split('"')[1])
            for rule in sanitizer:
                current_project = current_project.replace(*rule)
            self.project_cache[project] = json.loads(current_project)
            progress_bar.draw('c')
            progress_bar.increment()

    def query(self, project):
        """Get information about a project from the project cache."""

        return self.project_cache[project]    # todo: better handling

    def close(self):
        """Perform some cleanup tasks."""
        fh = gzip.open(self.project_cache_path, 'w+')
        fh.write(json.dumps(self.project_cache))
        fh.close()
        self.session.close()

class UserCacheV1(object):
    """Simple object for caching user information. Todo: implement this."""

    pass

def scrape_project_backers(creator, project, sleep=.2, spread=.1):
    """Scrape the list of backers from the target project."""

    progress_bar = ProgressBar()
    session = requests.Session()
    params = {}
    last_page = False
    project_backers = []
    project_backers_url = 'http://www.kickstarter.com/projects/{}/{}/backers'.format(creator, project)

    stdout.write('\n[{}] Scraping project backer list'.format(time.ctime()))
    while(not last_page):
        response = session.get('{}?{}'.format(project_backers_url, urlencode(params)))
        response_tree = etree.parse(StringIO(response.text), etree.HTMLParser(encoding = 'UTF-8'))
        page = response_tree.xpath("//li[@class='page']")[0]
        last_page = {'false': False, 'true': True}[page.attrib['data-last_page']]
        project_backers.extend(page.getchildren())
        params['cursor'] = project_backers[-1].attrib['data-cursor']
        progress_bar.draw()
        progress_bar.increment()
        if not last_page:
            time.sleep(sleep + random() * spread)

    session.close()
    return project_backers

def scrape_user_info(user_slug, session, sleep=.2, spread=.1):
    """Scrape information about the user, including the list of backed projects."""

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
        if 'This person is no longer active on Kickstarter.' in response.text:
            raise DeletedUserError
        page = response_tree.xpath("//li[@class='page']")[0]
        last_page = {'false': False, 'true': True}[page.attrib['data-last_page']]
        backed_projects = [tuple(project_url.split('/')[-2:]) for project_url in page.xpath('./a/@href')]
        user_info['user_backed_projects'].extend(backed_projects)
        params['page'] = int(page.attrib['data-page_number']) + 1
        if not last_page:
            time.sleep(sleep + random() * spread)

    wishlist = [('user_name', "//meta[@property='kickstarter:name']/@content"),
                ('user_joined', "//meta[@property='kickstarter:joined']/@content"),
                ('user_image_large', "//meta[@property='og:image']/@content")]
    for item in wishlist:
        user_info[item[0]] = response_tree.xpath(item[1])[0]

    return user_info

def process_project_backers(creator, project, project_backers):
    """Process the list of backers into dicts and scrape the user details."""

    progress_bar = ProgressBar()
    session = requests.Session()
    project_backers_processed = []
    project_backers_path = './project_backers/{}_{}_{}.json'

    stdout.write('\n[{}] Scraping users backed projects lists'.format(time.ctime()))
    for user in project_backers:
        user_slug = user.xpath("./a/@href")[0].split('/')[2]
        try:
            user_info = scrape_user_info(user_slug, session)
        except DeletedUserError:
            progress_bar.draw('x')
        else:
            project_backers_processed.append(user_info)
            progress_bar.draw()
        progress_bar.increment()

    session.close()
    f = open(project_backers_path.format(creator, project, int(time.time())), 'w+')
    f.write(json.dumps(project_backers_processed))
    f.close()

    return project_backers_processed

def print_similarity_statistics(project_cache, project_backers_processed, project_threshold, category_threshold):
    """Print statistical information about what other projects backers have backed."""

    progress_bar = ProgressBar()
    projects_data = {}
    category_data = {}

    stdout.write('\n[{}] Compiling project similarity statistics'.format(time.ctime()))
    for user in project_backers_processed:
        progress_bar.draw()
        progress_bar.increment()
        for creator_project in user['user_backed_projects']:
            project_cache.update(*creator_project, progress_bar=progress_bar)
            project = creator_project[1]
            if project in projects_data:
                projects_data[project][0] += 1   # Increment count
            else:
                projects_data[project] = [1, 0, '']

    stdout.write('\n[{}] Reticulating splines'.format(time.ctime()))
    stdout.flush()
    for project in projects_data:
        current_project = project_cache.query(project)
        projects_data[project][1] = category_id = current_project['category']['id']
        projects_data[project][2] = category_name = current_project['category']['name']
        # projects_data := {project: [project_count, category_id, category_name], ...}
        # current_project := Kickstarter project API json object (window.current_project)
        if category_id in category_data:
            category_data[category_id][0] += projects_data[project][0]
        else:
            category_data[category_id] = [projects_data[project][0], category_name]
        # category_data := {category_id: [category_count, category_name]}

    sorted_projects_data = sorted(projects_data.iteritems(), key=lambda (k,v): v[0], reverse=True)
    # sorted_projects_data := [(project, [project_count, category_id, category_name]), ...]

    stdout.write('\n[{0}]\n[{0}] Projects in common (popularity sort)'.format(time.ctime()))
    for project_data in sorted_projects_data:
        if project_data[1][0] >= int(project_threshold):
            stdout.write('\n[{}] {}'.format(time.ctime(), project_data[0]))
            stdout.write('\n[{}]     {} common backers'.format(time.ctime(), project_data[1][0]))
            stdout.write('\n[{}]     {} ({})'.format(time.ctime(), project_data[1][2], project_data[1][1]))
            stdout.flush()

    category_sum = sum([i[0] for i in category_data.values()])
    sorted_category_data = sorted(category_data.iteritems(), key=lambda (k,v): v[0], reverse=True)
    # sorted_category_data := [(category_id, [category_count, category_name]), ...]

    stdout.write('\n[{0}]\n[{0}] Favorite categories (popularity sort)'.format(time.ctime()))
    for category_data in sorted_category_data:
        category_match = float(category_data[1][0])/category_sum
        if category_match >= float(category_threshold):
            stdout.write('\n[{}] {}% {} ({})'.format(time.ctime(), round(category_match*100, 1), category_data[1][1], category_data[0]))

def main(args):
    project_url, project_threshold, category_threshold = args[1:]
    creator, project = urlparse(project_url)[2].split('/')[2:4]
    project_cache = ProjectCacheV1()

    project_backers = scrape_project_backers(creator, project)
    project_backers_processed = process_project_backers(creator, project, project_backers)
    print_similarity_statistics(project_cache, project_backers_processed, project_threshold, category_threshold)

    project_cache.close()
    stdout.write('\n\n')

if __name__ == '__main__':
    sys.exit(main(sys.argv))