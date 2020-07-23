#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
InterPlanetary Wayback indexer

This script reads a WARC file and returns a CDXJ representative of its
 contents. In doing so, it extracts all archived HTTP responses from
 warc-response records, separates the HTTP header from the body, pushes each
 into IPFS, and retains the hashes. These hashes are then used to populate the
 JSON block corresponding to the archived URI.
"""

import sys
import os
import json
import ipfshttpclient as ipfsapi
import zlib
import surt
import ntpath
import traceback
import tempfile

from io import BytesIO
from warcio.archiveiterator import ArchiveIterator
from warcio.recordloader import ArchiveLoadFailed

from requests.packages.urllib3.exceptions import NewConnectionError
from ipfshttpclient.exceptions import ConnectionError
# from requests.exceptions import ConnectionError

from six.moves import input
from six import PY2
from six import PY3

from ipwb.util import iso8601ToDigits14, ipfs_client

import requests
import datetime

from bs4 import BeautifulSoup

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import base64

from .__init__ import __version__ as ipwbVersion

DEBUG = False


def s2b(s):  # Convert str to bytes, cross-py
    return bytes(s) if PY2 else bytes(s, 'utf-8')


# TODO: put this method definition below indexFileAt()
def pushToIPFS(hstr, payload):
    ipfsRetryCount = 5  # WARC->IPFS attempts before giving up
    retryCount = 0
    while retryCount < ipfsRetryCount:
        try:
            # Py 2/3 str/unicode/byte resolution
            if isinstance(hstr, str):
                hstr = s2b(hstr)
            if isinstance(payload, str):
                payload = s2b(payload)

            if len(payload) == 0:  # py-ipfs-api issue #137
                return

            httpHeaderIPFSHash = pushBytesToIPFS(hstr)
            payloadIPFSHash = pushBytesToIPFS(payload)

            if retryCount > 0:
                m = f'Retrying succeeded after {retryCount} attempts'
                print(m)
            return [httpHeaderIPFSHash, payloadIPFSHash]
        except NewConnectionError as e:
            print('IPFS daemon is likely not running.')
            print('Run "ipfs daemon" in another terminal session.')

            sys.exit()
        except Exception as e:  # TODO: Do not use bare except
            attemptCount = f'{retryCount + 1}/{ipfsRetryCount}'
            logError(f'IPFS failed to add, retrying attempt {attemptCount}')
            logError(sys.exc_info())
            traceback.print_tb(sys.exc_info()[-1])

            retryCount += 1

    return None  # Process of adding to IPFS failed


def encrypt(hstr, payload, encryptionKey):
    paddedEncryptionKey = pad(encryptionKey, AES.block_size)
    key = base64.b64encode(paddedEncryptionKey)
    cipher = AES.new(key, AES.MODE_CTR)

    hstrBytes = base64.b64encode(cipher.encrypt(hstr)).decode('utf-8')

    payloadBytes = base64.b64encode(cipher.encrypt(payload)).decode('utf-8')
    nonce = base64.b64encode(cipher.nonce).decode('utf-8')

    return [hstrBytes, payloadBytes, nonce]


def createIPFSTempPath():
    ipfsTempPath = tempfile.gettempdir() + '/ipfs/'

    # Create temp path for ipwb temp files if it does not already exist
    if not os.path.exists(ipfsTempPath):
        os.makedirs(ipfsTempPath)


def indexFileAt(warcPaths, encryptionKey=None,
                compressionLevel=None, encryptTHENCompress=True,
                quiet=False, outfile=None, debug=False):
    global DEBUG
    DEBUG = debug

    if type(warcPaths) is str:
        warcPaths = [warcPaths]

    for warcPath in warcPaths:
        verifyFileExists(warcPath)

    cdxjLines = []

    if outfile:
        outdir = os.path.dirname(os.path.abspath(outfile))
        if not os.path.exists(outdir):
            try:
                os.makedirs(outdir)
            except Exception as e:
                logError(e)
                logError('CDXJ output directory was not created')
        try:
            outputFile = open(outfile, 'a+')
            # Read existing non-meta lines (if any) to allow automatic merge
            cdxjLines = [ln.strip() for ln in outputFile if ln[:1] != '!']
        except IOError as e:
            logError(e)
            logError('Writing generated CDXJ to STDOUT instead')
            outfile = None

    if encryptionKey is not None and len(encryptionKey) == 0:
        encryptionKey = askUserForEncryptionKey()
        if encryptionKey == '':
            encryptionKey = None
            logError('Blank key entered, encryption disabled')

    encryptionAndCompressionSetting = {
        'encryptTHENCompress': encryptTHENCompress,
        'encryptionKey': encryptionKey,
        'compressionLevel': compressionLevel
    }

    for warcPath in warcPaths:
        warcFileFullPath = warcPath

        try:
            cdxjLines += getCDXJLinesFromFile(
                warcFileFullPath, **encryptionAndCompressionSetting)
        except ArchiveLoadFailed:
            logError(warcPath + ' is not a valid WARC file.')

    # De-dupe and sort, needed for CDXJ adherence
    cdxjLines = list(set(cdxjLines))
    cdxjLines.sort()

    # Prepend metadata
    cdxjMetadataLines = generateCDXJMetadata(cdxjLines)
    cdxjLines = cdxjMetadataLines + cdxjLines

    if quiet:
        return cdxjLines

    if outfile:
        # Truncate existing CDXJ file contents (if any) before writing to it
        outputFile.seek(0)
        outputFile.truncate()
        for line in cdxjLines:
            outputFile.write(line + "\n")
        outputFile.close()
    else:
        print('\n'.join(cdxjLines))


def sanitizecdxjLine(cdxjLine):
    return cdxjLine


def getCDXJLinesFromFile(warcPath, **encCompOpts):
    recordCount = 0
    with open(warcPath, 'rb') as fhForCounting:
        recordCount = 0
        try:
            for record in ArchiveIterator(fhForCounting):
                recordCount += 1

        except ArchiveLoadFailed:
            print('Encountered a bad WARC record.', file=sys.stderr)

    with open(warcPath, 'rb') as fh:
        cdxjLines = []
        recordsProcessed = 0
        # Throws pywb.warc.recordloader.ArchiveLoadFailed if not a warc
        for record in ArchiveIterator(fh):
            msg = 'Processing WARC records in ' + ntpath.basename(warcPath)
            showProgress(msg, recordsProcessed, recordCount)

            recordsProcessed += 1
            # Only consider WARC resps records from reqs for web resources
            ''' TODO: Change conditional to return on non-HTTP responses
                      to reduce branch depth'''
            if record.rec_type != 'response' or \
               record.rec_headers.get_header('Content-Type') in \
                    ('text/dns', 'text/whois'):
                continue

            hstr = record.http_headers.to_str().strip()

            try:
                statusCode = record.http_headers.statusline.split()[0]
            except Exception as e:  # TODO: Do not use bare except
                break

            payload = record.content_stream().read()

            title = None
            try:
                ctype = record.http_headers.get_header('content-type')
                if ctype and ctype.lower().startswith('text/html'):
                    title = BeautifulSoup(payload, 'html.parser').title
                    if title is not None:
                        title = ' '.join(title.text.split()) or None
            except Exception as e:
                print('Failed to extract title', file=sys.stderr)
                print(e, file=sys.stderr)

            httpHeaderIPFSHash = ''
            payloadIPFSHash = ''
            retryCount = 0
            nonce = ''

            if encCompOpts.get('encryptTHENCompress'):
                if encCompOpts.get('encryptionKey') is not None:
                    key = encCompOpts.get('encryptionKey')
                    (hstr, payload, nonce) = encrypt(hstr, payload, key)
                if encCompOpts.get('compressionLevel') is not None:
                    compressionLevel = encCompOpts.get('compressionLevel')
                    hstr = zlib.compress(hstr, compressionLevel)
                    payload = zlib.compress(payload, compressionLevel)
            else:
                if encCompOpts.get('compressionLevel') is not None:
                    compressionLevel = encCompOpts.get('compressionLevel')
                    hstr = zlib.compress(hstr, compressionLevel)
                    payload = zlib.compress(payload, compressionLevel)
                if encCompOpts.get('encryptionKey') is not None:
                    encryptionKey = encCompOpts.get('encryptionKey')
                    (hstr, payload, nonce) = \
                        encrypt(hstr, payload, encryptionKey)

            # print(f'Adding {entry.get("url")} to IPFS')
            ipfsHashes = pushToIPFS(hstr, payload)

            if ipfsHashes is None:
                logError('Skipping ' +
                         record.rec_headers.get_header('WARC-Target-URI'))

                continue

            (httpHeaderIPFSHash, payloadIPFSHash) = ipfsHashes

            originaluri = record.rec_headers.get_header('WARC-Target-URI')
            originaluri_surted = \
                surt.surt(originaluri,
                          path_strip_trailing_slash_unless_empty=False)
            timestamp = iso8601ToDigits14(
                record.rec_headers.get_header('WARC-Date'))
            mime = record.http_headers.get_header('content-type')
            obj = {
                'locator': f'urn:ipfs/{httpHeaderIPFSHash}/{payloadIPFSHash}',
                'status_code': statusCode,
                'mime_type': mime or '',
                'original_uri': originaluri
            }
            if encCompOpts.get('encryptionKey') is not None:
                obj['encryption_key'] = encCompOpts.get('encryptionKey')
                obj['encryption_method'] = 'aes'
                obj['encryption_nonce'] = nonce
            if title is not None:
                obj['title'] = title

            objJSON = json.dumps(obj)

            cdxjLine = f'{originaluri_surted} {timestamp} {objJSON}'
            cdxjLines.append(cdxjLine)  # + '\n'
        return cdxjLines


def generateCDXJMetadata(cdxjLines=None):
    metadata = ['!context ["http://tools.ietf.org/html/rfc7089"]']
    metaVals = {
        'generator': f'InterPlanetary Wayback {ipwbVersion}',
        'created_at': datetime.datetime.now().isoformat()
    }
    metaVals = f'!meta {json.dumps(metaVals)}'
    metadata.append(metaVals)

    return metadata


def askUserForEncryptionKey():
    if DEBUG:  # Allows testing instead of requiring a user prompt
        return 'ipwb'

    outputRedirected = os.fstat(0) != os.fstat(1)
    promptString = 'Enter a key for encryption: '
    if outputRedirected:  # Prevents prompt in redir output
        logError(promptString, end='')
        promptString = ''

    key = input(promptString)

    return key


def verifyDaemonIsAlive(hostAndPort):
    """Ensure that the IPFS daemon is running via HTTP before proceeding"""
    try:
        requests.get('http://' + hostAndPort)
    except ConnectionError:
        print('Daemon is not running at http://' + hostAndPort)
        sys.exit()


def verifyFileExists(warcPath):
    if os.path.isfile(warcPath):
        return
    logError('File at ' + warcPath + ' does not exist!')
    sys.exit()


def showProgress(msg, i, n):
    line = f'{msg}: {i}/{n}'
    print(line, file=sys.stderr, end='\r')
    # Clear status line, show complete msg
    if i == n - 1:
        finalMsg = msg + ' complete'
        spaceDelta = len(finalMsg) - len(msg)
        spaces = '' * spaceDelta if spaceDelta > 0 else ''
        print(finalMsg + spaces, file=sys.stderr, end='\r\n')


def logError(errIn, end='\n'):
    print(errIn, file=sys.stderr, end=end)


def pullFromIPFS(hash):
    return ipfs_client().cat(hash)


def pushBytesToIPFS(bytes):
    """
    Call the IPFS API to add the byte string to IPFS.
    When IPFS returns a hash, return this to the caller
    """
    # Returns unicode in py2.7, str in py3.7
    try:
        res = ipfs_client().add_bytes(bytes)  # bytes)
    except TypeError as err:
        # print('fail')
        logError('IPFS_API had an issue pushing the item to IPFS')
        logError(sys.exc_info())
        logError(len(bytes))
        traceback.print_tb(sys.exc_info()[-1])
    except ipfsapi.exceptions.ConnectionError as connErr:
        # print('ConnErr')
        logError(sys.exc_info())
        traceback.print_tb(sys.exc_info()[-1])
        return

    # TODO: verify that the add was successful

    if type(res).__name__ == 'unicode':
        return res
    elif type(res).__name__ == 'str':
        return res

    logError('NEITHER UNICODE NOR STR RETURNED.')
    return res[0]['Hash']


def writeFile(filename, content):
    with open(filename, 'w') as tmpFile:
        tmpFile.write(content)
