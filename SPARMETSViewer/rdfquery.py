# -*- coding: utf-8 -*-
"""Queries to rdf endpoint."""

import sys
from functools import lru_cache
# from flask import jsonify
from flask_babel import gettext
from requests import get, codes

from SPARMETSViewer import app

from .identifiers import abstract_ark, is_uuid


def __fake_literal_result(value):
    return {
        "head": {"link": [], "vars": ["label"]},
        "results": {
            "distinct": "false", "ordered": "true",
            "bindings": [{"label": {"type": "literal",
                                    "xml:lang": "fr", "value": value}}]}
    }


def __fake_empty_result():
    return {
        "head": {"link": [], "vars": ["label"]},
        "results": {"distinct": "false", "ordered": "true", "bindings": []}
    }


def simple_query(query):
    """Make a SPARQL query to the appropriate platform"""
    # Make a SPARQL query to retrieve the label
    endpoint = app.config['ACCESS_ENDPOINT']
    # app.logger.debug("SPARQL query %s", query)
    response = get(
        endpoint,
        headers={'Accept': 'application/sparql-results+json'},
        params={'query': query, 'format': 'application/sparql-results+json'})
    if response.status_code != codes.ok:
        app.logger.debug("Bad response for query %s", query)
        raise ValueError(response.status_code)
    return response.json()


@lru_cache(maxsize=128)
def label_query(label, platform):
    """Make a SPARQL query to retrieve a label"""
    if platform == "TEST":
        if label == "sparprovenance:digitization":
            return __fake_literal_result("Num\u00E9risation")
        elif label == "sparprovenance:packageCreation":
            return __fake_literal_result("Cr\u00E9ation de paquet")
        elif label == "sparprovenance:digitizationRequests":
            return __fake_literal_result("Demande de num\u00E9risation")
        elif label == "sparprovenance:hasPerformer":
            return __fake_literal_result("ex\u00E9cutant")
        elif label == "ark:/12148/br2d2wf":
            return __fake_literal_result("Format TIFF NB G4")
        elif abstract_ark(label) == "ark:/12148/br2d27h":
            return __fake_literal_result("Processus ING_1")
        elif is_uuid(label):
            return __fake_literal_result("DSC - atelier RES")
        else:
            return __fake_empty_result()

    # Make a SPARQL query to retrieve the label
    label = label.strip()
    ark = abstract_ark(label)
    if ark is not None:
        same = ""
        value = "VALUES ?id { <%s> } " % ark
    elif label.startswith("info:"):
        same = "?id owl:sameAs ?uri. "
        value = "VALUES ?uri { <%s> } " % label
    elif label.startswith("spar"):
        same = ""
        value = "VALUES ?id { %s } " % label
    elif is_uuid(label):
        same = ""
        value = "VALUES ?id { <info:bnf/spar/agent/%s> } " % label
    else:
        return __fake_empty_result()

    query = """
        SELECT ?label WHERE {
          %s
          { ?id rdfs:label ?label }
          UNION { ?id foaf:name ?label }
          UNION { ?id doap:name ?label }
          UNION { ?id dc:title ?label }
          %s
          FILTER (lang(?label) = '%s' or lang(?label) = '')
        } LIMIT 1""" % (same, value, gettext("en"))
    app.logger.debug("SPARQL query %s", query)
    return simple_query(query)


def from_sparql_results_to_json(json, withCounts=False, count=100):
    values = []
    result = {}
    # print("THL from_sparql_results_to_json", json.get("results").get("bindings"), file=sys.stderr)
    if json.get("results") is None or json.get("results").get("bindings") is None:
        if withCounts:
            result['total'] = 0
            result['rows'] = values
            return result
        else:
            return values
    # print("THL from_sparql_results_to_json", file=sys.stderr)
    for binding in json.get("results").get("bindings"):
        dict = {}
        for key, entry in binding.items():
            # print("THL mapping ", key, entry.get("value"), file=sys.stderr)
            dict[key] = entry.get("value")
        values.append(dict)
    # Format the result depending on whether we need total or not
    if withCounts:
        result['total'] = count
        result['rows'] = values
        return result
    else:
        return values
