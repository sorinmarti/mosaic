""" Test cases for the flatten_dict_keys function in create_export_utils.py."""

from django.test import TestCase

from twf.utils.create_export_utils import flatten_dict_keys


class FlattenDictKeysTest(TestCase):
    """Test case for the flatten_dict_keys function."""

    def setUp(self):
        # Example inputs for testing
        self.simple_dict = {"outer": {"inner1": "", "inner2": ""}}

        self.dict_with_list = {
            "outer": {
                "inner1": "",
                "inner2": [
                    {"ex1": "value1", "ex2": "value2"},
                    {"ex1": "value3", "ex2": "value4"},
                ],
            }
        }

    def test_simple_dict(self):
        """
        Test that flatten_dict_keys works for a simple nested dictionary.
        """
        expected_output = ["outer.inner1", "outer.inner2"]
        result = flatten_dict_keys(self.simple_dict)
        self.assertEqual(result, expected_output)

    def test_dict_with_list_of_dicts(self):
        """
        Test that flatten_dict_keys works for a nested dictionary with a list of dictionaries.
        """
        expected_output = ["outer.inner1", "outer.inner2.0.ex1", "outer.inner2.0.ex2"]
        result = flatten_dict_keys(self.dict_with_list)
        self.assertEqual(result, expected_output)
