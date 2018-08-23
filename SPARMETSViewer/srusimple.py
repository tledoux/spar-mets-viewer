# -*- coding: utf-8 -*-
"""How to query with SRU to retrieve a single record."""

import re
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
    'mn': 'http://catalogue.bnf.fr/namespaces/motsnotices',
    'sd': 'http://www.loc.gov/zing/srw/diagnostic/',
}

"""Samples:
https://catalogue.bnf.fr/api/SRU?operation=searchRetrieve&recordSchema=dublincore&startRecord=1&maximumRecords=1&version=1.2&query=%28bib.ark+all+%22ark%3A%2F12148%2Fcb30512802t%22%29
https://gallica.bnf.fr/api/SRU?operation=searchRetrieve&recordSchema=dublincore&startRecord=1&maximumRecords=1&version=1.2&query=%28bib.ark+all+%22ark%3A%2F12148%2Fbpt6k6566369z%22%29
"""


class SRUSimple():
    """ Class to query a SRU endpoint"""

    DEBUG = True

    CATALOG_ENDPOINT = "https://catalogue.bnf.fr/api"
    GALLICA_ENDPOINT = "https://gallica.bnf.fr"
    BAM_ENDPOINT = "https://archivesetmanuscrits.bnf.fr"

    maximumrecords = 1
    num_records = 0
    query = ""
    recordschema = False
    startrecord = 1

    def __init__(self, kind="catalogue"):
        if kind == "catalogue":
            self.endpoint = self.CATALOG_ENDPOINT
        elif kind == "gallica":
            self.endpoint = self.GALLICA_ENDPOINT
        elif kind == "bam":
            self.endpoint = self.BAM_ENDPOINT
        else:
            raise ValueError(kind)

    def strip_prefix(self, value):
        i = value.find(':')
        if i >= 0:
            return value[i+1:]
        else:
            return value

    def no_http(self, url):
        new_url = re.sub(r'https?\://[^/]+/(.+)', r'\1', url)
        return new_url

    def from_oai_to_array(self, dc_xml):
        """parse a oai_dc to extract information. Use a array because tags can be repeated"""
        metadata = []
        if dc_xml is None:
            return metadata
        for elem in dc_xml:
            # Skip XML comments
            if elem.tag is etree.Comment:
                continue
            dc_type = elem.get('{http://www.w3.org/2001/XMLSchema-instance}type')
            dc_lang = elem.get('{http://www.w3.org/XML/1998/namespace}lang')

            dc_element = {}
            if self.DEBUG:
                print("THL DC attrib", elem.tag, dc_type, elem.text, file=sys.stderr)
            el = etree.QName(elem.tag)
            dc_element['element'] = el.localname
            if dc_type is not None:
                annot = self.strip_prefix(dc_type)
                if annot != 'ark':
                    dc_element['qualifier'] = annot

            dc_element['value'] = elem.text
            if dc_element['value'] is None:
                continue

            if dc_element['element'] == 'language' and len(dc_element['value']) != 3:
                continue
            if dc_element['element'] == 'type' and dc_lang != 'fre':
                continue
            if dc_element['element'] == 'rights' and dc_lang != 'fre':
                continue
            if dc_element['element'] == 'identifier' and dc_element['value'].startswith("http"):
                dc_element['value'] = self.no_http(dc_element['value'])

            metadata.append(dc_element)
        return metadata

    def from_dc_array_to_html(self, array):
        """Give a html representation of a dc dictionary"""
        html = ""
        for el in array:
            html += "<strong>%s:</strong> %s<br />" % (el['element'], el['value'])
        return html

    def search(self, query, recordschema='dublincore'):
        self.query = query
        self.recordschema = recordschema

        record_data = self.run_query()

        num_records = record_data.xpath(
            "/srw:searchRetrieveResponse/srw:numberOfRecords/text()", namespaces=NAMESPACES)
        if self.DEBUG:
            print("Num records %s" % num_records, file=sys.stderr)
        self.num_records = int(num_records[0])
        if self.num_records != 1:
            raise ValueError("Not found")
        oai_xpath = "/srw:searchRetrieveResponse/srw:records/srw:record/srw:recordData/oai_dc:dc"
        record = record_data.xpath(oai_xpath, namespaces=NAMESPACES)[0]
        return record

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
