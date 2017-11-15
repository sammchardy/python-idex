#!/usr/bin/env python
# coding=utf-8


class IdexException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return 'IdexException: {}'.format(self.message)


class IdexAPIException(Exception):
    """Exception class to handle general API Exceptions

        `code` values

        `message` format

    """
    def __init__(self, response):
        self.code = ''
        self.message = 'Unknown Error'
        try:
            json_res = response.json()
        except ValueError:
            self.message = response.content
        else:
            if 'error' in json_res:
                self.message = json_res['error']

        self.status_code = response.status_code
        self.response = response
        self.request = getattr(response, 'request', None)

    def __str__(self):
        return 'IdexAPIException: {}'.format(self.message)


class IdexRequestException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return 'IdexRequestException: {}'.format(self.message)
