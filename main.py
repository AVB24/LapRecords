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
from models import Track, Car, Race, Racer, Event, Sponsor, BestLap, RaceClass

JINJA_ENVIRONMENT = jinja2.Environment(
	loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
	extensions=['jinja2.ext.autoescape'])

class Importer(webapp2.RequestHandler):
	def get(self):
		with open('testdata/data.csv') as fp:
			for line in iter(fp.readline, ''):

				line = line.split(',')
				print line
				s = Sponsor.get_or_insert(key_name=line[16], name=line[16])
				t = Track.get_or_insert(key_name="LRP", name="LRP", lap_distance=1.02)
				c = Car.get_or_insert(key_name=line[10]+line[11]+line[13], make=line[10], model=line[11],year=line[13],color=line[12],number=line[2])
				cl = RaceClass.get_or_insert(key_name=line[4], name=line[4])
				r = Racer.get_or_insert(key_name=line[3].replace(' ','.')+'@gmail.com', driver=users.User(line[3].replace(' ','.')+'@gmail.com'), points=int(line[9]), car=c, sponsor=s,raceclass=cl).put()
				best = BestLap.get_or_insert(key_name=t.name+line[3].replace(' ','.'), driver=r, track=t, time=line[5])
		self.response.write('done')

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
	('/importer', Importer)
], debug=True)
