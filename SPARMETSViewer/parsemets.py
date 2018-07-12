# -*- coding: utf-8 -*-
"""How to parse a METS file."""

import json
import os
import sys

from flask_babel import gettext
from lxml import etree, objectify
from sqlalchemy.exc import IntegrityError

from SPARMETSViewer import db
from .models import METS
from .identifiers import convert_size, extract_date, add_naan


class METSFile(object):
    """
    Class for METS file parsing methods
    """

    # Dictionnary of XML prefixes and their namespaces
    NAMESPACES = {
        'xml': 'http://www.w3.org/XML/1998/namespace',
        'xsd': 'http://www.w3.org/2001/XMLSchema',
        'xlink': 'http://www.w3.org/1999/xlink',
        'dc': 'http://purl.org/dc/elements/1.1/',
        'dcterms': 'http://purl.org/dc/terms/',
        'dctype': 'http://purl.org/dc/dcmitype/',
        'spar_dc': 'http://bibnum.bnf.fr/ns/spar_dc',
        'mets': 'http://www.loc.gov/METS/',
        'premis': 'info:lc/xmlns/premis-v2',
        'textMD': 'info:lc/xmlns/textMD-v3',
        'mix': 'http://www.loc.gov/mix/v10',
        'mpeg7': 'urn:mpeg:mpeg7:schema:2004',
        'containerMD': 'http://bibnum.bnf.fr/ns/containerMD-v1',
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'harvestInfo': 'http://netarchive.dk/schema/harvestInfo',
        'detailsOp': 'http://bibnum.bnf.fr/ns/detailsOperation'
    }
    # Array of Dublic Elements to be translated
    DC_ELEMENTS = [
        gettext('title'), gettext('subject'), gettext('description'), gettext('source'),
        gettext('language'), gettext('relation'),
        gettext('coverage'), gettext('creator'), gettext('contributor'), gettext('publisher'),
        gettext('rights'), gettext('date'), gettext('type'),
        gettext('format'), gettext('identifier'),
        gettext('audience'), gettext('provenance'),
        gettext('Ark Identifier'), gettext('Production Identifier'),
        gettext('Version Identifier'), gettext('Channel Identifier')
    ]
    # Array of div level to be translated
    DIV_LEVEL = [
        gettext('structMap'), gettext('set'), gettext('group'), gettext('object'),
        gettext('file')
    ]
    # Compression decoder (MIX 6.1.3.1 Compression scheme value labels.)
    MIX_COMPRESSION = {
        "1": "uncompressed", "2": "CCITT 1D",
        "3": "CCITT Group 3", "4": "CCITT Group 4",
        "5": "LZW", "6": "JPEG", "7": "ISO JPEG", "8": "Deflate",
        "32661": "JBIG", "32766": "NEXT",
        "32771": "RLE with word alignment",
        "32773": "PackBits", "32774": "NeXT 2-bit encoding", "32775": "ThunderScan 4-bit encoding",
        "32895": "RasterPadding in CT or MP",
        "32896": "RLE for LW", "32897": "RLE for HC", "32898": "RLE for BL",
        "32908": "Pixar 10-bit LZW", "32909": "Pixar companded 11-bit ZIP encoding",
        "32946": "PKZIP-style Deflate encoding",
        "32947": "Kodak DCS",
        "34676": "SGI 32-bit Log Luminance encoding",
        "34677": "SGI 24-bit Log Luminance encoding",
        "34712": "JPEG 2000"
    }

    def __init__(self, path, dip_id, nickname):
        self.path = os.path.abspath(path)
        self.dip_id = dip_id
        self.nickname = nickname
        self.ark = ''

    def __str__(self):
        return self.path

    def strip_prefix(self, value):
        i = value.find(':')
        if i >= 0:
            return value[i+1:]
        else:
            return value

    def parse_dc(self, root):
        """
        Parse group-level Dublin Core metadata and PREMIS:OBJECT identifiers into
        dcmetadata array.
        """
        # Parse DC
        dmds = root.xpath('dmdSec/mdWrap[@MDTYPE="DC"]/parent::*')
        dcmetadata = []

        # Find which DC to parse
        if dmds:
            # Want most recently updated
            try:
                dmds = sorted(dmds, key=lambda e: e.get('CREATED'))
            except:
                pass
            # Only want SIP DC, not file DC
            div = root.find(
                'structMap[@TYPE="physical"]/div/div[@TYPE="group"]')
            dmdids = div.get('DMDID')
            # No SIP DC
            if dmdids is None:
                return dcmetadata
            dmdids = dmdids.split()
            for dmd in dmds[::-1]:  # Reversed
                if dmd.get('ID') in dmdids:
                    dc_xml = dmd.find('mdWrap/xmlData/spar_dc')
                    break
            dcmetadata = self.parse_spardc(dc_xml)
        # Add identifiers description
        techmd = root.find('amdSec/techMD/mdWrap[@MDTYPE="PREMIS:OBJECT"]/xmlData/object')
        premis_identifiers = {
            'ark identifier':
                'objectIdentifier[objectIdentifierType="ark"]/objectIdentifierValue',
            'production Identifier':
                'objectIdentifier[objectIdentifierType="productionIdentifier"]/'
                'objectIdentifierValue',
            'version identifier':
                'objectIdentifier[objectIdentifierType="versionIdentifier"]/objectIdentifierValue',
            'channel identifier':
                'relationship[relationshipSubType="channel"]/relatedObjectIdentification/'
                'relatedObjectIdentifierValue'
        }
        if techmd is not None:
            for key, value in premis_identifiers.items():
                # print("THL identifiers", key, file=sys.stderr)
                dc_element = dict()
                dc_element['element'] = key
                value = techmd.find(value).text
                if value:
                    if key == 'ark identifier':
                        self.ark = value
                    dc_element['value'] = add_naan(value)
                    dcmetadata.append(dc_element)
        else:
            # Try with the mets header
            header = root.find('metsHdr')
            if header is not None:
                production_identifier = header.xpath(
                    "concat(./altRecordID[@TYPE='producerIdentifier']/text(), "
                    "'_', ./altRecordID[@TYPE='productionIdentifier']/text())")
                dc_element = dict()
                dc_element['element'] = 'production Identifier'
                dc_element['value'] = production_identifier
                dcmetadata.append(dc_element)

        return dcmetadata

    def parse_spardc(self, dc_xml):
        """parse a spardc to extract information"""
        metadata = []
        if dc_xml is None:
            return metadata
        for elem in dc_xml:
            # Skip XML comments
            if elem.tag is etree.Comment:
                continue
            dc_type = elem.get('{http://www.w3.org/2001/XMLSchema-instance}type')

            dc_element = dict()
            # print("THL DC attrib", elem.tag, dc_type, elem.text, file=sys.stderr)
            dc_element['element'] = elem.tag
            if dc_type is not None:
                annot = self.strip_prefix(dc_type)
                if annot != 'ark':
                    dc_element['qualifier'] = annot

            if elem.tag == 'relation':
                dc_element['value'] = add_naan(elem.text)
            else:
                dc_element['value'] = elem.text

            if dc_element['value'] is not None:
                metadata.append(dc_element)
        return metadata

    def parse_element_with_given_xpaths(self, element, data, xpaths, with_naan=True):
        """parse an element to extract information according to the given dictionary"""
        for key, value in xpaths.items():
            target = element.xpath(value, namespaces=self.NAMESPACES)
            if target is None:
                continue
            # print("THL find", target, file=sys.stderr)
            if target and isinstance(target, str):
                data['{}'.format(key)] = target
                continue
            if target and isinstance(target, list):
                if isinstance(target[0], etree._Element):
                    if with_naan:
                        data['{}'.format(key)] = add_naan(target[0].text)
                    else:
                        data['{}'.format(key)] = target[0].text
                else:
                    data['{}'.format(key)] = target[0]

    def parse_file_premis_object(self, element, file_data):
        """parse premis object related to file"""
        # create dict for names and xpaths of desired info from individual files
        xml_file_elements = {
            'id': './object/objectIdentifier/objectIdentifierValue',
            'format': './object/objectCharacteristics/format/formatDesignation/formatName',
            'version': './object/objectCharacteristics/format/formatDesignation/formatVersion',
            'arkFormat': './object/objectCharacteristics/format/formatRegistry/formatRegistryKey'
        }
        # iterate over elements and write key, value for each to file_data dictionary
        self.parse_element_with_given_xpaths(element, file_data, xml_file_elements)

    def find_agent(self, my_agent, mets_root):
        """find the agent refered by its UUID"""
        agent_desc_key_values = {
            'agent_name': './agentName',
            'agent_kind': './agentType',
            'agent_note': './agentNote'
        }
        uuid = my_agent['agent_value']
        xpath_agent = "/mets/amdSec/digiprovMD/mdWrap/xmlData/"\
            "agent[./agentIdentifier/agentIdentifierValue='%s']" % uuid
        # print("THL xpath_agent ", xpath_agent, file=sys.stderr)
        agent_desc = mets_root.xpath(xpath_agent, namespaces=self.NAMESPACES)
        if not agent_desc:
            return
        # print("THL agent ", uuid, " agent desc=", agent_desc[0], file=sys.stderr)
        self.parse_element_with_given_xpaths(
                    agent_desc[0], my_agent, agent_desc_key_values, with_naan=False)

    def parse_premis_event(self, element):
        """parse a premis event"""
        # create dict for names and xpaths of desired elements
        premis_key_values = {
            'event_uuid': './event/eventIdentifier/eventIdentifierValue',
            'event_type': './event/eventType',
            'event_datetime': './event/eventDateTime',
            'event_detail': './event/eventDetail',
            'event_outcome': './event/eventOutcomeInformation/eventOutcome',
            'event_detail_note':
                './event/eventOutcomeInformation/eventOutcomeDetail/eventOutcomeDetailNote'
        }
        agent_key_values = {
            'agent_type': './linkingAgentIdentifierType',
            'agent_value': './linkingAgentIdentifierValue',
            'agent_role': './linkingAgentRole'
        }
        object_key_values = {
            'object_type': './linkingObjectIdentifierType',
            'object_value': './linkingObjectIdentifierValue',
            'object_role': './linkingObjectRole'
        }
        # create dict to store data
        premis_event = dict()
        # iterate over elements and write key, value for each to premis_event dictionary
        self.parse_element_with_given_xpaths(
            element, premis_event, premis_key_values, with_naan=False)
        # TODO iterate on eventOutcomeInformation

        # agents
        agents = element.xpath('./event/linkingAgentIdentifier', namespaces=self.NAMESPACES)
        if agents:
            premis_event['premis_agents'] = []
            for agent in agents:
                my_agent = dict()
                self.parse_element_with_given_xpaths(
                    agent, my_agent, agent_key_values, with_naan=True)
                if my_agent['agent_type'] == 'UUID':
                    self.find_agent(my_agent, element)
                premis_event['premis_agents'].append(my_agent)

        # objects
        link_objects = element.xpath('./event/linkingObjectIdentifier', namespaces=self.NAMESPACES)
        if link_objects:
            premis_event['premis_objects'] = []
            for link_object in link_objects:
                my_object = dict()
                self.parse_element_with_given_xpaths(
                    link_object, my_object, object_key_values, with_naan=True)
                if my_object.get('object_role') is None:
                    my_object['object_role'] = 'object'
                premis_event['premis_objects'].append(my_object)

        # Calculate a human readable date
        premis_event['event_date'] = extract_date(premis_event['event_datetime'])

        return premis_event

    def parse_file_mix(self, element, file_data):
        """parse mix element related to file"""
        # create dict for names and xpaths of desired elements
        key_values = {
            'mix_dimension': 'concat(./mix//imageHeight/text(), "x", ./mix//imageWidth/text())',
            'mix_height': './mix//imageHeight',
            'mix_width': './mix//imageWidth',
            'mix_bitsPerSample': './mix//bitsPerSampleValue',
            'mix_compression': './mix//compressionScheme',
            'mix_compression_ratio': './mix//compressionRatio',
            'mix_icc_profile': './mix//iccProfileName'
        }
        # iterate over elements and write key, value for each to file_data dictionary
        self.parse_element_with_given_xpaths(element, file_data, key_values)
        if 'mix_compression' in file_data:
            compressionScheme = file_data['mix_compression']
            if compressionScheme.isdigit():
                file_data['mix_compression'] = self.MIX_COMPRESSION[compressionScheme]
        file_data['mix_present'] = 'yes'

    def parse_file_textmd(self, element, file_data):
        """parse textmd element related to file"""
        # create dict for names and xpaths of desired elements
        key_values = {
            'textmd_charset': './textMD/character_info/charset',
            'textmd_markup_basis': './textMD/markup_basis',
            'textmd_markup_language': './textMD/markup_language'
        }
        # iterate over elements and write key, value for each to file_data dictionary
        self.parse_element_with_given_xpaths(element, file_data, key_values)
        file_data['textmd_present'] = 'yes'

    def parse_file_xmp(self, element, file_data):
        """parse xmp element related to file"""
        # create dict for names and xpaths of desired elements
        key_values = {
            'xmp_encryption':
                './RDF//hasSignificantProperties/Bag/'
                'li[@premis:hasSignificantPropertiesType="hasEncryption"]/'
                '@premis:hasSignificantPropertiesValue',
            'xmp_agent_validation':
                './RDF//hasEventRelatedAgent[./hasAgentType/'
                '@rdf:resource="http://id.loc.gov/vocabulary/preservation/agentType/sof"]/'
                'hasAgentName'
        }
        # iterate over elements and write key, value for each to file_data dictionary
        self.parse_element_with_given_xpaths(element, file_data, key_values)
        file_data['xmp_present'] = 'yes'

    def parse_file_containermd(self, element, file_data):
        """parse containerMD element related to file"""
        # create dict for names and xpaths of desired elements
        key_values = {
            'containermd_entries_number': './containerMD//entriesInformation/@number'
        }
        # iterate over elements and write key, value for each to file_data dictionary
        self.parse_element_with_given_xpaths(element, file_data, key_values)
        file_data['containermd_present'] = 'yes'

    def parse_file_mpeg7(self, element, file_data):
        """parse mpeg7 element related to file"""
        # create dict for names and xpaths of desired elements
        key_values = {
            'mpeg7_mediaformat': './Mpeg7//MediaFormat/Content/Name',
            'mpeg7_audio_format': './Mpeg7//AudioCoding/Format/Name',
            'mpeg7_audio_samplerate': './Mpeg7//AudioCoding/Sample/@rate',
            'mpeg7_video_format': './Mpeg7//VideoCoding/Format/Name',
            'mpeg7_video_samplerate': './Mpeg7//VideoCoding/Sample/@rate',
            'mpeg7_duration': './Mpeg7//MediaDuration',
        }
        # iterate over elements and write key, value for each to file_data dictionary
        self.parse_element_with_given_xpaths(element, file_data, key_values)
        file_data['mpeg7_present'] = 'yes'

    def parse_file_dc(self, element, file_data):
        """parse spardc element related to file"""
        # create dict for names and xpaths of desired elements
        key_values = {
            'title': './spar_dc/title',
            'description': './spar_dc/description',
            'source': './spar_dc/source',
            'identifier': './spar_dc/identifier'
        }
        # iterate over elements and write key, value for each to file_data dictionary
        self.parse_element_with_given_xpaths(element, file_data, key_values)
        file_data['dc_present'] = 'yes'

    def extract_object_info(self, target, mets_root):
        """extract information about the object in target"""
        # create new dictionary for this item's info
        object_data = {}
        # Add information from the object
        object_data['id'] = target.attrib['ID']
        if 'ORDERLABEL' in target.attrib:
            label = target.attrib.get('ORDERLABEL')
            if label is not None and label != 'NP':
                # print("THL object ", object_data['id'], " orderLabel=", label, file=sys.stderr)
                object_data['orderlabel'] = label
        if 'LABEL' in target.attrib:
            object_data['label'] = target.attrib['LABEL']
        object_data['order'] = target.attrib['ORDER']
        # gather the linked files
        fids = target.findall('./fptr')
        object_data['files'] = []
        for fid in fids:
            if 'FILEID' in fid.attrib:
                object_data['files'].append(fid.attrib['FILEID'])
            else:
                for area in fid.findall('.//area'):
                    sep = area.find('..').tag
                    area_order = area.attrib['ORDER']
                    fileid = area.attrib['FILEID']
                    object_data['files'].append(sep + area_order + '/' + fileid)

        # gather dmdsec id from div object
        dmdsec_ids = target.attrib.get('DMDID')
        if dmdsec_ids is not None:
            for dmdsec_id in dmdsec_ids.split(" "):
                # parse dmdSec
                dmdsec_xpath = ".//dmdSec[@ID='{}']".format(dmdsec_id)
                # Only one section per ID
                section = mets_root.find(dmdsec_xpath)
                if section is None:
                    continue
                dc_xml = section.find('mdWrap/xmlData/spar_dc')
                spardc = self.parse_spardc(dc_xml)
                object_data['dcmetadata'] = spardc
                for elt in spardc:
                    # print("THL see ", elt['element'], "=", elt['value'], file=sys.stderr)
                    if elt['element'] == 'title':
                        object_data['title'] = elt['value']
                    elif elt['element'] == 'description':
                        object_data['description'] = elt['value']
                break
        amdsec_ids = target.attrib.get('ADMID')
        if amdsec_ids is not None:
            object_data['premis_events'] = []
            for amdsec_id in amdsec_ids.split(" "):
                # parse amdSec
                amdsec_xpath = ".//amdSec/*[@ID='{}']".format(amdsec_id)
                # Only one section per ID
                section = mets_root.find(amdsec_xpath)
                if section is None:
                    continue
                # parse premis events related to file
                premis_event = section.find("./mdWrap[@MDTYPE='PREMIS:EVENT']/xmlData")
                if premis_event is not None:
                    object_data['premis_events'].append(self.parse_premis_event(premis_event))
                    continue
            # Sort the premis events by datetime
            object_data['premis_events'].sort(key=lambda event: event["event_datetime"])

        return object_data

    def extract_div_info(self, target, mets_root):
        """extract information about the structMap in target"""
        div_data = {}
        # Add information about the structmap
        div_data['level'] = target.tag
        div_data['type'] = target.attrib['TYPE']
        # Handle the SET level
        set_data = {}
        set_element = target.find('./div[@TYPE="set"]')
        set_data['level'] = set_element.attrib['TYPE']
        # gather dmdsec id from div set
        dmdsec_ids = set_element.attrib.get('DMDID')
        if dmdsec_ids is not None:
            for dmdsec_id in dmdsec_ids.split(" "):
                # parse dmdSec
                dmdsec_xpath = ".//dmdSec[@ID='{}']".format(dmdsec_id)
                # Only one section per ID
                section = mets_root.find(dmdsec_xpath)
                if section is None:
                    continue
                dc_xml = section.find('mdWrap/xmlData/spar_dc')
                if dc_xml is not None:
                    spardc = self.parse_spardc(dc_xml)
                    set_data['dcmetadata'] = spardc
                    for elt in spardc:
                        if elt['element'] == 'title':
                            set_data['title'] = elt['value']
                        elif elt['element'] == 'description':
                            set_data['description'] = elt['value']
                else:
                    dc_xml = section.find('mdRef')
                    if dc_xml is not None:
                        set_data['dcmetadata'] = []
                        elt = {}
                        elt['element'] = 'relation'
                        elt['value'] = add_naan(dc_xml.get('{http://www.w3.org/1999/xlink}href'))
                        set_data['dcmetadata'].append(elt)
        div_data['child'] = set_data

        # Handle the GROUP level
        group_data = {}
        group_element = set_element.find('.//div[@TYPE="group"]')
        group_data['level'] = group_element.attrib['TYPE']
        set_data['child'] = group_data
        # Handle the objects
        objects_element = group_element.findall('./div[@TYPE="object"]')
        objects_data = []
        for object_element in objects_element:
            object_data = self.extract_object_info(object_element, mets_root)
            object_data['level'] = object_element.attrib['TYPE']
            objects_data.append(object_data)
        group_data['objects'] = objects_data
        return div_data

    def extract_file_info(self, target, mets_root):
        """extract information about the file in target"""
        # create new dictionary for this item's info
        file_data = dict()
        # Add information from the file
        file_data['id'] = target.attrib['ID']  # default value
        file_data['use'] = target.find('..').get('USE')
        file_data['filepath'] = target.find('FLocat').get('{http://www.w3.org/1999/xlink}href')
        file_data['hashtype'] = target.attrib['CHECKSUMTYPE']
        file_data['hashvalue'] = target.attrib['CHECKSUM']
        file_data['bytes'] = target.get('SIZE', '0')
        file_data['format'] = target.get('MIMETYPE', '')  # default value

        # create new list of dicts for premis events in file_data
        file_data['premis_events'] = list()

        # gather amdsec id from filesec
        amdsec_ids = target.get('ADMID', '')
        file_data['amdsec_id'] = amdsec_ids
        for amdsec_id in amdsec_ids.split(" "):
            # parse amdSec
            amdsec_xpath = ".//amdSec/*[@ID='{}']".format(amdsec_id)
            # Only one section per ID
            section = mets_root.find(amdsec_xpath)
            if section is None:
                continue
            # is it a PREMIS:OBJECT section
            premis_object = section.find("./mdWrap[@MDTYPE='PREMIS:OBJECT']/xmlData")
            if premis_object is not None:
                self.parse_file_premis_object(premis_object, file_data)
                continue
            # is it a sourceMD section
            sourcemd = section.find("./mdWrap[@MDTYPE='DC']/xmlData")
            if sourcemd is not None:
                self.parse_file_dc(sourcemd, file_data)
                continue
            # parse premis events related to file
            premis_event = section.find("./mdWrap[@MDTYPE='PREMIS:EVENT']/xmlData")
            if premis_event is not None:
                file_data['premis_events'].append(self.parse_premis_event(premis_event))
                continue
            # parse mix related to file
            mix = section.find("./mdWrap[@MDTYPE='NISOIMG']/xmlData")
            if mix is not None:
                self.parse_file_mix(mix, file_data)
                # file_data['mix_rawoutput'] = etree.tostring(mix, pretty_print=True)
                continue
            # parse textMD related to file
            textmd = section.find("./mdWrap[@MDTYPE='TEXTMD']/xmlData")
            if textmd is not None:
                self.parse_file_textmd(textmd, file_data)
                # file_data['textmd_rawoutput'] = etree.tostring(textmd, pretty_print=True)
                continue
            # parse mpeg7 related to file
            mpeg7 = section.find("./mdWrap[@OTHERMDTYPE='MPEG7']/xmlData")
            if mpeg7 is not None:
                self.parse_file_mpeg7(mpeg7, file_data)
                continue
            # parse containerMD related to file
            containermd = section.find("./mdWrap[@OTHERMDTYPE='containerMD']/xmlData")
            if containermd is not None:
                self.parse_file_containermd(containermd, file_data)
                continue
            # parse XMP related to file
            xmp = section.find("./mdWrap[@OTHERMDTYPE='XMP']/xmlData")
            if xmp is not None:
                self.parse_file_xmp(xmp, file_data)

        # Sort the premis events by datetime
        file_data['premis_events'].sort(key=lambda event: event["event_datetime"])

        # create human-readable size
        file_data['bytes'] = int(file_data['bytes'])
        file_data['size'] = '0 bytes'  # default to none
        if file_data['bytes'] != 0:
            file_data['size'] = convert_size(file_data['bytes'])

        # gather dmdsec id from filesec
        dmdsec_ids = target.get('DMDID', '')
        file_data['dmdsec_id'] = dmdsec_ids
        for dmdsec_id in dmdsec_ids.split(" "):
            # parse dmdSec
            dmdsec_xpath = ".//dmdSec[@ID='{}']".format(dmdsec_id)
            # Only one section per ID
            section = mets_root.find(dmdsec_xpath)
            if section is None:
                continue
            # parse DC related to file
            dc = section.find("./mdWrap[@MDTYPE='DC']/xmlData")
            if dc is not None:
                self.parse_file_dc(dc, file_data)

        # Return the build dictionnary
        return file_data

    def extract_group_event(self, mets_root, dcmetadata):
        """
        Extract premis events related to the group level
        """
        div = mets_root.find(
            'structMap[@TYPE="physical"]/div/div[@TYPE="group"]')
        if div is None:
            return

        amdsec_ids = div.get('ADMID', '')
        events = []
        for amdsec_id in amdsec_ids.split(" "):
            # parse amdSec
            amdsec_xpath = ".//amdSec/*[@ID='{}']".format(amdsec_id)
            # Only one section per ID
            section = mets_root.find(amdsec_xpath)
            if section is None:
                continue
            # parse premis events related to group
            premis_event = section.find("./mdWrap[@MDTYPE='PREMIS:EVENT']/xmlData")
            if premis_event is not None:
                myEvent = self.parse_premis_event(premis_event)
                myEvent['event'] = 'premis'
                events.append(myEvent)
                continue
        events.sort(key=lambda event: event["event_datetime"])
        for event in events:
            dcmetadata.append(event)

    def parse_mets(self):
        """
        Parse METS file and save data to METS model
        """
        # create list
        original_files = []
        original_file_count = 0
        divs = []
        principal_level = 'group'

        # get METS file name
        mets_filename = os.path.basename(self.path)

        # open xml file and strip namespaces
        # TODO: use namespaces everywhere...
        tree = etree.parse(self.path)
        root = tree.getroot()

        for elem in root.getiterator():
            if not hasattr(elem.tag, 'find'):
                continue
            i = elem.tag.find('}')
            if i >= 0:
                # strip the namespace...
                elem.tag = elem.tag[i+1:]
        objectify.deannotate(root, cleanup_namespaces=True, xsi=False)

        # build xml document root
        mets_root = root

        # gather info for each file
        for target in mets_root.findall(".//fileGrp/file"):
            original_file_count += 1
            # create new dictionary for this item's info
            file_data = self.extract_file_info(target, mets_root)
            # append file_data to original files
            original_files.append(file_data)

        # gather info for each structmap
        for target in mets_root.findall(".//structMap"):
            div = self.extract_div_info(target, mets_root)
            divs.append(div)

        # gather dublin core metadata from most recent dmdSec
        dc_metadata = self.parse_dc(root)
        # gather event at the group level
        self.extract_group_event(root, dc_metadata)

        # add file info to database
        if not self.ark:
            self.ark = mets_filename
        if self.nickname is None or not self.nickname:
            self.nickname = self.ark
        else:
            self.nickname += " - " + self.ark

        # print("THL JSON ", json.dumps(dc_metadata, sort_keys=True, indent=2), file=sys.stderr)
        mets_instance = METS(mets_filename, self.nickname, principal_level,
                             original_files, dc_metadata, divs, original_file_count)
        isSuccess = True
        try:
            db.session.add(mets_instance)
            db.session.flush()
        except IntegrityError:
            isSuccess = False
            db.session.rollback()
        else:
            db.session.commit()
        return isSuccess
