#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# power-usage-logger
#

from flask import (
  Flask, request, Response, abort, json, render_template
)
app = Flask(__name__)
app.debug = True

from google.appengine.api import memcache
from google.appengine.ext import db
import datetime
import logging
import re

################################################################################

class PowerUsage(db.Model):
  sensorid = db.StringProperty(required=True)
  date = db.DateTimeProperty(required=True)
  usage = db.IntegerProperty(required=True)
  capacity = db.IntegerProperty(required=True)
  year = db.IntegerProperty(required=True)
  month = db.IntegerProperty(required=True)
  day = db.IntegerProperty(required=True)
  hour = db.IntegerProperty(required=True)
  minute = db.IntegerProperty(required=True)
  created = db.DateTimeProperty(auto_now_add=True)

  def dictify(usage):
    result = {}
    for prop in usage.properties():
      if prop == 'date' or prop == 'created':
        result[prop] = datetime.datetime.isoformat(getattr(usage, prop))
      else:
        result[prop] = getattr(usage, prop)
    result['uri'] = usage.uri()
    return result

  def uri(usage):
    uri_root = ''
    if not request:
      uri_root = 'http://power-usage-logger.appspot.com/'
    else:
      uri_root = request.url_root
    return uri_root + 'items/' + str(usage.key().id())

################################################################################

@app.route('/')
def index():
  return render_template('index.html', url_root=request.url_root)

def route_json(rule, **options):
  def decorator(func):
    def decorated(*args, **kw):
      memcache.delete(request.path)
      data = func(*args, **kw)
      if not data:
        abort(404)
      data = json.dumps(data, indent=2)
      return Response(data, mimetype='application/json')
    app.add_url_rule(rule, func.__name__, decorated, **options)
    return decorated
  return decorator

RE_CALLBACK = re.compile(r'^[a-zA-Z0-9_.]+$')
def route_cached_json(rule, **options):
  def decorator(func):
    def decorated(*args, **kw):
      callback = request.form.get('callback') or request.args.get('callback')
      if callback and not RE_CALLBACK.search(callback):
	abort(404)

      data = memcache.get(request.path)
      if not data or not isinstance(data, str):
	logging.info('Cache miss for %s' % request.path)
	data = func(*args, **kw)
	if not data:
	  abort(404)
	data = json.dumps(data, indent=2)
	memcache.set(request.path, data)

      if callback:
	return Response(
	    '%s(%s);' % (callback, data), mimetype='text/javascript')
      else:
	return Response(data, mimetype='application/json')
    app.add_url_rule(rule, func.__name__, decorated, **options)
    return decorated
  return decorator

@route_cached_json('/items/<int:itemid>', methods=['GET'])
def item_get(itemid):
  usage = PowerUsage.get_by_id(itemid)
  if usage:
    return usage.dictify()

def cleanup_related_cache(usage):
  sensorid = usage.sensorid
  year = usage.year
  month = usage.month
  day = usage.day
  hour = usage.hour
  minute = usage.minute
  memcache.delete("/sensors/%s" % sensorid)
  memcache.delete("/sensors/%s/latest" % sensorid)
  memcache.delete("/sensors/%s/%04d" % (sensorid, year))
  memcache.delete("/sensors/%s/%04d/%02d" % (sensorid, year, month))
  memcache.delete("/sensors/%s/%04d/%02d/%02d" % (sensorid, year, month, day))
  memcache.delete("/sensors/%s/%04d/%02d/%02d/%02d" % (sensorid, year, month, day, hour))
  memcache.delete("/sensors/%s/%04d/%02d/%02d/%02d/%02d" % (sensorid, year, month, day, hour, minute))

@route_json('/items/<int:itemid>', methods=['DELETE'])
def item_delete(itemid):
  usage = PowerUsage.get_by_id(itemid)
  if usage:
    cleanup_related_cache(usage)
    usage.delete()
    return { 'status': 'OK' }

@route_cached_json('/sensors', methods=['GET', 'POST'])
def sensors_get():
  pass

@route_cached_json('/sensors/<sensorid>', methods=['GET'])
def sensor_get(sensorid):
  usages = PowerUsage.all()
  usages = usages.filter("sensorid = ", sensorid)
  usages = usages.order("-date")
  usage = usages.get()
  if usage:
    return usage.dictify()

@route_json('/sensors/<sensorid>', methods=['POST'])
def sensor_post(sensorid):
  date = None
  usage = None
  capacity = None
  if 'date' in request.form:
    try:
      date = datetime.datetime.strptime(request.form['date'], '%Y%m%d%H%M%S')
    except ValueError:
      pass
  if 'usage' in request.form:
    usage = int(request.form['usage'])
  if 'capacity' in request.form:
    capacity = int(request.form['capacity'])
  if date and usage and capacity:
    usage = PowerUsage(
      sensorid=sensorid,
      date=date,
      year=date.year,
      month=date.month,
      day=date.day,
      hour=date.hour,
      minute=date.minute,
      usage=usage,
      capacity=capacity
      )
    usage.put()
    return { 'uri': usage.uri() }
  else:
    abort(400)

@route_cached_json('/sensors/<sensorid>/latest', methods=['GET', 'POST'])
def sensor_get_latest(sensorid):
  usages = PowerUsage.all()
  usages = usages.filter("sensorid = ", sensorid)
  usages = usages.order("-date")
  usage = usages.get()
  if usage:
    return usage.dictify()

@route_cached_json('/sensors/<sensorid>/<int:year>', methods=['GET', 'POST'])
def sensor_year_get(sensorid, year):
  usages = PowerUsage.all()
  usages = usages.filter("sensorid = ", sensorid)
  usages = usages.filter('year =', year)
  usages = usages.order('date')
  return [u.dictify() for u in usages]

@route_cached_json('/sensors/<sensorid>/<int:year>/<int:month>', methods=['GET', 'POST'])
def sensor_month_get(sensorid, year, month):
  usages = PowerUsage.all()
  usages = usages.filter("sensorid = ", sensorid)
  usages = usages.filter('year =', year)
  usages = usages.filter('month =', month)
  usages = usages.order('date')
  return [u.dictify() for u in usages]

@route_cached_json('/sensors/<sensorid>/<int:year>/<int:month>/<int:day>', methods=['GET', 'POST'])
def sensor_day_get(sensorid, year, month, day):
  usages = PowerUsage.all()
  usages = usages.filter("sensorid = ", sensorid)
  usages = usages.filter('year =', year)
  usages = usages.filter('month =', month)
  usages = usages.filter('day =', day)
  usages = usages.order('date')
  return [u.dictify() for u in usages]

@route_cached_json('/sensors/<sensorid>/<int:year>/<int:month>/<int:day>/<int:hour>', methods=['GET', 'POST'])
def sensor_hour_get(sensorid, year, month, day, hour):
  usages = PowerUsage.all()
  usages = usages.filter("sensorid = ", sensorid)
  usages = usages.filter('year =', year)
  usages = usages.filter('month =', month)
  usages = usages.filter('day =', day)
  usages = usages.filter('hour =', hour)
  usages = usages.order('date')
  return [u.dictify() for u in usages]

@route_cached_json('/sensors/<sensorid>/<int:year>/<int:month>/<int:day>/<int:hour>/<int:minute>', methods=['GET', 'POST'])
def sensor_hour_get(sensorid, year, month, day, hour, minute):
  usages = PowerUsage.all()
  usages = usages.filter("sensorid = ", sensorid)
  usages = usages.filter('year =', year)
  usages = usages.filter('month =', month)
  usages = usages.filter('day =', day)
  usages = usages.filter('hour =', hour)
  usages = usages.filter('minute =', minute)
  usages = usages.order('date')
  return [u.dictify() for u in usages]
