"""Module to interact with the Transkribus API."""

import json
import xmltodict
import requests


def get_session_id(username, password):
    """Get a session ID from the Transkribus API."""

    url = "https://transkribus.eu/TrpServer/rest/auth/login"
    response = requests.post(url, data={"user": username, "pw": password}, timeout=10)

    if response.status_code == 200:
        xml_response = xmltodict.parse(response.text)
        try:
            return xml_response["trpUserLogin"]["sessionId"]
        except KeyError:
            return None
    return None


def start_export(session_id, collection_id):
    """Start an export job for a collection."""

    api_url = "https://transkribus.eu/TrpServer/rest/"
    export_url = f"{api_url}collections/{collection_id}/export"
    params = {
        "format": "PAGE",
    }
    response = requests.post(
        export_url, json=params, cookies={"JSESSIONID": session_id}, timeout=10
    )

    if response.status_code == 200:
        return response.text
    return None


def start_test_export(session_id, collection_id):
    """Start an export job for a test document."""

    api_url = "https://transkribus.eu/TrpServer/rest/"
    export_url = f"{api_url}collections/{collection_id}/export"
    params = {
        "format": "PAGE",
    }
    response = requests.post(
        export_url, json=params, cookies={"JSESSIONID": session_id}, timeout=10
    )

    if response.status_code == 200:
        return response.text
    return None


def get_export_status(session_id, job_id):
    """Get the status of an export job."""

    api_url = "https://transkribus.eu/TrpServer/rest/"
    export_url = f"{api_url}jobs/{job_id}"
    response = requests.get(export_url, cookies={"JSESSIONID": session_id}, timeout=10)

    if response.status_code == 200:
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            return None
    return None
