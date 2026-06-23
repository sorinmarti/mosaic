""" This module contains the view functions for the AJAX download of the Transkribus export file. """

import datetime
import os
import threading
import time
import requests

from django.core.cache import cache
from django.core.files import File
from django.core.files.storage import FileSystemStorage
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from twf.models import Project
from twf.tasks.instant_tasks import save_instant_task_transkribus_export_download

PROGRESS_JOB_NAME = "extract-progress"
DETAIL_JOB_NAME = "extract-progress-detail"


def calculate_and_set_progress(processed_steps, total_steps, project_id, job_name):
    """This function calculates the progress of a process and saves it to the cache."""
    progress = (processed_steps / total_steps) * 100
    set_progress(progress, project_id, job_name)


def set_progress(progress, project_id, job_name):
    """This function saves the progress of a process to the cache."""
    cache.set(f"{project_id}_{job_name}", progress)


def base_event_stream(project_id, job_name, sleep_time=1):
    """This function streams the progress of a process to the client."""

    while True:
        progress = cache.get(f"{project_id}_{job_name}", 0)
        yield f"data: {progress}\n\n"
        if progress >= 100:
            break
        time.sleep(sleep_time)


@require_http_methods(["GET"])
@csrf_exempt
def ajax_transkribus_download_export(request):
    """Handles the request to start the download of the Transkribus export file."""
    project_id = request.session.get("project_id")
    session_key = request.session.session_key or "default_key"

    try:
        project = Project.objects.get(pk=project_id)
        url = project.job_download_url
    except Project.DoesNotExist:
        url = None

    def download_thread():
        """Download the file in a separate thread."""
        response = requests.get(url, stream=True, timeout=10)
        total_length = response.headers.get("content-length")
        if total_length is not None:
            total_length_int = int(total_length)
            downloaded = 0
            fs = FileSystemStorage()
            if not fs.exists("temp"):
                os.makedirs(fs.path("temp"))

            tmp_file_path = fs.path("temp/transkribus_export.zip")
            with open(tmp_file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=4096):
                    if chunk:  # filter out keep-alive chunks
                        f.write(chunk)
                        downloaded += len(chunk)
                        calculate_and_set_progress(
                            downloaded, total_length_int, project_id, PROGRESS_JOB_NAME
                        )

            with open(tmp_file_path, "rb") as f:
                project.downloaded_zip_file.save(
                    f"{project.collection_id}_export.zip", File(f)
                )

            set_progress(100, project_id, PROGRESS_JOB_NAME)
            project.downloaded_at = datetime.datetime.now()
            project.save(current_user=request.user)
            save_instant_task_transkribus_export_download(
                project, request.user, "The export file was downloaded."
            )

    threading.Thread(target=download_thread).start()
    return JsonResponse({"status": "Download started"})


def download_progress_view(request):
    """This function streams the progress of the extraction process to the client."""
    project_id = request.session.get("project_id")
    set_progress(0, project_id, PROGRESS_JOB_NAME)

    return StreamingHttpResponse(
        base_event_stream(project_id, PROGRESS_JOB_NAME),
        content_type="text/event-stream",
    )
