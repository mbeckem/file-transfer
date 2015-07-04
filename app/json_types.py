import json


class JsonError(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


def _mismatch(expected, found):
    raise JsonError(
        "type mismatch: expected {!r} but found {!r}".format(expected, found))


def parse_as(string, typeid):
    data = json.loads(string)
    if type(data) is typeid:
        return data
    _mismatch(typeid, type(data))


def get_as(obj, key, typeid, default=None):
    val = obj.get(key, default)
    if val is default:
        return val
    if type(val) is typeid:
        return val
    _mismatch(typeid, type(val))


def assert_as(obj, key, typeid):
    val = obj[key]
    if type(val) is typeid:
        return val
    _mismatch(typeid, type(val))
