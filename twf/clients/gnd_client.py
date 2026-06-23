""" Client for the GND (Gemeinsame Normdatei) authority file. """

import requests
from lxml import etree


def send_gnd_request(query):
    """Send a GND request to the SRU endpoint."""
    base_url = "https://services.dnb.de/sru/authorities"
    query_conditions = ['dnb.mat="persons"', f'dnb.woe="{query}"']

    # Combine query conditions
    query_string = " AND ".join(query_conditions)

    params = {
        "operation": "searchRetrieve",
        "version": "1.1",
        "query": query_string,
        "recordSchema": "RDFxml",
        "maximumRecords": "10",
    }

    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error sending GND request: {e}")
        return None


def parse_gnd_request(response):
    """Parse the GND XML response with improved handling."""
    namespace = {
        "srw": "http://www.loc.gov/zing/srw/",
        "gndo": "https://d-nb.info/standards/elementset/gnd#",
    }
    root = etree.fromstring(response.content)
    results = []

    for record in root.xpath(".//srw:record", namespaces=namespace):
        gnd_id = record.xpath(".//gndo:gndIdentifier/text()", namespaces=namespace)
        preferred_name = record.xpath(
            ".//gndo:preferredNameForThePerson/text()", namespaces=namespace
        )
        variant_names = record.xpath(
            ".//gndo:variantNameForThePerson/text()", namespaces=namespace
        )
        birth_date = record.xpath(".//gndo:dateOfBirth/text()", namespaces=namespace)
        death_date = record.xpath(".//gndo:dateOfDeath/text()", namespaces=namespace)

        # Trim roles to remove unnecessary whitespace
        roles = [
            role.strip()
            for role in record.xpath(
                ".//gndo:professionOrOccupation/text()", namespaces=namespace
            )
            if role.strip()
        ]

        identifiers = record.xpath(".//gndo:externalLink/text()", namespaces=namespace)

        results.append(
            {
                "gnd_id": gnd_id,
                "preferred_name": preferred_name,
                "variant_names": variant_names,
                "birth_date": birth_date,
                "death_date": death_date,
                "roles": roles,
                "identifiers": identifiers,
            }
        )

    return results


def search_gnd(
    query, earliest_birth_year=None, latest_birth_year=None, show_empty=False
):
    """Search GND with additional filtering for birth years."""
    response = send_gnd_request(query)
    if not response:
        return None

    parsed_results = parse_gnd_request(response)

    # Helper function to extract valid birth year
    def extract_year(date_string):
        try:
            if date_string.isdigit():  # Pure year (e.g., "1918")
                return int(date_string)
            elif (
                len(date_string) >= 4 and date_string[:4].isdigit()
            ):  # Full date (e.g., "1918-08-13")
                return int(date_string[:4])
        except ValueError:
            pass
        return None

    # Post-process results to filter by birth year
    filtered_results = []
    for result in parsed_results:
        try:
            birth_date = result["birth_date"][0] if result["birth_date"] else None
            birth_year = extract_year(birth_date) if birth_date else None

            if (
                (
                    not earliest_birth_year
                    or (birth_year and birth_year >= earliest_birth_year)
                )
                and (
                    not latest_birth_year
                    or (birth_year and birth_year <= latest_birth_year)
                )
            ) or show_empty:
                filtered_results.append(result)
        except Exception as e:
            print(f"Error processing result: {result}. Exception: {e}")
            continue

    return filtered_results
