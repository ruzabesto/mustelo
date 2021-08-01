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
    return dict(method="get", object=object, id=id)

@app.get("/gen")
async def method(request):
    def gen_response():
        for x in range(100):
            yield dict(obj="gen", value=x)
    return app.response(gen_response())

if __name__ == "__main__":
    app.run()