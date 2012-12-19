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
import markdown
import html2text
import feedparser

r = redis.StrictRedis(host='localhost', port=6379, db=4)
#r.flushdb()

md = markdown.Markdown(safe_mode="escape", output_format='html4')
h2t = html2text.HTML2Text()
                   
app = Flask(__name__)
app.config["SERVER_NAME"] = "localhost:5000"

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

@app.route("/u/<userid>")
@app.route("/u/<userid>/<contentkey>")
@app.route("/u/<userid>/<contentkey>/<subcontentkey>")
@app.route("/", subdomain="<userid>")
@app.route("/<contentkey>", subdomain="<userid>")
@app.route("/<contentkey>/<subcontentkey>", subdomain="<userid>")
def profile(userid, contentkey=None, subcontentkey=None):
	if userid != "www":
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
			menu = []
			for key, value in profile["content"].iteritems():
				menu.append(profile["content"][key]["title"])
			if contentkey not in profile["content"]:
				return abort(404)
			content = profile["content"][contentkey]
			if content.has_key("type"):
				content_type = content["type"]
			else:
				content_type = "article"
			
			if content_type == "article":
				return doArticle(profile, contentkey, content["content"])
			if content_type == "rss" or content_type == "atom" or content_type == "newsfeed":
				return doNewsFeed(profile, contentkey, content["content"])
			if content_type == "blog":
				return doBlog(profile, contentkey, subcontentkey)
			if content_type == "twitter":
				return doTwitter(profile, contentkey, content["screen_name"])

def doArticle(profile, contentkey, source):
	userid = profile["settings"]["id"]
	if not r.exists("cache:" + userid + ":" + contentkey):
		try:
			data = urlopen(source)
		except:
			abort(404)
		content = data.read()
		if source[-4:] == "html":
			content = h2t.handle(content)
		r.set("cache:" + userid + ":" + contentkey, md.convert(content))
		r.expire("cache:" + userid + ":" + contentkey, 24 * 60 * 60)
	content = r.get("cache:" + userid + ":" + contentkey)
	return render_template("profile_article.html", profile=profile, contentkey=contentkey, content=content)

def doNewsFeed(profile, contentkey, source):
	userid = profile["settings"]["id"]
	if not r.exists("cache:" + userid + ":" + contentkey):
		try:
			data = urlopen(source)
		except:
			abort(404)
		r.set("cache:" + userid + ":" + contentkey, data.read())
		r.expire("cache:" + userid + ":" + contentkey, 24 * 60 * 60)
	content = feedparser.parse(r.get("cache:" + userid + ":" + contentkey))
	return render_template("profile_newsfeed.html", profile=profile, content=content)

def doBlog(profile, contentkey, subcontentkey=None):
	userid = profile["settings"]["id"]
	if not r.exists("cache:" + userid + ":" + contentkey):
		content = profile["content"][contentkey]
		for key in content["content"]:
			source = content["content"][key]["content"]
			try:
				data = urlopen(source)
				data = data.read()
			except:
				data = ""
			if source[-4:] == "html":
				data = h2t.handle(data)
			content["content"][key]["key"] = key
			content["content"][key]["content"] = md.convert(data)
		r.set("cache:" + userid + ":" + contentkey, simplejson.dumps(content))
		r.expire("cache:" + userid + ":" + contentkey, 24 * 60 * 60)
	content = simplejson.loads(r.get("cache:" + userid + ":" + contentkey), object_pairs_hook=ordereddict.OrderedDict)	
	if subcontentkey:
		blogtitle = content["title"]
		return render_template(
			"profile_blog_article.html",
			profile=profile,
			blogtitle=blogtitle,
			contentkey=contentkey,
			subcontentkey=subcontentkey,
			content=content["content"][subcontentkey])
	else:
		return render_template("profile_blog.html", profile=profile, contentkey=contentkey, content=content)

def doTwitter(profile, contentkey, screen_name):
	userid = profile["settings"]["id"]
	if not r.exists("cache:" + userid + ":" + contentkey):
		try:
			data = urlopen("https://api.twitter.com/1/statuses/user_timeline.json?include_entities=true&include_rts=true&screen_name="+screen_name+"&count=25")
		except:
			abort(404)
		r.set("cache:" + userid + ":" + contentkey, data.read())
		r.expire("cache:" + userid + ":" + contentkey, 24 * 60 * 60)
	content = simplejson.loads(r.get("cache:" + userid + ":" + contentkey), object_pairs_hook=ordereddict.OrderedDict)	
	print content
	return render_template("profile_twitter.html", profile=profile, content=content)

if __name__ == "__main__":
	app.run(host='0.0.0.0', debug=True)
