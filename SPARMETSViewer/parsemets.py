# -*- coding: utf-8 -*-
"""How to parse a METS file."""

from urllib.parse import urlencode
import datetime
import math
import os
import sys

from flask_babel import gettext
from lxml import etree, objectify
from sqlalchemy.exc import IntegrityError

from SPARMETSViewer import db
from .models import METS


def convert_size(size):
    """convert size to human-readable form"""
    size_name = ("bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size, 1000)))
    divider = math.pow(1000, i)
    rounded_size = round(size / divider)
    string_size = str(rounded_size)
    string_size = string_size.replace('.0', '')
    return '{} {}'.format(string_size, size_name[i])


def add_naan(ark):
    """Add links to known ARKs identifier"""
    if ark.startswith('ark:/12148/cb'):
        myurl = "http://catalogue.bnf.fr/%s" % ark
        return "<a href=\"%s\" target=\"_blank\">%s</a>" % (myurl, ark)
    if ark.startswith('ark:/12148/cc'):
        myurl = "http://archivesetmanuscrits.bnf.fr/%s" % ark
        return "<a href=\"%s\" target=\"_blank\">%s</a>" % (myurl, ark)
    if ark.startswith('ark:/12148/bpt6k') or ark.startswith('ark:/12148/bttv'):
        myurl = "http://gallicaintramuros.bnf.fr/%s" % ark
        return "<a href=\"%s\" target=\"_blank\">%s</a>" % (myurl, ark)
    if ark.startswith('ark:/12148/br2d2'):
        myurl = "http://consultation.spar.bnf.fr/sparql?"
        myparams = {
            'query':
            'SELECT ?s ?p ?o WHERE { GRAPH ?g { <%s> a sparcontext:channel. ?s ?p ?o.}}' % ark
        }
        return "<a href=\"%s\" target=\"_blank\">%s</a>" % (myurl + urlencode(myparams), ark)
    return ark


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
        gettext('Title:'), gettext('Subject:'), gettext('Description:'), gettext('Source:'),
        gettext('Language:'), gettext('Relation:'),
        gettext('Coverage:'), gettext('Creator:'), gettext('Contributor:'), gettext('Publisher:'),
        gettext('Rights:'), gettext('Date:'), gettext('Type:'),
        gettext('Format:'), gettext('Identifier:'),
        gettext('Audience:'), gettext('Provenance:'),
        gettext('Ark Identifier:'), gettext('Production Identifier:'),
        gettext('Version Identifier:'), gettext('Channel Identifier:')
    ]

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
            # div = root.find(
            # 'structMap/div/div[@TYPE="Directory"][@LABEL="objects"]')
            dmdids = div.get('DMDID')
            # No SIP DC
            if dmdids is None:
                return dcmetadata
            dmdids = dmdids.split()
            for dmd in dmds[::-1]:  # Reversed
                if dmd.get('ID') in dmdids:
                    dc_xml = dmd.find('mdWrap/xmlData/spar_dc')
                    # dc_xml = dmd.find('mdWrap/xmlData/dublincore')
                    break
            for elem in dc_xml:
                # Skip XML comments
                if elem.tag is etree.Comment:
                    continue
                dc_type = elem.get('{http://www.w3.org/2001/XMLSchema-instance}type')

                dc_element = dict()
                if dc_type is None:
                    dc_element['element'] = elem.tag
                else:
                    if elem.tag in {'identifier', 'description', 'relation'}:
                        annot = self.strip_prefix(dc_type)
                        if annot == 'ark':
                            dc_element['element'] = elem.tag
                        else:
                            # print("THL DC attrib", elem.tag, dc_type, file=sys.stderr)
                            dc_element['element'] = elem.tag + ' (' + annot + ')'
                    else:
                        dc_element['element'] = elem.tag
                dc_element['value'] = elem.text

                if elem.tag == 'relation':
                    dc_element['value'] = add_naan(elem.text)

                if dc_element['value'] is not None:
                    dcmetadata.append(dc_element)
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

    def parse_element_with_given_xpaths(self, element, data, xpaths):
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
                    data['{}'.format(key)] = add_naan(target[0].text)
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
        # create dict to store data
        premis_event = dict()
        # iterate over elements and write key, value for each to premis_event dictionary
        self.parse_element_with_given_xpaths(element, premis_event, premis_key_values)

        # agents
        agents = element.xpath('./event/linkingAgentIdentifier', namespaces=self.NAMESPACES)
        if agents:
            premis_event['premis_agents'] = []
            for agent in agents:
                my_agent = dict()
                self.parse_element_with_given_xpaths(agent, my_agent, agent_key_values)
                premis_event['premis_agents'].append(my_agent)

        return premis_event

    def parse_file_mix(self, element, file_data):
        """parse mix element related to file"""
        # create dict for names and xpaths of desired elements
        key_values = {
            'mix_dimension': 'concat(./mix//imageHeight/text(), "x", ./mix//imageWidth/text())',
            'mix_height': './mix//imageHeight',
            'mix_width': './mix//imageWidth',
            'mix_bitsPerSample': './mix//bitsPerSampleValue'
        }
        # iterate over elements and write key, value for each to file_data dictionary
        self.parse_element_with_given_xpaths(element, file_data, key_values)
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
            'source': './spar_dc/source'
        }
        # iterate over elements and write key, value for each to file_data dictionary
        self.parse_element_with_given_xpaths(element, file_data, key_values)
        file_data['dc_present'] = 'yes'

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
        file_data['format'] = target.get('MIMETYPE')  # default value

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

        # create human-readable size
        file_data['bytes'] = int(file_data['bytes'])
        file_data['size'] = '0 bytes'  # default to none
        if file_data['bytes'] != 0:
            file_data['size'] = convert_size(file_data['bytes'])

        # create human-readable version of last modified Unix time stamp
        # (if file was characterized by FITS)
        if 'fits_modified_unixtime' in file_data:
            # convert milliseconds to seconds
            unixtime = int(file_data['fits_modified_unixtime'])/1000
            # convert from unix to iso8601
            file_data['modified_ois'] = datetime.datetime.fromtimestamp(unixtime).isoformat()
        else:
            file_data['modified_ois'] = ''

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
                dcmetadata.append(myEvent)
                continue

    def parse_mets(self):
        """
        Parse METS file and save data to METS model
        """
        # create list
        original_files = []
        original_file_count = 0

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

        # gather info for each file"
        for target in mets_root.findall(".//fileGrp/file"):
            original_file_count += 1
            # create new dictionary for this item's info
            file_data = self.extract_file_info(target, mets_root)
            # append file_data to original files
            original_files.append(file_data)

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

        mets_instance = METS(mets_filename, self.nickname,
                             original_files, dc_metadata, original_file_count)
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
