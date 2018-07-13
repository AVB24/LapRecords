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
from google.appengine.api import users, images, memcache
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from models import Track, Car, Race, Racer, Event, Sponsor, BestLap, RaceClass, Record
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext import blobstore
from paging import PagedQuery
import unicodedata
import csv

JINJA_ENVIRONMENT = jinja2.Environment(
	loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
	extensions=['jinja2.ext.autoescape'])

# Helpers
class DataServices():
	all_laps = None
	laps_count = None

	def get_all_laps(self):
		all_laps = memcache.get('allLaps')
		if all_laps is None:
			all_laps = db.GqlQuery('SELECT * from BestLap')
			try:
				added = memcache.add('allLaps', all_laps, 3600)
				if not added:
					logging.error('Memcache set failed.')
			except ValueError:
				logging.error('Memcache set failed - data larger than 1MB')
		else:
			logging.info("Using Memcache")
				
		logging.info("I got to get_all_laps")
		logging.info(all_laps)
		return all_laps

	def get_best_laps(self,numFirstRecord,numLastRecord):
		retBestLaps = db.GqlQuery('SELECT * from BestLap WHERE isBest = True').fetch(numLastRecord,numFirstRecord)
		return retBestLaps
	
	def get_laps(self, numFirstRecord,numLastRecord):
		lap_data = memcache.get('lap_data')
		if lap_data is None:
			lap_data = BestLap.all().fetch(numLastRecord,numFirstRecord)
			try:
				added = memcache.add('lap_data', lap_data, 3600)
				if not added:
					logging.error('Memcache set failed.')
			except ValueError:
				logging.error('Memcache set failed - data larger than 1MB')
		else:
			logging.info("Using Memcache")

		#ret_laps = all_laps.fetch(numLastRecord,numFirstRecord)
		#retLaps = db.GqlQuery('SELECT * from BestLap ORDER BY time ASC').fetch(numLastRecord,numFirstRecord)
		logging.info("I got to get_laps")
		logging.info(lap_data)
		return lap_data
	
	def get_total_pages(self, pageSize):
		return page_count
	
	def get_page_size(self):
		return 50
	
	def get_racers(self):
		myRacerQuery = PagedQuery(Racer.all(), 99999)
		return myRacerQuery.fetch_page()
	
	def get_race_classes(self):
		myClassQuery = PagedQuery(RaceClass.all(), 99999)
		return myClassQuery.fetch_page()
	
	def get_tracks(self):
		myTrackQuery = PagedQuery(Track.all(), 99999)
		return myTrackQuery.fetch_page()
	
	def set_data_mem(self, name, data, seconds):
		try:
			memcache.delete(name, 15)
			added = memcache.add(name, data, seconds)
			if not added:
				logging.error('Memcache set failed.')
		except ValueError:
			logging.error('Memcache set failed - data larger than 1MB')
	
	def get_data_mem(self, name):
		get_data = memcache.get(name)
		if get_data is None:
			logging.error("Nothing in Memory")
			#set_data_mem(name, data)
		else:
			logging.info("Using MemCache")
		
		return get_data

class UIServices():
	def get_greeting(self, user):
		if user:
			greeting = ("Welcome, %s! (<a href=\"%s\">sign out</a>)" %
							(user.nickname(), users.create_logout_url("/")))
		else:
			greeting = ("<a href=\"%s\">Sign in or register</a>." %
							users.create_login_url("/"))
		return greeting
	
	def get_menu(self, page):
		if not users.is_current_user_admin():
			if page == "lap":
				menu = ("&nbsp;&nbsp;<a href=\"%s\">Search Laps</a>&nbsp;&nbsp;<a href=\"%s\">Nasa NE</a>" %
					("/search", "http://nasane.com/"))
			elif page == "main":
				menu = ("&nbsp;&nbsp;<a href=\"%s\">All Laps</a>&nbsp;&nbsp;<a href=\"%s\">Search Laps</a>&nbsp;&nbsp;<a href=\"%s\">Nasa NE</a>" %
					("/laps", "/search", "http://nasane.com/"))
			elif page == "search":
				menu = ("&nbsp;&nbsp;<a href=\"%s\">All Laps</a>&nbsp;&nbsp;<a href=\"%s\">Nasa NE</a>" %
					("/laps", "http://nasane.com/"))
				
		else:
			if page == "lap":
				menu = ("&nbsp;&nbsp;<a href=\"%s\">Search Laps</a>&nbsp;&nbsp;<a href=\"%s\">Importer</a>&nbsp;&nbsp;<a href=\"%s\">Nasa NE</a>" %
					("/search","/importer","http://nasane.com/"))
			elif page == "search":
				menu = ("&nbsp;&nbsp;<a href=\"%s\">All Laps</a>&nbsp;&nbsp;<a href=\"%s\">Importer</a>&nbsp;&nbsp;<a href=\"%s\">Nasa NE</a>" %
					("/laps","/importer","http://nasane.com/"))
			elif page == "importer":
				menu = ("&nbsp;&nbsp;<a href=\"%s\">All Laps</a>&nbsp;&nbsp;<a href=\"%s\">Search Laps</a>&nbsp;&nbsp;<a href=\"%s\">Nasa NE</a>" %
					("/laps","/search","http://nasane.com/"))
		return menu

data_services = DataServices()
ui_services = UIServices()

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
	else:
		return 0.000

def normalize_string(str):
	normStr = unicodedata.normalize('NFKD',unicode(str,"ISO-8859-1")).encode("ascii","ignore")
	if normStr:
		return normStr
	else:
		return "None"

class PicuploadHandler(webapp2.RequestHandler):
	def post(self):
		driver_key = db.Key(self.request.get('driver'))
		racer = Racer.get(driver_key)
		racer.picture = db.Blob(self.request.get('img'))
		racer.put()
		self.redirect('/')

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

class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
	def post(self):
		track = self.request.get('track')
		bestlaps = {}
		for bl in BestLap.all().filter('track =', track):
			if bl.isBest is True:
				bestlaps[bl.raceclass.name] = bl

		upload_files = self.get_uploads('file')[0]
		blob_key = upload_files.key()
		blob_info = upload_files
		record = Record(csv=str(blob_info)).put()
		blob_reader = blobstore.BlobReader(blob_key)
		reader = csv.DictReader(blob_reader)

		for row in reader:
			#row = row.replace('"','').replace(', ', ' ').strip()
			if 'Best Tm' in row:
				time = row['Best Tm']
			else:
				time = row['Overall BestTm']
			
			if 'Laps' in row:
				laps = row['Laps']
			else:
				laps = row['Appeared']

			position = row['Pos']
			point_in_class = row['PIC']
			carnum = row['No.']
			racer_name = normalize_string(row['Name'])
			racer_class = normalize_string(row['Class'])
			diff = row['Diff']
			gap = row['Gap']
			points = row['Points']
			car_make = normalize_string(row['Make'])
			car_model = normalize_string(row['Model'])
			car_year = row['Year']
			car_color = row['Color']
			city = row['City']
			state = row['State']
			sponsor = normalize_string(row['Sponsor'])
			email = row['Email']

			if time.count(':') == 0 and time:
				time = '0:' + time
			
			pt = process_time(time)
			t = track #Track.get_or_insert(key_name=self.request.get('track'), name=self.request.get('track'), lap_distance=1.02)
			g = self.request.get('group')
			sd = self.request.get('date')
			dt = datetime.strptime(sd, '%Y-%m-%d')
			tr = Track.get_or_insert(key_name=t, name=t)
			e = Event.get_or_insert(key_name=g+t+sd, name=g+t, track=tr, date=dt)
			c = Car.get_or_insert(key_name=car_make+car_model+car_year, make=car_make, model=car_model,year=car_year,color=car_color,number=carnum)
			cl = RaceClass.get_or_insert(key_name=racer_class, name=racer_class)
			if email:
				email
			else:
				email = racer_name.split()[0].lower() + racer_name.split()[1].lower()+'@gmail.com'
			r = Racer.get_or_insert(key_name=racer_name.split()[0][0:1].lower() + racer_name.split()[1].lower(), email=email,name=racer_name, driver=users.User(email), points=int(points), car=c, raceclass=cl)
			if sponsor:
				r.sponsor=Sponsor.get_or_insert(key_name=sponsor, name=sponsor)

			r.put()
			best = BestLap.get_or_insert(key_name=sd+t+g+cl.name+racer_name.replace(' ','.'), driver=r, raceclass=cl, track=t, time=pt, event= e, isBest=False)

			if cl.name in bestlaps:
				if pt < bestlaps[cl.name].time and pt != 0.0:
					print str(pt) + ' is better than ' + bestlaps[cl.name].driver.name + 's time of ' + str(bestlaps[cl.name].time)
					best.isBest = True					#Mark current record as best
					bestlaps[cl.name].isBest = False	#Mark old record as not best
					bestlaps[cl.name].put()				#Commit old record to db
					bestlaps[cl.name] = best 			#Replace record in local dictionary with new best record for class
			elif pt != 0.0:
				best.isBest = True
				bestlaps[cl.name] = best
			best.put()
		self.redirect('/')

# Page Handlers
class MainHandler(webapp2.RequestHandler):
	def get(self):
		user = users.get_current_user()
		function = self.request.get('function')
		greeting = ui_services.get_greeting(user)
		menu = ui_services.get_menu("search")
		searchRacers = data_services.get_racers()
		searchClasses = data_services.get_race_classes()
		searchTracks = data_services.get_tracks()

		template_values = {
			'user': user,
			'menu': menu,
			'greeting': greeting,
			'page_size': 0,
			'page_count': 0,
			'page_num': 0,
			'searchRacers': searchRacers,
			'searchClasses': searchClasses,
			'searchTracks': searchTracks
		}

		template = JINJA_ENVIRONMENT.get_template('templates/search.html')
		self.response.write(template.render(template_values))

class LapHandler(webapp2.RequestHandler):
	def get(self):
		user = users.get_current_user()
		page_size = data_services.get_page_size()
		greeting = ui_services.get_greeting(user)
		menu = ui_services.get_menu("lap")	
		myPagedQuery = PagedQuery(BestLap.all(), page_size)
		myResults = myPagedQuery.fetch_page()

		template_values = {
			'user': user,
			'laps': myResults,
			'page_size': page_size,
			'page_count': myPagedQuery.page_count(),
			'page_num': 0,
			'greeting': greeting,
			'menu': menu
		}
		
		template = JINJA_ENVIRONMENT.get_template('templates/laps.html')
		self.response.write(template.render(template_values))
	
	def post(self):
		user = users.get_current_user()
		greeting = ui_services.get_greeting(user)
		menu = ui_services.get_menu("lap")
		function = self.request.get('function')
		page_size = int(self.request.get('page_size'))
		page_num = int(self.request.get('page_num'))

		myPagedQuery = PagedQuery(BestLap.all(), page_size)
		page_count = myPagedQuery.page_count()
		myResults = myPagedQuery.fetch_page(page_num)
		template_values = {
			'user': user,
			'laps': myResults,
			'page_size': page_size,
			'page_count':page_count,
			'page_num': page_num-1,
			'greeting': greeting,
			'menu': menu
		}

		template = JINJA_ENVIRONMENT.get_template('templates/laps.html')
		self.response.write(template.render(template_values))


class BestLapHandler(webapp2.RequestHandler):
	def get(self):
		user = users.get_current_user()
		page_size = data_services.get_page_size()
		greeting = ui_services.get_greeting(user)
		menu = ui_services.get_menu("best")	
		myBestQuery = PagedQuery(BestLap.all().filter("isBest", True), page_size)
		#myBestQuery.order('-event')
		page_count = myBestQuery.page_count()
		myResults = myBestQuery.fetch_page()

		template_values = {
			'user': user,
			'laps': myResults,
			'page_size': page_size,
			'page_count': page_count,
			'page_num': 0,
			'greeting': greeting,
			'menu': menu
		}
		
		template = JINJA_ENVIRONMENT.get_template('templates/bestlap.html')
		self.response.write(template.render(template_values))
	
	def post(self):
		user = users.get_current_user()
		greeting = ui_services.get_greeting(user)
		menu = ui_services.get_menu("lap")
		function = self.request.get('function')
		page_size = int(self.request.get('page_size'))
		page_num = int(self.request.get('page_num'))

		myBestQuery = PagedQuery(BestLap.all().filter("isBest", True), page_size)
		page_count = myBestQuery.page_count()
		myResults = myBestQuery.fetch_page(page_num)
		template_values = {
			'user': user,
			'laps': myResults,
			'page_size': page_size,
			'page_count':page_count,
			'page_num': page_num-1,
			'greeting': greeting,
			'menu': menu
		}
		
		template = JINJA_ENVIRONMENT.get_template('templates/bestlap.html')
		self.response.write(template.render(template_values))

class searchLapHandler(webapp2.RequestHandler):
	def get(self):
		user = users.get_current_user()
		function = self.request.get('function')
		greeting = ui_services.get_greeting(user)
		menu = ui_services.get_menu("search")
		searchRacers = data_services.get_racers()
		searchClasses = data_services.get_race_classes()
		searchTracks = data_services.get_tracks()

		template_values = {
			'user': user,
			'menu': menu,
			'greeting': greeting,
			'page_size': 0,
			'page_count': 0,
			'page_num': 0,
			'searchRacers': searchRacers,
			'searchClasses': searchClasses,
			'searchTracks': searchTracks
		}

		template = JINJA_ENVIRONMENT.get_template('templates/search.html')
		self.response.write(template.render(template_values))
	def post(self):
		user = users.get_current_user()
		function = self.request.get('function')
		greeting = ui_services.get_greeting(user)
		menu = ui_services.get_menu("search")
		racer = self.request.get('racer')
		race_class = self.request.get('race_class')
		track = self.request.get('track')
		isBest = self.request.get('isBest')
		searchRacers = data_services.get_racers()
		searchClasses = data_services.get_race_classes()
		searchTracks = data_services.get_tracks()
		
		
		
		myQuery = BestLap.all()
		if racer and racer != "None":
			driver = Racer.all().filter('name =', racer).fetch(1,0)[0]
			myQuery.filter('driver', driver)
			racer = driver.name
		else:
			racer = None

		if race_class and race_class != "None":
			race_class = RaceClass.all().filter('name =', race_class).fetch(1,0)[0]
			myQuery.filter('raceclass', race_class)
			race_class = race_class.name
		else:
			race_class = None

		if track and track != "None":
			myQuery.filter('track', track)
		else:
			track = None

		if isBest == "True":
			myQuery.filter('isBest', True)
		else:
			isBest = "False"
		
		if function == "search":
			page_num = 1
			page_size = data_services.get_page_size()
			myPagedQuery = PagedQuery(myQuery, page_size)
			page_count = myPagedQuery.page_count()
			myResults = myPagedQuery.fetch_page()
		elif function == "changePage":
			#logging.info(myQuery)
			page_num = int(self.request.get('page_num'))
			page_size = int(self.request.get('page_size'))
			myPagedQuery = PagedQuery(myQuery, page_size)
			page_count = myPagedQuery.page_count()
			myResults = myPagedQuery.fetch_page(page_num)
		#logging.info(myResults)
		template_values = {
			'user': user,
			'laps': myResults,
			'page_size': page_size,
			'page_count': page_count,
			'page_num': page_num-1,
			'greeting': greeting,
			'menu': menu,
			'racer': racer,
			'race_class': race_class,
			'track': track,
			'isBest': isBest,
			'searchRacers': searchRacers,
			'searchClasses': searchClasses,
			'searchTracks': searchTracks
		}

		template = JINJA_ENVIRONMENT.get_template('templates/search.html')
		self.response.write(template.render(template_values))

class Importer(webapp2.RequestHandler):
	def get(self):
		user = users.get_current_user()
		greeting = ui_services.get_greeting(user)
		menu = ui_services.get_menu("importer")		

		if not users.is_current_user_admin():
			self.redirect('/')
		drivers = Racer.all()
		upload_url = blobstore.create_upload_url('/upload')
		template_values = {
			'drivers': drivers,
			'user': user,
			'upload_url': upload_url,
			'menu': menu,
			'greeting': greeting
		}
		template = JINJA_ENVIRONMENT.get_template('templates/importer.html')
		self.response.write(template.render(template_values))

		# for b in blobstore.BlobInfo.all():
		# 	self.response.out.write('<li><a href="/serve/%s' % str(b.key()) + '">' + str(b.filename) + '</a>')

app = webapp2.WSGIApplication([
	('/', MainHandler, DataServices),
	('/laps', LapHandler),
	('/driver/(.*)', DriverHandler),
	('/bestlap', BestLapHandler),
	('/search', searchLapHandler),
	('/importer', Importer),
	('/picupload', PicuploadHandler),
	('/imageit',ImageHandler),
	('/upload', UploadHandler)], debug=True)
	