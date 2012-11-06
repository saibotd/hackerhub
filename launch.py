#!/usr/bin/python

from urllib2 import urlopen, Request, unquote
from urlparse import urljoin
import socket
from PIL import Image, ImageOps
import cStringIO
import redis
import traceback
from flask import (Flask, render_template, request, redirect, session, g, jsonify,
                   flash, send_from_directory, abort, make_response)
import sys, redis

r = redis.StrictRedis(host='localhost', port=6379, db=4)
                   
app = Flask(__name__)

@app.route("/")
def index():
	return render_template("index.html")

if __name__ == "__main__":
	app.run()
