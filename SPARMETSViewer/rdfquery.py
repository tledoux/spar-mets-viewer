# -*- coding: utf-8 -*-
"""Queries to rdf endpoint."""

from functools import lru_cache
from flask import jsonify
from flask_babel import gettext
from requests import get  # to make GET request

from SPARMETSViewer import app

from .identifiers import abstract_ark, is_uuid


def _fake_literal_result(value):
    return jsonify(
        {"head": {"link": [], "vars": ["label"]},
         "results": {
            "distinct": "false", "ordered": "true",
            "bindings": [{"label": {"type": "literal",
                                    "xml:lang": "fr", "value": value}}]}})


def _fake_empty_result():
    return jsonify(
        {"head": {"link": [], "vars": ["label"]},
         "results": {"distinct": "false", "ordered": "true", "bindings": []}})


@lru_cache(maxsize=128)
def label_query(label, platform):
    """Make a SPARQL query to retrieve a label"""
    if platform == "TEST":
        if label == "sparprovenance:digitization":
            return _fake_literal_result("Num\u00E9risation")
        elif label == "sparprovenance:packageCreation":
            return _fake_literal_result("Cr\u00E9ation de paquet")
        elif label == "sparprovenance:hasPerformer":
            return _fake_literal_result("ex\u00E9cutant")
        elif label == "ark:/12148/br2d2wf":
            return _fake_literal_result("Format TIFF NB G4")
        elif abstract_ark(label) == "ark:/12148/br2d27h":
            return _fake_literal_result("Processus ING_1")
        elif is_uuid(label):
            return _fake_literal_result("DSC - atelier RES")
        else:
            return _fake_empty_result()

    # Make a SPARQL query to retrieve the label
    endpoint = app.config['ACCESS_ENDPOINT']
    label = label.strip()
    ark = abstract_ark(label)
    if ark is not None:
        same = ""
        value = "VALUES ?id { <%s> } " % ark
    elif label.startswith("info:"):
        same = "?id owl:sameAs ?uri. "
        value = "VALUES ?uri { <%s> } " % label
    elif label.startswith("spar:"):
        same = ""
        value = "VALUES ?id { %s } " % label
    elif is_uuid(label):
        same = ""
        value = "VALUES ?id { sparagent:%s } " % label
    else:
        return _fake_empty_result()

    query = """
        SELECT ?label WHERE {
          %s
          { ?id rdfs:label ?label }
          UNION { ?id foaf:name ?label }
          UNION { ?id dc:title ?label }
          %s
          FILTER (lang(?label) = '%s' or lang(?label) = '')
        } LIMIT 1""" % (same, value, gettext("en"))
    app.logger.debug("SPARQL query %s", query)
    response = get(
        endpoint,
        headers={'Accept': 'application/sparql-results+json'},
        params={'query': query, 'format': 'application/sparql-results+json'})
    return response.content
