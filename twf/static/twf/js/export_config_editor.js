document.addEventListener('DOMContentLoaded', function () {
    const editor = document.getElementById('export-config-editor');
    const hiddenConfigField = document.getElementsByName('config')[0];
    const exportTypeSelect = document.getElementById('id_export_type');

    let currentEditingField = null; // Will hold { sectionName, fieldDiv } info

    exportTypeSelect.setAttribute('data-prev-value', exportTypeSelect.value);

    const exportTypeSections = {
        'document': ['general', 'documents', 'pages'],
        'page': ['general', 'pages'],
        'collection': ['general', 'items'],
        'dictionary': ['general', 'entries'],
        'tag_report': ['general', 'tags'],
    };

    function capitalize(s) {
        return s.charAt(0).toUpperCase() + s.slice(1);
    }

    function initializeEditor(initialData = null, selectedExportType = 'document') {

        // Prevent showing sections if no valid export type selected
        if (!selectedExportType || selectedExportType === '--------') {
            editor.innerHTML = '';
            return;
        }

        editor.innerHTML = '';  // Clear current editor contents

        const sections = exportTypeSections[selectedExportType] || ['general'];

        sections.forEach(section => {
            const sectionDiv = document.createElement('div');
            sectionDiv.classList.add('card', 'mb-3');
            sectionDiv.innerHTML = `
                <div class="card-header">
                    <strong>${capitalize(section)} Section</strong>
                </div>
                <div class="card-body" id="${section}-fields">
                </div>
                <div class="card-footer text-end">
                    <button type="button" class="btn btn-sm btn-danger me-2" onclick="resetSection('${section}')">Reset Section</button>
                    <button type="button" class="btn btn-sm btn-primary" onclick="addField('${section}')">Add Field</button>
                </div>
            `;
            editor.appendChild(sectionDiv);

            // Load existing fields if any
            if (initialData && initialData[section]) {
                Object.entries(initialData[section]).forEach(([exportKey, details]) => {
                    // Pass all details including options
                    const sourceType = details.source_type || '';
                    const source = details.source || '';
                    const fallback = details.fallback || '';
                    
                    console.log(`Loading field ${exportKey}:`, details);
                    // Pass the entire details object as the last parameter
                    addField(section, exportKey, sourceType, source, fallback, details);
                });
            }
        });
    }

    function askDangerConfirmation(message, onConfirm) {
        // Set modal body
        document.querySelector('#confirmDangerModal .modal-body').textContent = message;

        // Get the modal
        const dangerModal = new bootstrap.Modal(document.getElementById('confirmDangerModal'));
        dangerModal.show();

        // Replace the Confirm button handlers
        const confirmButton = document.getElementById('confirmDangerActionButton');
        confirmButton.replaceWith(confirmButton.cloneNode(true)); // clear old listeners
        const newConfirmButton = document.getElementById('confirmDangerActionButton');

        newConfirmButton.addEventListener('click', function () {
            dangerModal.hide();
            if (onConfirm) {
                onConfirm();
            }
        });
    }

    function updateFieldPreview(fieldDiv) {
        const keyInput = fieldDiv.querySelector('input[type="text"]');
        const preview = fieldDiv.querySelector('.source-preview');
        const sourceDataInput = fieldDiv.querySelector('.source-data');

        let valid = true;
        let summary = '';

        if (!keyInput || !sourceDataInput || !preview) return;

        const exportKey = keyInput.value.trim();
        if (!exportKey) {
            valid = false;
        }
        
        // Highlight nested key format nicely
        const isNested = exportKey.includes('.');
        const keyDisplay = isNested ? 
            `<span class="text-success">${exportKey}</span>` : 
            exportKey;

        try {
            const sourceInfo = JSON.parse(sourceDataInput.value);
            const type = sourceInfo.source_type;
            const source = sourceInfo.source;
            const fallback = sourceInfo.fallback;

            if (!type || !source) {
                valid = false;
            }

            if (type === 'static') {
                summary = `static: "${source}"`;
            } else if (type === 'metadata') {
                summary = `metadata: ${source}`;
            } else if (type === 'db_field') {
                summary = `db: ${source}`;
            } else if (type === 'text_content') {
                summary = `text: ${source}`;
            } else if (type === 'special') {
                summary = `special: ${source}`;
            }

            if (fallback) {
                summary += ` (fallback: "${fallback}")`;
            }
            
            // Add key path visualization for nested keys
            if (isNested) {
                const parts = exportKey.split('.');
                preview.innerHTML = `<strong>${keyDisplay}</strong>: ${summary}`;
            } else {
                preview.innerHTML = `<strong>${keyDisplay}</strong>: ${summary}`;
            }
        } catch (e) {
            valid = false;
            preview.innerHTML = 'Invalid source data';
        }

        if (valid) {
            fieldDiv.classList.remove('border', 'border-danger');
        } else {
            fieldDiv.classList.add('border', 'border-danger');
        }
    }


    function renderSourceOptions(section, sourceType, selectedSource) {
        const container = document.getElementById('source-options-field');
        container.innerHTML = '';

        if (sourceType === 'db_field') {
            const select = document.createElement('select');
            select.classList.add('form-select', 'mb-2');

            // Define hierarchical field access - parent fields available to children
            const sectionLabels = {
                'general': 'Project Fields',
                'documents': 'Document Fields',
                'pages': 'Page Fields',
                'items': 'Collection Item Fields',
                'entries': 'Dictionary Entry Fields',
                'tags': 'Tag Fields'
            };

            // Define which fields are available for each section (hierarchical)
            const availableFieldsMap = {
                'general': ['general'],  // Only project fields
                'documents': ['general', 'documents'],  // Project + Document fields
                'pages': ['general', 'documents', 'pages'],  // Project + Document + Page fields
                'items': ['general', 'items'],  // Project + Collection Item fields
                'entries': ['general', 'entries'],  // Project + Dictionary Entry fields
                'tags': ['general', 'tags']  // Project + Tag fields
            };

            // Get the list of field sections available for current section
            const availableSections = availableFieldsMap[section] || [section];

            // For each available section, create an optgroup
            availableSections.forEach(sectionKey => {
                const fields = allDbFields[sectionKey] || [];
                if (fields.length === 0) return;

                const optgroup = document.createElement('optgroup');
                optgroup.label = sectionLabels[sectionKey] || sectionKey;

                fields.forEach(fieldTuple => {
                    const [fieldName, label, sampleValue] = fieldTuple;
                    const option = document.createElement('option');
                    option.value = fieldName;
                    option.textContent = label;
                    if (fieldName === selectedSource) {
                        option.selected = true;
                    }
                    optgroup.appendChild(option);
                });

                select.appendChild(optgroup);
            });

            container.appendChild(select);

            // Sample value container
            const sampleDiv = document.createElement('div');
            sampleDiv.classList.add('mt-2', 'text-muted');
            sampleDiv.id = 'sample-value-display';
            container.appendChild(sampleDiv);

            function updateSampleValue(selectedField) {
                // Search all sections for the sample value
                let sampleValue = '';
                Object.keys(allDbFields).forEach(sectionKey => {
                    const fields = allDbFields[sectionKey] || [];
                    const match = fields.find(([fieldName]) => fieldName === selectedField);
                    if (match) {
                        sampleValue = match[2] || 'No sample available';
                    }
                });
                sampleDiv.textContent = sampleValue ? `Sample: ${sampleValue}` : '';
            }

            // Initial
            updateSampleValue(select.value);

            select.addEventListener('change', function () {
                updateSampleValue(this.value);
            });
        }
        else if (sourceType === 'metadata') {
            container.innerHTML = '';

            let selectedService = null;
            let selectedKey = null;

            if (selectedSource && selectedSource.includes('.')) {
                [selectedService, selectedKey] = selectedSource.split('.', 2);
            }

            const isPageSection = (section === 'pages');
            const fields = isPageSection ? metadataPageFields : metadataDocFields;
            const services = Object.keys(fields);

            if (!selectedService && services.length > 0) {
                selectedService = services[0];
            }

            // Create Service Select
            const serviceSelect = document.createElement('select');
            serviceSelect.classList.add('form-select', 'mb-2');
            services.forEach(service => {
                const option = document.createElement('option');
                option.value = service;
                option.textContent = service;
                if (service === selectedService) {
                    option.selected = true;
                }
                serviceSelect.appendChild(option);
            });
            container.appendChild(serviceSelect);

            // Key Select/Input container
            const keySelectOrInputDiv = document.createElement('div');
            keySelectOrInputDiv.id = 'metadata-key-container';
            container.appendChild(keySelectOrInputDiv);

            // Sample display
            const sampleDiv = document.createElement('div');
            sampleDiv.classList.add('mt-2', 'text-muted');
            sampleDiv.id = 'sample-value-display';
            container.appendChild(sampleDiv);

            function renderKeySelect(service) {
                keySelectOrInputDiv.innerHTML = '';

                if (fields[service]) {
                    const keySelect = document.createElement('select');
                    keySelect.classList.add('form-select');

                    fields[service].forEach(([keyName, label, sampleValue]) => {
                        const option = document.createElement('option');
                        option.value = keyName;
                        option.textContent = label;

                        if (keyName === selectedKey) {
                            option.selected = true;
                        }
                        keySelect.appendChild(option);
                    });

                    keySelectOrInputDiv.appendChild(keySelect);

                    function updateSampleValue(selectedKeyName) {
                        const keys = fields[service] || [];
                        const match = keys.find(([keyName]) => keyName === selectedKeyName);
                        if (match) {
                            sampleDiv.textContent = `Sample: ${match[2] || 'No sample available'}`;
                        } else {
                            sampleDiv.textContent = '';
                        }
                    }

                    updateSampleValue(keySelect.value);

                    keySelect.addEventListener('change', function () {
                        updateSampleValue(this.value);
                    });

                } else {
                    const keyInput = document.createElement('input');
                    keyInput.type = 'text';
                    keyInput.classList.add('form-control');
                    keyInput.placeholder = 'Metadata Key';
                    keyInput.value = selectedKey || '';
                    keySelectOrInputDiv.appendChild(keyInput);

                    sampleDiv.textContent = 'No known keys for this service.';
                }
            }

            renderKeySelect(selectedService);

            serviceSelect.addEventListener('change', function () {
                renderKeySelect(this.value);
            });
        }
        else if (sourceType === 'static') {
            const input = document.createElement('input');
            input.type = 'text';
            input.classList.add('form-control');
            input.placeholder = 'Static Value';
            input.value = selectedSource || '';
            container.appendChild(input);
        }
        else if (sourceType === 'template') {
            const input = document.createElement('input');
            input.type = 'text';
            input.classList.add('form-control', 'mb-2');
            input.placeholder = 'Template string, e.g., vm_p_{document.document_id}_{page.tk_page_id}';
            input.value = selectedSource || '';
            container.appendChild(input);

            // Add help text with available fields
            const helpDiv = document.createElement('div');
            helpDiv.classList.add('mt-2', 'text-muted', 'small');
            helpDiv.innerHTML = `
                <strong>Template Syntax:</strong><br>
                Use {field_name} for placeholders. Available fields:<br>
                <ul class="mb-0">
                    <li><code>{project.id}</code> - Mosaic Project ID</li>
                    <li><code>{project.collection_id}</code> - Transkribus Collection ID</li>
                    <li><code>{project.title}</code> - Project Title</li>
                    <li><code>{document.id}</code> - Mosaic Document ID</li>
                    <li><code>{document.document_id}</code> - Transkribus Document ID</li>
                    <li><code>{document.title}</code> - Document Title</li>
                    <li><code>{page.id}</code> - Mosaic Page ID</li>
                    <li><code>{page.tk_page_id}</code> - Transkribus Page ID</li>
                    <li><code>{page.tk_page_number}</code> - Page Number</li>
                </ul>
                <strong>Example:</strong> <code>vm_p_{document.id}_{page.id}</code>
            `;
            container.appendChild(helpDiv);
        }
        else if (sourceType === 'text_content') {
            const select = document.createElement('select');
            select.classList.add('form-select');

            const textOptions = {
                general: [],
                documents: [
                    {option: 'doc_text', value: 'Document Text'},
                    {option: 'page_text_list', value: 'List of Page Texts'},
                    {option: 'page_anno_list', value: 'List of Lists of Annotations'}
                ],
                pages: [
                    {option: 'page_text', value: 'Page Text'},
                    {option: 'anno_list', value: 'List of Annotations'}
                ]
            };

            const values = textOptions[section] || [];

            values.forEach(opt => {
                const option = document.createElement('option');
                option.value = opt.option;
                option.textContent = opt.value;
                if (opt.option === selectedSource) {
                    option.selected = true;
                }
                select.appendChild(option);
            });

          container.appendChild(select);
        }
        else if (sourceType === 'special') {
            const select = document.createElement('select');
            select.classList.add('form-select');

            let fields;
            if (section === 'general') {
                const exportType = exportTypeSelect.value;
                if (exportType === 'collection') {
                    fields = specialFields['general_collection'] || [];
                } else {
                    fields = specialFields['general_project'] || [];
                }
            } else {
                fields = specialFields[section] || [];
            }
            fields.forEach(fieldTuple => {
                const [field, label] = Array.isArray(fieldTuple) ? fieldTuple : [fieldTuple, fieldTuple];
                const option = document.createElement('option');
                option.value = field;
                option.textContent = label;
                if (field === selectedSource) {
                   option.selected = true;
                }
                select.appendChild(option);
            });

            container.appendChild(select);
        }
    }

    function updateConditionalFields(modal, outputType = null) {
        // Support both jQuery and vanilla DOM elements
        const isJQuery = typeof modal.find === 'function';
        
        // Get the selected output type
        let type;
        if (outputType) {
            // Use provided output type if available
            type = outputType;
        } else if (isJQuery) {
            type = modal.find('.config-output-type').val();
        } else {
            const select = document.querySelector('.config-output-type');
            type = select ? select.value : 'string';
        }
        
        // Hide all conditional fields first
        const conditionalFields = document.querySelectorAll('.conditional-field');
        conditionalFields.forEach(field => field.style.display = 'none');
        
        // Show only the relevant ones
        if (type === 'string') {
            document.querySelectorAll('.string-options').forEach(el => el.style.display = 'flex');
        } else if (type === 'float') {
            document.querySelectorAll('.float-options').forEach(el => el.style.display = 'flex');
        } else if (type === 'integer') {
            document.querySelectorAll('.integer-options').forEach(el => el.style.display = 'flex');
        }
        
        console.log(`Showing fields for output type: ${type}`);
    }

    function updateExportTypeDependentFields(val) {
        const showCollection = (val === 'collection');
        const showDictionary = (val === 'dictionary');

        const collectionDiv = document.querySelector('#div_id_collection');
        const dictionaryDiv = document.querySelector('#div_id_dictionary');

        if (collectionDiv) {
            collectionDiv.style.display = showCollection ? 'block' : 'none';
        }
        if (dictionaryDiv) {
            dictionaryDiv.style.display = showDictionary ? 'block' : 'none';
        }
    }

    window.openSourceEditor = function(section, buttonElement) {
        const fieldDiv = buttonElement.closest('.row');

        const sourceDataInput = fieldDiv.querySelector('.source-data');
        let sourceType = 'db_field';
        let source = '';
        let fallback = '';
        let outputType = 'string';
        let format = '';
        let textCase = '';
        let precision = '';
        let nanLabel = '';
        let isNew = true;
        
        console.log("Opening source editor for", fieldDiv);
        
        // Load existing configuration if available
        if (sourceDataInput && sourceDataInput.value) {
            try {
                const sourceInfo = JSON.parse(sourceDataInput.value);
                console.log("Loaded source data:", sourceInfo);
                
                // Load main required values
                sourceType = sourceInfo.source_type || 'db_field';
                source = sourceInfo.source || '';
                
                // Load all options (fallback is just one of many options)
                fallback = sourceInfo.fallback || '';
                outputType = sourceInfo.output_type || 'string';
                
                // Load type-specific options
                if (outputType === 'string') {
                    format = sourceInfo.format || '';
                    textCase = sourceInfo.text_case || '';
                } 
                else if (outputType === 'float') {
                    precision = sourceInfo.precision !== undefined ? sourceInfo.precision : '';
                }
                else if (outputType === 'integer') {
                    nanLabel = sourceInfo.nan_label || '';
                }

                const nonEmpty = sourceType && source;
                isNew = !nonEmpty;
            } catch (e) {
                console.error('Invalid source-data JSON:', e, sourceDataInput.value);
            }
        }

        console.log('Field details:', {
            isNew,
            sourceType,
            source,
            fallback,
            outputType,
            format,
            textCase,
            precision,
            nanLabel
        });

        // Set source type
        const sourceTypeSelect = document.getElementById('source-type');
        sourceTypeSelect.value = sourceType;

        // Set all options fields
        const fallbackInput = document.getElementById('fallback-value');
        fallbackInput.value = fallback;
        
        // Set output type 
        const outputTypeSelect = document.querySelector('.config-output-type');
        if (outputTypeSelect) {
            outputTypeSelect.value = outputType;
        }
        
        // Set String format options
        const formatInput = document.querySelector('.config-format');
        if (formatInput) {
            formatInput.value = format;
        }
        
        // Set text case options
        const textCaseSelect = document.querySelector('.config-text-case');
        if (textCaseSelect) {
            textCaseSelect.value = textCase;
        }
        
        // Set precision option for float
        const precisionInput = document.querySelector('.config-precision');
        if (precisionInput) {
            precisionInput.value = precision;
        }
        
        // Set NaN label for integer
        const nanLabelInput = document.querySelector('.config-int-nan');
        if (nanLabelInput) {
            nanLabelInput.value = nanLabel;
        }

        const sectionLabels = {
          general: "Project",
          documents: "Document",
          pages: "Page",
          items: "Collection Item",
          entries: "Dictionary Entry",
          tags: "Tag"
        };

        const sectionName = sectionLabels[section] || section.charAt(0).toUpperCase() + section.slice(1);
        document.getElementById('sourceEditorModalLabel').textContent = `Edit ${sectionName} Source`;

        const keyInput = fieldDiv.querySelector('input[type="text"]');
        const keyName = keyInput ? keyInput.value.trim() : '';
        document.getElementById('source-key-display').textContent = keyName ? `Export Key: "${keyName}"` : '';

        const disallowedTypes = [];
        if (section === 'general') {
          disallowedTypes.push('metadata', 'text_content');
        }

        Array.from(sourceTypeSelect.options).forEach(option => {
          option.disabled = disallowedTypes.includes(option.value);
        });

        // Set up dynamic source options initially
        renderSourceOptions(section, sourceType, source);

        // --- VERY IMPORTANT: Attach change listener dynamically ---
        if (sourceTypeSelect._changeListener) {
            sourceTypeSelect.removeEventListener('change', sourceTypeSelect._changeListener);
        }

        const changeListener = function() {
            renderSourceOptions(section, this.value, '');
        };

        sourceTypeSelect.addEventListener('change', changeListener);
        sourceTypeSelect._changeListener = changeListener;
        // ----------------------------------------------------------

        // Show/hide conditional fields based on output type
        const modalEl = document.getElementById('sourceEditorModal');
        updateConditionalFields(modalEl, outputType);

        currentEditingField = { section, fieldDiv };

        const modal = new bootstrap.Modal(modalEl);
        modal.show();
    };



    window.addField = function(section, exportKey = '', sourceType = '', source = '', fallback = '', details = null) {
        const container = document.getElementById(`${section}-fields`);
        const fieldDiv = document.createElement('div');
        fieldDiv.classList.add('row', 'mb-2');

        // Use all properties from details if provided, otherwise create basic sourceInfo
        let sourceInfo;
        if (details && typeof details === 'object') {
            sourceInfo = {...details};  // Clone the details object
            
            // Ensure core properties are set (source_type and source are the main values)
            sourceInfo.source_type = sourceType;
            sourceInfo.source = source;
            
            // Fallback is just another option, only set if explicitly provided in this call
            if (fallback) sourceInfo.fallback = fallback;
            
            console.log("Using provided details for field:", sourceInfo);
        } else {
            // Create basic sourceInfo with just the required main values
            sourceInfo = {
                source_type: sourceType,
                source: source
            };
            
            // Only add fallback if it's provided (it's an optional field)
            if (fallback) sourceInfo.fallback = fallback;
        }

        fieldDiv.innerHTML = `
            <div class="col-5">
                <input type="text" class="form-control" placeholder="Export Key (use dots for nesting)" value="${exportKey}">
                <small class="text-muted">For nested keys use: parent.child.leaf</small>
            </div>
            <div class="col-5">
                <button type="button" class="btn btn-outline-secondary btn-sm" onclick="openSourceEditor('${section}', this)">Edit Source</button>
                <input type="hidden" class="source-data" value='${JSON.stringify(sourceInfo)}'>
                <div class="source-preview small text-muted mt-1"></div>
            </div>
            <div class="col-2">
                <button type="button" class="btn btn-danger btn-sm" onclick="this.parentElement.parentElement.remove()">X</button>
            </div>
        `;

        container.appendChild(fieldDiv);
        updateFieldPreview(fieldDiv);

        const keyInput = fieldDiv.querySelector('input[type="text"]');
            keyInput.addEventListener('input', () => {
                updateFieldPreview(fieldDiv);
        });
    }


    window.resetSection = function(section) {
        const container = document.getElementById(`${section}-fields`);
        if (container) {
            askDangerConfirmation(`Are you sure you want to reset all fields in the "${capitalize(section)}" section?`, function () {
                container.innerHTML = '';
            });
        }
    }

    document.getElementById('save-source-button').addEventListener('click', function () {
        if (!currentEditingField) return;

        // Reset all validation states
        document.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
        
        // Validate form before saving
        let formValid = true;
        
        const sourceType = document.getElementById('source-type').value;
        let source = '';

        // Get the source value from the appropriate input/select field
        const sourceContainer = document.getElementById('source-options-field');
        if (sourceType === 'metadata') {
            const serviceSelect = sourceContainer.querySelector('select');
            const keyInputOrSelect = sourceContainer.querySelector('#metadata-key-container select, #metadata-key-container input');

            const service = serviceSelect ? serviceSelect.value.trim() : '';
            const key = keyInputOrSelect ? keyInputOrSelect.value.trim() : '';

            if (service && key) {
                source = `${service}.${key}`;
            }
        } else {
            const sourceInput = sourceContainer.querySelector('input, select');
            source = sourceInput ? sourceInput.value.trim() : '';
        }
        
        // Validate source is not empty
        if (!source) {
            // Mark source input as invalid
            const sourceInput = sourceContainer.querySelector('input, select');
            if (sourceInput) {
                sourceInput.classList.add('is-invalid');
                formValid = false;
            }
        }
        
        // Get any existing sourceData from the hidden input to preserve other properties
        const sourceDataInput = currentEditingField.fieldDiv.querySelector('.source-data');
        let sourceData = {};
        
        if (sourceDataInput && sourceDataInput.value) {
            try {
                sourceData = JSON.parse(sourceDataInput.value);
            } catch (e) {
                console.error('Invalid existing source data:', e);
            }
        }
        
        // Update the core properties - source_type and source are the main values
        sourceData.source_type = sourceType;
        sourceData.source = source;

        // Gather all options - fallback is just another option like output_type, format, etc.
        const fallback = document.getElementById('fallback-value').value.trim();
        // Always set fallback to whatever value is in the form (even if empty)
        sourceData.fallback = fallback;
        
        // Get output formatting options
        const outputType = document.querySelector('.config-output-type')?.value;
        if (outputType) {
            sourceData.output_type = outputType;
            
            // Add type-specific options
            if (outputType === 'string') {
                const formatInput = document.querySelector('.config-format');
                const format = formatInput?.value.trim();
                
                // Validate string format contains {} if not empty
                if (format && !format.includes('{}')) {
                    formatInput.classList.add('is-invalid');
                    formValid = false;
                } else {
                    // Always set format (even if empty) to overwrite existing
                    sourceData.format = format;
                }
                
                const textCase = document.querySelector('.config-text-case')?.value;
                sourceData.text_case = textCase || "";
                
                // Remove non-string options that might exist from previous change
                delete sourceData.precision;
                delete sourceData.nan_label;
            } 
            else if (outputType === 'float') {
                const precisionInput = document.querySelector('.config-precision');
                const precision = precisionInput?.value.trim();
                
                // Validate precision is a number between 0 and 10
                if (precision !== '') {
                    const precisionNum = parseInt(precision);
                    if (isNaN(precisionNum) || precisionNum < 0 || precisionNum > 10) {
                        precisionInput.classList.add('is-invalid');
                        formValid = false;
                    } else {
                        sourceData.precision = precisionNum;
                    }
                } else {
                    sourceData.precision = "";
                }
                
                // Remove non-float options
                delete sourceData.format;
                delete sourceData.text_case;
                delete sourceData.nan_label;
            }
            else if (outputType === 'integer') {
                const nanLabel = document.querySelector('.config-int-nan')?.value.trim();
                sourceData.nan_label = nanLabel || "";
                
                // Remove non-integer options
                delete sourceData.format;
                delete sourceData.text_case;
                delete sourceData.precision;
            }
        }

        // If validation failed, don't save and return
        if (!formValid) {
            return;
        }
        
        console.log("Saving source data:", sourceData);

        // Save the updated sourceData to the hidden input
        sourceDataInput.value = JSON.stringify(sourceData);
        
        // Update the preview to show the new source info
        updateFieldPreview(currentEditingField.fieldDiv);

        const modal = bootstrap.Modal.getInstance(document.getElementById('sourceEditorModal'));
        modal.hide();
    });


    const form = document.getElementById('export-configuration-form');
    if (!form) {
        console.error('Form not found — check placement of script or crispy output.');
    } else {
        console.log("Form found", form);
        form.addEventListener('submit', function (event) {
            event.preventDefault();
            console.log("SAVE FORM");

            const hiddenConfigField = form.querySelector('input[name="config"]');
            if (!hiddenConfigField) {
                console.error('Missing hidden config input!');
                return;
            }

            const result = {};
            const currentSections = exportTypeSections[exportTypeSelect.value] || ['general'];

            currentSections.forEach(section => {
                const sectionFields = document.getElementById(`${section}-fields`)?.querySelectorAll('.row') || [];
                if (sectionFields.length > 0) {
                    result[section] = {};
                    sectionFields.forEach(field => {
                        const keyInput = field.querySelector('input[type="text"]');
                        const sourceDataInput = field.querySelector('.source-data');

                        if (!keyInput || !sourceDataInput) return;

                        const exportKey = keyInput.value.trim();
                        let sourceInfo = {};

                        try {
                            sourceInfo = JSON.parse(sourceDataInput.value);
                            console.log(`Adding field ${exportKey} with source data:`, sourceInfo);
                        } catch (e) {
                            console.error('Invalid source-data JSON:', e);
                            return;
                        }

                        if (exportKey && sourceInfo.source_type && sourceInfo.source) {
                            // Ensure we preserve all properties of sourceInfo
                            result[section][exportKey] = sourceInfo;
                        }
                    });
                }
            });

            console.log("Final form configuration:", result);
            hiddenConfigField.value = JSON.stringify(result);
            form.submit();
        });
    }


    // Listen for export_type changes
    exportTypeSelect.addEventListener('change', function () {
        const currentSections = exportTypeSections[this.getAttribute('data-prev-value')] || ['general'];
        const val = this.value;
        updateExportTypeDependentFields(val);
        let hasExistingFields = false;

        // Check if any fields exist
        currentSections.forEach(section => {
            const sectionFields = document.getElementById(`${section}-fields`);
            if (sectionFields && sectionFields.querySelector('.row')) {
                hasExistingFields = true;
            }
        });

        if (hasExistingFields) {
            askDangerConfirmation(
                "You have unsaved field mappings. Changing the export type will clear them. Continue?",
                () => {
                    initializeEditor(null, this.value);
                    this.setAttribute('data-prev-value', this.value);
                }
            );
        } else {
            initializeEditor(null, this.value);
            this.setAttribute('data-prev-value', this.value);
        }
    });

    // Listen for changes in the output type select
    const outputTypeSelect = document.querySelector('.config-output-type');
    if (outputTypeSelect) {
        outputTypeSelect.addEventListener('change', function() {
            // Reset validation states when changing output type
            document.querySelectorAll('.is-invalid').forEach(el => {
                el.classList.remove('is-invalid');
            });
            
            // Hide/show the appropriate conditional fields
            updateConditionalFields(document.getElementById('sourceEditorModal'));
        });
    }

    // Initial form state
    updateExportTypeDependentFields(exportTypeSelect.value);

    // Load existing config if available
    try {
        const initialData = JSON.parse(hiddenConfigField.value);
        initializeEditor(initialData, exportTypeSelect.value);
    } catch (e) {
        initializeEditor(null, exportTypeSelect.value);
    }


});
