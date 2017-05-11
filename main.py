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

JINJA_ENVIRONMENT = jinja2.Environment(
	loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
	extensions=['jinja2.ext.autoescape'])

def prefetch_refprop(entities, prop):
	ref_keys = [prop.get_value_for_datastore(x) for x in entities]
	ref_entities = dict((x.key(), x) for x in db.get(set(ref_keys)))
	for entity, ref_key in zip(entities, ref_keys):
		prop.__set__(entity, ref_entities[ref_key])
	return entities

def process_time(time):
	if time:
		if time != '0: ':
			t = datetime.strptime(time, "%M:%S.%f")
			delta = timedelta(minutes=t.minute, seconds=t.second,microseconds=t.microsecond)
			return float(delta.total_seconds())
		else:
			return 0.000

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

		# for b in blobstore.BlobInfo.all():
		# 	self.response.out.write('<li><a href="/serve/%s' % str(b.key()) + '">' + str(b.filename) + '</a>')

class PicuploadHandler(webapp2.RequestHandler):
	def post(self):
		driver_key = db.Key(self.request.get('driver'))
		racer = Racer.get(driver_key)
		racer.picture = db.Blob(self.request.get('img'))
		racer.put()
		self.redirect('/')


class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):

	def post(self):
		track = self.request.get('track')
		bestlaps = {}
		for bl in BestLap.all().filter('track =', track):
			if bl.isBest is True:
				bestlaps[bl.raceclass.name] = bl
				# print 'heres a best'
				# print bestlaps[bl.raceclass.name].key

		upload_files = self.get_uploads('file')[0]
		blob_key = upload_files.key()
		blob_info = upload_files
		record = Record(csv=str(blob_info)).put()
		blob_reader = blobstore.BlobReader(blob_key)
		count = 0
		for line in blob_reader.readlines():

			if count == 0:		#This is to skip the header line on the input forms
				count = count + 1
				continue
			else:
				line = line.replace('"','').replace(', ', ' ').strip().split(',')
				for index, item in enumerate(line):
					if item == '':
						line[index] = ' '
				print line
				time = line[5]
				if time.count(':') == 0 and time:
					time = '0:' + time
				
				pt = process_time(time)
				if not pt:
					pt = 999.999
				t = track #Track.get_or_insert(key_name=self.request.get('track'), name=self.request.get('track'), lap_distance=1.02)
				g = self.request.get('group')
				sd = self.request.get('date')
				dt = datetime.strptime(sd, '%Y-%m-%d')
				tr = Track.get_or_insert(key_name=t, name=t)
				e = Event.get_or_insert(key_name=g+t+sd, name=g+t, track=tr, date=dt)
				c = Car.get_or_insert(key_name=line[10]+line[11]+line[13], make=line[10], model=line[11],year=line[13],color=line[12],number=line[2])
				cl = RaceClass.get_or_insert(key_name=line[4], name=line[4])
				if line[17]:
					email = line[17]
				else:
					email = line[3].split()[0][0:1].lower() + line[3].split()[1].lower()+'@gmail.com'
				r = Racer.get_or_insert(key_name=line[3].split()[0][0:1].lower() + line[3].split()[1].lower(), name=line[3], driver=users.User(email), points=int(line[9]), car=c, raceclass=cl)
				if line[16]:
					r.sponsor=Sponsor.get_or_insert(key_name=line[16], name=line[16])
				if line[17]:
					r.email = line[17]
					r.driver = users.User(line[17])
				r.put()
				best = BestLap.get_or_insert(key_name=sd+t+cl.name+line[3].replace(' ','.'), driver=r, raceclass=cl, track=t, time=pt, event= e, isBest=False)

				if cl.name in bestlaps:
					if pt < bestlaps[cl.name].time:
						print str(pt) + ' is better than ' + bestlaps[cl.name].driver.name + 's time of ' + str(bestlaps[cl.name].time)
						best.isBest = True					#Mark current record as best
						bestlaps[cl.name].isBest = False	#Mark old record as not best
						bestlaps[cl.name].put()				#Commit old record to db
						bestlaps[cl.name] = best 			#Replace record in local dictionary with new best record for class
				else:
					best.isBest = True
					bestlaps[cl.name] = best
				best.put()
				count = count + 1
		self.redirect('/bestlap')

class MainHandler(webapp2.RequestHandler):
	def get(self):
		user = users.get_current_user()
		if user:
			greeting = ("Welcome, %s! (<a href=\"%s\">sign out</a>)" %
							(user.nickname(), users.create_logout_url("/")))
		else:
			greeting = ("<a href=\"%s\">Sign in or register</a>." %
							users.create_login_url("/"))

		bestlaps = BestLap.all()
		tracks = Track.all()
		template_values = {
			'user': user,
			'bestlaps': bestlaps,
			'bestlaps_count': bestlaps.count()+1,
			'tracks': tracks,
			'greeting': greeting
		}
		
		template = JINJA_ENVIRONMENT.get_template('templates/index.html')
		self.response.write(template.render(template_values))
	
	def post(self):
		user = users.get_current_user()
		if user:
			greeting = ("Welcome, %s! (<a href=\"%s\">sign out</a>)" %
							(user.nickname(), users.create_logout_url("/")))
		else:
			greeting = ("<a href=\"%s\">Sign in or register</a>." %
							users.create_login_url("/"))
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
			'tracks': tracks,
			'greeting': greeting
		}


class BestLapHandler(webapp2.RequestHandler):
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
		bestlaps_query = BestLap.all() #db.GqlQuery('SELECT * from BestLap ORDER BY time ASC').fetch(100,0)
		bestlaps_query.filter("isBest =", True)
		bestlaps_query.order('-time')
		bestlaps = bestlaps_query.fetch(1000, 0)
		tracks = Track.all()#db.GqlQuery('SELECT DISTINCT track from BestLap').fetch(100,0)
		template_values = {
			'user': user,
			'bestlaps': bestlaps,
			'bestlaps_count': len(bestlaps)+1,
			'tracks': tracks,
			'greeting': greeting
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
		nickname = racer.driver.nickname()
		bl = BestLap.all().filter('driver =', racer).fetch(100,0)
		template_values = {
			'racer': racer,
			'nickname': nickname,
			'bestlaps': bl,
			'bestlaps_count': len(bl) + 1
		}
		template = JINJA_ENVIRONMENT.get_template('templates/driver.html')
		self.response.write(template.render(template_values))

class ImageHandler (webapp.RequestHandler):
  def get(self):
	racer_key=self.request.get('key')
	racer = db.get(racer_key)
	if racer.picture:
		img = images.Image(racer.picture)
		img.resize(width=200, crop_to_fit=False, allow_stretch=False)
		img.im_feeling_lucky()
		rp = img.execute_transforms(output_encoding=images.JPEG)
		self.response.headers['Content-Type'] = "image/png"
		self.response.out.write(rp)
	else:
		self.error(404)

app = webapp2.WSGIApplication([
	('/', MainHandler),
	('/driver/(.*)', DriverHandler),
	('/bestlap', BestLapHandler),
	('/importer', Importer),
	('/picupload', PicuploadHandler),
	('/imageit',ImageHandler),
	('/upload', UploadHandler)], debug=True)