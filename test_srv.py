#!/usr/bin/env python
# -*- coding: utf-8 -*-

from mustelo import Mustelo

app = Mustelo()

@app.route("/")
async def index():
    return "Hello"

@app.route("/static/{filename:path}")
async def static(filename):
    app.abort(400)

@app.get("/api/get/{object}/{id}")
async def method(request, object, id):
    print(locals())
    app.abort(500)

if __name__ == "__main__":
    app.run()