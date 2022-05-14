import json


class IdexException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return "IdexException: {}".format(self.message)


class IdexAPIException(Exception):
    """Exception class to handle general API Exceptions

    `code` values

    `message` format

    """

    def __init__(self, response, status_code, text):
        self.code = ""
        self.message = "Unknown Error"
        try:
            json_res = json.loads(text)
        except ValueError:
            self.message = response.content
        else:
            if "message" in json_res:
                self.message = json_res["message"]
            if "code" in json_res:
                self.message = f"{json_res['code']} - {self.message}"

        self.status_code = status_code
        self.response = response
        self.request = getattr(response, "request", None)

    def __str__(self):
        return "IdexAPIException: {}".format(self.message)


class IdexRequestException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return "IdexRequestException: {}".format(self.message)


class IdexCurrencyNotFoundException(IdexException):
    def __str__(self):
        return "IdexCurrencyNotFoundException: {} not found".format(self.message)
