import pytest

from . import testUtil as ipwbTest
from ipwb import replay
from time import sleep

import requests

import urllib

# Successful retrieval
# Accurate retrieval
# Comprehensive retrieval of sub-resources


@pytest.mark.parametrize("warc,lookup,has_md_header", [
    ('HTTP404.warc', 'memento/20200202100000/memento.us/', True),
    ('HTTP404.warc', 'memento/20200202100000/memento.ca/', False),
    ('HTTP404.warc', 'loremipsum', False)])
def test_replay_404(warc, lookup, has_md_header):
    ipwbTest.start_replay(warc)

    resp = requests.get(f'http://localhost:5000/{lookup}',
                        allow_redirects=False)

    assert resp.status_code == 404

    if has_md_header:
        assert 'Memento-Datetime' in resp.headers
    else:
        assert 'Memento-Datetime' not in resp.headers

    ipwbTest.stop_replay()


@pytest.mark.parametrize("warc,lookup,status,location", [
    ('salam-home.warc', 'memento/*/cs.odu.edu/~salam/', 302,
     '/memento/20160305192247/cs.odu.edu/~salam/'),
    ('1memento.warc', 'memento/*/memento.us', 302,
     '/memento/20130202100000/memento.us/'),
    ('2mementos.warc', 'memento/*/memento.us', 200, None),
    ('salam-home.warc', 'memento/*/?url=cs.odu.edu/~salam/', 301,
     '/memento/*/cs.odu.edu/~salam/'),
    ('1memento.warc', 'memento/*/?url=memento.us', 301,
     '/memento/*/memento.us'),
    ('2mementos.warc', 'memento/*/?url=memento.us', 301,
     '/memento/*/memento.us'),
    ('2mementos_queryString.warc',
     '/memento/20130202100000/memento.us/' +
     'index.php?anotherval=ipsum&someval=lorem', 200, None),
])
def test_replay_search(warc, lookup, status, location):
    ipwbTest.start_replay(warc)

    resp = requests.get(f'http://localhost:5000/{lookup}',
                        allow_redirects=False)
    assert resp.status_code == status
    if location is not None:  # Allow for checks w/o redirects
        assert resp.headers.get('location') == location

    ipwbTest.stop_replay()


def test_replay_dated_memento():
    ipwbTest.start_replay('salam-home.warc')

    url = 'http://localhost:5000/memento/{}/cs.odu.edu/~salam/'
    dest = '/memento/20160305192247/cs.odu.edu/~salam/'

    invalidDts = [
        '18',
        '20181',
        '201800',
        '20180132',
        '2018010226',
        '20181301000000',
        '20180932000000',
        '20180230000000',
        '20180102263127',
    ]
    for dt in invalidDts:
        resp = requests.get(url.format(dt), allow_redirects=False)
        assert resp.status_code == 400

    typoDts = [
        'foo',
        '201l',
        '2018010100000O',
        '20181126134257.123',
    ]
    for dt in typoDts:
        resp = requests.get(url.format(dt), allow_redirects=False)
        assert resp.status_code == 404

    validDts = [
        '2018',
        '201811',
        '20181126',
        '2018112613',
        '201811261342',
        '20181126134257',
    ]
    for dt in validDts:
        resp = requests.get(url.format(dt), allow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers.get('location') == dest

    resp = requests.get(url.format('20160305192247'), allow_redirects=False)
    assert resp.status_code == 200

    ipwbTest.stop_replay()


@pytest.mark.skip(reason='not implemented')
def test_retrieveWARCRecord_fromIPFSHash():
    pass


@pytest.mark.skip(reason='not implemented')
def test_retrieveWARCRecord_fromLocalCDXJFile():
    pass


@pytest.mark.skip(reason='not implemented')
def test_retrieveWARCRecord_fromRemoteCDXJFile_ByIPFSHash():
    pass


@pytest.mark.skip(reason='not implemented')
def test_retrieveWARCRecord_fromRemoteCDXJFile_ByHTTP():
    pass


@pytest.mark.skip(reason='not implemented')
def test_retrieveWARCRecord_fromRemoteCDXJFile_ByHTTPS():
    pass


@pytest.mark.skip(reason='not implemented')
def test_retrieveWARCRecord_fromRemoteCDXJFile_ByFTP():
    pass


@pytest.mark.skip(reason='not implemented')
def test_retrieveWARCRecord_fromRemoteCDXJFile_ByBitTorrentMagnetLink():
    pass


@pytest.mark.skip(reason='not implemented')
def test_retrieveWARCRecord_fromRemoteCDXJFile_BySMB():
    pass


@pytest.mark.skip(reason='not implemented')
def test_accuracy_retrievedContent_vsWARC():
    pass


@pytest.mark.skip(reason='not implemented')
def test_availability_subResources():
    pass


@pytest.mark.skip(reason='not implemented')
def test_inclusionInWebpage_selectResources():
    pass


@pytest.mark.skip(reason='not implemented')
def test_exclusionInWebpage_selectIrrelevantResources():
    pass


@pytest.mark.skip(reason='not implemented')
def test_fileImport_nonCDXJ():  # Fail w/ friendly message when non-cdxj
    pass


@pytest.mark.skip(reason='not implemented')
def test_helpWithoutDaemon():  # See #244
    pass


def test_unit_commandDaemon():
    replay.commandDaemon('start')
    sleep(10)
    try:
        urllib.request.urlopen('http://localhost:5001')
    except urllib.error.HTTPError as e:
        assert e.code == 404
    except Exception as e:
        assert False


@pytest.mark.parametrize("expected,input", [
    (True, 'http://example.com'),
    (True, 'https://example.com'),
    (True, 'HTTP://EXAMPLE.COM'),
    (True, 'HTTPS://EXAMPLE.COM'),
    (True, 'http://example.com/'),
    (True, 'http://example.com/foo.bar'),
    (True, 'https://www.example.com/foo?a=b&c=d'),
    (False, ''),
    (False, 'foo'),
    (False, 'foo/bar.baz'),
    (False, 'foo?a=b&c=d'),
    (False, '/'),
    (False, '/foo'),
    (False, '/foo/bar.baz'),
    (False, '/foo?a=b&c=d'),
    (False, './'),
    (False, './foo'),
    (False, './foo/bar.baz'),
    (False, './foo?a=b&c=d'),
    (False, '../'),
    (False, '../foo'),
    (False, '../foo/bar.baz'),
    (False, '../foo?a=b&c=d'),
    (False, '../../'),
    (False, '../../foo'),
    (False, '../../foo/bar.baz'),
    (False, '../../foo?a=b&c=d'),
    (False, 'ftp://example.com'),
    (False, 'httpd://example.com'),
    (False, 'http//example.com'),
    (False, 'http:/example.com'),
    (False, 'http:example.com'),
    (False, 'http.example.com'),
    (False, 'http-bin.com'),
])
def test_isUri(expected, input):
    assert expected == bool(replay.isUri(input))


# TODO: Have unit tests for each function in replay.py
