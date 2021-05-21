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

from urllib.request import urlopen
from urllib.error import URLError

import json
from .__init__ import __version__ as ipwb_version
from . import settings

from ipfshttpclient.exceptions import ConnectionError, AddressError
from multiaddr.exceptions import StringParseError
from pkg_resources import parse_version

from .exceptions import IPFSDaemonNotAvailable

logger = logging.getLogger(__name__)


IPWBREPLAY_ADDRESS = 'localhost:5000'

(IPWBREPLAY_HOST, IPWBREPLAY_PORT) = IPWBREPLAY_ADDRESS.split(':')
IPWBREPLAY_PORT = int(IPWBREPLAY_PORT)

INDEX_FILE = os.path.join('samples', 'indexes', 'salam-home.cdxj')

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


dt_pattern = re.compile(r"^(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?$")


def create_ipfs_client():
    """Create and return IPFS client."""
    daemonMultiaddr = settings.App.config("ipfsapi")
    try:
        return ipfshttpclient.Client(daemonMultiaddr)
    except Exception as err:
        raise Exception('Cannot create an IPFS client.') from err


@functools.lru_cache()
def ipfs_client():
    """
    Create and cache IPFS client instance.

    Caching is the single difference between this and
    `create_ipfs_client()` above.
    """
    return create_ipfs_client()


def check_daemon_is_alive():
    """Ensure that the IPFS daemon is running via HTTP before proceeding"""
    client = ipfs_client()
    daemonMultiaddr = settings.App.config("ipfsapi")

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


def is_valid_cdxj(stringIn):  # TODO: Check specific strict syntax
    # Also, be sure to mind the meta headers starting with @/#, etc.
    return True


def is_valid_cdxj_line(cdxj_line):
    try:
        (surt_uri, datetime, jsonData) = cdxj_line.split(' ', 2)

        json.loads(jsonData)
        valid_datetime = len(datetime) == 14

        valid_surt = True  # TODO: check valid SURT URI

        return valid_surt and valid_datetime
    except ValueError:  # Not valid JSON
        return False
    except NameError:
        return is_cdxj_metadata_record(cdxj_line)
    except Exception as e:
        return False


# Compare versions of software, <0 if a<b, 0 if ==, >1 if b>a
def compare_versions(versionA, versionB):
    return parse_version(versionA) < parse_version(versionB)


def is_cdxj_metadata_record(cdxj_line):
    return cdxj_line.strip()[:1] == '!'


def is_localhosty(uri):
    # TODO: check for these SW conditions
    # (*, localhost, *); (*, 127/8, *); (*, ::1/128, *)
    localhosts = ['localhost', '127.0.0.1']
    for lh in localhosts:
        if lh in uri:
            return True
    return False


def set_locale():
    currentOS = platform.system()

    if currentOS == 'Darwin':
        new_locale = 'en_US'
    elif currentOS == 'Windows':
        new_locale = 'english'
    else:  # Assume Linux
        new_locale = 'en_US.utf8'

    try:
        locale.setlocale(locale.LC_TIME, new_locale)
    except locale.Error:
        locale.setlocale(locale.LC_TIME, '')


def digits14_to_rfc1123(digits14):
    set_locale()
    d = datetime.datetime.strptime(digits14, '%Y%m%d%H%M%S')
    return d.strftime('%a, %d %b %Y %H:%M:%S GMT')


def rfc1123_to_digits14(rfc1123_datestring):
    set_locale()
    d = datetime.datetime.strptime(rfc1123_datestring,
                                   '%a, %d %b %Y %H:%M:%S %Z')

    # TODO: Account for conversion if TZ other than GMT not specified

    return d.strftime('%Y%m%d%H%M%S')


def iso8601_to_digits14(iso8601DateString):
    set_locale()
    d = datetime.datetime.strptime(iso8601DateString,
                                   "%Y-%m-%dT%H:%M:%SZ")

    # TODO: Account for conversion if TZ other than GMT not specified

    return d.strftime('%Y%m%d%H%M%S')


def is_rfc1123_compliant(dtstr):
    try:
        datetime.datetime.strptime(dtstr, '%a, %d %b %Y %H:%M:%S GMT')
        return True
    except ValueError as err:
        return False


def get_rfc1123_of_now():
    set_locale()
    d = datetime.datetime.now()
    return d.strftime('%a, %d %b %Y %H:%M:%S GMT')


def pad_digits14(dtstr, validate=False):
    '''Pad datetime to make a 14-digit string and optionally validate it'''
    match = dt_pattern.match(dtstr)
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
def read_ipfs_config():
    ipfs_config_path = os.path.join(expanduser("~"), '.ipfs', 'config')
    if 'IPFS_PATH' in os.environ:
        ipfs_config_path = os.path.join(
            os.environ.get('IPFS_PATH'), 'config')

    try:
        with open(ipfs_config_path, 'r') as f:
            return json.load(f)

    except IOError as err:
        raise Exception(
            'IPFS config not found. Have you installed ipfs and run ipfs init?'
        ) from err


def write_ipfs_config(json_to_write):
    ipfs_config_path = os.path.join(expanduser("~"), '.ipfs', 'config')
    if 'IPFS_PATH' in os.environ:
        ipfs_config_path = os.path.join(
            os.environ.get('IPFS_PATH'), 'config')

    with open(ipfs_config_path, 'w') as f:
        f.write(json.dumps(json_to_write, indent=4, sort_keys=True))


def get_ipfsapi_host_and_port():
    daemon_address = settings.App.config("ipfsapi")
    # format right now is "/dns/localhost/tcp/5001/http"

    (scheme, host, protocol, port, protocol2) = daemon_address[1:].split('/')
    if protocol2 == "https" and port == "443":
        # if https is used, rely on a 301/302 redirect response
        return host
    else:
        return host + ':' + port


def get_ipwb_replay_config(ipfs_json=None):
    if not ipfs_json:
        ipfs_json = read_ipfs_config()
    port = None
    if ('Ipwb' in ipfs_json and 'Replay' in ipfs_json['Ipwb'] and
       'Port' in ipfs_json['Ipwb']['Replay']):
        host = ipfs_json['Ipwb']['Replay']['Host']
        port = ipfs_json['Ipwb']['Replay']['Port']
        return (host, port)
    else:
        return None


def set_ipwb_replay_config(Host, Port, ipfs_json=None):
    if not ipfs_json:
        ipfs_json = read_ipfs_config()
    ipfs_json['Ipwb'] = {}
    ipfs_json['Ipwb']['Replay'] = {
      u'Host': Host,
      u'Port': Port
    }
    write_ipfs_config(ipfs_json)


def set_ipwb_replay_index_path(cdxj):
    if cdxj is None:
        cdxj = INDEX_FILE
    ipfs_json = read_ipfs_config()
    ipfs_json['Ipwb']['Replay']['Index'] = cdxj
    write_ipfs_config(ipfs_json)
    return


def get_ipwb_replay_index_path():
    ipfs_json = read_ipfs_config()
    if 'Ipwb' not in ipfs_json:
        set_ipwb_replay_config(IPWBREPLAY_HOST, IPWBREPLAY_PORT)
        ipfs_json = read_ipfs_config()

    if 'Index' in ipfs_json['Ipwb']['Replay']:
        return ipfs_json['Ipwb']['Replay']['Index']
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
