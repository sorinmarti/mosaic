from django.test import TestCase
from unittest.mock import patch

from lxml import etree

from twf.clients.gnd_client import send_gnd_request, parse_gnd_request, search_gnd
import requests


class GNDClientTests(TestCase):
    """Tests for the GND client functionality."""

    @patch("twf.clients.gnd_client.requests.get")
    def test_send_gnd_request_success(self, mock_get):
        """Test sending a GND request and receiving a valid response."""
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response._content = b"<root><test>response</test></root>"
        mock_get.return_value = mock_response

        response = send_gnd_request("test_query")
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)
        mock_get.assert_called_once_with(
            "https://services.dnb.de/sru/authorities",
            params={
                "operation": "searchRetrieve",
                "version": "1.1",
                "query": 'dnb.mat="persons" AND dnb.woe="test_query"',
                "recordSchema": "RDFxml",
                "maximumRecords": "10",
            },
            timeout=10,
        )

    @patch("twf.clients.gnd_client.requests.get")
    def test_send_gnd_request_failure(self, mock_get):
        """Test sending a GND request when an exception occurs."""
        mock_get.side_effect = requests.exceptions.RequestException
        response = send_gnd_request("test_query")
        self.assertIsNone(response)

    def test_parse_gnd_request_success(self):
        """Test parsing a valid GND response."""
        valid_xml = """
        <root xmlns:srw="http://www.loc.gov/zing/srw/"
              xmlns:gndo="https://d-nb.info/standards/elementset/gnd#">
          <srw:record>
            <gndo:gndIdentifier>12345</gndo:gndIdentifier>
            <gndo:preferredNameForThePerson>John Doe</gndo:preferredNameForThePerson>
            <gndo:variantNameForThePerson>J. Doe</gndo:variantNameForThePerson>
          </srw:record>
        </root>
        """
        response = requests.Response()
        response._content = valid_xml.encode()
        response.status_code = 200

        results = parse_gnd_request(response)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], ["12345"])
        self.assertEqual(results[0][1], ["John Doe"])
        self.assertEqual(results[0][2], ["J. Doe"])

    def test_parse_gnd_request_invalid(self):
        """Test parsing an invalid GND response."""
        invalid_xml = "<root><invalid>/invalid></rot>"
        response = requests.Response()
        response._content = invalid_xml.encode()
        response.status_code = 200

        with self.assertRaises(etree.XMLSyntaxError):
            parse_gnd_request(response)

    def test_parse_gnd_request_missing_elements(self):
        """Test parsing a GND response with missing required elements."""
        incomplete_xml = """
        <root xmlns:srw="http://www.loc.gov/zing/srw/"
              xmlns:gndo="https://d-nb.info/standards/elementset/gnd#">
          <srw:record>
            <gndo:gndIdentifier>12345</gndo:gndIdentifier>
          </srw:record>
        </root>
        """  # Missing preferredNameForThePerson or variantNameForThePerson

        response = requests.Response()
        response._content = incomplete_xml.encode()
        response.status_code = 200

        results = parse_gnd_request(response)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], ["12345"])  # Identifier exists
        self.assertEqual(results[0][1], [])  # No preferredNameForThePerson
        self.assertEqual(results[0][2], [])  # No variantNameForThePerson

    @patch("twf.clients.gnd_client.send_gnd_request")
    def test_search_gnd_success(self, mock_send_request):
        """Test searching GND with a successful response."""
        mock_response = requests.Response()
        mock_response._content = b"""
        <root xmlns:srw="http://www.loc.gov/zing/srw/"
              xmlns:gndo="https://d-nb.info/standards/elementset/gnd#">
          <srw:record>
            <gndo:gndIdentifier>12345</gndo:gndIdentifier>
            <gndo:preferredNameForThePerson>John Doe</gndo:preferredNameForThePerson>
            <gndo:variantNameForThePerson>J. Doe</gndo:variantNameForThePerson>
          </srw:record>
        </root>
        """
        mock_response.status_code = 200
        mock_send_request.return_value = mock_response

        results = search_gnd("test_query")
        self.assertIsNotNone(results)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], ["12345"])
        self.assertEqual(results[0][1], ["John Doe"])
        self.assertEqual(results[0][2], ["J. Doe"])

    @patch("twf.clients.gnd_client.send_gnd_request")
    def test_search_gnd_failure(self, mock_send_request):
        """Test searching GND when the request fails."""
        mock_send_request.return_value = None
        results = search_gnd("test_query")
        self.assertIsNone(results)
