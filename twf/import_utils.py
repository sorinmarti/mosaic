""" This module contains utility functions for importing data into the database."""

import pandas as pd

from .models import Dictionary, DictionaryEntry, Variation


def import_dictionary_from_csv(
    csv_file_path,
    user,
    type_name,
    label,
    label_column="preferred_name",
    variations_column="variations",
):
    """
    Import a dictionary from a CSV file.
    :param csv_file_path:       The path to the CSV file.
    :param user:
    :param type_name:           The type of the dictionary.
    :param label:               The label of the dictionary.
    :param label_column:        The name of the column containing the labels.
    :param variations_column:   The name of the column containing the variations.
    :return:
    """

    df = pd.read_csv(csv_file_path, encoding="utf-8")

    dictionary = Dictionary(label=label, type=type_name)
    dictionary.save(current_user=user)

    # Create dictionary entries
    for index, row in df.iterrows():
        entry = DictionaryEntry(dictionary=dictionary, label=row[label_column])
        entry.save(current_user=user)
        variations = row[variations_column].split(",")
        for variation in variations:
            if variation != "":
                if not Variation.objects.filter(
                    entry__dictionary__type=type_name, variation=variation
                ).exists():
                    var = Variation(entry=entry, variation=variation)
                    var.save(current_user=user)
                else:
                    print(f"Skipping duplicate variation for entry {entry.label}")

            else:
                print(f"Skipping empty variation for entry {entry.label}")
