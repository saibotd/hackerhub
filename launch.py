#!/usr/bin/python

from urllib2 import urlopen, Request, unquote, quote
from urlparse import urljoin
import simplejson
import socket
from PIL import Image, ImageOps
import cStringIO
import redis
import traceback
from flask import (Flask, render_template, request, redirect, session, g, jsonify,
                   flash, send_from_directory, abort, make_response)
import sys, redis
import ordereddict

r = redis.StrictRedis(host='localhost', port=6379, db=4)
#r.flushdb()
                   
app = Flask(__name__)
app.config["SERVER_NAME"] = "eeepc:5000"
	
@app.route("/", methods=['GET', 'POST'])
def register():
	if request.method == 'GET':
		return render_template("index.html")
	if request.method == 'POST':
		error = None
		if not request.form['register_url']:
			return render_template("index.html", error="Form data missing")
		try:
			register_url = request.form['register_url']
			data = urlopen(register_url)
		except Exception,e:
			return render_template("index.html", error="Profile not found at " + register_url, register_url = register_url)
		try:
			json = simplejson.load(data, object_pairs_hook=ordereddict.OrderedDict)
		except Exception,e:
			return render_template("index.html", error="Invalid JSON: " + str(e), register_url = register_url)
		try:
			userid = json["settings"]["id"]
		except:
			return render_template("index.html", error="Invalid profile (user id is missing)", register_url = register_url)
		if len(userid) is not len(quote(userid.encode("utf-8").lower())):
			return render_template("index.html", error="The user id \""+ userid +"\" is not valid. Only lowercased letters and numbers are allowed", register_url = register_url)
		if r.exists("profileloc:" + userid):
			return render_template("index.html", error="The user id \""+ userid +"\" is already registered, sorry", register_url = register_url)
		r.set("profile:" + userid, simplejson.dumps(json))
		r.expire("profile:" + userid, 24 * 60 * 60)
		r.set("profileloc:" + userid, register_url)
		return redirect("http://" + userid + "." + app.config["SERVER_NAME"])

@app.route("/<userid>")
@app.route("/<userid>/<contentkey>")
@app.route("/", subdomain="<userid>")
@app.route("/<contentkey>", subdomain="<userid>")
def profile(userid, contentkey=None):
	if userid is not "www":
		if not r.exists("profileloc:" + userid):
			return abort(404)
		
		if not r.exists("profile:" + userid):
			register_url = r.get("profileloc:" + userid)
			try:
				data = urlopen(register_url)
			except Exception,e:
				return render_template("profile.html", error="Profile not found")
			try:
				json = simplejson.load(data, object_pairs_hook=ordereddict.OrderedDict)
			except Exception,e:
				return render_template("profile.html", error="Invalid JSON: " + str(e))
			r.set("profile:" + userid, simplejson.dumps(json))
		profile = simplejson.loads(r.get("profile:" + userid), object_pairs_hook=ordereddict.OrderedDict)
		if not profile["content"]:
			return render_template("profile.html", error="Profile is missing a 'content' section")
		if not contentkey:
			for key, value in profile["content"].iteritems():
				return redirect("/" + key)
			return render_template("profile.html", error="Content section in profile is empty")
		else:
			content = profile["content"][contentkey]



	else:
		return register()
	

if __name__ == "__main__":
	app.run(host='0.0.0.0',debug=True)
