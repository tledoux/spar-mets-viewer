# -*- coding: utf-8 -*-
"""Storing of reference data."""

from .rdfquery import simple_query, from_sparql_results_to_json


class Singleton(object):
    def __new__(cls, *args, **kw):
        if not hasattr(cls, '_instance'):
            orig = super(Singleton, cls)
            cls._instance = orig.__new__(cls)
        return cls._instance


class ReferenceData(Singleton):
    """
    Class for reference data
    """
    KINDS = [
        "channel", "use", "type", "event",
        "knownFormat", "managedFormat", 
        "identificationTool", "characterizationTool", "validationTool"
    ]

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

    TEST_TYPES = [
        {"label": "harvest data", "id": "harvest data"},
        {"label": "monograph", "id": "monograph"},
        {"label": "multivolume monograph", "id": "multivolume monograph"},
        {"label": "periodical", "id": "periodical"},
        {"label": "web data", "id": "web data"},
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

    TEST_FORMATS = [
        {"label": "jpeg", "id": "ark:/12148/br2",
         "title": "Format JPEG", "desc": "image/jpeg"},
    ]

    TEST_TOOLS = [
        {"label": "jhove_1_5", "id": "ark:/12148/br2",
         "title": "Outil Jhove 1.5"},
        {"label": "jhove_1_18", "id": "ark:/12148/br2",
         "title": "Outil Jhove 1.18"},
    ]

    def __init__(self, platform):
        self.platform = platform
        self.values = {}

    def __str__(self):
        return self.platform + " [" + len(self.values) + "]"

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
            elif kind == "type":
                return ReferenceData.TEST_TYPES
            elif kind == "event":
                return ReferenceData.TEST_EVENTS
            elif kind.endswith("Format"):
                return ReferenceData.TEST_FORMATS
            elif kind.endswith("Tool"):
                return ReferenceData.TEST_TOOLS
            else:
                raise ValueError(kind)

        if kind == "channel":
            query = """
                SELECT (STRAFTER(STR(?uri), 'context/') AS ?label) ?id ?title ?desc WHERE {
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
        elif kind == "type":
            query = """
                SELECT DISTINCT (?id AS ?label) ?id WHERE {
                  [] dc:type ?id.
                } ORDER BY ?id LIMIT 100"""
        elif kind == "event":
            query = """
                SELECT (STRAFTER(STR(?id), 'provenance#') AS ?label) ?id ?title ?desc WHERE {
                  ?id rdfs:subClassOf sparprovenance:event.
                  ?id rdfs:label ?title.
                  OPTIONAL { ?id rdfs:comment ?desc. }
                  FILTER (lang(?title) = 'fr')
                  FILTER (lang(?desc) = 'fr')
                } ORDER BY ?id LIMIT 1000"""
        elif kind.endswith("Format"):
            query = """
                SELECT (STRAFTER(STR(?uri), 'representation/') AS ?label) ?id
                ?title (GROUP_CONCAT(?mime ;separator=", ") AS ?desc)
                WHERE {
                GRAPH ?g {
                  ?id a sparrepresentation:%s.
                  ?id owl:sameAs ?uri.
                  OPTIONAL { ?id rdfs:label ?title. }
                  OPTIONAL { ?id sparrepresentation:hasMimetype ?mime. }
                }} ORDER BY ?uri LIMIT 500""" % kind
        elif kind.endswith("Tool"):
            query = """
                SELECT (STRAFTER(STR(?uri), 'agent/') AS ?label) ?id ?title (SAMPLE(?des) AS ?desc)
                WHERE {
                GRAPH ?g {
                  ?id a sparagent:softwareAgent.
                  ?id a sparrepresentation:%s.
                  ?id owl:sameAs ?uri.
                  OPTIONAL { ?id foaf:name ?title. }
                  OPTIONAL { ?id dc:description ?des. }
                }
                } ORDER BY ?uri LIMIT 500
                """ % kind
        results = simple_query(query)
        return from_sparql_results_to_json(results)
