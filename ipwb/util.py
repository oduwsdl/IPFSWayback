import functools
from os.path import expanduser

import os

import ipfshttpclient
import requests

import re
# Datetime conversion to rfc1123
import locale
import datetime
import logging
import platform

from enum import Enum, auto

from urllib.request import urlopen
from urllib.error import URLError

import json
from .__init__ import __version__ as ipwb_version

from ipfshttpclient.exceptions import ConnectionError, AddressError
from multiaddr.exceptions import StringParseError
from pkg_resources import parse_version

from .exceptions import IPFSDaemonNotAvailable

logger = logging.getLogger(__name__)


IPFSAPI_MUTLIADDRESS = '/dns/localhost/tcp/5001/http'
# or '/dns/{host}/tcp/{port}/http'
# or '/ip4/{ipaddress}/tcp/{port}/http'
# or '/ip6/{ipaddress}/tcp/{port}/http

IPWBREPLAY_ADDRESS = 'localhost:5000'

(IPWBREPLAY_HOST, IPWBREPLAY_PORT) = IPWBREPLAY_ADDRESS.split(':')
IPWBREPLAY_PORT = int(IPWBREPLAY_PORT)

INDEX_FILE = os.path.join('samples', 'indexes', 'salam-home.cdxj')


class MementoMatch(Enum):
    WRONGKEY = auto()
    RIGHTKEYWRONGDATE = auto()
    EXACTMATCH = auto()


log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


dtPattern = re.compile(r"^(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?$")


def create_ipfs_client(daemonMultiaddr=IPFSAPI_MUTLIADDRESS):
    """Create and return IPFS client."""
    try:
        return ipfshttpclient.Client(daemonMultiaddr)
    except Exception as err:
        raise Exception('Cannot create an IPFS client.') from err


@functools.lru_cache()
def ipfs_client(daemonMultiaddr=IPFSAPI_MUTLIADDRESS):
    """
    Create and cache IPFS client instance.

    Caching is the single difference between this and
    `create_ipfs_client()` above.
    """
    return create_ipfs_client(daemonMultiaddr)


def check_daemon_is_alive(daemonMultiaddr=IPFSAPI_MUTLIADDRESS):
    """Ensure that the IPFS daemon is running via HTTP before proceeding"""
    client = ipfs_client()

    try:
        # ConnectionError/AttributeError if IPFS daemon not running
        client.id()
        return True

    except ConnectionError as err:
        raise IPFSDaemonNotAvailable(
            f'Daemon is not running at: {daemonMultiaddr}',
        ) from err

    except OSError as err:
        raise IPFSDaemonNotAvailable(
            'IPFS is likely not installed. See https://ipfs.io/docs/install/'
        ) from err

    except Exception as err:
        raise IPFSDaemonNotAvailable(
            'Unknown error in retrieving IPFS daemon status.',
        ) from err


def isValidCDXJ(stringIn):  # TODO: Check specific strict syntax
    # Also, be sure to mind the meta headers starting with @/#, etc.
    return True


def isValidCDXJLine(cdxjLine):
    try:
        (surtURI, datetime, jsonData) = cdxjLine.split(' ', 2)

        json.loads(jsonData)
        validDatetime = len(datetime) == 14

        validSURT = True  # TODO: check valid SURT URI

        return validSURT and validDatetime
    except ValueError:  # Not valid JSON
        return False
    except NameError:
        return isCDXJMetadataRecord(cdxjLine)
    except Exception as e:
        return False


# Compare versions of software, <0 if a<b, 0 if ==, >1 if b>a
def compareVersions(versionA, versionB):
    return parse_version(versionA) < parse_version(versionB)


def isCDXJMetadataRecord(cdxjLine):
    return cdxjLine.strip()[:1] == b'!'


def isLocalHosty(uri):
    # TODO: check for these SW conditions
    # (*, localhost, *); (*, 127/8, *); (*, ::1/128, *)
    localhosts = ['localhost', '127.0.0.1']
    for lh in localhosts:
        if lh in uri:
            return True
    return False


def setLocale():
    currentOS = platform.system()

    if currentOS == 'Darwin':
        newLocale = 'en_US'
    elif currentOS == 'Windows':
        newLocale = 'english'
    else:  # Assume Linux
        newLocale = 'en_US.utf8'

    try:
        locale.setlocale(locale.LC_TIME, newLocale)
    except locale.Error:
        locale.setlocale(locale.LC_TIME, '')


def digits14ToRFC1123(digits14):
    setLocale()
    # Trim to 14-digits max for testing
    if len(digits14) > 14:
        digits14 = digits14[0:14]
    d = datetime.datetime.strptime(digits14, '%Y%m%d%H%M%S')
    return d.strftime('%a, %d %b %Y %H:%M:%S GMT')


def rfc1123ToDigits14(rfc1123DateString):
    setLocale()
    d = datetime.datetime.strptime(rfc1123DateString,
                                   '%a, %d %b %Y %H:%M:%S %Z')

    # TODO: Account for conversion if TZ other than GMT not specified

    return d.strftime('%Y%m%d%H%M%S')


def iso8601ToDigits14(iso8601DateString):
    setLocale()
    d = datetime.datetime.strptime(iso8601DateString,
                                   "%Y-%m-%dT%H:%M:%SZ")

    # TODO: Account for conversion if TZ other than GMT not specified

    return d.strftime('%Y%m%d%H%M%S')


def isRFC1123Compliant(dtstr):
    try:
        datetime.datetime.strptime(dtstr, '%a, %d %b %Y %H:%M:%S GMT')
        return True
    except ValueError as err:
        return False


def getRFC1123OfNow():
    setLocale()
    d = datetime.datetime.now()
    return d.strftime('%a, %d %b %Y %H:%M:%S GMT')


def padDigits14(dtstr, validate=False):
    '''Pad datetime to make a 14-digit string and optionally validate it'''
    match = dtPattern.match(dtstr)
    if match:
        Y = match.group(1)
        m = match.group(2) or '01'
        d = match.group(3) or '01'
        H = match.group(4) or '00'
        M = match.group(5) or '00'
        S = match.group(6) or '00'
        dtstr = f'{Y}{m}{d}{H}{M}{S}'
    if validate:
        datetime.datetime.strptime(dtstr, '%Y%m%d%H%M%S')
    return dtstr


def fetch_remote_file(path):
    try:
        r = requests.get(path)
        return r.text

    except ConnectionError:
        raise Exception(f'File at {path} is unavailable.')

    except Exception as err:
        raise Exception(
            'An unknown error occurred trying to fetch {}'.format(path)
        ) from err


# IPFS Config manipulation from here on out.
def readIPFSConfig():
    ipfsConfigPath = os.path.join(expanduser("~"), '.ipfs', 'config')
    if 'IPFS_PATH' in os.environ:
        ipfsConfigPath = os.path.join(
            os.environ.get('IPFS_PATH'), 'config')

    try:
        with open(ipfsConfigPath, 'r') as f:
            return json.load(f)

    except IOError as err:
        raise Exception(
            'IPFS config not found. Have you installed ipfs and run ipfs init?'
        ) from err


def writeIPFSConfig(jsonToWrite):
    ipfsConfigPath = os.path.join(expanduser("~"), '.ipfs', 'config')
    if 'IPFS_PATH' in os.environ:
        ipfsConfigPath = os.path.join(
            os.environ.get('IPFS_PATH'), 'config')

    with open(ipfsConfigPath, 'w') as f:
        f.write(json.dumps(jsonToWrite, indent=4, sort_keys=True))


def getIPFSAPIHostAndPort(ipfsJSON=None):
    if not ipfsJSON:
        ipfsJSON = readIPFSConfig()

    (scheme, host, protocol, port) = (
        ipfsJSON['Addresses']['API'][1:].split('/')
    )
    return host + ':' + port


def getIPWBReplayConfig(ipfsJSON=None):
    if not ipfsJSON:
        ipfsJSON = readIPFSConfig()
    port = None
    if ('Ipwb' in ipfsJSON and 'Replay' in ipfsJSON['Ipwb'] and
       'Port' in ipfsJSON['Ipwb']['Replay']):
        host = ipfsJSON['Ipwb']['Replay']['Host']
        port = ipfsJSON['Ipwb']['Replay']['Port']
        return (host, port)
    else:
        return None


def setIPWBReplayConfig(Host, Port, ipfsJSON=None):
    if not ipfsJSON:
        ipfsJSON = readIPFSConfig()
    ipfsJSON['Ipwb'] = {}
    ipfsJSON['Ipwb']['Replay'] = {
      u'Host': Host,
      u'Port': Port
    }
    writeIPFSConfig(ipfsJSON)


def setIPWBReplayIndexPath(cdxj):
    if cdxj is None:
        cdxj = INDEX_FILE
    ipfsJSON = readIPFSConfig()
    ipfsJSON['Ipwb']['Replay']['Index'] = cdxj
    writeIPFSConfig(ipfsJSON)
    return


def getIPWBReplayIndexPath():
    ipfsJSON = readIPFSConfig()
    if 'Ipwb' not in ipfsJSON:
        setIPWBReplayConfig(IPWBREPLAY_HOST, IPWBREPLAY_PORT)
        ipfsJSON = readIPFSConfig()

    if 'Index' in ipfsJSON['Ipwb']['Replay']:
        return ipfsJSON['Ipwb']['Replay']['Index']
    else:
        return ''


# From pywb 2.0.4
def unsurt(surt):
    try:
        index = surt.index(')/')
        parts = surt[0:index].split(',')
        parts.reverse()
        host = '.'.join(parts)
        host += surt[index+1:]
        return host

    except ValueError:
        # May not be a valid surt
        return surt


def get_latest_version():
    try:
        resp = urlopen('https://pypi.org/pypi/ipwb/json')
        return json.loads(resp.read())['info']['version']
    except Exception:
        return None


def check_for_update(_):
    latest = get_latest_version()
    if not latest:
        print("Failed to check for the latest version.")
        return
    current = re.sub(r'\.0+', '.', ipwb_version)
    if latest == current:
        print(f"Installed version {current} is up to date.")
    else:
        print("The installed version of ipwb is outdated.")
        print(f"* Installed: {current}\n* Latest:    {latest}")
        print("Please run `pip install --upgrade ipwb` to upgrade.")
