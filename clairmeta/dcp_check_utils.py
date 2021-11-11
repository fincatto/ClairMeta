# Clairmeta - (C) YMAGIS S.A.
# See LICENSE for more information

import six
import re
from datetime import datetime
from dateutil import parser

from clairmeta.logger import get_log
from clairmeta.utils.uuid import check_uuid
from clairmeta.utils.xml import validate_xml
from clairmeta.settings import DCP_SETTINGS


def get_schema(name):
    for k, v in six.iteritems(DCP_SETTINGS['xmlns']):
        if name == k or name == v:
            return v


def check_xml_constraints(xml_path):
    """ Check D-Cinema XML Contraints

        References:
            TI Subtitle Operational Recommendation for DLP Cinema Projectors (Draft A)
            https://web.archive.org/web/20140924153620/http://dlp.com/downloads/pdf_dlp_cinema_subtitle_operational_recommendation_rev_a.pdf
            SMPTE ST 429-17:2017
            W3C Extensible Markup Language v (1.0)
    """

    # Follow the XML spec precicely for the definition of XMLDecl, except for:
    # VersionNum := '1.0'
    # EncName    := 'UTF-8'
    # EncodingDecl not optional
    # SDDecl must have 'no'
    RE_XML_S             = '([\x20\x09\x0D\x0A])'
    RE_XML_Eq            = '(' + RE_XML_S + '?=' + RE_XML_S + '?)'
    RE_XML_SDDecl        = '(' + RE_XML_S + 'standalone' + RE_XML_Eq + '(\'no\'|"no"))'
    RE_XML_EncName       = '(UTF\-8)'
    RE_XML_EncodingDecl  = '(' + RE_XML_S + 'encoding' + RE_XML_Eq + '("' + RE_XML_EncName + '"|\'' + RE_XML_EncName + '\'))'
    RE_XML_VersionNum    = '(1\.0)'
    RE_XML_VersionInfo   = '(' + RE_XML_S + 'version' + RE_XML_Eq + '(\'' + RE_XML_VersionNum + '\'|"' + RE_XML_VersionNum + '"))'
    RE_XML_XMLDecl       = '<\?xml' + RE_XML_VersionInfo + RE_XML_EncodingDecl + RE_XML_SDDecl + '?' + RE_XML_S + '?' + '\?>'

    try:
        with open(xml_path) as file:
            xml_file = file.read()
    except IOError as e:
        get_log().info("Error opening XML file {} : {}".format(xml_path, str(e)))
        return

    errors = []

    if re.match('\ufeff', xml_file):
        errors.append("BOM not allowed in XML file")

    if not (re.match(RE_XML_XMLDecl, xml_file) or re.match('\ufeff' + RE_XML_XMLDecl, xml_file)):
        errors.append("Invalid XML Declaration")

    if xml_file[-2:] != '>\n' and xml_file[-3:] != '>\r\n':
        errors.append("XML file has invalid ending")

    if errors:
        raise CheckException('\n'.join(errors))


def check_xml(checker, xml_path, xml_ns, schema_type, schema_dcp):
    check_xml_constraints(xml_path)

    # Correct namespace
    schema_id = get_schema(xml_ns)
    if not schema_id:
        checker.error("Namespace unknown : {}".format(xml_ns), "namespace")

    # Coherence with package schema
    if schema_type != schema_dcp:
        message = "Schema is not valid got {} but was expecting {}".format(
            schema_type, schema_dcp)
        checker.error(message, "schema_coherence")

    # XSD schema validation
    try:
        validate_xml(xml_path, schema_id)
    except LookupError as e:
        get_log().info("Schema validation skipped : {}".format(xml_path))
    except Exception as e:
        message = (
            "Schema validation error : {}\n"
            "Using schema : {}".format(str(e), schema_id))
        checker.error(message, "schema_validation")


def check_issuedate(checker, date):
    # As a reminder, date should be already correctly formatted as checked
    # by XSD validation.
    parse_date = parser.parse(date)
    now_date = datetime.now().replace(tzinfo=parse_date.tzinfo)

    if parse_date > now_date:
        checker.error("IssueDate is post dated : {}".format(parse_date))


def compare_uuid(checker, uuid_to_check, uuid_reference):
    name, uuid = uuid_to_check
    name_ref, uuid_ref = uuid_reference

    if not check_uuid(uuid):
        checker.error("Invalid {} uuid found : {}".format(name, uuid))
    if uuid.lower() != uuid_ref.lower():
        checker.error("Uuid {} ({}) not equal to {} ({})".format(
            name, uuid, name_ref, uuid_ref))
