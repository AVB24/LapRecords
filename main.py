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

def determine_best(time, entity):
	logging.info('Starting Logging for Racer:' + entity.driver.name)
	race_class = entity.raceclass#.name
	track = entity.track
	bestlaps_query = BestLap.all()
	bestlaps_query.filter("raceclass =", race_class)
	bestlaps_query.filter("track =", track)
	bestlaps_query.filter("isBest =", True)
	q = bestlaps_query.fetch(1,0)
	logging.info('Query Count: ' + str(len(q)))
	logging.info('RaceClass: ' + entity.raceclass.name)
	logging.info('Track: ' + entity.track)
	logging.info('Time: ' +  str(time))
	logging.info('Entity Time: ' +  str(entity.time))
	if q:
		for lap in q:
			logging.info('Lap Driver:' + lap.driver.name)
			logging.info('Lap Driver Time: ' +  str(lap.time))
			if time < lap.time:
				lap.isBest = False
				lap.put()
				entity.isBest = True
				logging.info('Changing Best from ' + lap.driver.name + ' to ' + entity.driver.name)
	else:
		logging.info( 'New Best')
		entity.isBest = True
	entity.put()
	sleep(.1)
	logging.info('Ending Logging for Racer:' + entity.driver.name)

def prefetch_refprop(entities, prop):
	ref_keys = [prop.get_value_for_datastore(x) for x in entities]
	ref_entities = dict((x.key(), x) for x in db.get(set(ref_keys)))
	for entity, ref_key in zip(entities, ref_keys):
		prop.__set__(entity, ref_entities[ref_key])
	return entities

def process_time(time):
	if time:
		t = datetime.strptime(time, "%M:%S.%f")
		delta = timedelta(minutes=t.minute, seconds=t.second,microseconds=t.microsecond)
		return float(delta.total_seconds())

class Importer(webapp2.RequestHandler):
	def get(self):
		upload_url = blobstore.create_upload_url('/upload')
		template_values = {
			'upload_url': upload_url
		}
		template = JINJA_ENVIRONMENT.get_template('templates/importer.html')
		self.response.write(template.render(template_values))

		# for b in blobstore.BlobInfo.all():
		# 	self.response.out.write('<li><a href="/serve/%s' % str(b.key()) + '">' + str(b.filename) + '</a>')

class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
	def post(self):
		upload_files = self.get_uploads('file')[0]
		blob_key = upload_files.key()
		blob_info = upload_files
		record = Record(csv=str(blob_info)).put()
		blob_reader = blobstore.BlobReader(blob_key)
		count = 0
		for line in blob_reader.readlines():

			if count == 0:
				count = count + 1
				continue
			else:
				line = line.replace('"','').split(',')
				time = line[5]
				if time.count(':') == 0 and time:
					time = '0:' + time
				#print line
				pt = process_time(time)
				s = Sponsor.get_or_insert(key_name=line[16], name=line[16])
				t = self.request.get('track') #Track.get_or_insert(key_name=self.request.get('track'), name=self.request.get('track'), lap_distance=1.02)
				g = self.request.get('group')
				sd = self.request.get('date')
				dt = datetime.strptime(sd, '%Y-%m-%d')
				tr = Track.get_or_insert(key_name=t, name=t)
				e = Event.get_or_insert(key_name=g+t+sd, name=g+t, track=tr, date=dt)
				c = Car.get_or_insert(key_name=line[10]+line[11]+line[13], make=line[10], model=line[11],year=line[13],color=line[12],number=line[2])
				cl = RaceClass.get_or_insert(key_name=line[4], name=line[4])
				r = Racer.get_or_insert(key_name=line[3].replace(' ','.')+'@gmail.com', name=line[3], driver=users.User(line[3].replace(' ','.')+'@gmail.com'), points=int(line[9]), car=c, sponsor=s,raceclass=cl).put()
				best = BestLap.get_or_insert(key_name=sd+t+cl.name+line[3].replace(' ','.'), driver=r, raceclass=cl, track=t, time=pt, isBest=False)
				best.put()
				determine_best(pt, best)
				print best.driver.name, str(best.isBest)
				count = count + 1
		
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

		#cars = Car.all()
		#racers = Racer.all()
		bestlaps = BestLap.all()
		tracks = Track.all()
		template_values = {
			'user': user,
			'bestlaps': bestlaps,
			'bestlaps_count': bestlaps.count()+1,
			'tracks': tracks
		}
		
		template = JINJA_ENVIRONMENT.get_template('templates/index.html')
		self.response.write(template.render(template_values))
	
	def post(self):
		if users.get_current_user():
			user = users.get_current_user()
			url = users.create_logout_url(self.request.uri)
			url_linktext = 'Logout'
		else:
			url = users.create_login_url(self.request.uri)
			url_linktext = 'Login'
		track = self.request.get('track')

		bestlaps_query = BestLap.all()
		if track != 'all':
			bestlaps_query.filter('track =', track)
		bestlaps = bestlaps_query.fetch(1000,0)
		tracks = Track.all()
		template_values = {
			'user': user,
			'bestlaps': bestlaps,
			'bestlaps_count': len(bestlaps)+1,
			'tracks': tracks
		}


class BestLapHandler(webapp2.RequestHandler):
	def get(self):
		if users.get_current_user():
			user = users.get_current_user()
			url = users.create_logout_url(self.request.uri)
			url_linktext = 'Logout'
		else:
			url = users.create_login_url(self.request.uri)
			url_linktext = 'Login'
		
		bestlaps_query = BestLap.all() #db.GqlQuery('SELECT * from BestLap ORDER BY time ASC').fetch(100,0)
		bestlaps_query.filter("isBest =", True)
		bestlaps_query.order('-time')
		bestlaps = bestlaps_query.fetch(1000, 0)
		tracks = Track.all()#db.GqlQuery('SELECT DISTINCT track from BestLap').fetch(100,0)
		template_values = {
			'user': user,
			'bestlaps': bestlaps,
			'bestlaps_count': len(bestlaps)+1,
			'tracks': tracks
		}
		
		template = JINJA_ENVIRONMENT.get_template('templates/bestlap.html')
		self.response.write(template.render(template_values))

	def post(self):
		if users.get_current_user():
			user = users.get_current_user()
			url = users.create_logout_url(self.request.uri)
			url_linktext = 'Logout'
		else:
			url = users.create_login_url(self.request.uri)
			url_linktext = 'Login'
		track = self.request.get('track')

		bestlaps_query = BestLap.all()
		bestlaps_query.filter("isBest =", True)
		if track != 'all':
			bestlaps_query.filter('track =', track)
		bestlaps = bestlaps_query.fetch(1000,0)
		tracks = Track.all()
		template_values = {
			'user': user,
			'bestlaps': bestlaps,
			'bestlaps_count': len(bestlaps)+1,
			'tracks': tracks
		}
		
		template = JINJA_ENVIRONMENT.get_template('templates/bestlap.html')
		self.response.write(template.render(template_values))

class DriverHandler(webapp2.RequestHandler):
	def get(self, driver):
		racer = Racer.all().filter('name =', driver).fetch(1,0)[0]
		print racer.name
		bl = BestLap.all().filter('driver =', racer).fetch(100,0)
		template_values = {
			'racer': racer,
			'bestlaps': bl,
			'bestlaps_count': len(bl) + 1
		}
		template = JINJA_ENVIRONMENT.get_template('templates/driver.html')
		self.response.write(template.render(template_values))


app = webapp2.WSGIApplication([
	('/', MainHandler),
	('/driver/(.*)', DriverHandler),
	('/bestlap', BestLapHandler),
	('/importer', Importer),
	('/upload', UploadHandler)], debug=True)