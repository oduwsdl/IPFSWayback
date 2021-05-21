import pytest


from ipwb import __main__
from multiaddr import exceptions as multiaddr_exceptions


class dotdict(dict):
    """dot.notation access to dictionary attributes"""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


daemon = None
args = {
        "c": False,
        "compressFirst": False,
        "daemon_address": daemon,
        "debug": False,
        "e": False,
        "outfile": None,
        "update_check": False,
        "warc_path": ['../samples/warcs/sample-1.warc.gz']
    }


def test_daemon_wrong_scheme():
    daemon = "/dnswrong/localhost/tcp/5001/http"
    args['daemon_address'] = daemon
    with pytest.raises(multiaddr_exceptions.StringParseError):
        __main__.checkArgs_index(dotdict(args))
        __main__.checkArgs_replay(dotdict(args))


def test_daemon_wrong_ip():
    daemon = "/ip4/256.999.478.444/tcp/5001/http"
    args['daemon_address'] = daemon
    with pytest.raises(multiaddr_exceptions.StringParseError):
        __main__.checkArgs_index(dotdict(args))
        __main__.checkArgs_replay(dotdict(args))


def test_daemon_wrong_protocol():
    daemon = "/dns/localhost/tcp/5001/httpwrong"
    args['daemon_address'] = daemon
    with pytest.raises(multiaddr_exceptions.StringParseError):
        __main__.checkArgs_index(dotdict(args))
        __main__.checkArgs_replay(dotdict(args))


def test_daemon_wrong_format():
    daemon = "localhost:5001"
    args['daemon_address'] = daemon
    with pytest.raises(multiaddr_exceptions.StringParseError):
        __main__.checkArgs_index(dotdict(args))
        __main__.checkArgs_replay(dotdict(args))
