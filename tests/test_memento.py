import pytest

from . import testUtil as ipwbTest
from ipwb import replay
from ipwb import indexer
from ipwb import __file__ as moduleLocation
from time import sleep
import os
import subprocess
from urllib.request import urlopen
import requests
import random
import string
import re
import sys


def getURIMsFromTimeMapInWARC(warcFilename):
    ipwbTest.start_replay(warcFilename)

    tmURI = 'http://localhost:5000/timemap/link/memento.us/'
    tm = urlopen(tmURI).read().decode('utf-8')

    urims = []
    for line in tm.split('\n'):
        isAMemento = len(re.findall('rel=".*memento"', line)) > 0
        if isAMemento:
            urims.append(re.findall('<(.*)>', line)[0])
    ipwbTest.stop_replay()

    return urims


def getRelsFromURIMSinWARC(warc):
    urims = getURIMsFromTimeMapInWARC(warc)
    ipwbTest.start_replay(warc)

    # Get Link header values for each memento
    linkHeaders = []
    for urim in urims:
        linkHeaders.append(urlopen(urim).info().get('Link'))

    relsForURIMs = []
    for linkHeader in linkHeaders:
        relForURIM = ipwbTest.extractRelationEntriesFromLinkTimeMap(linkHeader)
        relsForURIMs.append(relForURIM)

    ipwbTest.stop_replay()
    return relsForURIMs


@pytest.mark.parametrize("warc,lookup,acceptdatetime,status", [
    ('5mementos.warc', 'timegate/memento.us',
     'Thu, 31 May 2007 20:35:00 GMT', 302),
    ('5mementos.warc', 'timegate/memento.us',
     'Thu, 31 May 2007 20:35:00', 400),
    ('5mementos.warc', 'timegate/memento.us',
     'Thu, 31 May 2007 20:35 GMT', 400),
    ('5mementos.warc', 'timegate/memento.us',
     '20181001123636', 400)
])
def test_acceptdatetime_status(warc, lookup, acceptdatetime, status):
    ipwbTest.start_replay(warc)

    headers = {'Accept-Datetime': acceptdatetime}

    resp = requests.get(f'http://localhost:5000/{lookup}',
                        allow_redirects=False, headers=headers)
    assert resp.status_code == status

    ipwbTest.stop_replay()


def test_mementoRelations_one():
    relsForURIMs = getRelsFromURIMSinWARC('1memento.warc')

    relsForURIMs = list(filter(lambda k: 'memento' in k, relsForURIMs[0]))
    m1_m1 = relsForURIMs[0].split(' ')

    onlyOneMemento = len(relsForURIMs) == 1

    cond_firstMemento = 'first' in m1_m1
    cond_lastMemento = 'last' in m1_m1

    assert onlyOneMemento and \
        cond_firstMemento and \
        cond_lastMemento


def test_mementoRelations_two():
    relsForURIMs = getRelsFromURIMSinWARC('2mementos.warc')

    cond_firstMemento = False
    cond_lastNextMemento = False
    cond_firstPrevMemento = False
    cond_lastMemento = False

    relsForURIMs1of2 = list(filter(lambda k: 'memento' in k, relsForURIMs[0]))
    relsForURIMs2of2 = list(filter(lambda k: 'memento' in k, relsForURIMs[1]))

    # mX_mY = URI-M requested, Y-th URIM-M in header
    m1_m1 = relsForURIMs1of2[0].split(' ')
    m1_m2 = relsForURIMs1of2[1].split(' ')
    m2_m1 = relsForURIMs2of2[0].split(' ')
    m2_m2 = relsForURIMs2of2[1].split(' ')

    cond_firstMemento = 'first' in m1_m1
    cond_lastNextMemento = 'last' in m1_m2 and 'next' in m1_m2
    cond_firstPrevMemento = 'first' in m2_m1 and 'prev' in m2_m1
    cond_lastMemento = 'last' in m2_m2

    assert cond_firstMemento and \
        cond_lastNextMemento and \
        cond_firstPrevMemento and \
        cond_lastMemento


def test_mementoRelations_three():
    relsForURIMs = getRelsFromURIMSinWARC('3mementos.warc')

    cond_m1m1_firstMemento = False
    cond_m1m2_nextMemento = False
    cond_m1m3_lastMemento = False
    cond_m2m1_firstPrevMemento = False
    cond_m2m2_memento = False
    cond_m2m3_lastNextMemento = False
    cond_m3m1_firstMemento = False
    cond_m3m2_prevMemento = False
    cond_m3m3_lastMemento = False

    relsForURIMs1of3 = list(filter(lambda k: 'memento' in k, relsForURIMs[0]))
    relsForURIMs2of3 = list(filter(lambda k: 'memento' in k, relsForURIMs[1]))
    relsForURIMs3of3 = list(filter(lambda k: 'memento' in k, relsForURIMs[2]))

    # mX_mY = URI-M requested, Y-th URIM-M in header
    m1_m1 = relsForURIMs1of3[0].split(' ')
    m1_m2 = relsForURIMs1of3[1].split(' ')
    m1_m3 = relsForURIMs1of3[2].split(' ')
    m2_m1 = relsForURIMs2of3[0].split(' ')
    m2_m2 = relsForURIMs2of3[1].split(' ')
    m2_m3 = relsForURIMs2of3[2].split(' ')
    m3_m1 = relsForURIMs3of3[0].split(' ')
    m3_m2 = relsForURIMs3of3[1].split(' ')
    m3_m3 = relsForURIMs3of3[2].split(' ')

    cond_m1m1_firstMemento = 'first' in m1_m1
    cond_m1m2_nextMemento = 'next' in m1_m2
    cond_m1m3_lastMemento = 'last' in m1_m3
    cond_m2m1_firstPrevMemento = 'first' in m2_m1 and 'prev' in m2_m1
    cond_m2m2_memento = len(m2_m2) == 1
    cond_m2m3_lastNextMemento = 'last' in m2_m3 and 'next' in m2_m3
    cond_m3m1_firstMemento = 'first' in m3_m1
    cond_m3m2_prevMemento = 'prev' in m3_m2
    cond_m3m3_lastMemento = 'last' in m3_m3

    assert (cond_m1m1_firstMemento and
            cond_m1m2_nextMemento and
            cond_m1m3_lastMemento and
            cond_m2m1_firstPrevMemento and
            cond_m2m2_memento and
            cond_m2m3_lastNextMemento and
            cond_m3m1_firstMemento and
            cond_m3m2_prevMemento and
            cond_m3m3_lastMemento)


def test_mementoRelations_four():
    relsForURIMs = getRelsFromURIMSinWARC('4mementos.warc')

    cond_m1m1_firstMemento = False
    cond_m1m2_nextMemento = False
    cond_m1m3 = False
    cond_m1m4_lastMemento = False
    cond_m2m1_firstPrevMemento = False
    cond_m2m2_memento = False
    cond_m2m3_nextMemento = False
    cond_m2m4_lastMemento = False
    cond_m3m1_firstMemento = False
    cond_m3m2_prevMemento = False
    cond_m3m3_memento = False
    cond_m3m4_lastNextMemento = False
    cond_m4m1_firstMemento = False
    cond_m4m2 = False
    cond_m4m3_prevMemento = False
    cond_m4m4_lastMemento = False

    relsForURIMs1of4 = list(filter(lambda k: 'memento' in k, relsForURIMs[0]))
    relsForURIMs2of4 = list(filter(lambda k: 'memento' in k, relsForURIMs[1]))
    relsForURIMs3of4 = list(filter(lambda k: 'memento' in k, relsForURIMs[2]))
    relsForURIMs4of4 = list(filter(lambda k: 'memento' in k, relsForURIMs[3]))

    # mX_mY = URI-M requested, Y-th URIM-M in header
    m1_m1 = relsForURIMs1of4[0].split(' ')
    m1_m2 = relsForURIMs1of4[1].split(' ')
    # m1_m3 = relsForURIMs1of4[2].split(' ')
    m1_m4 = relsForURIMs1of4[2].split(' ')
    m2_m1 = relsForURIMs2of4[0].split(' ')
    m2_m2 = relsForURIMs2of4[1].split(' ')
    m2_m3 = relsForURIMs2of4[2].split(' ')
    m2_m4 = relsForURIMs2of4[3].split(' ')
    m3_m1 = relsForURIMs3of4[0].split(' ')
    m3_m2 = relsForURIMs3of4[1].split(' ')
    m3_m3 = relsForURIMs3of4[2].split(' ')
    m3_m4 = relsForURIMs3of4[3].split(' ')
    m4_m1 = relsForURIMs4of4[0].split(' ')
    # m4_m2 = relsForURIMs4of4[1].split(' ')
    m4_m3 = relsForURIMs4of4[1].split(' ')
    m4_m4 = relsForURIMs4of4[2].split(' ')

    cond_m1m1_firstMemento = 'first' in m1_m1
    cond_m1m2_nextMemento = 'next' in m1_m2
    # M3 not present
    cond_m1m4_lastMemento = 'last' in m1_m4
    cond_m2m1_firstPrevMemento = 'first' in m2_m1 and 'prev' in m2_m1
    cond_m2m2_memento = len(m2_m2) == 1
    cond_m2m3_nextMemento = 'next' in m2_m3
    cond_m2m4_lastMemento = 'last' in m2_m4
    cond_m3m1_firstMemento = 'first' in m3_m1
    cond_m3m2_prevMemento = 'prev' in m3_m2
    cond_m3m3_memento = len(m3_m3) == 1
    cond_m3m4_lastNextMemento = 'last' in m3_m4 and 'next' in m3_m4
    cond_m4m1_firstMemento = 'first' in m4_m1
    # M2 not present
    cond_m4m3_prevMemento = 'prev' in m4_m3
    cond_m4m4_lastMemento = 'last' in m4_m4

    assert (cond_m1m1_firstMemento and
            cond_m1m2_nextMemento and
            # cond_m1m3 and
            cond_m1m4_lastMemento and
            cond_m2m1_firstPrevMemento and
            cond_m2m2_memento and
            cond_m2m3_nextMemento and
            cond_m2m4_lastMemento and
            cond_m3m1_firstMemento and
            cond_m3m2_prevMemento and
            cond_m3m3_memento and
            cond_m3m4_lastNextMemento and
            cond_m4m1_firstMemento and
            # cond_m4m2 and
            cond_m4m3_prevMemento and
            cond_m4m4_lastMemento)


def test_mementoRelations_five():
    relsForURIMs = getRelsFromURIMSinWARC('5mementos.warc')

    cond_m1m1_firstMemento = False
    cond_m1m2_nextMemento = False
    cond_m1m3 = False
    cond_m1m4 = False
    cond_m1m5_lastMemento = False
    cond_m2m1_firstPrevMemento = False
    cond_m2m2_memento = False
    cond_m2m3_nextMemento = False
    cond_m2m4 = False
    cond_m2m5_lastMemento = False
    cond_m3m1_firstMemento = False
    cond_m3m2_prevMemento = False
    cond_m3m3_memento = False
    cond_m3m4_nextMemento = False
    cond_m3m5_lastMemento = False
    cond_m4m1_firstMemento = False
    cond_m4m2 = False
    cond_m4m3_prevMemento = False
    cond_m4m4_memento = False
    cond_m4m5_lastNextMemento = False
    cond_m5m1_firstMemento = False
    cond_m5m2 = False
    cond_m5m3 = False
    cond_m5m4_prevMemento = False
    cond_m5m5_lastMemento = False

    relsForURIMs1of5 = list(filter(lambda k: 'memento' in k, relsForURIMs[0]))
    relsForURIMs2of5 = list(filter(lambda k: 'memento' in k, relsForURIMs[1]))
    relsForURIMs3of5 = list(filter(lambda k: 'memento' in k, relsForURIMs[2]))
    relsForURIMs4of5 = list(filter(lambda k: 'memento' in k, relsForURIMs[3]))
    relsForURIMs5of5 = list(filter(lambda k: 'memento' in k, relsForURIMs[4]))

    # mX_mY = URI-M requested, Y-th URIM-M in header
    m1_m1 = relsForURIMs1of5[0].split(' ')
    m1_m2 = relsForURIMs1of5[1].split(' ')
    # M3 not present
    # M4 not present
    m1_m5 = relsForURIMs1of5[2].split(' ')
    m2_m1 = relsForURIMs2of5[0].split(' ')
    m2_m2 = relsForURIMs2of5[1].split(' ')
    m2_m3 = relsForURIMs2of5[2].split(' ')
    # M4 not present
    m2_m5 = relsForURIMs2of5[3].split(' ')
    m3_m1 = relsForURIMs3of5[0].split(' ')
    m3_m2 = relsForURIMs3of5[1].split(' ')
    m3_m3 = relsForURIMs3of5[2].split(' ')
    m3_m4 = relsForURIMs3of5[3].split(' ')
    m3_m5 = relsForURIMs3of5[4].split(' ')
    m4_m1 = relsForURIMs4of5[0].split(' ')
    # M2 not present
    m4_m3 = relsForURIMs4of5[1].split(' ')
    m4_m4 = relsForURIMs4of5[2].split(' ')
    m4_m5 = relsForURIMs4of5[3].split(' ')
    m5_m1 = relsForURIMs5of5[0].split(' ')
    # M2 not present
    # M3 not present
    m5_m4 = relsForURIMs5of5[1].split(' ')
    m5_m5 = relsForURIMs5of5[2].split(' ')

    cond_m1m1_firstMemento = 'first' in m1_m1
    cond_m1m2_nextMemento = 'next' in m1_m2
    # M3 not present
    # M4 not present
    cond_m1m5_lastMemento = 'last' in m1_m5
    cond_m2m1_firstPrevMemento = 'first' in m2_m1 and 'prev' in m2_m1
    cond_m2m2_memento = len(m2_m2) == 1
    cond_m2m3_nextMemento = 'next' in m2_m3
    # M4 not present
    cond_m2m5_lastMemento = 'last' in m1_m5
    cond_m3m1_firstMemento = 'first' in m3_m1
    cond_m3m2_prevMemento = 'prev' in m3_m2
    cond_m3m3_memento = len(m3_m3) == 1
    cond_m3m4_nextMemento = 'next' in m3_m4
    cond_m3m5_lastMemento = 'last' in m3_m5
    cond_m4m1_firstMemento = 'first' in m4_m1
    # M2 not present
    cond_m4m3_prevMemento = 'prev' in m4_m3
    cond_m4m4_memento = len(m4_m4) == 1
    cond_m4m5_lastNextMemento = 'last' in m4_m5 and 'next' in m4_m5
    cond_m5m1_firstMemento = 'first' in m4_m1
    # M2 not present
    # M3 not present
    cond_m5m4_prevMemento = 'prev' in m5_m4
    cond_m5m5_lastMemento = 'last' in m5_m5

    assert (cond_m1m1_firstMemento and
            cond_m1m2_nextMemento and
            # cond_m1m3 and
            # cond_m1m4 and
            cond_m1m5_lastMemento and
            cond_m2m1_firstPrevMemento and
            cond_m2m2_memento and
            cond_m2m3_nextMemento and
            # cond_m2m4 and
            cond_m2m5_lastMemento and
            cond_m3m1_firstMemento and
            cond_m3m2_prevMemento and
            cond_m3m3_memento and
            cond_m3m4_nextMemento and
            cond_m3m5_lastMemento and
            cond_m4m1_firstMemento and
            # cond_m4m2 and
            cond_m4m3_prevMemento and
            cond_m4m4_memento and
            cond_m4m5_lastNextMemento and
            cond_m5m1_firstMemento and
            # cond_m5m2 and
            # cond_m5m3 and
            cond_m5m4_prevMemento and
            cond_m5m5_lastMemento)
