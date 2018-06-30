# -*- coding: utf-8 -*-
"""Manipulation and detection of identifiers."""

from urllib.parse import urlencode
import math
import re

from flask_babel import gettext


SIZE_NAME = (
    gettext("bytes"), gettext("KB"), gettext("MB"), gettext("GB"),
    gettext("TB"), gettext("PB"), gettext("EB"),
    gettext("ZB"), gettext("YB"))


def convert_size(size):
    """convert size to human-readable form"""
    size_name = ("bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size, 1000)))
    divider = math.pow(1000, i)
    rounded_size = round(size / divider)
    string_size = str(rounded_size)
    string_size = string_size.replace('.0', '')
    return '{} {}'.format(string_size, size_name[i])


def abstract_ark(ark):
    """Extract the ark with no qualifiers"""
    ARK_REGEX = re.compile(r'(ark:/\d{5}/[0-9bcdfghjkmnpqrstvwxz]+).*')
    m = ARK_REGEX.match(ark)
    if m is None:
        return m
    return m.group(1)


def extract_date(xml_datetime):
    """Extract the date and time from an XML date time"""
    DT_REGEX = re.compile(r'(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2}).*')
    m = DT_REGEX.match(xml_datetime)
    if m is None:
        return xml_datetime
    return m.group(1) + " " + m.group(2)


def is_uuid(value):
    """Verify if the value can be a uuid"""
    UUID_REGEX = re.compile(r'^[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}$',
                            re.IGNORECASE)
    m = UUID_REGEX.match(value)
    return m is not None


def add_naan(ark):
    """Add links to known ARKs identifier"""

    PREFIX_URL = {
        'ark:/12148/cb': 'http://catalogue.bnf.fr/%s',
        'ark:/12148/cc': 'http://archivesetmanuscrits.bnf.fr/%s',
        'ark:/12148/bpt6k': 'http://gallicaintramuros.bnf.fr/%s',
        'ark:/12148/bttv': 'http://gallicaintramuros.bnf.fr/%s'
    }
    pure_ark = abstract_ark(ark)
    if pure_ark is None:
        return ark
    for prefix, url in PREFIX_URL.items():
        if ark.startswith(prefix):
            full_url = url % pure_ark
            return "<a href=\"%s\" target=\"_blank\">%s</a>" % (full_url, ark)

    if ark.startswith('ark:/12148/br2d2'):
        url = "http://consultation.spar.bnf.fr/sparql?"
        params = {
            'query':
            "SELECT ?s ?p ?o WHERE { GRAPH ?g { "
            "?s a ?kind. ?s ?p ?o. "
            "VALUES ?s { <%s> } "
            "VALUES ?kind { "
            "sparcontext:channel "
            "sparrepresentation:knownFormat sparrepresentation:managedFormat "
            "sparagent:softwareAgent sparagent:sparProcess sparagent:personAgent "
            "} FILTER (!ISBLANK(?o)) } } ORDER BY ?s" % pure_ark
        }
        return "<a href=\"%s\" target=\"_blank\">%s</a>" % (url + urlencode(params), ark)
    return ark
