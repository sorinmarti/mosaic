""" This module contains functions to search for locations using the GeoNames API"""

from geopy.geocoders import GeoNames
from fuzzywuzzy import fuzz


def search_location(
    query, geonames_username, exactly_one=False, country=None, threshold=80
):
    """Search for a location using the GeoNames API
    :param query: the location query
    :param geonames_username: the GeoNames username
    :param exactly_one: return only one location
    :param country: the country code
    :param threshold: the similarity threshold
    :return: a list of clean locations
    """
    geolocator = GeoNames(username=geonames_username)

    location = geolocator.geocode(query, exactly_one=exactly_one, country=country)
    if location:
        if isinstance(location, list):
            clean_locations = clean_location(location, query, threshold)
            return clean_locations

        clean_locations = clean_location(
            [
                location,
            ],
            query,
            threshold,
        )
        return clean_locations

    return None


def clean_location(locations, original_query, threshold=80):
    """Clean the locations based on the similarity ratio with the original query
    :param locations: a list of locations
    :param original_query: the original search query
    :param threshold: the similarity threshold
    :return: a list of clean locations
    """

    clean_locations = []
    for location in locations:
        similarity_ratio = fuzz.ratio(location.raw["name"], original_query)
        if similarity_ratio > int(threshold):
            c_location = {
                "id": location.raw.get("geonameId", "Error getting Id"),
                "name": location.raw.get("name", "Error getting name"),
                "country": location.raw.get("countryName", ""),
                "lat": location.latitude,
                "lng": location.longitude,
            }
            clean_locations.append((c_location, similarity_ratio))
    return clean_locations
