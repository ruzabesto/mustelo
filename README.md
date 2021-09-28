# mustelo

Mustelo (en:weasel) is a tiny ASGI web framework with no hard external depenedencies. Inspired by bottle.py

Only one optional dependency is "uvicorn", required to run server via
``app.run()``.
For running mustelo wit any other ASGI server, no other dependencies needed.

## Usage

### Basic usage

```python
from mustelo import Mustelo

app = Mustelo()

@app.route("/")
async def index():
    return "Hello"

if __name__ == "__main__":
    app.run()
```

To run applicaiton with `app.run()` need to have installed "uvicorn".

### Routes

Path variables defined by "{variable_name:variable_type}".

"variable_type" is optional, default is "str"

Supported types:
* str - string of any characters except "/"
* int - integer number
* path - anything including "/" character

Variable must be defined in route function.

```python
@app.route("/static/{filename:path}")
async def static(filename):
    return open("static_files/%s" % filename, "r").read()

@app.get("/api/get/{object}/{id}")
async def method(object, id):
    return dict(method="get", object=object, id=id)
```

### Response

By default response type is deteceted from function return value.
Supported types:
* Response object - created by `app.response(data="something", status=200, headers={})`
* bytes - binary data
* dict - transformed into json response (with tailing "\n" useful for streaming json data)
* any other types - converted to string 


#### Response stream

Streaming implemented by generators

```python
@app.get("/gen")
async def gen_hadler(request):
    def gen_response():
        for x in range(100):
            yield dict(obj="gen", value=x)
    return app.response(data=gen_response())

```

#### Errors

To interrupt process and return an error, call `abort` method

```python

@app.route("/check/{name}")
async def static(name):
    if name != "Loki":
        app.abort(400)
    else:
        return 'ok'
```