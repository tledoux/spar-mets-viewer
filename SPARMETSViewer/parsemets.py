from SPARMETSViewer import db
from .models import METS

import collections
import datetime
import fnmatch
import math
import os
import sys
from flask_babel import gettext
from lxml import etree, objectify
from urllib.parse import urlencode

def convert_size(size):
    # convert size to human-readable form
    size_name = ("bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size,1000)))
    p = math.pow(1000, i)
    s = round(size/p)
    s = str(s)
    s = s.replace('.0', '')
    return '{} {}'.format(s, size_name[i])

def addNaan(ark):
    if ark.startswith('ark:/12148/c'):
        myurl = "http://catalogue.bnf.fr/%s"%ark
        return "<a href=\"%s\" target=\"_blank\">%s</a>" % (myurl, ark)
    if ark.startswith('ark:/12148/bpt6k') or ark.startswith('ark:/12148/bttv'):
        myurl = "http://gallicaintramuros.bnf.fr/%s"%ark
        return "<a href=\"%s\" target=\"_blank\">%s</a>" % (myurl, ark)
    if ark.startswith('ark:/12148/br2d2'):
        myurl = "http://consultation.spar.bnf.fr/sparql?"
        myparams = { 'query':'SELECT ?s ?p ?o WHERE { GRAPH ?g { <%s> a sparcontext:channel. ?s ?p ?o.}}'%ark }
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
    DC_ELEMENTS = [ gettext('Title:'), gettext('Subject:'), gettext('Description:'), gettext('Source:'), 
        gettext('Language:'), gettext('Relation:'),
        gettext('Coverage:'), gettext('Creator:'), gettext('Contributor:'), gettext('Publisher:'),
        gettext('Rights:'), gettext('Date:'), gettext('Type:'), gettext('Format:'), gettext('Identifier:'), 
        gettext('Audience:'), gettext('Provenance:'),
        gettext('Ark Identifier:'), gettext('Production Identifier:'), gettext('Version Identifier:'), gettext('Channel Identifier:') ]

    def __init_gettext(self, path, dip_id, nickname):
        self.path = os.path.abspath(path)
        self.dip_id = dip_id
        self.nickname = nickname
        self.ark = ''

    def __str__(self):
        return self.path

    def parse_dc(self, root):
        """
        Parse group-level Dublin Core metadata and PREMIS:OBJECT identifiers into dcmetadata dictionary.
        """
        # Parse DC
        dmds = root.xpath('dmdSec/mdWrap[@MDTYPE="DC"]/parent::*')
        dcmetadata = []
        
        # Find which DC to parse
        if len(dmds) > 0:
            # Want most recently updated
            try:
              dmds = sorted(dmds, key=lambda e: e.get('CREATED'))
            except:
              pass
            # Only want SIP DC, not file DC
            div = root.find('structMap[@TYPE="physical"]/div/div[@TYPE="group"]')
            #div = root.find('structMap/div/div[@TYPE="Directory"][@LABEL="objects"]')
            dmdids = div.get('DMDID')
            # No SIP DC
            if dmdids is None:
                return
            dmdids = dmdids.split()
            for dmd in dmds[::-1]:  # Reversed
                if dmd.get('ID') in dmdids:
                    dc_xml = dmd.find('mdWrap/xmlData/spar_dc')
                    #dc_xml = dmd.find('mdWrap/xmlData/dublincore')
                    break
            for elem in dc_xml:
                dc_element = dict()
                dc_element['element'] = elem.tag
                dc_element['value'] = elem.text

                #dc_type = elem.get('{http://www.w3.org/2001/XMLSchema-instance}type')
                if elem.tag == 'relation' :
                  dc_element['value'] = addNaan(elem.text)

                if not dc_element['value'] is None:
                    dcmetadata.append(dc_element)
        #Add identifiers description
        #div = root.find('structMap[@TYPE="physical"]/div/div[@TYPE="group"]')
        #amdids = div.get('ADMID')
        #techMd = root.find('amdSec/techMD/mdWrap[@MDTYPE="PREMIS:OBJECT"]/xmlData/object[@{http://www.w3.org/2001/XMLSchema-instance}type="premis:representation"]')
        techMd = root.find('amdSec/techMD/mdWrap[@MDTYPE="PREMIS:OBJECT"]/xmlData/object')
        if not techMd is None:
            dc_element = dict()
            dc_element['element'] = 'ark identifier'
            self.ark = techMd.find('objectIdentifier[objectIdentifierType="ark"]/objectIdentifierValue').text
            dc_element['value'] = addNaan(self.ark)
            dcmetadata.append(dc_element)
            dc_element2 = dict()
            dc_element2['element'] = 'production Identifier'
            dc_element2['value'] = techMd.find('objectIdentifier[objectIdentifierType="productionIdentifier"]/objectIdentifierValue').text
            dcmetadata.append(dc_element2)
            dc_element3 = dict()
            dc_element3['element'] = 'version identifier'
            dc_element3['value'] = techMd.find('objectIdentifier[objectIdentifierType="versionIdentifier"]/objectIdentifierValue').text
            dcmetadata.append(dc_element3)
            dc_element4 = dict()
            dc_element4['element'] = 'channel identifier'
            dc_element4['value'] = addNaan(techMd.find('relationship[relationshipSubType="channel"]/relatedObjectIdentification/relatedObjectIdentifierValue').text)
            dcmetadata.append(dc_element4)
        else:
            toto = root.find("amdSec/techMD/mdWrap[@MDTYPE='PREMIS:OBJECT']/xmlData/object")
            # print("THL", toto.tag, toto.attrib, file=sys.stderr)

        return dcmetadata

    def parse_element_with_xpath_dictionary(self, element, data, dict):
        """parse an element to extract information according to the given dictionary"""
        for key, value in dict.items():
            #print("THL search ", key, value, file=sys.stderr)
            #target = element.find(value)
            #if key == "xmp_encryption":
            #    target = element.xpath('./RDF//hasSignificantProperties/Bag/li[@premis:hasSignificantPropertiesType="hasEncryption"]', namespaces={'premis': 'http://www.loc.gov/premis/rdf/v1#'})
            #    print("THL elem", target[0].attrib, file=sys.stderr)
            target = element.xpath(value, namespaces = self.NAMESPACES)
            #  namespaces={'premis': 'http://www.loc.gov/premis/rdf/v1#', 'rdf':'http://www.w3.org/1999/02/22-rdf-syntax-ns#'})
            if target is None:
                continue
            #print("THL find", target, file=sys.stderr)
            if isinstance(target, str) and len(target) > 0:
                data['{}'.format(key)] = target
                continue
            if isinstance(target, list) and len(target) > 0:
                #print("THL find", target[0], type(target[0]), file=sys.stderr)
                if isinstance(target[0], etree._Element):
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
            'arkFormat': './object/objectCharacteristics/format/formatRegistry/formatRegistryKey', 
            }
        # iterate over elements and write key, value for each to premis_event dictionary
        self.parse_element_with_xpath_dictionary(element, file_data, xml_file_elements)

    def parse_file_premis_event(self, element):
        """parse premis events related to file"""
        # create dict for names and xpaths of desired elements
        premis_key_values = {
            'event_uuid': './event/eventIdentifier/eventIdentifierValue', 
            'event_type': './event/eventType', 
            'event_datetime': './event/eventDateTime', 
            'event_detail': './event/eventDetail', 
            'event_outcome': './event/eventOutcomeInformation/eventOutcome', 
            'event_detail_note': './event/eventOutcomeInformation/eventOutcomeDetail/eventOutcomeDetailNote'
        }
        # create dict to store data
        premis_event = dict()
        # iterate over elements and write key, value for each to premis_event dictionary
        self.parse_element_with_xpath_dictionary(element, premis_event, premis_key_values)
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
        # iterate over elements and write key, value for each to premis_event dictionary
        self.parse_element_with_xpath_dictionary(element, file_data, key_values)
        file_data['mix_present'] = 'yes'

    def parse_file_textmd(self, element, file_data):
        """parse textmd element related to file"""
        # create dict for names and xpaths of desired elements
        key_values = {
            'textmd_charset': './textMD/character_info/charset',
            'textmd_markup_basis': './textMD/markup_basis',
            'textmd_markup_language': './textMD/markup_language'
        }
        # iterate over elements and write key, value for each to premis_event dictionary
        self.parse_element_with_xpath_dictionary(element, file_data, key_values)
        file_data['textmd_present'] = 'yes'

    def parse_file_xmp(self, element, file_data):
        """parse xmp element related to file"""
        # create dict for names and xpaths of desired elements
        key_values = {
            'xmp_encryption': './RDF//hasSignificantProperties/Bag/li[@premis:hasSignificantPropertiesType="hasEncryption"]/@premis:hasSignificantPropertiesValue',
            'xmp_agent_validation': './RDF//hasEventRelatedAgent[./hasAgentType/@rdf:resource="http://id.loc.gov/vocabulary/preservation/agentType/sof"]/hasAgentName'
        }
        # iterate over elements and write key, value for each to premis_event dictionary
        self.parse_element_with_xpath_dictionary(element, file_data, key_values)
        file_data['xmp_present'] = 'yes'

    def parse_file_containermd(self, element, file_data):
        """parse containerMD element related to file"""
        # create dict for names and xpaths of desired elements
        key_values = {
            'containermd_entries_number': './containerMD//entriesInformation/@number'
        }
        # iterate over elements and write key, value for each to premis_event dictionary
        self.parse_element_with_xpath_dictionary(element, file_data, key_values)
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
        # iterate over elements and write key, value for each to premis_event dictionary
        self.parse_element_with_xpath_dictionary(element, file_data, key_values)
        file_data['mpeg7_present'] = 'yes'

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
        tree = etree.parse(self.path)
        root = tree.getroot()

        for elem in root.getiterator():
            if not hasattr(elem.tag, 'find'): continue  # (1)
            i = elem.tag.find('}')
            if i >= 0:
                elem.tag = elem.tag[i+1:]
        objectify.deannotate(root, cleanup_namespaces=True)

        # build xml document root
        mets_root = root

        # gather info for each file"
        for target in mets_root.findall(".//fileGrp/file"):

            original_file_count += 1

            # create new dictionary for this item's info
            file_data = dict()
            # Add information from the file
            file_data['use'] = target.find('..').get('USE')
            file_data['filepath'] = target.find('FLocat').get('{http://www.w3.org/1999/xlink}href')
            file_data['hashtype'] = target.attrib['CHECKSUMTYPE']
            file_data['hashvalue'] = target.attrib['CHECKSUM']
            file_data['bytes'] = target.attrib['SIZE']

            # create new list of dicts for premis events in file_data
            file_data['premis_events'] = list()

            # gather amdsec id from filesec
            amdsec_ids = target.attrib['ADMID']
            file_data['amdsec_id'] = amdsec_ids
            for amdsec_id in amdsec_ids.split(" "):
              # parse amdSec 
              amdsec_xpath = ".//amdSec/*[@ID='{}']".format(amdsec_id)
              # Only one section per ID
              section = mets_root.find(amdsec_xpath)
              # is it a PREMIS:OBJECT section
              premisObject = section.find("./mdWrap[@MDTYPE='PREMIS:OBJECT']/xmlData")
              if not premisObject is None:
                  self.parse_file_premis_object(premisObject, file_data)
                  continue
              # parse premis events related to file
              premisEvent = section.find("./mdWrap[@MDTYPE='PREMIS:EVENT']/xmlData")
              if not premisEvent is None:
                  file_data['premis_events'].append(self.parse_file_premis_event(premisEvent))
                  continue
              # parse mix related to file
              mix = section.find("./mdWrap[@MDTYPE='NISOIMG']/xmlData")
              if not mix is None:
                  self.parse_file_mix(mix, file_data)
                  #file_data['mix_rawoutput'] = etree.tostring(mix, pretty_print=True)
                  continue
              # parse textMD related to file
              textmd = section.find("./mdWrap[@MDTYPE='TEXTMD']/xmlData")
              if not textmd is None:
                  self.parse_file_textmd(textmd, file_data)
                  #file_data['textmd_rawoutput'] = etree.tostring(textmd, pretty_print=True)
                  continue
              # parse mpeg7 related to file
              mpeg7 = section.find("./mdWrap[@OTHERMDTYPE='MPEG7']/xmlData")
              if not mpeg7 is None:
                  self.parse_file_mpeg7(mpeg7, file_data)
                  continue
              # parse containerMD related to file
              containermd = section.find("./mdWrap[@OTHERMDTYPE='containerMD']/xmlData")
              if not containermd is None:
                  self.parse_file_containermd(containermd, file_data)
                  continue
              # parse XMP related to file
              xmp = section.find("./mdWrap[@OTHERMDTYPE='XMP']/xmlData")
              if not xmp is None:
                  self.parse_file_xmp(xmp, file_data)

            # create human-readable size
            file_data['bytes'] = int(file_data['bytes'])
            file_data['size'] = '0 bytes' # default to none
            if file_data['bytes'] != 0:
                file_data['size'] = convert_size(file_data['bytes'])

            # create human-readable version of last modified Unix time stamp (if file was characterized by FITS)
            if 'fits_modified_unixtime' in file_data:
                unixtime = int(file_data['fits_modified_unixtime'])/1000 # convert milliseconds to seconds
                file_data['modified_ois'] = datetime.datetime.fromtimestamp(unixtime).isoformat() # convert from unix to iso8601
            else:
                file_data['modified_ois'] = ''

            # append file_data to original files
            original_files.append(file_data)

        # gather dublin core metadata from most recent dmdSec
        dc_metadata = self.parse_dc(root)

        # add file info to database
        if self.nickname is None or len(self.nickname) == 0 :
          self.nickname = self.ark
        else:
          self.nickname += " - " + self.ark

        mets_instance = METS(mets_filename, self.nickname, original_files, dc_metadata, original_file_count)
        db.session.add(mets_instance)
        db.session.commit()
