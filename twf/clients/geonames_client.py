"""Functions to search and fetch locations using the GeoNames API."""

import requests

GEONAMES_SEARCH_URL = "http://api.geonames.org/searchJSON"
GEONAMES_GET_URL = "http://api.geonames.org/getJSON"

FEATURE_CLASSES = {
    "A": "Administrative division",
    "H": "Hydrographic (rivers, lakes…)",
    "L": "Landscape",
    "P": "Populated place",
    "R": "Road / railroad",
    "S": "Spot, building, farm",
    "T": "Mountain, hill, rock",
    "U": "Undersea",
    "V": "Vegetation",
}


def _parse_place(place):
    """Extract the fields we care about from a raw GeoNames place dict."""
    return {
        "id": place.get("geonameId", ""),
        "name": place.get("name", ""),
        "ascii_name": place.get("asciiName", ""),
        "country": place.get("countryName", ""),
        "country_code": place.get("countryCode", ""),
        "admin1": place.get("adminName1", ""),
        "lat": place.get("lat", ""),
        "lng": place.get("lng", ""),
        "fcode": place.get("fcode", ""),
        "fcode_name": place.get("fcodeName", ""),
        "fcl": place.get("fcl", ""),
        "fcl_name": FEATURE_CLASSES.get(place.get("fcl", ""), place.get("fcl", "")),
        "population": place.get("population", 0),
    }


def search_location(
    query,
    geonames_username,
    exactly_one=False,
    country_bias=None,
    country=None,
    feature_class=None,
    max_rows=15,
):
    """Search GeoNames by name/query string.

    Parameters
    ----------
    query : str
        Search term (any language / transliteration — GeoNames searches alternate names).
    geonames_username : str
        GeoNames account username.
    exactly_one : bool
        Return only the first result.
    country_bias : str or None
        ISO-3166 two-letter code to rank results from this country first.
    country : str or None
        Restrict results to this country only.
    feature_class : str or None
        One of A, H, L, P, R, S, T, U, V.
    max_rows : int
        Maximum number of results to return.

    Returns
    -------
    list of dict
        Each dict has id, name, country, lat, lng, fcode, fcode_name, fcl, fcl_name, etc.
        Returns an empty list if nothing found.
    """
    params = {
        "q": query,
        "maxRows": 1 if exactly_one else max_rows,
        "username": geonames_username,
        "type": "json",
        "style": "FULL",
    }
    if country_bias:
        params["countryBias"] = country_bias
    if country:
        params["country"] = country
    if feature_class:
        params["featureClass"] = feature_class

    try:
        resp = requests.get(GEONAMES_SEARCH_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"GeoNames API error: {exc}") from exc

    if "status" in data:
        raise RuntimeError(data["status"].get("message", "GeoNames error"))

    places = data.get("geonames", [])
    results = [_parse_place(p) for p in places]

    if exactly_one:
        return results[0] if results else None
    return results


def lookup_by_id(geoname_id, geonames_username):
    """Fetch a single GeoNames entry by its numeric ID.

    Parameters
    ----------
    geoname_id : int or str
        The GeoNames ID.
    geonames_username : str
        GeoNames account username.

    Returns
    -------
    dict or None
        Parsed place dict, or None if not found.
    """
    params = {
        "geonameId": geoname_id,
        "username": geonames_username,
        "style": "FULL",
    }
    try:
        resp = requests.get(GEONAMES_GET_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"GeoNames API error: {exc}") from exc

    if "status" in data:
        raise RuntimeError(data["status"].get("message", "GeoNames error"))

    return _parse_place(data)