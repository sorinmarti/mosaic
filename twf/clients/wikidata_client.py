import requests


WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"


def search_wikidata_entities(query, entity_type, language="en", limit=10):
    """
    Search Wikidata for entities of a specific type and language, including coordinates.
    :param query: Search term (e.g., "Berlin").
    :param entity_type: Type of entity (e.g., "City," "Person").
    :param language: Language for the results (default: 'en').
    :param limit: Number of results to return (default: 10).
    :return: List of matching Wikidata entities with optional coordinates.
    """
    params = {
        "action": "wbsearchentities",
        "search": query,
        "language": language,  # Specify the language for labels/descriptions
        "format": "json",
        "limit": limit,
        "type": "item",  # Search for items (not properties or media)
    }

    response = requests.get(WIKIDATA_API_URL, params=params, timeout=10)
    if response.status_code != 200:
        raise ValueError(f"Error: {response.status_code}")

    results = response.json().get("search", [])
    filtered_results = []

    for result in results:
        if is_entity_of_type(result["id"], entity_type):
            entity_data = get_wikidata_entity(result["id"])
            coordinates = get_coordinates(entity_data)

            filtered_results.append(
                {
                    "id": result["id"],
                    "label": result.get("label", ""),  # Label in the specified language
                    "description": result.get(
                        "description", ""
                    ),  # Description in the specified language
                    "coordinates": coordinates,  # Add coordinates if available
                }
            )

    return filtered_results


def is_entity_of_type(entity_id, entity_type):
    """
    Check if an entity belongs to a specific type using P31 ('instance of').
    """
    type_property = {
        "city": [
            "Q1901835",  # Seat of government
            "Q515",  # City
            "Q200250",  # Metropolis
            "Q208511",  # Global city
            "Q174844",  # mega city
            "Q1549591",  # big city
            "Q1422929",  # primate city
            "Q108178728",  # national capital
        ],
        "person": ["Q5", "Q215627"],  # Human or person
        "event": ["Q1656682", "Q1190554"],  # Event or occurrence
        "ship": ["Q11446", "Q11447"],  # Ship or watercraft
        "building": ["Q41176", "Q811979"],  # Building or structure
    }.get(entity_type)

    if not type_property:
        raise ValueError(f"Invalid entity type: {entity_type}")

    # Get entity data
    entity_data = get_wikidata_entity(entity_id)
    claims = entity_data.get("entities", {}).get(entity_id, {}).get("claims", {})

    # Debugging output
    # print(f"Entity Data for {entity_id}: {claims}")

    # Check 'instance of' (P31) property
    instance_of = claims.get("P31", [])
    for claim in instance_of:
        instance_type_id = (
            claim.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
        )
        # print(f"Instance of {entity_id}: {instance_type_id}")
        if instance_type_id in type_property:
            return True

    return False


def get_wikidata_entity(entity_id):
    """Get the data for a Wikidata entity."""
    params = {
        "action": "wbgetentities",
        "ids": entity_id,
        "format": "json",
        "props": "claims",  # Include claims (properties) for the entity
    }

    response = requests.get(WIKIDATA_API_URL, params=params, timeout=10)
    return response.json()


def get_coordinates(entity_data):
    """Get the coordinates for a Wikidata entity."""
    claims = (
        entity_data.get("entities", {})
        .get(list(entity_data["entities"].keys())[0], {})
        .get("claims", {})
    )
    if "P625" in claims:  # P625 = Coordinate location
        coordinates_data = claims["P625"][0]["mainsnak"]["datavalue"]["value"]
        latitude = coordinates_data["latitude"]
        longitude = coordinates_data["longitude"]
        return latitude, longitude
    return None
