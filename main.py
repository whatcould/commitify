#!/usr/bin/env python

import wsgiref.handlers

from google.appengine.api.labs import taskqueue
from google.appengine.ext import webapp
from google.appengine.api import users
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.api import urlfetch

from google.appengine.api import mail
from django.utils import simplejson as json

import logging
import time, urllib, os, hashlib
import key


def notify(email, text, title, link=None):
    params = {'text':text,'title':title, 'icon': 'http://commitify.appspot.com/icons/github_favicon_white.png', 'tags':'sticky', 'sticky':'true'}
    if link:
        params['link'] = link
    count = 0
    while True:
        try:
            return urlfetch.fetch('http://api.notify.io/v1/notify/%s?api_key=%s' % (hashlib.md5(email).hexdigest(), key.api_key), method='POST', payload=urllib.urlencode(params))
        except urlfetch.DownloadError:
            count += 1
            logging.debug('DownloadError on fetch: %s, %s' % (email, title))
            if count == 3:
                raise

class Subscription(db.Model):
    user = db.UserProperty(auto_current_user_add=True)
    repo = db.StringProperty(required=True)
    private_key = db.StringProperty()
    created = db.DateTimeProperty(auto_now_add=True)
    updated = db.DateTimeProperty(auto_now=True)

class MainHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            logout_url = users.create_logout_url("/")
            subscriptions = Subscription.all().filter('user =', user).order('repo')
            
            temp_key = hashlib.md5(str(time.time()) + hashlib.md5(user.email()).hexdigest() ).hexdigest()[0:15]
        else:
            login_url = users.create_login_url('/')
        self.response.out.write(template.render('main.html', locals()))
    
    def post(self):
        user = users.get_current_user()
        if self.request.get('id'):
            subscription = Subscription.get_by_id(int(self.request.get('id')))
            if subscription.user == user:
                subscription.delete()
                self.redirect('/')
        
        if self.request.get('repo'):
            repo_url = self.request.get('repo').strip('/')
            key = self.request.get('key')
            subscription = Subscription(repo = repo_url, private_key = key)
            subscription.put()

            self.redirect('/')
        else:
            self.redirect('/')
            return


class CommitHandler(webapp.RequestHandler):
    
    def post(self):
        
        payload = json.loads(self.request.get('payload'))
        
        # get info for title, url of commit

        repo_url_parts = payload['repository']['url'].split('/')
        repo_title = "%s/%s" % (repo_url_parts[-2],repo_url_parts[-1])
        
        commit_count = len(payload['commits'])
        if commit_count == 0:
            logging.debug('No commits for push to repo: %s' % repo_title)
            self.response.out.write('Thanks, github.')
            return
        
        commit_url = payload['commits'][-1]['url']
        commit_message = payload['commits'][-1]['message']
        commit_author = payload['commits'][-1]['author']['name']
        logging.debug('Commit url/author: %s - %s' % (commit_url, commit_author))
        
        if commit_count == 1:
            title = 'Commit for %s by %s' % (repo_title, commit_author)
            text = "by %s. Message: %s" % (commit_author, commit_message)
        else:
            title = '%s commits for %s, latest by %s' % (commit_count, repo_title, commit_author)
            text = "Last commit by %s. Message: %s" % (commit_author, commit_message)
        
        if self.request.get('key'):
            private_key = self.request.get('key')
            subscriptions = Subscription.all().filter('repo =', repo_title).filter('private_key =', private_key).fetch(100)
        else:
            subscriptions = Subscription.all().filter('repo =', repo_title).fetch(100)
        if len(subscriptions) == 0:
            logging.debug('No subscriptions for push to repo: %s' % repo_title)
            
        for subscription in subscriptions:
            logging.debug('Email: %s / title: %s' % (subscription.user.email(), title))
            taskqueue.add(url='/notify', params={'email': subscription.user.email(), 'text':text, 'title':title, 'url': commit_url})
        
        self.response.out.write('Thanks, github.')

    def get(self):
        self.response.out.write('Whoops, github.')

        
class NotifyHandler(webapp.RequestHandler):
    
    def post(self):
        email = self.request.get('email')
        text = self.request.get('text')
        title = self.request.get('title')
        url = self.request.get('url')
        notify(email, text, title, url)


def main():
    logging.getLogger().setLevel(logging.DEBUG)
    
    application = webapp.WSGIApplication([
        ('/', MainHandler), 
        ('/commit', CommitHandler),
        ('/notify', NotifyHandler)
        ], debug=True)
    wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
    main()
