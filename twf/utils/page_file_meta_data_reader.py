""" This module provides a function to extract
    metadata from a Transkribus XML file. """

import xml.etree.ElementTree as ETree


def extract_transkribus_file_metadata(file_path):
    """Extract metadata from a Transkribus XML file.

    Args:
        file_path (str): The path to the Transkribus XML file.

    Returns:
        dict: A dictionary containing the metadata.
    """
    namespace = {
        "page": "http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15"
    }

    try:
        xml_tree = ETree.parse(file_path)
    except ETree.ParseError as error:
        raise error

    if "http://" in str(xml_tree.getroot().tag.split("}")[0].strip("{")):
        xmlns = xml_tree.getroot().tag.split("}")[0].strip("{")
    else:
        try:
            ns = xml_tree.getroot().attrib
            xmlns = str(ns).split(" ")[1].strip("}").strip("'")
        except IndexError:
            xmlns = ""

    if xmlns not in namespace.values():
        return {"error": "Namespace not found in the file."}

    result = {}
    metadata_block = xml_tree.find(".//{%s}Metadata" % xmlns)
    tk_metadata_block = metadata_block.find("{%s}TranskribusMetadata" % xmlns)
    if tk_metadata_block is not None:
        for t_property in tk_metadata_block.iterfind(".//{%s}Property" % xmlns):
            key = t_property.attrib.get("key")
            value = t_property.attrib.get("value")
            result[key] = value
        for attrib in tk_metadata_block.attrib:
            result[attrib] = tk_metadata_block.attrib[attrib]
    else:
        return {"error": "TranskribusMetadata block not found in the file."}

    return result
