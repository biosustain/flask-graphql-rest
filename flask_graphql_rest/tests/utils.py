from flask import json
from flask.testing import FlaskClient
from werkzeug.utils import cached_property


class JSONResponseMixin(object):
    @cached_property
    def json(self):
        return json.loads(self.data)


class ApiClient(FlaskClient):
    def open(self, *args, **kwargs):
        """
        Sends HTTP Authorization header with  the ``HTTP_AUTHORIZATION`` config value
        unless :param:`authorize` is ``False``.
        """
        headers = kwargs.pop('headers', [])

        if 'data' in kwargs and not isinstance(kwargs['data'], str):
            kwargs['data'] = json.dumps(kwargs['data'])
            kwargs['content_type'] = 'application/json'

        return super(ApiClient, self).open(*args, headers=headers, **kwargs)
