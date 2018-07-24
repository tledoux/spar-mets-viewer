# -*- coding: utf-8 -*-
"""How to query with SRU."""

import json
import sys

from lxml import etree
from requests import get, codes
# from urllib.parse import quote

# from .identifiers import convert_size, extract_date, add_naan


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
    'mn': 'http://catalogue.bnf.fr/namespaces/motsnotices',
    'sd': 'http://www.loc.gov/zing/srw/diagnostic/',
}


class SRUResponse():
    """
    Class handling a SRU response
    """

    def __init__(self, record_data, sru):
        self.record_data = record_data
        self.sru = sru

    @property
    def records(self):
        if self.sru.num_records == 0:
            record_data = "<xml></xml>"
        else:
            record_data = self.record_data.xpath("srw:records/srw:record",
                                                 namespaces=NAMESPACES)[0]
        return(SRURecord(record_data, self.sru))

    # TODO: distinguish by xsi:type
    @property
    def identifiers(self):
        baseurl = 'http://catalogue.bnf.fr/'
        result = [r.text.replace(baseurl, '') for r in self.record_data.iter() if
                  r.tag.endswith('identifier') and r.text.find(':') > -1]
        return result

    @property
    def types(self):
        # dc_type = elem.get('{http://www.w3.org/2001/XMLSchema-instance}type')
        return [r.text for r in self.record_data.iter() if
                r.tag.endswith('type')
                and 'fre' == r.get('{http://www.w3.org/XML/1998/namespace}lang')]

    @property
    def languages(self):
        return [r.text for r in self.record_data.iter() if
                r.tag.endswith('language')]

    @property
    def dates(self):
        return [r.text for r in self.record_data.iter() if
                r.tag.endswith('date')]

    @property
    def extents(self):
        return [r.text for r in self.record_data.iter() if
                r.tag.endswith('extent')]

    @property
    def creators(self):
        return [r.text for r in self.record_data.iter() if
                r.tag.endswith('creator')]

    @property
    def contributors(self):
        return [r.text for r in self.record_data.iter() if
                r.tag.endswith('contributor')]

    # TODO: distinguish by xsi:type and xml:lang
    @property
    def subjects(self):
        return [r.text for r in self.record_data.iter() if
                r.tag.endswith('subject')]

    @property
    def titles(self):
        return [r.text for r in self.record_data.iter() if
                r.tag.endswith('title')]

    @property
    def publishers(self):
        return [r.text for r in self.record_data.iter() if
                r.tag.endswith('publisher')]

    # Following properties occur in GGC

    @property
    def annotations(self):
        return [r.text for r in self.record_data.iter() if
                r.tag.endswith('annotation')]


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


class SRU():
    """ Class to query a SRU endpoint"""

    DEBUG = True

    CATALOG_ENDPOINT = "http://catalogue.bnf.fr/api"
    GALLICA_ENDPOINT = "https://gallica.bnf.fr"

    maximumrecords = 50
    num_records = 0
    query = ""
    recordschema = False
    startrecord = 0

    def __init__(self, kind="catalogue"):
        if kind == "catalogue":
            self.endpoint = self.CATALOG_ENDPOINT
        elif kind == "gallica":
            self.endpoint = self.GALLICA_ENDPOINT
        else:
            raise ValueError(kind)

    def search(self, query, startrecord=1, maximumrecords=1,
               recordschema='dublincore'):
        self.maximumrecords = maximumrecords
        self.query = query
        self.startrecord = startrecord
        self.recordschema = recordschema

        record_data = self.run_query()

        num_records = record_data.xpath(
            "/srw:searchRetrieveResponse/srw:numberOfRecords/text()", namespaces=NAMESPACES)
        # num_records = [i.text for i in record_data.iter() if
        #                 i.tag.endswith('numberOfRecords')][0]
        print("Num records %s" % num_records, file=sys.stderr)
        self.num_records = int(num_records[0])
        if self.num_records > 0:
            return SRUResponse(record_data, self)

        return False

    def run_query(self):
        endpoint = "%s/SRU" % self.endpoint

        if self.DEBUG:
            print('run_query: [%s], query: [%s]' % (endpoint, self.query), file=sys.stderr)

        #    headers={'Accept': 'application/sparql-results+json'},
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
