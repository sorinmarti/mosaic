""" Utility functions to parse date strings. """

import re
import dateparser
from datetime import datetime

YEAR = "year"
MONTH = "month"
DAY = "day"

month_abbreviations = {
    "1": ["jan", "januar", "january", "janvier", "gennaio"],
    "2": ["feb", "februar", "february", "février", "febbraio"],
    "3": ["mar", "märz", "march", "mars", "marzo"],
    "4": ["apr", "april", "avril", "aprile"],
    "5": ["may", "mai", "maggio"],
    "6": ["jun", "juni", "june", "juin", "giugno"],
    "7": ["jul", "juli", "july", "juillet", "luglio"],
    "8": ["aug", "august", "août", "agosto"],
    "9": ["sep", "september", "septembre", "settembre"],
    "10": ["oct", "okt", "oktober", "october", "octobre", "ottobre"],
    "11": ["nov", "november", "novembre"],
    "12": ["dec", "dez", "december", "décembre", "dicembre"],
}


def parse_date_string(date_string, resolve_to="day", date_format="DMY"):
    """Parse the date string using dateparser and return the date in EDTF format."""

    parsed_date = parse_year_only(date_string, resolve_to)

    if not parsed_date:
        parsed_date = parse_month_year(date_string, resolve_to)

    if not parsed_date:
        parsed_date = parse_with_dateparser(date_string, resolve_to, date_format)

    return parsed_date


def parse_year_only(date_string, resolve_to):
    """Parse the date string if it only contains a year."""

    # Check if the date string contains only a year
    date_string = date_string.strip()
    if re.match(r"^\d{4}$", date_string):
        # If it's only a year, return first day of the year
        if resolve_to == YEAR:
            return date_string
        elif resolve_to == MONTH:
            return date_string + "-XX"
        elif resolve_to == DAY:
            return date_string + "-XX-XX"
    return None


def parse_month_year(date_string, resolve_to):
    """Parse the date string if it contains a month and a year."""
    regex = r"^([\w\.éèû]*) (\d{4})$"
    match = re.match(regex, date_string)
    if match:
        month = match.group(1)
        year = match.group(2)

        # Check if the month is an abbreviation
        for month_number, abbreviations in month_abbreviations.items():
            if month.lower() in abbreviations:
                if resolve_to == YEAR:
                    return year
                elif resolve_to == MONTH:
                    return f"{year}-{month_number}"
                elif resolve_to == DAY:
                    return f"{year}-{month_number}-XX"

    return None


def parse_with_dateparser(date_string, resolve_to, date_format):
    """Parse the date string using dateparser."""

    settings = {
        "PREFER_DAY_OF_MONTH": "first",  # If day is missing, assume first
        "PREFER_DATES_FROM": "past",  # Choose dates from past by default
        "RELATIVE_BASE": datetime.now(),  # To parse relative dates like 'today'
        "STRICT_PARSING": True,  # Avoid parsing incomplete dates unless valid
    }

    if date_format == "DMY":
        settings["DATE_ORDER"] = "DMY"
    elif date_format == "MDY":
        settings["DATE_ORDER"] = "MDY"

    parsed_date = dateparser.parse(date_string, settings=settings)

    if parsed_date:
        if resolve_to == YEAR:
            return parsed_date.strftime("%Y")
        elif resolve_to == MONTH:
            return parsed_date.strftime("%Y-%m")
        elif resolve_to == DAY:
            return parsed_date.strftime("%Y-%m-%d")

    return None
