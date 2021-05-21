import dataclasses
from typing import Optional
from urllib.parse import urlparse

import ipfshttpclient
import requests

from ipwb import util, settings


@dataclasses.dataclass(frozen=True)
class BackendError(Exception):
    backend_name: str

    def __str__(self):
        return 'Cannot load index file from {self.backend_name}.'.format(
            self=self,
        )


def format_ipfs_cid(path: str) -> Optional[str]:
    """Format IPFS CID properly."""
    if path.startswith('Qm'):
        return path

    elif path.startswith('ipfs://'):
        return path.replace('ipfs://', '')


def fetch_ipfs_index(path: str) -> Optional[str]:
    """Fetch CDXJ file content from IPFS by hash."""
    ipfs_hash = format_ipfs_cid(path)

    if ipfs_hash is None:
        return None

    try:
        with ipfshttpclient.connect(settings.App.config("ipfsapi")) as client:
            return client.cat(path).decode('utf-8')

    except ipfshttpclient.exceptions.StatusError as err:
        raise BackendError(backend_name='ipfs') from err


def fetch_web_index(path: str) -> Optional[str]:
    """Fetch CDXJ file content from a URL."""
    scheme = urlparse(path).scheme

    if not scheme:
        return None

    try:
        return requests.get(path).text

    except (
        requests.ConnectionError,
        requests.HTTPError,
    ) as err:
        raise BackendError(backend_name='web') from err


def fetch_local_index(path: str) -> str:
    """Fetch CDXJ index contents from a file on local disk."""
    with open(path, 'r') as f:
        return f.read()


def get_web_archive_index(path: str) -> str:
    """
    Based on path, choose appropriate backend and fetch the file contents.
    """

    # TODO right now, every backend is just a function which returns contents
    #   of a CDXJ file as string. In the future, however, backends will be
    #   probably represented as classes with much more sophisticated methods
    #   of manipulating the archive index records.
    # TODO also, it will be possible to choose a backend and configure it;
    #   whereas right now we choose a backend automatically based on the given
    #   path itself.

    # Maybe it is an IPFS address?
    response = fetch_ipfs_index(path)
    if response is not None:
        return response

    # Or a traditional Web address?
    response = fetch_web_index(path)
    if response is not None:
        return response

    # Okay, this is probably a file on local disk
    response = fetch_local_index(path)
    if response is not None:
        return response

    raise ValueError((
        f'Unknown format of index file location: {path}. Please provide '
        f'a valid local path, HTTP or FTP URL, or an IPFS QmHash.'
    ))
