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
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from models import Track, Car, Race, Racer, Event, Sponsor, BestLap, RaceClass, Record
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext import blobstore

JINJA_ENVIRONMENT = jinja2.Environment(
	loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
	extensions=['jinja2.ext.autoescape'])

class Importer(webapp2.RequestHandler):
	def get(self):
		upload_url = blobstore.create_upload_url('/upload')
		self.response.out.write('<html><body>')
		self.response.out.write('<form action="%s" method="POST" enctype="multipart/form-data">' % upload_url)
		self.response.out.write("""Upload File: <input type="file" name="file"><br> <input type="submit" name="submit" value="Submit"> </form></body></html>""")

		for b in blobstore.BlobInfo.all():
			self.response.out.write('<li><a href="/serve/%s' % str(b.key()) + '">' + str(b.filename) + '</a>')

class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
	def post(self):
		upload_files = self.get_uploads('file')[0]
		blob_key = upload_files.key()
		blob_info = upload_files
		record = Record(csv=str(blob_info)).put()
		blob_reader = blobstore.BlobReader(blob_key)
#		with open(blob_info) as fp:
		for line in blob_reader.readlines():

			line = line.split(',')
			print line
			s = Sponsor.get_or_insert(key_name=line[16], name=line[16])
			t = Track.get_or_insert(key_name="LRP", name="LRP", lap_distance=1.02)
			c = Car.get_or_insert(key_name=line[10]+line[11]+line[13], make=line[10], model=line[11],year=line[13],color=line[12],number=line[2])
			cl = RaceClass.get_or_insert(key_name=line[4], name=line[4])
			r = Racer.get_or_insert(key_name=line[3].replace(' ','.')+'@gmail.com', name=line[3], driver=users.User(line[3].replace(' ','.')+'@gmail.com'), points=int(line[9]), car=c, sponsor=s,raceclass=cl).put()
			best = BestLap.get_or_insert(key_name=t.name+line[3].replace(' ','.'), driver=r, track=t, time=line[5])
		
		self.redirect('/bestlap')

class MainHandler(webapp2.RequestHandler):
	def get(self):
		if users.get_current_user():
			user = users.get_current_user()
			url = users.create_logout_url(self.request.uri)
			url_linktext = 'Logout'
		else:
			url = users.create_login_url(self.request.uri)
			url_linktext = 'Login'

		cars = Car.all()	
		template_values = {
			'user': user,
			'cars': cars,
			'cars_count': cars.count()+1
		}
		
		template = JINJA_ENVIRONMENT.get_template('templates/index.html')
		self.response.write(template.render(template_values))

class BestLapHandler(webapp2.RequestHandler):
	def get(self):
		if users.get_current_user():
			user = users.get_current_user()
			url = users.create_logout_url(self.request.uri)
			url_linktext = 'Logout'
		else:
			url = users.create_login_url(self.request.uri)
			url_linktext = 'Login'
	
		bestlaps = BestLap.all()	
		template_values = {
			'user': user,
			'bestlaps': bestlaps,
			'bestlaps_count': bestlaps.count()+1
		}
		
		template = JINJA_ENVIRONMENT.get_template('templates/bestlap.html')
		self.response.write(template.render(template_values))

app = webapp2.WSGIApplication([
	('/', MainHandler),
	('/bestlap', BestLapHandler),
	('/importer', Importer),
	('/upload', UploadHandler)
], debug=True)
