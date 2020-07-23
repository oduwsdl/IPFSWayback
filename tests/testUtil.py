import os
import random
import string
import re
import tempfile

from time import sleep

from ipwb import replay
from ipwb import indexer
from ipwb import __file__ as moduleLocation

from multiprocessing import Process
from pathlib import Path

p = Process()


def createUniqueWARC():
    lines = []
    warcInFilename = 'frogTest.warc'
    warcInPath = os.path.join(
        Path(os.path.dirname(__file__)).parent,
        'samples', 'warcs', warcInFilename)

    stringToChange = b'abcdefghijklmnopqrstuvwxz'
    randomString = getRandomString(len(stringToChange))
    randomBytes = str.encode(randomString)

    with open(warcInPath, 'rb') as warcFile:
        newContent = warcFile.read().replace(stringToChange, randomBytes)

    warcOutFilename = warcInFilename.replace('.warc', '_' +
                                             randomString + '.warc')
    warcOutPath = os.path.join(
        Path(os.path.dirname(__file__)).parent,
        'samples', 'warcs', warcOutFilename)

    print(warcOutPath)
    with open(warcOutPath, 'wb') as warcFile:
        warcFile.write(newContent)

    return warcOutPath


def getRandomString(n):
    return ''.join(random.SystemRandom().choice(
                   string.ascii_lowercase + string.digits) for _ in range(n))


def countCDXJEntries(cdxjData):
    urimCount = 0
    lines = cdxjData.strip().split('\n')
    for line in lines:
        if line[0] != '!':  # Exclude metadata from count
            urimCount += 1
    return urimCount


def start_replay(warc_filename):
    global p
    path_of_warc = os.path.join(
        Path(os.path.dirname(__file__)).parent,
        'samples', 'warcs', warc_filename)

    fh, tempfile_path = tempfile.mkstemp(suffix='.cdxj')
    os.close(fh)

    p = Process(target=replay.start, args=[tempfile_path])
    p.start()
    sleep(5)

    cdxj_list = indexer.indexFileAt(path_of_warc, quiet=True)
    cdxj = '\n'.join(cdxj_list)

    with open(tempfile_path, 'w') as f:
        f.write(cdxj)


def stop_replay():
    global p
    p.terminate()


def extractRelationEntriesFromLinkTimeMap(tm):
    matches = re.findall('rel=".*?"', tm)
    matches = map(lambda s: s[5:-1], matches)
    return matches
