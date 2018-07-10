# -*- coding: utf-8 -*-
"""Storing of reference data."""

from .rdfquery import simple_query, from_sparql_results_to_json


class Singleton(object):
    def __new__(cls, *args, **kw):
        if not hasattr(cls, '_instance'):
            orig = super(Singleton, cls)
            cls._instance = orig.__new__(cls, *args, **kw)
        return cls._instance


class ReferenceData(Singleton):
    """
    Class for reference data
    """
    KINDS = ["channel", "use", "event"]

    TEST_CHANNELS = [
        {"label": "fil_addn_a", "id": "ark:/12148/br2d2f5z"},
        {"label": "fil_aud_b", "id": "ark:/12148/br2d26qc"},
        {"label": "fil_dl_auto_cia", "id": "ark:/12148/br2d28r1"},
        {"label": "fil_dl_auto_htt", "id": "ark:/12148/br2d28th"},
        {"label": "fil_dl_auto_nas", "id": "ark:/12148/br2d28pj"},
        {"label": "fil_num_cons_a", "id": "ark:/12148/br2d22g"},
        {"label": "fil_num_cons_b", "id": "ark:/12148/br2d2bxn"},
        {"label": "fil_num_cons_c", "id": "ark:/12148/br2d2csw"},
        {"label": "fil_num_cons_d", "id": "ark:/12148/br2d2f10"},
        {"label": "fil_num_cons_e", "id": "ark:/12148/br2d2f27"},
        {"label": "fil_num_cons_f", "id": "ark:/12148/br2d2f8p"},
        {"label": "fil_prod_adm_a", "id": "ark:/12148/br2d2b1c"},
        {"label": "fil_ref_agent", "id": "ark:/12148/br2d230p"},
        {"label": "fil_ref_channel", "id": "ark:/12148/br2d231x"},
        {"label": "fil_ta_cnacgp01", "id": "ark:/12148/br2d290x"},
    ]

    TEST_USES = [
        {"label": "adaptative", "id": "adaptative"},
        {"label": "colorProfile", "id": "colorProfile"},
        {"label": "container", "id": "container"},
        {"label": "dataManagement", "id": "dataManagement"},
        {"label": "documentation", "id": "documentation"},
        {"label": "epub", "id": "epub"},
        {"label": "master", "id": "master"},
        {"label": "ocr", "id": "ocr"},
        {"label": "referenceDocument", "id": "referenceDocument"},
        {"label": "sample", "id": "sample"},
        {"label": "source", "id": "source"},
        {"label": "toc", "id": "toc"},
    ]

    TEST_EVENTS = [
        {"label": "audioCutting", "id": "info:bnf/spar/provenance#audioCutting",
         "title": "Découpage du fichier audio"},
        {"label": "digitization", "id": "info:bnf/spar/provenance#digitization",
         "title": "Numérisation"},
        {"label": "documentReception", "id": "info:bnf/spar/provenance#documentReception",
         "title": "Réception du document"},
        {"label": "ingestCompletion", "id": "info:bnf/spar/provenance#ingestCompletion",
         "title": "Fin du versement"},
    ]

    def __init__(self):
        self.platform = "TEST"
        self.values = {}

    def __str__(self):
        return self.platform + " [" + len(self.values) + "]"

    def set_platform(self, platform):
        self.platform = platform

    def get_data(self, kind):
        if kind not in ReferenceData.KINDS:
            raise ValueError(kind)
        if kind in self.values:
            return self.values[kind]
        self.values[kind] = self.__load(kind)
        return self.values[kind]

    def __load(self, kind):
        if self.platform == "TEST":
            if kind == "channel":
                return ReferenceData.TEST_CHANNELS
            elif kind == "use":
                return ReferenceData.TEST_USES
            elif kind == "event":
                return ReferenceData.TEST_EVENTS
            else:
                raise ValueError(kind)

        if kind == "channel":
            query = """
                SELECT (STRAFTER(STR(?uri), "context/" AS ?label) ?id ?title ?desc WHERE {
                  ?id a sparcontext:channel.
                  ?id owl:sameAs ?uri.
                  ?id dc:title ?title.
                  OPTIONAL { ?id dc:description ?desc. }
                } ORDER BY ?uri LIMIT 100"""
        elif kind == "use":
            query = """
                SELECT DISTINCT (?id AS ?label) ?id WHERE {
                  [] sparrepresentation:isUsedAs ?id.
                } ORDER BY ?id LIMIT 100"""
        elif kind == "event":
            query = """
                SELECT (STRAFTER(STR(?id), "provenance#" AS ?label) ?id ?title ?desc WHERE {
                  ?id rdfs:subClassOf sparprovenance:event.
                  ?id rdfs:label ?title.
                  OPTIONAL { ?id rdfs:comment ?desc. }
                  FILTER (lang(?title) = 'fr')
                  FILTER (lang(?desc) = 'fr')
                } ORDER BY ?id LIMIT 1000"""
        results = simple_query(query)
        return from_sparql_results_to_json(results.json)
