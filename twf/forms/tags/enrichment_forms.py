"""
Tag Enrichment Forms
===================

Forms for enriching tags with normalized data (dates, bible verses, locations, etc.).
"""

from django import forms
from django.urls import reverse
from abc import ABCMeta, abstractmethod
import re
import json
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Div, HTML, ButtonHolder
from django_select2.forms import Select2Widget

# Import API clients for query-assisted forms
from twf.clients.gnd_client import search_gnd
from twf.clients.wikidata_client import search_wikidata_entities
from twf.clients.geonames_client import search_location
from twf.models import DictionaryEntry


class AbstractFormMeta(ABCMeta, type(forms.Form)):
    """Metaclass combining ABC and Django Form metaclass."""


class BaseTagEnrichmentForm(forms.Form, metaclass=AbstractFormMeta):
    """
    Abstract base for tag enrichment forms.

    Provides common structure for all enrichment types.
    Subclasses must implement:
    - propose_normalization(): Generate initial normalized value
    - build_enrichment_data(): Build structured JSON data
    - get_enrichment_type(): Return enrichment type string
    """

    item_id = forms.IntegerField(widget=forms.HiddenInput())
    normalized_value = forms.CharField(
        max_length=500,
        label="Normalized Value",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "readonly": "readonly"}),
    )

    def __init__(self, *args, project=None, tag=None, item=None, **kwargs):
        # Support both 'tag' (backward compatibility) and 'item' (new generic name)
        if item is None:
            item = tag
        if not project or not item:
            raise ValueError("Project and item are required.")

        super().__init__(*args, **kwargs)
        self.project = project
        self.item = item
        # Keep 'tag' attribute for backward compatibility
        self.tag = item
        self.fields["item_id"].initial = item.pk

        # Check if item already has enrichment of this type
        enrichment_type = self.get_enrichment_type()
        if item.has_enrichment(enrichment_type):
            existing_data = item.get_enrichment().get(enrichment_type, {})
            # Pre-populate with existing data
            self.fields["normalized_value"].initial = existing_data.get("normalized_value", "")
            # Subclasses can override _populate_from_existing to populate specific fields
            if hasattr(self, '_populate_from_existing'):
                self._populate_from_existing(existing_data.get("enrichment_data", {}))
        else:
            # Get initial normalized proposal
            proposal = self.propose_normalization(item.get_variation(), project)
            self.fields["normalized_value"].initial = proposal

        # Setup crispy forms helper with buttons
        # Park button behavior depends on context:
        # - For tags in tag detail view: HTML link to park URL
        # - For dictionary entries in workflow: Submit button for park_and_next
        park_button = None
        if hasattr(item, 'is_parked'):
            if isinstance(item, DictionaryEntry):
                # Workflow context - use submit button
                park_button = Submit(
                    "park_and_next",
                    "Park & Next",
                    css_class="btn btn-warning ms-2",
                )
            else:
                # Tag detail context - use link
                park_url = reverse("twf:tags_park", kwargs={"pk": item.pk})
                park_button = HTML(
                    f'<a href="{park_url}" class="btn btn-secondary ms-2">'
                    f'<i class="fa fa-box-archive"></i> Park</a>'
                )

        buttons = [
            Submit(
                "save_and_next",
                "Save & Next",
                css_class="btn btn-primary",
            )
        ]
        if park_button:
            buttons.append(park_button)

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            "item_id",
            self._get_form_fields_layout(),
            ButtonHolder(
                *buttons,
                css_class="mt-3",
            ),
        )

    def _get_park_button(self):
        """
        Get park button appropriate for the item type.

        Returns:
            Submit or HTML button, or None if item doesn't support parking
        """
        if not hasattr(self.item, 'is_parked'):
            return None

        # Check item type by class name to avoid circular import issues
        if self.item.__class__.__name__ == 'DictionaryEntry':
            # Workflow context - use submit button
            return Submit(
                "park_and_next",
                "Park & Next",
                css_class="btn btn-warning ms-2",
            )
        else:
            # Tag detail context - use link
            park_url = reverse("twf:tags_park", kwargs={"pk": self.item.pk})
            return HTML(
                f'<a href="{park_url}" class="btn btn-secondary ms-2">'
                f'<i class="fa fa-box-archive"></i> Park</a>'
            )

    def _get_form_fields_layout(self):
        """
        Get layout for form-specific fields.

        Override in subclasses to customize field layout.
        Returns field names or Layout objects for crispy forms.
        """
        # Default: return all fields except item_id
        return Div(
            *[
                field_name
                for field_name in self.fields.keys()
                if field_name != "item_id"
            ]
        )

    @abstractmethod
    def propose_normalization(self, variation, project):
        """
        Generate initial normalization proposal.

        Parameters
        ----------
        variation : str
            The tag variation text
        project : Project
            The project context

        Returns
        -------
        str
            Proposed normalized value
        """

    @abstractmethod
    def build_enrichment_data(self, cleaned_data):
        """
        Build structured enrichment_data dict from form data.

        Parameters
        ----------
        cleaned_data : dict
            Form cleaned data

        Returns
        -------
        dict
            Structured data for enrichment_data JSONField
        """

    @abstractmethod
    def get_enrichment_type(self):
        """
        Return enrichment type string.

        Returns
        -------
        str
            Type identifier (e.g., 'date', 'verse', 'location')
        """

    def save(self, user):
        """
        Save enrichment data to item.enrichment field (or item.metadata for DictionaryEntry).

        Parameters
        ----------
        user : User
            User performing the enrichment

        Returns
        -------
        PageTag or DictionaryEntry
            Updated item instance
        """
        # Use the enrichment protocol (works for both PageTag and DictionaryEntry)
        self.item.set_enrichment(
            enrichment_type=self.get_enrichment_type(),
            normalized_value=self.cleaned_data["normalized_value"],
            enrichment_data=self.build_enrichment_data(self.cleaned_data),
            user=user
        )

        return self.item


class DateEnrichmentForm(BaseTagEnrichmentForm):
    """Form for date normalization to EDTF format."""

    resolve_to = forms.ChoiceField(
        label="Resolve to",
        choices=[("year", "Year"), ("month", "Month"), ("day", "Day")],
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    input_date_format = forms.ChoiceField(
        label="Input Date Format",
        choices=[
            ("DMY", "Day-Month-Year"),
            ("MDY", "Month-Day-Year"),
            ("YMD", "Year-Month-Day"),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Get date config from project
        conf = self.project.get_task_configuration("date_normalization")
        self.fields["resolve_to"].initial = conf.get("resolve_to", "day")
        self.fields["input_date_format"].initial = conf.get("input_date_format", "DMY")

        # Make normalized_value editable for dates (override readonly from base)
        self.fields["normalized_value"].widget.attrs.pop("readonly", None)

    def propose_normalization(self, variation, project):
        """
        Parse date string to EDTF format.

        Parameters
        ----------
        variation : str
            Date variation text
        project : Project
            Project context

        Returns
        -------
        str
            EDTF date string
        """
        from twf.utils.date_utils import parse_date_string

        conf = project.get_task_configuration("date_normalization")
        return parse_date_string(
            variation,
            resolve_to=conf.get("resolve_to", "day"),
            date_format=conf.get("input_date_format", "DMY"),
        )

    def build_enrichment_data(self, cleaned_data):
        """
        Build structured date data from EDTF.

        Parameters
        ----------
        cleaned_data : dict
            Form cleaned data

        Returns
        -------
        dict
            Date data with year, month, day, edtf fields
        """
        edtf = cleaned_data["normalized_value"]

        # Parse EDTF to structured data
        data = {"edtf": edtf}
        parts = edtf.split("-")
        if len(parts) >= 1 and parts[0].isdigit():
            data["year"] = int(parts[0])
        if len(parts) >= 2 and parts[1] not in ("XX", "xx") and parts[1].isdigit():
            data["month"] = int(parts[1])
        if len(parts) >= 3 and parts[2] not in ("XX", "xx") and parts[2].isdigit():
            data["day"] = int(parts[2])

        return data

    def get_enrichment_type(self):
        """Return enrichment type."""
        return "date"


class BibleVerseEnrichmentForm(BaseTagEnrichmentForm):
    """Form for bible verse normalization."""
    BOOK_CHOICES = [
        ("Gen", "Genesis / Genesis / Genesis"),
        ("Exod", "Exodus / Exodus / Exodus"),
        ("Lev", "Leviticus / Levitikus / Leviticus"),
        ("Num", "Numbers / Numeri / Numeri"),
        ("Deut", "Deuteronomy / Deuteronomium / Deuteronomium"),
        ("Josh", "Joshua / Josua / Josue"),
        ("Judg", "Judges / Richter / Judicum"),
        ("Ruth", "Ruth / Ruth / Ruth"),
        ("1Sam", "1 Samuel / 1. Samuel / 1 Regum"),
        ("2Sam", "2 Samuel / 2. Samuel / 2 Regum"),
        ("1Kgs", "1 Kings / 1. Könige / 3 Regum"),
        ("2Kgs", "2 Kings / 2. Könige / 4 Regum"),
        ("1Chr", "1 Chronicles / 1. Chronik / 1 Paralipomenon"),
        ("2Chr", "2 Chronicles / 2. Chronik / 2 Paralipomenon"),
        ("Ezra", "Ezra / Esra / Esdras"),
        ("Neh", "Nehemiah / Nehemia / Nehemias"),
        ("Esth", "Esther / Ester / Esther"),
        ("Job", "Job / Hiob / Job"),
        ("Ps", "Psalms / Psalmen / Psalmi"),
        ("Prov", "Proverbs / Sprüche / Proverbia"),
        ("Eccl", "Ecclesiastes / Prediger / Ecclesiastes"),
        ("Song", "Song of Solomon / Hohelied Salomos / Canticum Canticorum"),
        ("Isa", "Isaiah / Jesaja / Isaias"),
        ("Jer", "Jeremiah / Jeremia / Jeremias"),
        ("Lam", "Lamentations / Klagelieder / Threni"),
        ("Ezek", "Ezekiel / Hesekiel / Ezechiel"),
        ("Dan", "Daniel / Daniel / Daniel"),
        ("Hos", "Hosea / Hosea / Osee"),
        ("Joel", "Joel / Joel / Joel"),
        ("Amos", "Amos / Amos / Amos"),
        ("Obad", "Obadiah / Obadja / Abdias"),
        ("Jonah", "Jonah / Jona / Jonas"),
        ("Mic", "Micah / Micha / Michaeas"),
        ("Nah", "Nahum / Nahum / Nahum"),
        ("Hab", "Habakkuk / Habakuk / Habacuc"),
        ("Zeph", "Zephaniah / Zefanja / Sophonias"),
        ("Hag", "Haggai / Haggai / Aggaeus"),
        ("Zech", "Zechariah / Sacharja / Zacharias"),
        ("Mal", "Malachi / Maleachi / Malachias"),
        ("Matt", "Matthew / Matthäus / Matthaeus"),
        ("Mark", "Mark / Markus / Marcus"),
        ("Luke", "Luke / Lukas / Lucas"),
        ("John", "John / Johannes / Joannes"),
        ("Acts", "Acts / Apostelgeschichte / Actus Apostolorum"),
        ("Rom", "Romans / Römer / Ad Romanos"),
        ("1Cor", "1 Corinthians / 1. Korinther / 1 ad Corinthios"),
        ("2Cor", "2 Corinthians / 2. Korinther / 2 ad Corinthios"),
        ("Gal", "Galatians / Galater / Ad Galatas"),
        ("Eph", "Ephesians / Epheser / Ad Ephesios"),
        ("Phil", "Philippians / Philipper / Ad Philippenses"),
        ("Col", "Colossians / Kolosser / Ad Colossenses"),
        ("1Thess", "1 Thessalonians / 1. Thessalonicher / 1 ad Thessalonicenses"),
        ("2Thess", "2 Thessalonians / 2. Thessalonicher / 2 ad Thessalonicenses"),
        ("1Tim", "1 Timothy / 1. Timotheus / 1 ad Timotheum"),
        ("2Tim", "2 Timothy / 2. Timotheus / 2 ad Timotheum"),
        ("Titus", "Titus / Titus / Ad Titum"),
        ("Phlm", "Philemon / Philemon / Ad Philemonem"),
        ("Heb", "Hebrews / Hebräer / Ad Hebraeos"),
        ("Jas", "James / Jakobus / Jacobus"),
        ("1Pet", "1 Peter / 1. Petrus / 1 Petrus"),
        ("2Pet", "2 Peter / 2. Petrus / 2 Petrus"),
        ("1John", "1 John / 1. Johannes / 1 Joannes"),
        ("2John", "2 John / 2. Johannes / 2 Joannes"),
        ("3John", "3 John / 3. Johannes / 3 Joannes"),
        ("Jude", "Jude / Judas / Judas"),
        ("Rev", "Revelation / Offenbarung / Apocalypsis"),
        ("Tob", "Tobit / Tobit / Tobias"),
        ("Jdt", "Judith / Judith / Judith"),
        ("Wis", "Wisdom of Solomon / Weisheit Salomos / Sapientia"),
        ("Sir", "Sirach (Ecclesiasticus) / Jesus Sirach / Ecclesiasticus"),
        ("Bar", "Baruch / Baruch / Baruch"),
        ("1Macc", "1 Maccabees / 1. Makkabäer / 1 Machabaeorum"),
        ("2Macc", "2 Maccabees / 2. Makkabäer / 2 Machabaeorum"),
    ]

    book = forms.ChoiceField(
        label="Book",
        choices=BOOK_CHOICES,
        widget=Select2Widget(attrs={"class": "form-control"}),
        help_text="Select a book",
    )

    chapter = forms.IntegerField(
        label="Chapter",
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Enter 0 for entire book",
    )

    verse = forms.CharField(
        label="Verse",
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="Single verse (7) or range (7-9). Leave empty for entire chapter.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Parse variation to populate fields
        self._parse_and_populate()

        # Build book choices mapping for JavaScript
        import json
        book_choices_map = {
            code: label.split(" / ")[0]
            for code, label in self.BOOK_CHOICES
        }
        book_choices_json = json.dumps(book_choices_map)

        # Add JavaScript to update normalized_value dynamically
        self.helper.layout.append(
            HTML(f"""
            <script>
            (function() {{
                const bookField = document.querySelector('[name="book"]');
                const chapterField = document.querySelector('[name="chapter"]');
                const verseField = document.querySelector('[name="verse"]');
                const normalizedField = document.querySelector('[name="normalized_value"]');

                const bookChoices = {book_choices_json};

                function updateNormalizedValue() {{
                    const book = bookField.value;
                    const chapter = chapterField.value;
                    const verse = verseField.value.trim();

                    if (!book || chapter === '') {{
                        normalizedField.value = '';
                        return;
                    }}

                    const bookName = bookChoices[book] || book;

                    // Chapter 0 means entire book
                    if (chapter === '0') {{
                        normalizedField.value = bookName;
                    }} else if (verse) {{
                        normalizedField.value = `${{bookName}} ${{chapter}}:${{verse}}`;
                    }} else {{
                        normalizedField.value = `${{bookName}} ${{chapter}}`;
                    }}
                }}

                if (bookField && chapterField && verseField && normalizedField) {{
                    bookField.addEventListener('change', updateNormalizedValue);
                    chapterField.addEventListener('input', updateNormalizedValue);
                    verseField.addEventListener('input', updateNormalizedValue);

                    // Initial update
                    updateNormalizedValue();
                }}
            }})();
            </script>
            """)
        )

    def propose_normalization(self, variation, project):
        """
        Attempt to parse bible verse notation.

        Parameters
        ----------
        variation : str
            Verse variation text
        project : Project
            Project context

        Returns
        -------
        str
            Normalized verse reference
        """
        # Pattern: "Hebr. 13. V. 7." or "Genesis 1:1"
        patterns = [
            r"(\w+)\.\s*(\d+)\.\s*V\.\s*(\d+)",  # "Hebr. 13. V. 7."
            r"(\w+)\s+(\d+):(\d+)",  # "Hebrews 13:7"
            r"(\w+)\s+(\d+),\s*(\d+)",  # "Hebrews 13, 7"
        ]

        for pattern in patterns:
            match = re.search(pattern, variation, re.IGNORECASE)
            if match:
                book_abbrev, chapter, verse = match.groups()
                book_full = self.expand_book_abbreviation(book_abbrev)
                if verse:
                    return f"{book_full} {chapter}:{verse}"
                return f"{book_full} {chapter}"

        return variation  # Return as-is if can't parse

    def _parse_and_populate(self):
        """Parse variation to populate form fields."""
        variation = self.item.get_variation()

        patterns = [
            r"(\w+)\.\s*(\d+)\.\s*V\.\s*(\d+(?:-\d+)?)",  # "Hebr. 13. V. 7." or "Hebr. 13. V. 7-9."
            r"(\w+)\s+(\d+):(\d+(?:-\d+)?)",  # "Hebrews 13:7" or "Hebrews 13:7-9"
            r"(\w+)\s+(\d+),\s*(\d+(?:-\d+)?)",  # "Hebrews 13, 7" or "Hebrews 13, 7-9"
        ]

        for pattern in patterns:
            match = re.search(pattern, variation, re.IGNORECASE)
            if match:
                book_abbrev, chapter, verse = match.groups()
                book_code = self.expand_book_abbreviation(book_abbrev)
                self.fields["book"].initial = book_code
                self.fields["chapter"].initial = int(chapter)
                if verse:
                    self.fields["verse"].initial = verse
                break

        # Update normalized_value based on parsed fields
        self._update_normalized_value()

    def expand_book_abbreviation(self, abbrev):
        """
        Map common bible book abbreviations to choice codes.

        Parameters
        ----------
        abbrev : str
            Book abbreviation

        Returns
        -------
        str
            Book choice code (e.g., 'Heb', 'Gen')
        """
        abbrev_map = {
            "gen": "Gen",
            "exod": "Exod",
            "lev": "Lev",
            "num": "Num",
            "deut": "Deut",
            "josh": "Josh",
            "judg": "Judg",
            "ruth": "Ruth",
            "1sam": "1Sam",
            "2sam": "2Sam",
            "1kgs": "1Kgs",
            "2kgs": "2Kgs",
            "1chr": "1Chr",
            "2chr": "2Chr",
            "ezra": "Ezra",
            "neh": "Neh",
            "esth": "Esth",
            "job": "Job",
            "ps": "Ps",
            "prov": "Prov",
            "eccl": "Eccl",
            "song": "Song",
            "isa": "Isa",
            "jer": "Jer",
            "lam": "Lam",
            "ezek": "Ezek",
            "dan": "Dan",
            "hos": "Hos",
            "joel": "Joel",
            "amos": "Amos",
            "obad": "Obad",
            "jonah": "Jonah",
            "mic": "Mic",
            "nah": "Nah",
            "hab": "Hab",
            "zeph": "Zeph",
            "hag": "Hag",
            "zech": "Zech",
            "mal": "Mal",
            "matt": "Matt",
            "mark": "Mark",
            "luke": "Luke",
            "john": "John",
            "acts": "Acts",
            "rom": "Rom",
            "1cor": "1Cor",
            "2cor": "2Cor",
            "gal": "Gal",
            "eph": "Eph",
            "phil": "Phil",
            "col": "Col",
            "1thess": "1Thess",
            "2thess": "2Thess",
            "1tim": "1Tim",
            "2tim": "2Tim",
            "titus": "Titus",
            "phlm": "Phlm",
            "hebr": "Heb",
            "heb": "Heb",
            "jas": "Jas",
            "1pet": "1Pet",
            "2pet": "2Pet",
            "1jn": "1John",
            "2jn": "2John",
            "3jn": "3John",
            "1john": "1John",
            "2john": "2John",
            "3john": "3John",
            "jude": "Jude",
            "rev": "Rev",
            "tob": "Tob",
            "jdt": "Jdt",
            "wis": "Wis",
            "sir": "Sir",
            "bar": "Bar",
            "1macc": "1Macc",
            "2macc": "2Macc",
        }
        return abbrev_map.get(abbrev.lower(), abbrev.title())

    def _update_normalized_value(self):
        """Generate normalized_value from current field values."""
        book = self.fields["book"].initial
        chapter = self.fields["chapter"].initial
        verse = self.fields["verse"].initial

        if not book or chapter is None:
            return

        # Get book display name (first part of the choice label)
        book_display = dict(self.BOOK_CHOICES).get(book, book)
        if book_display:
            book_display = book_display.split(" / ")[0]  # Get English name

        # Chapter 0 means entire book
        if chapter == 0:
            self.fields["normalized_value"].initial = book_display
        elif verse:
            self.fields["normalized_value"].initial = f"{book_display} {chapter}:{verse}"
        else:
            self.fields["normalized_value"].initial = f"{book_display} {chapter}"

    def clean(self):
        """Validate and auto-generate normalized_value."""
        cleaned_data = super().clean()

        # Validate verse format (single number or range)
        verse = cleaned_data.get("verse", "").strip()
        chapter = cleaned_data.get("chapter")

        if verse:
            if not re.match(r"^\d+(-\d+)?$", verse):
                raise forms.ValidationError({
                    "verse": "Verse must be a single number (7) or range (7-9)"
                })
            # Can't have verse without chapter
            if chapter == 0:
                raise forms.ValidationError({
                    "verse": "Cannot specify verse when referencing entire book (chapter 0)"
                })

        # Auto-generate normalized_value
        book = cleaned_data.get("book")

        if book and chapter is not None:
            book_display = dict(self.BOOK_CHOICES).get(book, book)
            if book_display:
                book_display = book_display.split(" / ")[0]  # Get English name

            # Chapter 0 means entire book
            if chapter == 0:
                cleaned_data["normalized_value"] = book_display
            elif verse:
                cleaned_data["normalized_value"] = f"{book_display} {chapter}:{verse}"
            else:
                cleaned_data["normalized_value"] = f"{book_display} {chapter}"

        return cleaned_data

    def build_enrichment_data(self, cleaned_data):
        """
        Build structured verse data.

        Parameters
        ----------
        cleaned_data : dict
            Form cleaned data

        Returns
        -------
        dict
            Verse data with book, chapter, verse_start, verse_end fields
        """
        data = {
            "book": cleaned_data["book"],
        }

        chapter = cleaned_data.get("chapter")
        # Only include chapter if not 0 (0 means entire book)
        if chapter != 0:
            data["chapter"] = chapter

        # Parse verse range
        verse = cleaned_data.get("verse", "").strip()
        if verse:
            if "-" in verse:
                verse_start, verse_end = verse.split("-")
                data["verse_start"] = int(verse_start)
                data["verse_end"] = int(verse_end)
            else:
                data["verse_start"] = int(verse)
                data["verse_end"] = int(verse)

        return data

    def get_enrichment_type(self):
        """Return enrichment type."""
        return "verse"


class IDEnrichmentForm(BaseTagEnrichmentForm):
    """
    Form for enriching tags with external authority IDs.

    Supports various ID systems like:
    - GND (Gemeinsame Normdatei) for persons, places, organizations
    - GeoNames for geographic locations
    - VIAF for persons
    - Wikidata for any entity
    """

    id_type = forms.ChoiceField(
        label="ID Type",
        choices=[
            ("gnd", "GND (Gemeinsame Normdatei)"),
            ("geonames", "GeoNames"),
            ("viaf", "VIAF"),
            ("wikidata", "Wikidata"),
            ("other", "Other"),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="The authority control system or database",
    )

    id_value = forms.CharField(
        label="ID Value",
        max_length=100,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "e.g., 118540238, 2950159"}
        ),
        help_text="The identifier in the selected system",
    )

    resource_url = forms.URLField(
        label="Resource URL",
        required=False,
        widget=forms.URLInput(
            attrs={"class": "form-control", "placeholder": "https://..."}
        ),
        help_text="Direct link to the authority record (optional)",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Try to extract ID from variation if it looks like one
        self._populate_from_variation()

    def propose_normalization(self, variation, project):
        """
        Generate normalized label for the entity.

        Parameters
        ----------
        variation : str
            The tag variation text
        project : Project
            Project context

        Returns
        -------
        str
            Proposed normalized name
        """
        # Clean up the variation for use as normalized value
        return variation.strip()

    def _populate_from_variation(self):
        """Try to detect ID type and value from the variation text."""
        variation = self.item.get_variation().lower()

        # Check for GND patterns
        if "gnd" in variation or "d-nb.info" in variation:
            self.fields["id_type"].initial = "gnd"
            # Try to extract GND number
            gnd_match = re.search(r"(\d{8,10})", variation)
            if gnd_match:
                self.fields["id_value"].initial = gnd_match.group(1)

        # Check for GeoNames patterns
        elif "geonames" in variation:
            self.fields["id_type"].initial = "geonames"
            geonames_match = re.search(r"(\d{6,8})", variation)
            if geonames_match:
                self.fields["id_value"].initial = geonames_match.group(1)

        # Check for VIAF patterns
        elif "viaf" in variation:
            self.fields["id_type"].initial = "viaf"
            viaf_match = re.search(r"(\d{8,})", variation)
            if viaf_match:
                self.fields["id_value"].initial = viaf_match.group(1)

        # Check for Wikidata patterns
        elif "wikidata" in variation or "Q" in variation:
            self.fields["id_type"].initial = "wikidata"
            wd_match = re.search(r"Q(\d+)", variation, re.IGNORECASE)
            if wd_match:
                self.fields["id_value"].initial = f"Q{wd_match.group(1)}"

    def build_enrichment_data(self, cleaned_data):
        """
        Build structured ID data.

        Parameters
        ----------
        cleaned_data : dict
            Form cleaned data

        Returns
        -------
        dict
            ID data with type, value, and optional URL
        """
        data = {
            "id_type": cleaned_data["id_type"],
            "id_value": cleaned_data["id_value"],
        }

        if cleaned_data.get("resource_url"):
            data["resource_url"] = cleaned_data["resource_url"]

        # Generate standard URL if not provided
        if not data.get("resource_url"):
            data["resource_url"] = self._generate_standard_url(
                cleaned_data["id_type"], cleaned_data["id_value"]
            )

        return data

    def _generate_standard_url(self, id_type, id_value):
        """
        Generate standard URL for common ID systems.

        Parameters
        ----------
        id_type : str
            The ID system type
        id_value : str
            The ID value

        Returns
        -------
        str
            Standard URL for the resource
        """
        url_templates = {
            "gnd": "https://d-nb.info/gnd/{id}",
            "geonames": "https://www.geonames.org/{id}/",
            "viaf": "https://viaf.org/viaf/{id}/",
            "wikidata": "https://www.wikidata.org/wiki/{id}",
        }

        template = url_templates.get(id_type)
        if template:
            return template.format(id=id_value)
        return ""

    def get_enrichment_type(self):
        """Return enrichment type."""
        return "authority_id"


class GNDEnrichmentForm(IDEnrichmentForm):
    """Form for GND authority IDs specifically."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["id_type"].initial = "gnd"
        self.fields["id_type"].widget.attrs["readonly"] = True


class WikidataEnrichmentForm(IDEnrichmentForm):
    """Form for Wikidata IDs specifically."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["id_type"].initial = "wikidata"
        self.fields["id_type"].widget.attrs["readonly"] = True


class GeoNamesEnrichmentForm(IDEnrichmentForm):
    """Form for GeoNames IDs specifically."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["id_type"].initial = "geonames"
        self.fields["id_type"].widget.attrs["readonly"] = True


def get_enrichment_form_class(enrichment_type):
    """
    Factory to get form class for enrichment type.

    Parameters
    ----------
    enrichment_type : str
        Type of enrichment (e.g., 'date', 'verse')

    Returns
    -------
    class
        Form class for the enrichment type
    """
    form_map = {
        "date": DateEnrichmentForm,
        "verse": BibleVerseEnrichmentForm,
        "authority_id": IDEnrichmentForm,
        "gnd": GNDQueryEnrichmentForm,  # Query-assisted form
        "wikidata": WikidataQueryEnrichmentForm,  # Query-assisted form
        "geonames": GeoNamesQueryEnrichmentForm,  # Query-assisted form
    }
    return form_map.get(enrichment_type, BaseTagEnrichmentForm)


# Query-Assisted Enrichment Forms
# These forms query external APIs and let users select from results


class GNDQueryEnrichmentForm(BaseTagEnrichmentForm):
    """Form for searching GND and selecting from results."""

    search_query = forms.CharField(
        label="Search GND",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Edit search term..."}),
    )
    
    selected_result = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
    )
    
    result_choice = forms.ChoiceField(
        label="Select Result",
        choices=[],
        widget=forms.RadioSelect(),
        required=False,
    )

    def __init__(self, *args, project=None, item=None, tag=None, **kwargs):
        # Get search results from POST data if present
        search_results = None
        if args and len(args) > 0 and isinstance(args[0], dict):
            search_results_json = args[0].get('search_results_json')
            if search_results_json:
                try:
                    search_results = json.loads(search_results_json)
                except json.JSONDecodeError:
                    pass

        super().__init__(*args, project=project, item=item, tag=tag, **kwargs)
        
        # Pre-fill search query with item label
        self.fields["search_query"].initial = self.item.get_variation()
        
        # If we have search results, populate the choices
        if search_results:
            choices = []
            for idx, result in enumerate(search_results):
                gnd_id = result["gnd_id"][0] if result["gnd_id"] else ""
                preferred_name = result["preferred_name"][0] if result["preferred_name"] else ""
                birth = result["birth_date"][0] if result.get("birth_date") else ""
                death = result["death_date"][0] if result.get("death_date") else ""
                roles = ", ".join(result.get("roles", [])[:2])  # First 2 roles
                
                label = f"{preferred_name}"
                if birth or death:
                    label += f" ({birth}–{death})"
                if roles:
                    label += f" — {roles}"
                label += f" [GND: {gnd_id}]"
                
                choices.append((str(idx), label))
            
            self.fields["result_choice"].choices = choices
            self.search_results = search_results
        else:
            self.search_results = []
            self.fields["result_choice"].widget = forms.HiddenInput()

        # Update helper to include search button
        park_button = self._get_park_button()

        self.helper = FormHelper()
        self.helper.form_method = "post"

        if not search_results:
            # Show search interface
            buttons = [
                Submit(
                    "search",
                    "Search GND",
                    css_class="btn btn-primary",
                )
            ]
            if park_button:
                buttons.append(park_button)

            self.helper.layout = Layout(
                "item_id",
                "search_query",
                HTML('<input type="hidden" name="search_results_json" value="">'),
                ButtonHolder(
                    *buttons,
                    css_class="mt-3",
                ),
            )
        else:
            # Show results selection
            buttons = [
                Submit(
                    "search",
                    "Search Again",
                    css_class="btn btn-secondary",
                ),
                Submit(
                    "save_and_next",
                    "Save & Next",
                    css_class="btn btn-primary ms-2",
                ),
            ]
            if park_button:
                buttons.append(park_button)

            self.helper.layout = Layout(
                "item_id",
                "search_query",
                HTML('<input type="hidden" name="search_results_json" value="{}">'.format(
                    json.dumps(search_results).replace('"', '&quot;')
                )),
                "result_choice",
                "normalized_value",
                ButtonHolder(
                    *buttons,
                    css_class="mt-3",
                ),
            )

    def propose_normalization(self, variation, project):
        """Return the variation as-is."""
        return variation

    def clean(self):
        """Handle search action or validate selection."""
        cleaned_data = super().clean()
        
        # If this is a search action, we don't need to validate the result selection
        if 'search' in self.data:
            return cleaned_data
        
        # For save action, we need a selected result
        if 'save_and_next' in self.data:
            result_choice = cleaned_data.get('result_choice')
            if not result_choice and self.search_results:
                raise forms.ValidationError("Please select a result to save.")
        
        return cleaned_data

    def build_enrichment_data(self, cleaned_data):
        """Build enrichment data from selected result."""
        if not self.search_results:
            return {}
        
        result_idx = int(cleaned_data.get('result_choice', 0))
        result = self.search_results[result_idx]
        
        gnd_id = result["gnd_id"][0] if result["gnd_id"] else None
        preferred_name = result["preferred_name"][0] if result["preferred_name"] else ""
        
        return {
            "id_type": "gnd",
            "id_value": gnd_id,
            "resource_url": f"https://d-nb.info/gnd/{gnd_id}",
            "preferred_name": preferred_name,
            "variant_names": result.get("variant_names", []),
            "birth_date": result["birth_date"][0] if result.get("birth_date") else None,
            "death_date": result["death_date"][0] if result.get("death_date") else None,
            "roles": result.get("roles", []),
        }

    def get_normalized_value(self):
        """Get normalized value from selected result."""
        if not self.search_results or not self.cleaned_data.get('result_choice'):
            return self.item.get_variation()
        
        result_idx = int(self.cleaned_data['result_choice'])
        result = self.search_results[result_idx]
        preferred_name = result["preferred_name"][0] if result["preferred_name"] else self.item.get_variation()
        return preferred_name

    def save(self, user):
        """Save enrichment data."""
        # Update normalized_value from selected result
        self.cleaned_data['normalized_value'] = self.get_normalized_value()
        return super().save(user)

    def get_enrichment_type(self):
        """Return enrichment type for GND."""
        return "gnd"


class WikidataQueryEnrichmentForm(BaseTagEnrichmentForm):
    """Form for searching Wikidata and selecting from results."""

    search_query = forms.CharField(
        label="Search Wikidata",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Edit search term..."}),
    )

    selected_result = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
    )

    result_choice = forms.ChoiceField(
        label="Select Result",
        choices=[],
        widget=forms.RadioSelect(),
        required=False,
    )

    def __init__(self, *args, project=None, item=None, tag=None, **kwargs):
        # Get search results from POST data if present
        search_results = None
        if args and len(args) > 0 and isinstance(args[0], dict):
            search_results_json = args[0].get('search_results_json')
            if search_results_json:
                try:
                    search_results = json.loads(search_results_json)
                except json.JSONDecodeError:
                    pass

        super().__init__(*args, project=project, item=item, tag=tag, **kwargs)

        # Pre-fill search query with item label
        self.fields["search_query"].initial = self.item.get_variation()

        # If we have search results, populate the choices
        if search_results:
            choices = []
            for idx, result in enumerate(search_results):
                wikidata_id = result.get("id", "")
                label = result.get("label", "")
                description = result.get("description", "")

                display_label = f"{label}"
                if description:
                    display_label += f" — {description}"
                display_label += f" [Wikidata: {wikidata_id}]"

                choices.append((str(idx), display_label))

            self.fields["result_choice"].choices = choices
            self.search_results = search_results
        else:
            self.search_results = []
            self.fields["result_choice"].widget = forms.HiddenInput()

        # Update helper to include search button
        park_button = self._get_park_button()

        self.helper = FormHelper()
        self.helper.form_method = "post"

        if not search_results:
            # Show search interface
            buttons = [
                Submit(
                    "search",
                    "Search Wikidata",
                    css_class="btn btn-primary",
                )
            ]
            if park_button:
                buttons.append(park_button)

            self.helper.layout = Layout(
                "item_id",
                "search_query",
                HTML('<input type="hidden" name="search_results_json" value="">'),
                ButtonHolder(
                    *buttons,
                    css_class="mt-3",
                ),
            )
        else:
            # Show results selection
            buttons = [
                Submit(
                    "search",
                    "Search Again",
                    css_class="btn btn-secondary",
                ),
                Submit(
                    "save_and_next",
                    "Save & Next",
                    css_class="btn btn-primary ms-2",
                ),
            ]
            if park_button:
                buttons.append(park_button)

            self.helper.layout = Layout(
                "item_id",
                "search_query",
                HTML('<input type="hidden" name="search_results_json" value="{}">'.format(
                    json.dumps(search_results).replace('"', '&quot;')
                )),
                "result_choice",
                "normalized_value",
                ButtonHolder(
                    *buttons,
                    css_class="mt-3",
                ),
            )

    def propose_normalization(self, variation, project):
        """Return the variation as-is."""
        return variation

    def clean(self):
        """Handle search action or validate selection."""
        cleaned_data = super().clean()

        # If this is a search action, we don't need to validate the result selection
        if 'search' in self.data:
            return cleaned_data

        # For save action, we need a selected result
        if 'save_and_next' in self.data:
            result_choice = cleaned_data.get('result_choice')
            if not result_choice and self.search_results:
                raise forms.ValidationError("Please select a result to save.")

        return cleaned_data

    def build_enrichment_data(self, cleaned_data):
        """Build enrichment data from selected result."""
        if not self.search_results:
            return {}

        result_idx = int(cleaned_data.get('result_choice', 0))
        result = self.search_results[result_idx]

        wikidata_id = result.get("id", "")
        label = result.get("label", "")

        enrichment_data = {
            "id_type": "wikidata",
            "id_value": wikidata_id,
            "resource_url": f"https://www.wikidata.org/wiki/{wikidata_id}",
            "description": result.get("description", ""),
        }

        # Add coordinates if available
        if result.get("coordinates"):
            coords = result["coordinates"]
            enrichment_data["latitude"] = coords.get("latitude")
            enrichment_data["longitude"] = coords.get("longitude")

        return enrichment_data

    def get_normalized_value(self):
        """Get normalized value from selected result."""
        if not self.search_results or not self.cleaned_data.get('result_choice'):
            return self.item.get_variation()

        result_idx = int(self.cleaned_data['result_choice'])
        result = self.search_results[result_idx]
        label = result.get("label", self.item.get_variation())
        return label

    def save(self, user):
        """Save enrichment data."""
        # Update normalized_value from selected result
        self.cleaned_data['normalized_value'] = self.get_normalized_value()
        return super().save(user)

    def get_enrichment_type(self):
        """Return enrichment type for Wikidata."""
        return "wikidata"


class GeoNamesQueryEnrichmentForm(BaseTagEnrichmentForm):
    """Form for searching GeoNames and selecting from results."""

    search_query = forms.CharField(
        label="Search GeoNames",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Edit search term..."}),
    )

    selected_result = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
    )

    result_choice = forms.ChoiceField(
        label="Select Result",
        choices=[],
        widget=forms.RadioSelect(),
        required=False,
    )

    def __init__(self, *args, project=None, item=None, tag=None, **kwargs):
        import logging
        logger = logging.getLogger(__name__)

        # Get search results from POST data if present
        # POST data can come from either args[0] (manual form creation) or kwargs['data'] (FormView)
        search_results = None
        post_data = None

        if args and len(args) > 0:
            post_data = args[0]
            logger.debug(f"GeoNames form init: POST data from args[0], type={type(post_data)}")
        elif 'data' in kwargs:
            post_data = kwargs['data']
            logger.debug(f"GeoNames form init: POST data from kwargs['data'], type={type(post_data)}")
        else:
            logger.debug("GeoNames form init: No POST data found in args or kwargs")

        if post_data and hasattr(post_data, 'get'):
            search_results_json = post_data.get('search_results_json')
            logger.debug(f"GeoNames form init: search_results_json present={bool(search_results_json)}, length={len(search_results_json) if search_results_json else 0}")

            if search_results_json:
                try:
                    search_results = json.loads(search_results_json)
                    logger.debug(f"GeoNames form init: Successfully parsed {len(search_results)} results")
                except json.JSONDecodeError as e:
                    logger.error(f"GeoNames form init: Failed to parse JSON: {e}")
                    logger.error(f"GeoNames form init: JSON string was: {search_results_json[:200]}")
            else:
                logger.debug("GeoNames form init: search_results_json is empty or None")
        elif post_data:
            logger.warning(f"GeoNames form init: POST data doesn't have 'get' method: {type(post_data)}")

        super().__init__(*args, project=project, item=item, tag=tag, **kwargs)

        # Pre-fill search query with item label
        self.fields["search_query"].initial = self.item.get_variation()

        # If we have search results, populate the choices
        if search_results:
            choices = []
            for idx, result in enumerate(search_results):
                geonames_id = result.get("id", "")
                name = result.get("name", "")
                country = result.get("country", "")
                lat = result.get("lat", "")
                lng = result.get("lng", "")

                display_label = f"{name}"
                if country:
                    display_label += f" ({country})"
                if lat and lng:
                    display_label += f" — {lat}, {lng}"
                display_label += f" [GeoNames: {geonames_id}]"

                choices.append((str(idx), display_label))

            self.fields["result_choice"].choices = choices
            self.search_results = search_results
            logger.debug(f"GeoNames form init: Set {len(choices)} choices for result_choice field")
        else:
            self.search_results = []
            self.fields["result_choice"].widget = forms.HiddenInput()
            logger.debug("GeoNames form init: No search results, hiding result_choice field")

        # Update helper to include search button
        park_button = self._get_park_button()

        self.helper = FormHelper()
        self.helper.form_method = "post"

        if not search_results:
            # Show search interface
            buttons = [
                Submit(
                    "search",
                    "Search GeoNames",
                    css_class="btn btn-primary",
                )
            ]
            if park_button:
                buttons.append(park_button)

            self.helper.layout = Layout(
                "item_id",
                "search_query",
                HTML('<input type="hidden" name="search_results_json" value="">'),
                ButtonHolder(
                    *buttons,
                    css_class="mt-3",
                ),
            )
        else:
            # Show results selection
            buttons = [
                Submit(
                    "search",
                    "Search Again",
                    css_class="btn btn-secondary",
                ),
                Submit(
                    "save_and_next",
                    "Save & Next",
                    css_class="btn btn-primary ms-2",
                ),
            ]
            if park_button:
                buttons.append(park_button)

            self.helper.layout = Layout(
                "item_id",
                "search_query",
                HTML('<input type="hidden" name="search_results_json" value="{}">'.format(
                    json.dumps(search_results).replace('"', '&quot;')
                )),
                "result_choice",
                "normalized_value",
                ButtonHolder(
                    *buttons,
                    css_class="mt-3",
                ),
            )

    def propose_normalization(self, variation, project):
        """Return the variation as-is."""
        return variation

    def clean(self):
        """Handle search action or validate selection."""
        cleaned_data = super().clean()

        # If this is a search action, we don't need to validate the result selection
        if 'search' in self.data:
            return cleaned_data

        # For save action, we need a selected result
        if 'save_and_next' in self.data:
            result_choice = cleaned_data.get('result_choice')
            # Check if we have search results but no selection
            if self.search_results and (not result_choice or result_choice == ''):
                raise forms.ValidationError("Please select a result from the search results before saving.")
            # Also validate that result_choice is a valid index if provided
            if result_choice and self.search_results:
                try:
                    idx = int(result_choice)
                    if idx < 0 or idx >= len(self.search_results):
                        raise forms.ValidationError(f"Invalid result selection: {result_choice}")
                except (ValueError, TypeError):
                    raise forms.ValidationError(f"Invalid result selection format: {result_choice}")

        return cleaned_data

    def build_enrichment_data(self, cleaned_data):
        """Build enrichment data from selected result."""
        if not self.search_results:
            return {}

        result_idx = int(cleaned_data.get('result_choice', 0))
        result = self.search_results[result_idx]

        geonames_id = result.get("id", "")
        name = result.get("name", "")

        return {
            "id_type": "geonames",
            "id_value": str(geonames_id),
            "resource_url": f"https://www.geonames.org/{geonames_id}/",
            "country": result.get("country", ""),
            "latitude": result.get("lat"),
            "longitude": result.get("lng"),
        }

    def get_normalized_value(self):
        """Get normalized value from selected result."""
        if not self.search_results or not self.cleaned_data.get('result_choice'):
            return self.item.get_variation()

        result_idx = int(self.cleaned_data['result_choice'])
        result = self.search_results[result_idx]
        name = result.get("name", self.item.get_variation())
        return name

    def save(self, user):
        """Save enrichment data."""
        # Update normalized_value from selected result
        self.cleaned_data['normalized_value'] = self.get_normalized_value()
        return super().save(user)

    def get_enrichment_type(self):
        """Return enrichment type for GeoNames."""
        return "geonames"
