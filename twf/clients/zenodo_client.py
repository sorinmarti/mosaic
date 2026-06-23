import os
import tempfile

import requests
from django.conf import settings


ZENODO_LIVE_URL = "https://zenodo.org"
ZENODO_TEST_URL = "https://sandbox.zenodo.org"

ZENODO_URL = ZENODO_TEST_URL + "/api/deposit/depositions"

LICENSE_CHOICES = [
    ("CC BY 4.0", "Creative Commons Attribution 4.0 International (CC BY 4.0)"),
    (
        "CC BY-SA 4.0",
        "Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)",
    ),
    ("CC0 1.0", "Creative Commons Zero v1.0 Universal (CC0 1.0)"),
    ("MIT", "MIT License"),
    ("GPL-3.0", "GNU General Public License v3.0 (GPL-3.0)"),
    ("Apache-2.0", "Apache License 2.0"),
]


def create_metadata_json(project):
    """
    Create Zenodo-compatible metadata JSON from a project.

    Args:
        project: Project instance containing title, description, owner, members, etc.

    Returns:
        dict: Metadata dictionary formatted for Zenodo API
    """
    project_metadata = {
        "metadata": {
            "title": project.title,
            "upload_type": "dataset",
            "description": project.description,
            "creators": [
                {
                    "name": f"{project.owner.user.last_name}, {project.owner.user.first_name}",
                    "affiliation": project.owner.affiliation,
                }
            ],
        },
        "keywords": project.keywords,
        "license": project.license,
        "access_right": "open",
        "relations": {"version": project.version},
    }

    for member in project.members.all():
        project_metadata["metadata"]["creators"].append(
            {
                "name": f"{member.user.last_name}, {member.user.first_name}",
                "affiliation": member.affiliation,
            }
        )
    return project_metadata


def create_project_md(project):
    """
    Create a markdown README file content for a project.

    Args:
        project: Project instance containing metadata and configuration

    Returns:
        str: Markdown-formatted README content with project details
    """
    project_md = f"""
# {project.title} Dataset

## Project Overview
**Title:** {project.title}
**Description:** {project.description}
**Version:** {project.version}
**Creator:** {project.owner.user.last_name}, {project.owner.user.first_name} ({project.owner.affiliation})
**Keywords:** {', '.join(project.keywords)}
**License:** {project.license}

## Members
"""
    for member in project.members.all():
        project_md += f"- {member.user.last_name}, {member.user.first_name} ({member.affiliation})\n"

    project_md += f"""
## Workflow Description


## Technical Details
The data stems from the Transkribus platform and has been processed by the TWF.

- **Data Format:** Tha data is stored as JSON files.
- **Data Structure:** The data is structured in documents and pages. Documents and pages contain additional metadata,
injected by the TWF.
- **Data Volume:** The dataset contains {project.documents.all().count()} documents.
- **Transkribus Collection ID:** {project.collection_id}
- **Transkribus Export Date:** {project.downloaded_at}
- **TWF Version:** {settings.TWF_VERSION}
"""
    return project_md


def get_zenodo_uploads(project):
    """Returns a list of uploads to Zenodo."""
    access_token = project.get_credentials("zenodo").get("zenodo_token")
    r = requests.get(ZENODO_URL, params={"access_token": access_token})

    if r.status_code != 200:
        return None

    return r.json()


def create_new_deposition(project):
    """
    Create a new empty deposition on Zenodo.

    Args:
        project: Project instance with Zenodo credentials

    Returns:
        dict: JSON response from Zenodo API containing deposition details

    Raises:
        HTTPError: If the API request fails
    """
    access_token = project.get_credentials("zenodo").get("zenodo_token")
    headers = {"Content-Type": "application/json"}
    r = requests.post(
        ZENODO_URL,
        params={"access_token": access_token},
        json={},  # Start with empty metadata
        headers=headers,
    )
    r.raise_for_status()
    return r.json()


def get_deposition(project):
    """
    Retrieve details of an existing Zenodo deposition.

    Args:
        project: Project instance with Zenodo credentials and deposition ID

    Returns:
        dict: JSON response from Zenodo API with deposition details

    Raises:
        HTTPError: If the API request fails
    """
    token = project.get_credentials("zenodo")["zenodo_token"]
    depo_id = project.zenodo_deposition_id
    r = requests.get(f"{ZENODO_URL}/{depo_id}", params={"access_token": token})
    r.raise_for_status()
    return r.json()


def create_new_version_from_deposition(project):
    """
    Create a new version draft from an existing published Zenodo deposition.

    Args:
        project: Project instance with Zenodo credentials and deposition ID

    Returns:
        dict: JSON response from Zenodo API with new draft deposition details

    Raises:
        HTTPError: If the API request fails
    """
    token = project.get_credentials("zenodo")["zenodo_token"]
    depo_id = project.zenodo_deposition_id
    r = requests.post(
        f"{ZENODO_URL}/{depo_id}/actions/newversion", params={"access_token": token}
    )
    r.raise_for_status()

    # Get new draft from the 'latest_draft' link
    latest_draft = r.json()["links"]["latest_draft"]
    r2 = requests.get(latest_draft, params={"access_token": token})
    r2.raise_for_status()
    return r2.json()


def upload_file_to_deposition(project, deposition_id, file_path, filename=None):
    """
    Upload a file to a Zenodo deposition.

    Args:
        project: Project instance with Zenodo credentials
        deposition_id: ID of the Zenodo deposition
        file_path: Local path to the file to upload
        filename: Optional custom filename (default: uses basename of file_path)

    Returns:
        None

    Raises:
        HTTPError: If the upload fails
    """
    token = project.get_credentials("zenodo")["zenodo_token"]
    bucket_url = get_deposition(project)["links"]["bucket"]

    with open(file_path, "rb") as fp:
        file_name = filename or os.path.basename(file_path)
        r = requests.put(
            f"{bucket_url}/{file_name}", data=fp, params={"access_token": token}
        )
        r.raise_for_status()


def update_deposition_metadata(project, deposition_id):
    """
    Update the metadata of a Zenodo deposition.

    Args:
        project: Project instance with Zenodo credentials and metadata
        deposition_id: ID of the Zenodo deposition to update

    Returns:
        None

    Raises:
        HTTPError: If the update fails
    """
    access_token = project.get_credentials("zenodo").get("zenodo_token")
    metadata = create_metadata_json(project)
    r = requests.put(
        f"{ZENODO_URL}/{deposition_id}",
        params={"access_token": access_token},
        json=metadata,
    )
    r.raise_for_status()


def publish_deposition(project, deposition_id):
    """
    Publish a Zenodo deposition, making it publicly available.

    Args:
        project: Project instance with Zenodo credentials
        deposition_id: ID of the Zenodo deposition to publish

    Returns:
        dict: JSON response from Zenodo API with published deposition details

    Raises:
        HTTPError: If the publish action fails
    """
    access_token = project.get_credentials("zenodo").get("zenodo_token")
    r = requests.post(
        f"{ZENODO_URL}/{deposition_id}/actions/publish",
        params={"access_token": access_token},
    )
    r.raise_for_status()
    return r.json()


def create_temp_readme_from_project(project):
    """
    Create a temporary README file from a project's workflow description.

    Args:
        project: Project instance with optional workflow_description field

    Returns:
        str: Path to the temporary README.md file
    """
    readme_content = project.workflow_description or "No description provided."
    temp = tempfile.NamedTemporaryFile(
        delete=False, suffix=".md", mode="w+", encoding="utf-8"
    )
    temp.write(readme_content)
    temp.flush()
    return temp.name
