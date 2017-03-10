import os
import pprint
from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.api import mail
from google.appengine.api import urlfetch
from google.appengine.ext import db

pprint.pprint(os.environ.copy())

import models

s = models.Sponsor(name='Burger King').put()
t = models.Track(name='Watkins Glen', lap_distance=1.0).put()
c = models.Car(make='Volkswagen',model='Rabbit',year='1981',color='red',number='24').put()
c = models.Car(make='Audi',model='S4',year='2005',color='silver',number='69').put()
cl = models.RaceClass(name='American Iron').put()
r = models.Racer(driver=users.User('jstableford@gmail.com'),points=0, car=c, sponsor=s,raceclass=cl).put()
best = models.BestLap(driver=r, track=t,time=59.062).put()