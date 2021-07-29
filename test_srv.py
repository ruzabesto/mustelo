#!/usr/bin/env python
# -*- coding: utf-8 -*-

from mustelo import Mustelo

app = Mustelo()

@app.route("/")
async def index():
    return "Hello"

@app.route("/static/{filename:path}")
async def static(filename):
    return app.abort(400)

@app.route("/api/get/{object}/{id}")
async def method(request, object, id):
    print(locals())
    return app.abort(500)

if __name__ == "__main__":
    app.run()