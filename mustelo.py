#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Mustelo ASGI Web Framework

Copyright (c) 2021, Mike Vorozhbyanskiy.
License: MIT (see LICENSE for details)
"""

import os
import re
import json
import mimetypes
import inspect
from functools import partial
from urllib.parse import parse_qsl

__author__ = 'Mike Vorozhbyanskiy'
__version__ = '0.0.1-dev'
__license__ = 'MIT'


class MusteloError(Exception):
    pass


class ConfigurationError(MusteloError):
    pass


class AbortError(MusteloError):
    def __init__(self, status, message=None):
        self.status = status
        self.message = message


class HandlerError(MusteloError):
    pass

def gues_datatype(data):
    if data:
        if type(data) == dict:
            return 'application/json; charset=UTF-8'
    return 'text/html; charset=UTF-8'


class HEADER(object):
    content_type = 'Content-Type'
    content_enc = 'Content-Encoding'
    content_disp = 'Content-Disposition'
    content_len = 'Content-Length'


class QueryDict(object):
    def __init__(self, items):
        self.data = dict()
        for k, v in items:
            kd = k.decode()
            if kd not in self.data:
                self.data[kd] = []
            self.data[kd].append(v.decode())

    def __getitem__(self, key):
        return self.data.get(key) or []

    def __len__(self):
        return len(self.data)

    def __repr__(self):
        return "QueryDict%s" % self.data

    def __getattr__(self, key):
        obj = self.data.get(key)
        if type(obj) == list:
            if len(obj) > 0:
                return obj[0]
        elif obj:
            return obj
        return None


class HeaderDict(object):
    def __init__(self, items):
        self.data = dict()
        for k, v in items:
            self.data[k.decode().lower()] = v.decode()

    def __getitem__(self, key):
        return self.data.get(key.lower())

    def __len__(self):
        return len(self.data)

    def __repr__(self):
        return "HeaderDict%s" % self.data


class ResponseHeaders(object):
    def __init__(self, items=None):
        self.data = dict()
        self.update(items)

    def __getitem__(self, key):
        return self.data.get(key.lower())

    def __contains__(self, key):
        return key.lower() in self.data

    def __setitem__(self, key, val):
        if val is not None:
            self.data[key.lower()] = val
        elif key in self.data:
            del self.data[key]

    def update(self, other):
        if other:
            for k, v in other.items():
                self.__setitem__(k, v)

    def items(self):
        return self.data.items()


class Route(object):

    _matcher = re.compile(r"\{([a-zA-Z]\w*):?([a-zA-Z]+)?\}")
    _types = ["path", "str", "int"]
    _ERR1 = "Handler does not have param defined in route. hadler=%s, param=%s"
    _ERR2 = "Handler has params not defined in route. handler=%s, route=%s"
    _ERR3 = "Cannot start route from variable. route=%s"
    _ERR4 = "Wrong paramenter type. Allowed types %s. route=%s, parameter=%s, type=%s"

    def __init__(self, path, method, handler):
        self.path = path
        self.method = method
        self.handler = handler
        self.prefix, self.params, self.checker = self._complie(path)
        self.has_request_param = self._validate_handler(self.params, handler)
        print("init: %s" % (self))

    def __str__(self):
        return "Route(%s -> %s)" % (self.path, self.handler.__name__)

    def _complie(self, path):
        params = self._matcher.findall(path)
        params = list(map(lambda x: (x[0], "str") if x[1] == "" else x, params))
        if params:
            prefix = path[:path.find("{%s" % params[0][0])]
            for name, typ in params:
                if typ not in self._types:
                    raise ConfigurationError(self._ERR4 % (", ".join(self._types), path, name, typ))
            expr = "%s$" % path
            for p, t in params:
                if "{%s}" % p in expr:
                    n = "{%s}" % p
                else:
                    n = "{%s:%s}" % (p, t)
                if t == "str":
                    expr = expr.replace(n, "([^/]+)")
                elif t == "int":
                    expr = expr.replace(n, "(\\d+)")
                elif t == "path":
                    expr = expr.replace(n, "(.*)")
            checker = re.compile(expr)
        else:
            prefix = path
            checker = None
        if not prefix:
            raise ConfigurationError(self._ERR3 % path)
        return prefix, params, checker

    def _validate_handler(self, params, handler):
        """
        raise ConfigurationError in case "parameters" do not match to method's arguments
        """
        argspec = inspect.getfullargspec(handler)
        for name, typ in params:
            if name not in argspec.args:
                raise ConfigurationError(self._ERR1 % (handler.__name__, name))
        if "request" in argspec.args:
            if len(argspec.args) != len(params) + 1:
                raise ConfigurationError(self._ERR2 % (handler.__name__, self.path))
            return True
        return False

    def match(self, path):
        if not self.params:
            return self.path == path, None
        m = self.checker.match(path)
        if m:
            return True, m.groups()
        return False, None

    def extract_params(self, request, params):
        if params:
            res = dict(zip(map(lambda x: x[0], self.params), params))
        else:
            res = dict()
        if self.has_request_param:
            res["request"] = request
        return res


class Request(object):
    def __init__(self, path, method, headers=None, query=None, body=None):
        self.path = path
        self.method = method
        self.headers = headers or {}
        self.query = query or {}
        self.body = body

    @property
    def text(self) -> str:
        return self.body.decode()

    @property
    def json(self) -> object:
        return json.loads(self.body)

    def __repr__(self):
        return "Request%s" % self.__dict__


class Response(object):
    _ERR1 = "async generator is not supported. handler=%s"

    def __init__(self, data=None, status=200, headers=None):
        self.data = data
        self.status = status
        self.headers = ResponseHeaders()
        # default headers 
        self.headers['Content-Type'] = gues_datatype(self.data)
        self.headers.update(headers)

    def generator(self):
        if inspect.isgenerator(self.data):
            yield from self.data
        elif inspect.isasyncgen(self.data):
            raise ConfigurationError(self._ERR1 % self.data.__name__)
        else:
            yield self.data

    def __repr__(self):
        return "Response%s" % self.__dict__


class MicroTemplate(object):
    _ERR = "Template context must be dict. template: %s, context.type: %s"

    def __init__(self, templates_root):
        self.templates_root = templates_root

    @staticmethod
    def render(engine, template, ctx):
        if type(ctx) is not dict:
            HandlerError(self._ERR1 % (template, type(ctx)))
        absroot = os.path.abspath(engine.templates_root)
        filename = os.path.join(absroot, template.replace("/", os.path.sep))
        if not os.path.abspath(filename).startswith(absroot):
            self.abort(403, "Access denied")
        if not os.path.exists(filename) or not os.path.isfile(filename):
            self.abort(404, "File not found")
        with open(filename, "rb") as file:
            data = file.read()
            if ctx:
                return data % ctx
            else:
                return data


class Mustelo(object):
    def __init__(self, templates_root="templates"):
        self.routes = []
        self.listeners = {}
        self._template_engine = MicroTemplate(templates_root)
        self._template_render = MicroTemplate.render

    def route(self, path, method='GET'):
        return partial(self._add_route, path, method)

    def get(self, path):
        method='GET'
        return partial(self._add_route, path, method)

    def post(self, path):
        method='POST'
        return partial(self._add_route, path, method)

    def _add_route(self, path, method, handler):
        self.routes.append(Route(path, method, handler))

    @staticmethod
    def abort(status, message=None):
        raise AbortError(status=status, message=message)

    @staticmethod
    def response(data=None, status=200, headers=None):
        return Response(data, status, headers)

    def _find_route(self, path):
        for route in self.routes:
            if path.startswith(route.prefix):
                match, params = route.match(path)
                if match:
                    return route, params
        return None, None

    async def _handle_request_(self, scope, receive):
        route, params = self._find_route(scope['path'])
        # print("route=%s, params=%s" % (route, params))
        if route is None:
            return Response(status=404)

        if route.method != scope['method']:
            return Response(status=405)

        request = Request(
            path=scope['path'],
            method=scope['method'],
            headers=HeaderDict(scope['headers']),
            query=QueryDict(parse_qsl(scope['query_string'])),
            body=await self._read_request_body(receive),
        )
        values = route.extract_params(request, params)
        try:
            resp = await route.handler(**values)
        except AbortError as err:
            return Response(status=err.status, data=err.message)
        if not isinstance(resp, Response):
            return Response(data=resp)
        return resp

    def _encode_data(self, data):
        if data is None:
            return b''
        elif isinstance(data, bytes):
            return data
        elif isinstance(data, (dict, list)):
            return ("%s\n" % json.dumps(data)).encode()
        else:
            return str(data).encode()
            

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return
        response = await self._handle_request_(scope, receive)
        header_sent = False

        async def send_headers(data=None):
            hdrs = response.headers
            if HEADER.content_type not in hdrs and data is not None:
                hdrs[HEADER.content_type] = gues_datatype(data)
            await send({
                'type': 'http.response.start',
                'status': response.status,
                'headers': [(k.encode(), str(v).encode()) for k, v in hdrs.items()],
            })

        for data in response.generator():
            if not header_sent:
                await send_headers(data)
                header_sent = True
            await send({
                'type': 'http.response.body',
                'body': self._encode_data(data),
                'more_body': True
            })
        if not header_sent:
            await send_headers()
        await send({
            'type': 'http.response.body',
            'body': b'',
            'more_body': False
        })

    @staticmethod
    async def _read_request_body(receive):
        body = bytearray()
        while True:
            msg = await receive()
            body += msg['body']
            if not msg.get('more_body'):
                break
        return bytes(body)

    def run(self, host="localhost", port=8888):
        from uvicorn.main import main
        args = list()
        args.append("--host=%s" % host)
        args.append("--port=%s" % port)
        s = str(self)
        ## some black magic to get instance name and file name
        frame = inspect.currentframe().f_back
        name = None
        for k,v in frame.f_globals.items():
            if str(v) == s:
                f = frame.f_globals["__file__"]
                name = f.split(".")[0] + ":" + k
        if not name:
            raise ConfigurationError("Looks like application object is not global. object=%s" % s)
        args.append(name)
        return main(args)

    def static_file(self, filepath, fileroot="", download=False):
        absroot = os.path.abspath(fileroot)
        filename = os.path.join(absroot, filepath.replace("/", os.path.sep))
        if not os.path.abspath(filename).startswith(absroot):
            self.abort(403, "Access denied")
        if not os.path.exists(filename) or not os.path.isfile(filename):
            self.abort(404, "File not found")
        def read_file():
            with open(filename, "rb") as file:
                while True:
                    data = file.read(1048576)
                    if not data:
                        break
                    yield data
        mimetype, encoding = mimetypes.guess_type(filename)
        stats = os.stat(filename)
        headers = dict()
        headers[HEADER.content_type] = mimetype
        headers[HEADER.content_enc] = encoding
        headers[HEADER.content_len] = stats.st_size
        if download:
            headers[HEADER.content_disp] = 'attachment; filename="%s"' % \
                os.path.basename(filename)
        return self.response(read_file(), headers = headers)

    def template_engine(self, engine, renderfunc):
        self._template_engine = engine
        self._template_render = renderfunc

    def render(self, template, ctx={}):
        return self._template_render(self._template_engine, template, ctx)

