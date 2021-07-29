#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Fetter AGSI Test Server

Copyright (c) 2021, Mike Vorozhbyanskiy.
License: MIT (see LICENSE for details)
"""

from a2wsgi import ASGIMiddleware
from wsgiref.simple_server import make_server

def run(host, port, asgi_app):
    wsgi_app = ASGIMiddleware(asgi_app)
    with make_server(host, port, wsgi_app) as httpd:
        httpd.serve_forever()