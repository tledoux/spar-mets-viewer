# -*- coding: utf-8 -*-
"""How to query with SRU in Unimarc."""

import sys

from lxml import etree
from requests import get, codes


# Dictionnary of XML prefixes and their namespaces
NAMESPACES = {
    'xml': 'http://www.w3.org/XML/1998/namespace',
    'xsd': 'http://www.w3.org/2001/XMLSchema',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    'xlink': 'http://www.w3.org/1999/xlink',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'dcterms': 'http://purl.org/dc/terms/',
    'dctype': 'http://purl.org/dc/dcmitype/',
    'oai_dc': 'http://www.openarchives.org/OAI/2.0/oai_dc/',
    'srw': 'http://www.loc.gov/zing/srw/',
    'ixm': 'http://catalogue.bnf.fr/namespaces/InterXMarc',
    'mxc': 'info:lc/xmlns/marcxchange-v2',
    'mn': 'http://catalogue.bnf.fr/namespaces/motsnotices',
    'sd': 'http://www.loc.gov/zing/srw/diagnostic/',
}


class SRUResponse():
    """
    Class handling a SRU response in UniXMarc
    """

    def __init__(self, record_data, sru):
        self.record_data = record_data
        self.sru = sru

    def xpathfor(self, tag, code):
        prefix = ".//srw:record/srw:recordData/mxc:record/"
        return prefix + "mxc:datafield[@tag='%s']/mxc:subfield[@code='%s']" % (tag, code)

    @property
    def records(self):
        if self.sru.num_records == 0:
            record_data = "<xml></xml>"
        else:
            record_data = self.record_data.xpath("srw:records/srw:record",
                                                 namespaces=NAMESPACES)[0]
        return(SRURecord(record_data, self.sru))

    @property
    def urls(self):
        xpath = self.xpathfor('856', 'u')
        baseurl = 'http://gallica.bnf.fr/'
        result = [r.text.replace(baseurl, '')
                  for r in self.record_data.xpath(xpath, namespaces=NAMESPACES)]
        return result

    @property
    def identifiers(self):
        return [r.text
                for r in self.record_data.xpath(".//srw:record/srw:recordIdentifier",
                                                namespaces=NAMESPACES)]

    @property
    def dates(self):
        xpath = self.xpathfor('210', 'd')
        return [r.text for r in self.record_data.xpath(xpath, namespaces=NAMESPACES)]

    @property
    def callnumbers(self):
        xpath = self.xpathfor('930', 'a')
        return [r.text for r in self.record_data.xpath(xpath, namespaces=NAMESPACES)]

    @property
    def creators(self):
        xpathCreator = ".//srw:recordData/mxc:record/mxc:datafield[@tag='700' or @tag='702']"
        xpathNom = "./mxc:subfield[@code='a']/text()"
        xpathPrenom = "./mxc:subfield[@code='b']/text()"
        xpathDates = "./mxc:subfield[@code='f']/text()"
        xpathFonction = "./mxc:subfield[@code='4']/text()"
        r = []
        for el in self.record_data.xpath(xpathCreator, namespaces=NAMESPACES):
            nom = el.xpath(xpathNom, namespaces=NAMESPACES)
            prenom = el.xpath(xpathPrenom, namespaces=NAMESPACES)
            dates = el.xpath(xpathDates, namespaces=NAMESPACES)
            r.append(", ".join(nom + prenom + dates))
        return r

    @property
    def titles(self):
        xpath = self.xpathfor('200', 'a')
        return [r.text for r in self.record_data.xpath(xpath, namespaces=NAMESPACES)]

    @property
    def publishers(self):
        xpathPublisher = ".//srw:recordData/mxc:record/mxc:datafield[@tag='210']"
        xpathName = "./mxc:subfield[@code='c']/text()"
        xpathLieu = "./mxc:subfield[@code='a']/text()"
        r = []
        for el in self.record_data.xpath(xpathPublisher, namespaces=NAMESPACES):
            name = el.xpath(xpathName, namespaces=NAMESPACES)
            lieu = el.xpath(xpathLieu, namespaces=NAMESPACES)
            r.append(", ".join(name + lieu))
        return r


class SRURecord():
    """ Class for keeping a SRU record"""

    def __init__(self, record_data, sru):
        self.record_data = record_data
        self.sru = sru

    def __iter__(self):
        return self

    def __next__(self):
        if self.sru.num_records == 0:
            raise StopIteration
        if self.sru.startrecord < self.sru.num_records + 1:
            record_data = self.sru.run_query()
            self.sru.startrecord += 1
            return SRUResponse(record_data, self.sru)
        else:
            raise StopIteration

    def next(self):
        return self.__next__()


class SRUUnimarc():
    """ Class to query a SRU endpoint"""

    DEBUG = True

    CATALOG_ENDPOINT = "http://catalogue.bnf.fr/api"

    maximumrecords = 50
    num_records = 0
    query = ""
    recordschema = False
    startrecord = 0

    def __init__(self, kind="catalogue"):
        if kind == "catalogue":
            self.endpoint = self.CATALOG_ENDPOINT
        else:
            raise ValueError(kind)

    def search(self, query, startrecord=1, maximumrecords=1,
               recordschema='unimarcXchange'):
        self.maximumrecords = maximumrecords
        self.query = query
        self.startrecord = startrecord
        self.recordschema = recordschema

        record_data = self.run_query()

        num_records = record_data.xpath(
            "/srw:searchRetrieveResponse/srw:numberOfRecords/text()", namespaces=NAMESPACES)
        if self.DEBUG:
            print("Num records %s" % num_records, file=sys.stderr)
        self.num_records = int(num_records[0])
        if self.num_records > 0:
            return SRUResponse(record_data, self)

        return False

    def run_query(self):
        endpoint = "%s/SRU" % self.endpoint

        if self.DEBUG:
            print('run_query: [%s], query: [%s]' % (endpoint, self.query), file=sys.stderr)

        r = get(
            endpoint,
            params={
                'version': '1.2', 'operation': 'searchRetrieve',
                'startRecord': self.startrecord, 'maximumRecords': self.maximumrecords,
                'recordSchema': self.recordschema, 'query': self.query,
            })

        if not r.status_code == codes.ok:
            raise Exception('Error while getting data from %s' % endpoint)

        record_data = etree.fromstring(r.content)
        return record_data
