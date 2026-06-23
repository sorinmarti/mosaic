$(document).ready(function() {
    const aiConfigSelect = document.querySelector("select[name='ai_configuration']");
    const previewCard = document.getElementById("ai-config-preview");

    // If AI configuration selector doesn't exist, exit
    if (!aiConfigSelect) {
        console.warn("AI Configuration Manager: AI config selector not found, skipping initialization.");
        return;
    }

    // Initialize Select2 for AI configuration dropdown with custom formatting
    $("#id_ai_configuration").select2({
        templateResult: formatAIConfigDropdown,
        templateSelection: formatAIConfigSelection,
        width: '100%'
    });

    // Load AI Configuration preview when selected
    $(aiConfigSelect).on("change", function() {
        const configId = this.value;

        if (!configId) {
            // User selected empty option, hide preview
            if (previewCard) {
                previewCard.style.display = 'none';
            }
            return;
        }

        // Show loading indicator
        do_alert("Loading AI Configuration...", "info");

        fetch(`/ajax/ai-config/${configId}/`, {
            method: "GET",
            headers: {
                "X-CSRFToken": getCSRFToken(),
            },
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                do_alert("Error loading AI Configuration: " + data.error, "danger");
                if (previewCard) {
                    previewCard.style.display = 'none';
                }
                return;
            }

            // Display preview
            if (previewCard) {
                document.getElementById("preview-provider").textContent = data.provider || "N/A";
                document.getElementById("preview-model").textContent = data.model || "N/A";
                document.getElementById("preview-temperature").textContent = data.temperature || "0.7";
                document.getElementById("preview-max-tokens").textContent = data.max_tokens || "1000";
                document.getElementById("preview-role").textContent = data.system_role || "No system role defined";
                document.getElementById("preview-prompt").textContent = data.prompt_template || "No prompt template defined";

                previewCard.style.display = 'block';
            }

            do_alert(`Loaded: ${data.name}`, "success");
        })
        .catch(error => {
            console.error("Error loading AI configuration:", error);
            do_alert("Error loading AI configuration.", "danger");
            if (previewCard) {
                previewCard.style.display = 'none';
            }
        });
    });

    // CSRF Token Helper Function
    function getCSRFToken() {
        return document.cookie.split("; ")
            .find(row => row.startsWith("csrftoken="))
            ?.split("=")[1] || "";
    }

    function do_alert(message, type="info") {
        const messagesContainer = document.querySelector(".messages");

        if (!messagesContainer) {
            console.warn("Messages container not found.");
            return;
        }

        // Bootstrap alert HTML
        const alertDiv = document.createElement("div");
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.role = "alert";
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;

        messagesContainer.appendChild(alertDiv);

        // Automatically remove the alert after 5 seconds
        setTimeout(() => {
            $(alertDiv).alert('close');
        }, 5000);
    }

    // Format AI Config dropdown to show name and provider in the dropdown list
    function formatAIConfigDropdown(option) {
        if (!option.id) {
            return option.text;
        }

        const $option = $(option.element);
        const provider = $option.attr("data-provider") || "";
        const model = $option.attr("data-model") || "";

        if (provider || model) {
            return $(`
                <div>
                    <strong>${option.text}</strong>
                    <br>
                    <small class="text-muted">${provider} - ${model}</small>
                </div>
            `);
        }

        return option.text;
    }

    // Format selected AI Config (shown in the select box when closed)
    function formatAIConfigSelection(option) {
        if (!option.id) {
            return option.text;
        }
        return option.text;
    }
});