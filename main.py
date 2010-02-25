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

from xml.dom import minidom
import time, urllib, os, hashlib
import key

def notify(user, text, title, link=None):
    params = {'text':text,'title':title, 'icon': 'http://feednotifier.appspot.com/favicon.ico'}
    if link:
        params['link'] = link
    urlfetch.fetch('http://api.notify.io/v1/notify/%s?api_key=%s' % (hashlib.md5(user.email()).hexdigest(), key.api_key), method='POST', payload=urllib.urlencode(params))

class Subscription(db.Model):
    user = db.UserProperty(auto_current_user_add=True)
    repo = db.StringProperty(required=True)
    private_repo = db.BooleanProperty()
    private_key = db.StringProperty()
    created = db.DateTimeProperty(auto_now_add=True)
    updated = db.DateTimeProperty(auto_now=True)

class MainHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            logout_url = users.create_logout_url("/")
            subscriptions = Subscription.all().filter('user =', user)
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
            repo_url = self.request.get('repo')
            subscription = Subscription(repo = repo_url, private_key = 'david')
            subscription.put()
            #taskqueue.add(url='/subscribe', params={'id': feed.key().id()})

            self.redirect('/')
        else:
            self.response.out.write("Enter a feed")
            return


class NotifyHandler(webapp.RequestHandler):
    
    def post(self):
        private_key = self.request.get('key')
        payload = json.load(self.request.body)
        
        # feed = Feed.get_by_id(int(feed_id))
        # feed_dom = minidom.parseString(self.request.body.encode('utf-8', 'xmlcharrefreplace'))
        # for entry in feed_dom.getElementsByTagName('entry'):
        #     entry_title = entry.getElementsByTagName('title')[0].firstChild
        #     entry_title = entry_title.data if entry_title else "???"
        #     notify(feed.user, entry_title, feed.title or feed.url)

def main():
    application = webapp.WSGIApplication([
        ('/', MainHandler), 
        ('/notify/.*', NotifyHandler),
        ], debug=True)
    wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
    main()
