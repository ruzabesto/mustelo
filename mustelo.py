#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Mustelo ASGI Web Framework

Copyright (c) 2021, Mike Vorozhbyanskiy.
License: MIT (see LICENSE for details)
"""

import re
import json
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


class Route(object):

    _matcher = re.compile(r"\{([a-zA-Z]\w*):?([a-zA-Z]+)?\}")
    _types = ["path", "str", "int"]
    _ERR1 = "Handler does not have param defined in route. hadler=%s, param=%s"
    _ERR2 = "Handler has params not defined in route. handler=%s, route=%s"
    _ERR3 = "Cannot start route from variable. route=%s"
    _ERR4 = "Wrong paramenter type. Allowed types %s. route=%s, parameter=%s, type=%s"

    def __init__(self, path, method, handler):
        self.prefix, self.params, self.checker = self._complie(path)
        self.path = path
        self.method = method
        self.has_request_param = self._validate_handler(self.params, handler)
        self.handler = handler
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
    def __init__(self, data=None, status=200, headers=None):
        self.data = data
        self.status = status
        self.headers = headers or {}

    @property
    def body(self):
        if self.data is None:
            return b''
        elif isinstance(self.data, bytes):
            return self.data
        elif isinstance(self.data, str):
            return self.data.encode()
        elif isinstance(self.data, (dict, list)):
            return json.dumps(self.data).encode()
        else:
            raise TypeError(type(self.data))

    def __repr__(self):
        return "Response%s" % self.__dict__

class Mustelo(object):
    def __init__(self):
        self.routes = []
        self.listeners = {}

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

    def _find_route(self, path):
        for route in self.routes:
            if path.startswith(route.prefix):
                match, params = route.match(path)
                if match:
                    return route, params
        return None, None

    async def _handle_request_(self, scope, receive):
        route, params = self._find_route(scope['path'])
        print("route=%s, params=%s" % (route, params))
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

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return
        response = await self._handle_request_(scope, receive)

        await send({
            'type': 'http.response.start',
            'status': response.status,
            'headers': [(k.encode(), v.encode()) for k, v in response.headers.items()],
        })
        await send({
            'type': 'http.response.body',
            'body': response.body,
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
        import ferret
        print("Test server started at %s:%s" % (host, port))
        ferret.run(host, port, self)



