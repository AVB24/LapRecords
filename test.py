#!/usr/bin/env python

import webapp2
import logging
from google.appengine.ext import db
from google.appengine.ext.db import GqlQuery
import urllib
import jinja2
import webapp2
import sys
import os
from datetime import datetime, timedelta
from time import sleep
from google.appengine.api import users, images
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from models import Track, Car, Race, Racer, Event, Sponsor, BestLap, RaceClass, Record
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext import blobstore
import csv
import unicodedata

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'])

def prefetch_refprop(entities, prop):
    ref_keys = [prop.get_value_for_datastore(x) for x in entities]
    ref_entities = dict((x.key(),x) for x in db.get(set(ref_keys)))
    for entity, ref_key in zip(entities, ref_keys):
        prop.__set__(entity, ref_entities[ref_key])
    return entities

def process_time(time):
    if time:
        if time != '0:':
            t = datetime.strptime(time, "%M:%S.%f")
            delta = timedelta(minutes=t.minute, seconds=t.second, microseconds=t.microsecond)
            return float(delta.total_seconds())
        else:
            return 0.000

def normalize_string(str):
    normStr = unicodedata.normalize('NFKD',unicode(str,"ISO-8859-1")).encode("ascii","ignore")
    return normStr

class Importer(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            greeting = ("Welcome, %s! (<a href=\"%s\">sign out</a>)" %
							(user.nickname(), users.create_logout_url("/")))
        else:
            greeting = ("<a href=\"%s\">Sign in or register</a>." %
							users.create_login_url("/"))
        		if not users.is_current_user_admin():
			self.redirect('/')
		drivers = Racer.all()
		upload_url = blobstore.create_upload_url('/upload')
		template_values = {
			'drivers': drivers,
			'user': user,
			'upload_url': upload_url,
			'greeting': greeting
		}
		template = JINJA_ENVIRONMENT.get_template('templates/importer.html')
		self.response.write(template.render(template_values))

class PicuploadHandler(webapp2.RequestHandler):
    def post(self):
        driver_key = db.Key(self.request.get('driver'))
		racer = Racer.get(driver_key)
		racer.picture = db.Blob(self.request.get('img'))
		racer.put()
		self.redirect('/')
################### Testing #################
with open('importdata/2006/20060804_rg_lrp.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        print(row['Name'], row['Class'], row['Model'])
        print normalize_string(row['Model'])
        #print dir(row['Model'])