import json


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
    def __init__(self, response, status_code, text):
        self.code = ''
        self.message = 'Unknown Error'
        try:
            json_res = json.loads(text)
        except ValueError:
            self.message = response.content
        else:
            if 'error' in json_res:
                self.message = json_res['error']

        self.status_code = status_code
        self.response = response
        self.request = getattr(response, 'request', None)

    def __str__(self):
        return 'IdexAPIException: {}'.format(self.message)


class IdexRequestException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return 'IdexRequestException: {}'.format(self.message)


class IdexCurrencyNotFoundException(IdexException):

    def __str__(self):
        return 'IdexCurrencyNotFoundException: {} not found'.format(self.message)


class IdexWalletAddressNotFoundException(Exception):
    def __str__(self):
        return 'IdexWalletAddressNotFoundException: Wallet address not set'.format(self.message)


class IdexPrivateKeyNotFoundException(Exception):
    def __str__(self):
        return 'IdexPrivateKeyNotFoundException: Private key not set'.format(self.message)
