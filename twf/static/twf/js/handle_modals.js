$(document).ready(function () {
  // Initialize both modals
  const normalModal = new bootstrap.Modal($('#confirmModal')[0]);
  const dangerModal = new bootstrap.Modal($('#confirmDangerModal')[0]);

  // Single event listener for both types of modals
  $('.show-confirm-modal, .show-danger-modal').on('click', function (event) {
    event.preventDefault(); // Prevent default button behavior

    const button = $(this);
    const isDanger = button.hasClass('show-danger-modal');
    const modal = isDanger ? dangerModal : normalModal;
    const modalBody = isDanger ? '#confirmDangerModal .modal-body' : '#confirmModal .modal-body';
    const confirmButton = isDanger ? $('#confirmDangerActionButton') : $('#confirmActionButton');

    // Automatically find the closest form
    const form = button.closest("form");

    // **Validate form before showing modal**
    if (form.length > 0) {
      if (!form[0].checkValidity()) {
        form[0].reportValidity(); // Show native validation messages
        return; // Stop here, don't show modal
      }
    }

    // Set modal message dynamically
    const message = button.data('message') || 'Are you sure you want to proceed?';
    $(modalBody).html(message);

    let taskFunction = null;
    const redirectUrl = button.data('redirect-url');
    const startTaskUrl = button.data('start-url');
    const cancelTaskUrl = button.data('cancel-url');

    if (form.length > 0) {
      taskFunction = () => form.submit(); // Submit the form
    }
    if (redirectUrl) {
      taskFunction = () => (window.location.href = redirectUrl); // Redirect to the specified URL
    }
    if (startTaskUrl) {
      // Delete the metadata key from entry
      if(button.data('delete-md-key')) {
        const key = button.data('delete-md-key');

        taskFunction = () => {
          fetch(startTaskUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify({ key: key }),
          })
          .then(response => response.json())
          .then(() => {
            const entry = document.getElementById('metadata-' + key);
            if (entry) entry.remove();
          });
        };
      }
      // Start the Celery task
      else {
        const progressUrlBase = button.data('progress-url-base');
        const progressBarId = button.data('progress-bar-id');
        const logTextareaId = button.data('log-textarea-id');

        let formData = new FormData(form[0]); // Keep FormData intact

        taskFunction = () => {
          console.log("Starting Celery task at:", startTaskUrl, "with data:", formData);
          startTask(startTaskUrl, progressUrlBase, progressBarId, logTextareaId, formData);
        };
      }
    }
    if (cancelTaskUrl) {
      taskFunction = () => cancelTask(cancelTaskUrl, button.attr('id')); // Cancel the task
    }

    // Attach task function to confirm button
    confirmButton.off('click').on('click', function () {
      if (taskFunction) {
        taskFunction(); // Execute the task function (submit or redirect)
      }
      modal.hide();
    });

    // Show the appropriate modal
    modal.show();
  });
});
