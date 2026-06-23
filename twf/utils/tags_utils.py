"""Utility functions for tags."""

import json
import re
import logging
from django.db.models import Count
from fuzzywuzzy import process, fuzz
from twf.models import PageTag, Variation

logger = logging.getLogger(__name__)


def get_translated_tag_type(project, tag_type):
    """Translate the tag type based on the project configuration."""
    task_configurations = project.get_task_configuration("tag_types")
    if "tag_type_translator" not in task_configurations:
        return tag_type

    try:
        tag_type_translator = json.loads(task_configurations["tag_type_translator"])
    except json.JSONDecodeError:
        # Handle JSON decoding error
        return tag_type

    if tag_type in tag_type_translator:
        return tag_type_translator[tag_type]

    return tag_type


def get_all_tag_types(project):
    """
    Get the distinct tag types configured for grouping workflow.

    Excludes:
    - Ignored types (workflow_type = 'ignore')
    - Enrichment types (workflow_type = 'enrich')

    Returns only tag types configured for grouping (workflow_type = 'group').
    """
    enrichment_types = get_enrichment_types(project)
    distinct_variation_types = (
        PageTag.objects.filter(page__document__project=project)
        .exclude(variation_type__in=get_excluded_types(project))
        .exclude(variation_type__in=enrichment_types.keys())
        .values("variation_type")
        .annotate(count=Count("variation_type"))
        .order_by("variation_type")
    )

    # Extracting the distinct variation types from the queryset
    distinct_variation_types_list = [
        item["variation_type"] for item in distinct_variation_types
    ]
    return distinct_variation_types_list


def get_excluded_types(project):
    """Get the excluded tag types."""
    task_configurations = project.get_task_configuration("tag_types")
    if "ignored_tag_types" in task_configurations:
        try:
            conf = json.loads(task_configurations["ignored_tag_types"])
            if "ignored" in conf:
                return conf["ignored"]
        except json.JSONDecodeError:
            return []
    return []


def get_date_types(project):
    """Get the date tag types."""
    task_configurations = project.get_task_configuration("tag_types")
    if "ignored_tag_types" in task_configurations:
        try:
            conf = json.loads(task_configurations["ignored_tag_types"])
            if "dates" in conf:
                return conf["dates"]
        except json.JSONDecodeError:
            return []
        return []
    return []


def get_enrichment_types(project):
    """
    Get tag types configured for direct enrichment (not grouping).

    Returns dict mapping tag_type to enrichment config:
    {
        'date': {'workflow_title': '...', 'form_type': 'date'},
        'bible_verse': {'workflow_title': '...', 'form_type': 'verse'}
    }
    """
    task_config = project.get_task_configuration("tag_types")

    # Try new enrichment_types_config field first
    if "enrichment_types_config" in task_config:
        try:
            return json.loads(task_config["enrichment_types_config"])
        except json.JSONDecodeError:
            logger.warning("Failed to parse enrichment_types_config JSON")

    # Backward compatibility: dates from ignored_tag_types
    date_types = get_date_types(project)
    if date_types:
        return {
            dt: {"workflow_title": "Normalize Dates", "form_type": "date"}
            for dt in date_types
        }

    return {}


def get_enrichment_type_for_tag_type(project, tag_type):
    """
    Get enrichment config for a specific tag type.

    Returns None if the tag type uses grouping instead of enrichment.
    """
    enrichment_types = get_enrichment_types(project)
    return enrichment_types.get(tag_type)


def get_closest_variations(page_tag):
    """
    Return the 5 closest dictionary entries to the tag.

    Groups variations by entry and returns unique entries.
    Entries with multiple strong matches are marked as such.

    Returns:
        List of tuples: (variation, score, match_count)
        - variation: The best matching Variation object for this entry
        - score: The highest similarity score for this entry
        - match_count: Number of variations with score >= 80 for this entry
    """

    dict_type = page_tag.variation_type
    dict_type = get_translated_tag_type(page_tag.page.document.project, dict_type)

    variations = Variation.objects.filter(
        entry__dictionary__in=page_tag.page.document.project.selected_dictionaries.all(),
        entry__dictionary__type=dict_type,
    )
    variations_list = [variation.variation for variation in variations]

    # Get many more matches to ensure we capture all good matches per entry
    # Use limit=None to get all matches, or a high number like 50
    all_matches = process.extract(page_tag.variation, variations_list, limit=50)

    # Group matches by dictionary entry
    entry_matches = {}  # {entry_id: [(variation, score), ...]}

    for match in all_matches:
        variation_text, score = match
        matched_variation = variations.filter(variation=variation_text).first()
        if matched_variation:
            entry_id = matched_variation.entry.id
            if entry_id not in entry_matches:
                entry_matches[entry_id] = []
            entry_matches[entry_id].append((matched_variation, score))

    # For each entry, determine the best variation and count strong matches
    entry_results = []
    for entry_id, matches in entry_matches.items():
        # Sort matches by score (highest first)
        matches.sort(key=lambda x: x[1], reverse=True)
        best_variation, best_score = matches[0]

        # Count how many variations have a strong match (score >= 80)
        strong_match_count = sum(1 for _, score in matches if score >= 80)

        entry_results.append((best_variation, best_score, strong_match_count))

    # Sort entries by best score and return top 5
    entry_results.sort(key=lambda x: x[1], reverse=True)

    return entry_results[:5]


def assign_tag(page_tag, user):
    """Assign the tag to a dictionary entry."""

    try:
        dictionary_type = page_tag.variation_type
        dictionary_type = get_translated_tag_type(
            page_tag.page.document.project, dictionary_type
        )
        try:
            entry = Variation.objects.get(
                variation=page_tag.variation,
                entry__dictionary__in=page_tag.page.document.project.selected_dictionaries.all(),
                entry__dictionary__type=dictionary_type,
            )
        except Variation.MultipleObjectsReturned:
            # TODO: Handle multiple objects returned
            entry = Variation.objects.filter(
                variation=page_tag.variation,
                entry__dictionary__in=page_tag.page.document.project.selected_dictionaries.all(),
                entry__dictionary__type=dictionary_type,
            ).first()

        page_tag.dictionary_entry = entry.entry
        page_tag.save(current_user=user)
        return True
    except Variation.DoesNotExist:
        return False


def extract_tags_from_parsed_data(parsed_data):
    """
    Extract tags from PAGE XML parsed data.

    Parses the 'custom' attribute from PAGE XML elements to extract tag information
    including person names, places, organizations, works, etc.

    With simple-alto-parser v0.0.22+, the parser provides positional data directly:
    - offset: Character position within the line
    - length: Length of the tagged text
    - line_index: Which line within the region (0-based)
    - line_text: The actual text of that specific line

    Args:
        parsed_data: Dict containing parsed PAGE XML data with 'elements' key

    Returns:
        List of tag dicts with structure:
        {
            'variation': 'Richard Wagner',
            'type': 'person',
            'offset': 15,
            'length': 14,
            'continued': False,
            'line_id': 'r_tl_1',
            'line_text': 'Qu\'importe que Richard Wagner...',
            'region_index': 0,
            'line_index_in_region': 0,
            'line_index_global': 0
        }
    """
    tags = []

    if not parsed_data or "elements" not in parsed_data:
        return tags

    # Track global line count across all regions
    global_line_counter = 0

    for region_index, element in enumerate(parsed_data.get("elements", [])):
        # Get region identifier
        element_id = element.get("id", "")

        # Generate a synthetic line_id based on element position if element_id is empty
        # This ensures we have consistent line IDs for matching even when Transkribus doesn't provide them
        if not element_id or element_id == "":
            element_id = f"synthetic_region_{region_index}"

        element_data = element.get("element_data", {})

        # Get all text lines in this region (for line counting)
        text_lines = element_data.get("text_lines", [])
        lines_in_region = len(text_lines) if text_lines else 0

        # Parse custom attribute to extract tags
        custom_data = element_data.get("custom_structure", {})
        custom_str = ""

        # Handle different possible structures
        if isinstance(custom_data, dict):
            structure = custom_data.get("structure", {})
            if isinstance(structure, dict):
                custom_str = structure.get("custom", "")
            elif isinstance(structure, str):
                custom_str = structure
        elif isinstance(custom_data, str):
            custom_str = custom_data

        # Check custom_list_structure (standard format from parser v0.0.22+)
        custom_list = element_data.get("custom_list_structure", [])

        # If we have custom_list_structure, use that (current format)
        if custom_list:
            for tag_data in custom_list:
                if not isinstance(tag_data, dict):
                    continue

                tag_type = tag_data.get("type", "")
                if not tag_type or tag_type == "readingOrder":
                    continue

                # Extract tag text (parser v0.0.22+ provides this directly)
                variation_text = tag_data.get("text", "").strip()
                if not variation_text:
                    continue

                # Get positional data from parser
                offset = tag_data.get("offset", 0)
                length = tag_data.get("length", len(variation_text))
                continued = tag_data.get("continued", False)

                # NEW in parser v0.0.22+: line_index and line_text
                line_index_in_region = tag_data.get("line_index", 0)
                tag_line_text = tag_data.get("line_text", "")

                # Fallback: if parser didn't provide line_text, use joined region text
                if not tag_line_text and text_lines:
                    tag_line_text = " ".join(text_lines)

                # Calculate global line index
                line_index_global = global_line_counter + line_index_in_region

                tags.append(
                    {
                        "variation": variation_text,
                        "type": tag_type,
                        "offset": offset,
                        "length": length,
                        "continued": continued,
                        "line_id": element_id,
                        "line_text": tag_line_text,
                        "region_index": region_index,
                        "line_index_in_region": line_index_in_region,
                        "line_index_global": line_index_global,
                    }
                )

        # Otherwise parse from custom string (for raw PAGE XML - legacy support)
        elif custom_str:
            # Extract tags using regex: tagType {key:value; key:value;}
            tag_pattern = re.compile(r"(\w+)\s+\{([^}]+)\}")

            # Join all lines for legacy extraction
            region_text = " ".join(text_lines) if text_lines else ""

            for match in tag_pattern.finditer(custom_str):
                tag_type = match.group(1)

                # Skip metadata entries
                if tag_type == "readingOrder" or tag_type == "structure":
                    continue

                # Parse attributes
                attrs_str = match.group(2)
                attrs = {}
                for attr in attrs_str.split(";"):
                    attr = attr.strip()
                    if ":" in attr:
                        key, val = attr.split(":", 1)
                        attrs[key.strip()] = val.strip()

                # Get offset, length, and continued flag
                try:
                    offset = int(attrs.get("offset", 0))
                    length = int(attrs.get("length", 0))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid offset/length in tag: {attrs}")
                    continue

                continued = attrs.get("continued", "").lower() == "true"

                # Extract tagged text from region using offset and length
                if length > 0 and offset >= 0 and offset + length <= len(region_text):
                    variation_text = region_text[offset : offset + length].strip()
                else:
                    # Fallback if extraction fails
                    logger.warning(
                        f"Could not extract tag text at offset {offset}, length {length} "
                        f"from region: {region_text[:50]}..."
                    )
                    continue

                if variation_text:
                    # Legacy mode: can't determine exact line, use region-level data
                    tags.append(
                        {
                            "variation": variation_text,
                            "type": tag_type,
                            "offset": offset,
                            "length": length,
                            "continued": continued,
                            "line_id": element_id,
                            "line_text": region_text,
                            "region_index": region_index,
                            "line_index_in_region": 0,  # Unknown in legacy mode
                            "line_index_global": global_line_counter,
                        }
                    )

        # Update global line counter for next region
        global_line_counter += lines_in_region

    return tags


class SmartTagMatcher:
    """
    Smart matching algorithm for tags that handles transcription changes.

    Uses multi-signal scoring to match old tags to new tags even when:
    - Transcription text changes (offsets shift)
    - Tag text has typos that get fixed
    - Line content is edited

    Matching is based on:
    - Same line ID (required)
    - Same tag type (required)
    - Text similarity (exact or fuzzy)
    - Offset proximity
    - Length similarity
    """

    # Matching thresholds and weights
    MATCH_THRESHOLD = 60  # Minimum score to consider a match
    EXACT_TEXT_SCORE = 40
    MAX_FUZZY_TEXT_SCORE = 30
    FUZZY_TEXT_THRESHOLD = 80  # Minimum similarity for fuzzy match
    MAX_OFFSET_SCORE = 30
    MAX_LENGTH_SCORE = 10

    def __init__(self):
        """Initialize the matcher."""
        self.ambiguous_matches = []

    def match_tags(self, old_tags, new_tags_data, page):
        """
        Match old PageTag objects to new tag data from XML.

        Args:
            old_tags: List of existing PageTag objects
            new_tags_data: List of tag dicts from extract_tags_from_parsed_data()
            page: Page object (for logging)

        Returns:
            Tuple of (matches, unmatched_old, unmatched_new) where:
            - matches: List[(old_tag, new_tag_data)] of matched pairs
            - unmatched_old: List[old_tag] to delete
            - unmatched_new: List[new_tag_data] to create
        """
        potential_matches = []

        # Phase 1: Calculate scores for all combinations
        for new_tag_data in new_tags_data:
            for old_tag in old_tags:
                score = self.calculate_match_score(old_tag, new_tag_data)
                if score >= self.MATCH_THRESHOLD:
                    potential_matches.append((old_tag, new_tag_data, score))
                elif score >= self.MATCH_THRESHOLD * 0.85:  # 85% of threshold
                    # Log ambiguous cases
                    self.ambiguous_matches.append(
                        {
                            "page": page.tk_page_number,
                            "line": new_tag_data["line_id"],
                            "old_text": old_tag.variation,
                            "new_text": new_tag_data["variation"],
                            "score": score,
                        }
                    )

        # Phase 2: Greedy best-match (highest scores first)
        potential_matches.sort(key=lambda x: x[2], reverse=True)

        used_old = set()
        used_new = set()
        final_matches = []

        for old_tag, new_tag_data, score in potential_matches:
            old_id = old_tag.id
            # Use a tuple of identifying features for new tags
            new_id = (
                new_tag_data["line_id"],
                new_tag_data["type"],
                new_tag_data["offset"],
                new_tag_data["variation"],
            )

            if old_id not in used_old and new_id not in used_new:
                final_matches.append((old_tag, new_tag_data, score))
                used_old.add(old_id)
                used_new.add(new_id)

        # Phase 3: Identify unmatched
        unmatched_old = [t for t in old_tags if t.id not in used_old]
        unmatched_new = [
            t
            for t in new_tags_data
            if (t["line_id"], t["type"], t["offset"], t["variation"]) not in used_new
        ]

        return final_matches, unmatched_old, unmatched_new

    def calculate_match_score(self, old_tag, new_tag_data):
        """
        Calculate similarity score between old PageTag and new tag data from XML.

        Args:
            old_tag: Existing PageTag object
            new_tag_data: Dict from extract_tags_from_parsed_data()

        Returns:
            int: Match score (0-100)
        """
        score = 0

        # REQUIRED: Same line ID (for backward compatibility)
        # Try new explicit fields first, fall back to additional_information
        old_line_id = (
            old_tag.additional_information.get("line_id", "")
            if old_tag.additional_information
            else ""
        )
        new_line_id = new_tag_data["line_id"]

        # Special case: If old_line_id is empty (legacy data without proper line IDs),
        # allow matching based on other signals instead of requiring line ID match.
        # This handles transition from empty line IDs to synthetic line IDs.
        if old_line_id and new_line_id and old_line_id != new_line_id:
            return 0  # Different lines = not the same tag

        # REQUIRED: Same variation_type
        if old_tag.variation_type != new_tag_data["type"]:
            return 0

        # Signal 1: Text similarity (max 40 points for exact, 30 for fuzzy)
        if old_tag.variation == new_tag_data["variation"]:
            score += self.EXACT_TEXT_SCORE
        else:
            # Fuzzy match for typo corrections
            similarity = fuzz.ratio(old_tag.variation, new_tag_data["variation"])
            if similarity >= self.FUZZY_TEXT_THRESHOLD:
                # Scale fuzzy match score
                score += (similarity / 100) * self.MAX_FUZZY_TEXT_SCORE

        # Signal 2: Offset proximity (max 30 points)
        # Use new explicit field, fall back to additional_information for old data
        old_offset = (
            old_tag.offset_in_line
            if hasattr(old_tag, "offset_in_line")
            else old_tag.additional_information.get("offset", 0)
        )
        new_offset = new_tag_data["offset"]
        offset_diff = abs(old_offset - new_offset)

        if offset_diff == 0:
            score += 30  # Exact same position
        elif offset_diff <= 3:
            score += 25  # Very close (minor transcription edits)
        elif offset_diff <= 10:
            score += 15  # Close (moderate edits)
        elif offset_diff <= 20:
            score += 5  # Somewhat close
        # else: 0 points

        # Signal 3: Length similarity (bonus up to 10 points)
        # Use new explicit field, fall back to additional_information for old data
        old_length = (
            old_tag.length
            if hasattr(old_tag, "length")
            else old_tag.additional_information.get("length", len(old_tag.variation))
        )
        new_length = new_tag_data["length"]
        length_diff = abs(old_length - new_length)

        if length_diff == 0:
            score += self.MAX_LENGTH_SCORE
        elif length_diff <= 2:
            score += 5

        return score

    def get_ambiguous_matches(self):
        """Return list of ambiguous matches that were close but didn't make threshold."""
        return self.ambiguous_matches

    def clear_ambiguous_matches(self):
        """Clear the ambiguous matches list."""
        self.ambiguous_matches = []
