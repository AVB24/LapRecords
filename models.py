import os
import re
from datetime import datetime

from google.appengine.api import mail
from google.appengine.ext import db

class Sponsor(db.Model):
	name = db.TextProperty()

class RaceClass(db.Model):
	name = db.StringProperty()

class Track(db.Model):
	name = db.StringProperty()
	#group = db.StringProperty()
	#lap_distance = db.FloatProperty()

class Event(db.Model):
	name = db.StringProperty()
#	track = db.ReferenceProperty(Track)
	date = db.DateTimeProperty()

class Car(db.Model):
	make = db.StringProperty()
	model = db.StringProperty()
	year = db.StringProperty()
	color = db.StringProperty()
	number = db.StringProperty()

class Racer(db.Model):
	email = db.EmailProperty()
	driver = db.UserProperty()
	name = db.StringProperty()
	city = db.StringProperty()
	state = db.StringProperty()
	points = db.IntegerProperty()
	car = db.ReferenceProperty(Car)
	sponsor = db.ReferenceProperty(Sponsor)
	picture = db.BlobProperty()

class Race(db.Model):
	driver = db.ReferenceProperty(Racer)
	track = db.ReferenceProperty(Track)
	event = db.ReferenceProperty(Event)
	time = db.StringProperty()

class BestLap(db.Model):
	driver = db.ReferenceProperty(Racer)
	raceclass = db.ReferenceProperty(RaceClass)
	event = db.ReferenceProperty(Event)
	track = db.StringProperty() #db.ReferenceProperty(Track)
	time = db.FloatProperty()
	isBest = db.BooleanProperty()
	date = db.DateTimeProperty()

class Record(db.Model):
	csv = db.BlobProperty()
