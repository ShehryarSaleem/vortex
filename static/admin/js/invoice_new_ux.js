(function($) {
    'use strict';

    console.log('=== Invoice UX Script Loading ===');

    var selectedApplications = [];
    var availableApplications = [];

    // Get jQuery - try multiple sources
    var $ = null;
    if (typeof django !== 'undefined' && django.jQuery) {
        $ = django.jQuery;
        console.log('Using django.jQuery');
    } else if (typeof jQuery !== 'undefined') {
        $ = jQuery;
        console.log('Using jQuery');
    } else if (typeof window.$ !== 'undefined') {
        $ = window.$;
        console.log('Using window.$');
    } else {
        console.error('jQuery not found!');
        return;
    }

    function getSelectedApplicationsTotal() {
        var total = 0;
        $.each(selectedApplications, function(index, app) {
            total += parseFloat(app.price) || 0;
        });
        return total;
    }

    function getDiscountValue() {
        var discountField = $('#id_discount');
        var discountVal = 0;
        if (discountField.length) {
            var parsed = parseFloat(discountField.val());
            if (!isNaN(parsed)) {
                discountVal = parsed;
            }
        }
        return discountVal;
    }

    // Get CSRF token
    function getCSRFToken() {
        return $('[name=csrfmiddlewaretoken]').val() ||
               $('input[name="csrfmiddlewaretoken"]').val() ||
               '';
    }

    // Load available applications for a client
    function loadAvailableApplications(clientId, invoiceId) {
        console.log('=== loadAvailableApplications ===');
        console.log('Client ID:', clientId);
        console.log('Invoice ID:', invoiceId);

        if (!clientId || clientId === '' || clientId === null) {
            console.log('No client ID, clearing dropdown');
            var select = $('#available-applications');
            if (select.length === 0) {
                select = $('select[name="available_applications"]');
            }
            select.empty().append('<option value="">-- Select a client first --</option>');
            select.prop('disabled', true);
            select.trigger('change');
            $('#add-application-btn, #btn_add_application').prop('disabled', true);
            availableApplications = [];
            selectedApplications = [];
            renderSelectedApplications();
            return;
        }

        // Construct absolute URL to avoid relative URL resolution issues
        // Get the base admin URL from the current page
        var baseUrl = window.location.origin;
        var adminPath = '/admin/core/invoice/available-applications/';
        var url = baseUrl + adminPath + '?client_id=' + encodeURIComponent(clientId);
        if (invoiceId && invoiceId !== 0) {
            url += '&invoice_id=' + encodeURIComponent(invoiceId);
        }

        console.log('AJAX URL:', url);

        // Show loading state
        var select = $('#available-applications');
        if (select.length === 0) {
            select = $('select[name="available_applications"]');
        }
        if (select.length === 0) {
            console.error('Select element not found!');
            return;
        }
        select.empty().append('<option value="">Loading...</option>').prop('disabled', true);
        select.trigger('change'); // Update widget if enhanced
        $('#btn_add_application').prop('disabled', true);
        $('#applications-error').hide();

        $.ajax({
            url: url,
            type: 'GET',
            dataType: 'json',
            beforeSend: function(xhr) {
                var token = getCSRFToken();
                if (token) {
                    xhr.setRequestHeader("X-CSRFToken", token);
                }
            },
            success: function(response) {
                console.log('=== AJAX Success ===');
                console.log('Response:', response);

                if (response.error) {
                    console.error('Server error:', response.error);
                    $('#applications-error').text('Error: ' + response.error).show();
                    var select = $('#available-applications');
                    if (select.length === 0) {
                        select = $('select[name="available_applications"]');
                    }
                    select.empty().append('<option value="">Error loading applications</option>');
                    select.prop('disabled', true);
                    select.trigger('change');
                    $('#add-application-btn, #btn_add_application').prop('disabled', true);
                    return;
                }

                availableApplications = response.available_applications || [];
                console.log('Loaded applications:', availableApplications.length);

                // Ensure each app has required properties
                $.each(availableApplications, function(index, app) {
                    app.id = parseInt(app.id);
                    // Handle price as string "120.00" or number
                    app.price = parseFloat(app.price) || 0;
                    app.currency = app.currency || 'GBP';
                    // Use 'name' field from API response
                    if (app.name) {
                        app.display = app.name;
                        app.text = app.name;
                    } else if (!app.display && app.text) {
                        app.display = app.text;
                        app.name = app.text;
                    } else if (!app.display) {
                        app.display = 'Application #' + app.id;
                        app.name = app.display;
                        app.text = app.display;
                    }
                    // Ensure all required fields exist
                    if (!app.name) app.name = app.display || 'Application #' + app.id;
                    if (!app.display) app.display = app.name;
                    if (!app.text) app.text = app.name;
                });

                console.log('Processed available applications:', availableApplications);

                updateAvailableDropdown();
            },
            error: function(xhr, status, error) {
                console.error('=== AJAX Error ===');
                console.error('Status:', status);
                console.error('Error:', error);
                console.error('Response:', xhr.responseText);
                console.error('Status Code:', xhr.status);

                var errorMsg = 'Error loading applications';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMsg = xhr.responseJSON.error;
                } else if (xhr.status === 404) {
                    errorMsg = 'Client not found';
                } else if (xhr.status === 403) {
                    errorMsg = 'Permission denied';
                }

                $('#applications-error').text(errorMsg).show();
                var select = $('#available-applications');
                if (select.length === 0) {
                    select = $('select[name="available_applications"]');
                }
                select.empty().append('<option value="">Error loading applications</option>');
                select.prop('disabled', true);
                select.trigger('change');
                $('#add-application-btn, #btn_add_application').prop('disabled', true);
            }
        });
    }

    // Update the available applications dropdown
    function updateAvailableDropdown() {
        console.log('=== updateAvailableDropdown ===');
        console.log('Available apps count:', availableApplications.length);

        // Find the actual select element - try multiple selectors
        var select = $('#available-applications');
        if (select.length === 0) {
            // Fallback: try to find by name or other attributes
            select = $('select[name="available_applications"]');
        }
        if (select.length === 0) {
            // Try Django's auto-generated ID format
            select = $('#id_available_applications');
        }

        if (select.length === 0) {
            console.error('Select element not found! Tried: #available-applications, select[name="available_applications"], #id_available_applications');
            return;
        }

        var selectElement = select[0]; // Get native DOM element

        // Check if Unfold/Select2 is wrapping the select
        var isSelect2 = select.hasClass('select2-hidden-accessible') || select.parent().hasClass('select2-container');
        var isUnfold = select.closest('.unfold-select-wrapper, .select-wrapper').length > 0;

        // Clear existing options using native DOM for reliability
        selectElement.innerHTML = '';

        // Build options HTML
        var optionsHtml = '';
        if (availableApplications.length === 0) {
            optionsHtml = '<option value="">No applications available for this client</option>';
            select.prop('disabled', true);
            $('#add-application-btn, #btn_add_application').prop('disabled', true);
        } else {
            select.prop('disabled', false);
            optionsHtml = '<option value="">-- Select an application --</option>';
            $.each(availableApplications, function(index, app) {
                // Format: {country/type} — {status} — {price}
                var displayText = app.display || app.name || app.text || 'Application #' + app.id;
                var price = parseFloat(app.price) || 0;
                var currency = app.currency || 'GBP';
                var currencySymbol = currency === 'GBP' ? '£' : currency === 'USD' ? '$' : currency === 'EUR' ? '€' : currency + ' ';
                var priceText = price > 0 ? currencySymbol + price.toFixed(2) : 'No price';
                // Parse display text to extract type and status if available
                // Format expected: "Schengen - Initial" or similar
                var parts = displayText.split(' - ');
                var typePart = parts[0] || displayText;
                var statusPart = parts[1] || '';
                var optionText = typePart;
                if (statusPart) {
                    optionText += ' — ' + statusPart;
                }
                optionText += ' — ' + priceText;
                optionsHtml += '<option value="' + app.id + '">' + optionText + '</option>';
            });
            updateAddButtonState();
        }

        // Set options using native DOM for reliability
        selectElement.innerHTML = optionsHtml;

        // Force UI update - multiple approaches for maximum compatibility
        select.val('').trigger('change');

        // If Select2 is being used, refresh it
        if (isSelect2 && typeof $.fn.select2 === 'function') {
            try {
                select.select2('destroy');
                select.select2();
                console.log('Select2 refreshed');
            } catch (e) {
                console.log('Select2 refresh error:', e);
            }
        }

        // If Choices.js is being used (Unfold might use this)
        if (typeof Choices !== 'undefined' && selectElement.choices) {
            try {
                selectElement.choices.destroy();
                new Choices(selectElement, {
                    searchEnabled: false,
                    removeItemButton: false
                });
                console.log('Choices.js refreshed');
            } catch (e) {
                console.log('Choices.js refresh error:', e);
            }
        }

        // Trigger custom events for Unfold/widget refresh
        select.trigger('select2:reload');
        select.trigger('unfold:refresh');
        select.trigger('input');
        select.trigger('update');

        // Force browser reflow (helps with some widgets)
        var height = selectElement.offsetHeight;

        // Additional refresh for stubborn widgets - small delay to ensure DOM is updated
        setTimeout(function() {
            select.trigger('change');
            // Try to find and update any visible wrapper
            var wrapper = select.parent();
            if (wrapper.hasClass('select2-container') || wrapper.hasClass('choices')) {
                wrapper.trigger('update');
            }
            console.log('Dropdown refresh triggered. Options count:', select.find('option').length);
            console.log('Current select value:', select.val());
        }, 100);

        console.log('Dropdown updated. Options count:', select.find('option').length);
        console.log('Select element:', selectElement);
    }

    // Update add button state
    function updateAddButtonState() {
        var select = $('#available-applications');
        if (select.length === 0) {
            select = $('select[name="available_applications"]');
        }
        if (select.length === 0) {
            select = $('#id_available_applications');
        }
        var selectedId = select.val();
        var isDisabled = !selectedId || selectedId === '' || selectedId === null;
        var button = $('#add-application-btn, #btn_add_application');
        button.prop('disabled', isDisabled);
        console.log('Add button state updated. Selected ID:', selectedId, 'Disabled:', isDisabled);
    }

    // Render selected applications list
    function renderSelectedApplications() {
        console.log('=== renderSelectedApplications ===');
        console.log('Selected apps count:', selectedApplications.length);
        console.log('Selected apps data:', selectedApplications);

        // Try multiple selectors to find the container
        var container = $('#selected_applications_container');
        if (container.length === 0) {
            container = $('#selected-applications-container');
        }
        if (container.length === 0) {
            container = $('.selected-applications').find('div').first();
        }

        if (container.length === 0) {
            console.error('Selected applications container not found!');
            return;
        }

        console.log('Container found:', container.length);

        if (selectedApplications.length === 0) {
            console.log('No selected applications, showing empty state');
            container.html(
                '<div class="empty-state" style="text-align: center; padding: 20px; color: #6b7280; font-size: 14px;">' +
                '<p style="margin: 0;">No applications selected. Select a client and add applications above.</p>' +
                '</div>'
            );
            updateSubtotal(0);
            return;
        }

        console.log('Rendering', selectedApplications.length, 'selected applications');

        var html = '<div class="selected-applications-list" style="display: flex; flex-direction: column; gap: 10px;">';
        var total = 0;
        var currency = 'GBP'; // Default currency

        $.each(selectedApplications, function(index, app) {
            var price = parseFloat(app.price) || 0;
            total += price;
            if (app.currency) {
                currency = app.currency;
            }
            var displayText = app.display || app.name || app.text || 'Application #' + app.id;
            var currencySymbol = currency === 'GBP' ? '£' : currency === 'USD' ? '$' : currency === 'EUR' ? '€' : currency + ' ';
            var priceText = price > 0 ? currencySymbol + price.toFixed(2) : '<span style="color: #dc3545;">⚠️ No price</span>';

            html += '<div class="selected-app-item" data-app-id="' + app.id + '" style="' +
                'display: flex; justify-content: space-between; align-items: center; ' +
                'padding: 12px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px;">';
            html += '<div style="flex: 1;">';
            html += '<div style="font-weight: 500; color: #111827; margin-bottom: 4px;">' + displayText + '</div>';
            html += '<div style="font-size: 14px; color: #6b7280;">Price: ' + priceText + '</div>';
            html += '</div>';
            html += '<button type="button" class="remove-btn" data-app-id="' + app.id + '" style="' +
                'padding: 6px 12px; background: #ef4444; color: white; border: none; ' +
                'border-radius: 4px; cursor: pointer; font-size: 13px; margin-left: 12px;">Remove</button>';
            html += '</div>';
        });

        html += '</div>';
        container.html(html);

        updateSubtotal(total);
    }

    // Update subtotal
    function updateSubtotal(amount) {
        var total = parseFloat(amount) || 0;
        var discountVal = getDiscountValue();
        var totalAfterDiscount = total - discountVal;
        if (totalAfterDiscount < 0) {
            totalAfterDiscount = 0;
        }
        var taxRateField = $('#id_tax_rate');
        var taxRate = 0;
        if (taxRateField.length) {
            var parsedTax = parseFloat(taxRateField.val());
            if (!isNaN(parsedTax)) {
                taxRate = parsedTax;
            }
        }
        var taxAmount = (totalAfterDiscount * taxRate) / 100;
        var totalWithTax = totalAfterDiscount + taxAmount;

        $('#items-subtotal-display').text(total.toFixed(2));
        $('#discount-display').text(discountVal.toFixed(2));
        $('#subtotal-display').text(totalAfterDiscount.toFixed(2));

        var subtotalField = $('#id_subtotal');
        if (subtotalField.length) {
            var wasReadonly = subtotalField.prop('readonly');
            subtotalField.prop('readonly', false);
            subtotalField.val(total.toFixed(2));
            if (wasReadonly) {
                subtotalField.prop('readonly', true);
            }
        }

        var taxAmountField = $('#id_tax_amount');
        if (taxAmountField.length) {
            var taxReadonly = taxAmountField.prop('readonly');
            taxAmountField.prop('readonly', false);
            taxAmountField.val(taxAmount.toFixed(2));
            if (taxReadonly) {
                taxAmountField.prop('readonly', true);
            }
        }

        var totalField = $('#id_total_amount');
        if (totalField.length) {
            var totalReadonly = totalField.prop('readonly');
            totalField.prop('readonly', false);
            totalField.val(totalWithTax.toFixed(2));
            if (totalReadonly) {
                totalField.prop('readonly', true);
            }
        }

        updateSelectedApplicationsField();
    }

    // Update hidden field
    function updateSelectedApplicationsField() {
        var hiddenField = $('#selected-applications-data');
        if (hiddenField.length) {
            hiddenField.val(JSON.stringify(selectedApplications));
        }
    }

    // Add application
    function addApplication(visaAppId) {
        console.log('=== addApplication ===');
        console.log('Application ID:', visaAppId);

        var invoiceId = window.INVOICE_ID || null;

        // Check for duplicates
        var alreadySelected = selectedApplications.some(function(app) {
            return parseInt(app.id) === parseInt(visaAppId);
        });

        if (alreadySelected) {
            $('#applications-error').text('This application is already selected').show();
            setTimeout(function() {
                $('#applications-error').fadeOut();
            }, 3000);
            return;
        }

        if (!invoiceId || invoiceId === 0) {
            // For new invoices, add to local array
            console.log('Adding application for new invoice. Available apps:', availableApplications.length);
            var app = availableApplications.find(function(a) {
                return parseInt(a.id) === parseInt(visaAppId);
            });

            if (app) {
                console.log('Found application to add:', app);
                // Create a proper copy with all required fields
                var appCopy = {
                    id: parseInt(app.id),
                    name: app.name || app.display || app.text || 'Application #' + app.id,
                    display: app.display || app.name || app.text || 'Application #' + app.id,
                    text: app.text || app.name || app.display || 'Application #' + app.id,
                    price: parseFloat(app.price) || 0,
                    currency: app.currency || 'GBP'
                };
                selectedApplications.push(appCopy);
                console.log('Added to selectedApplications. New count:', selectedApplications.length);

                // Remove from available
                availableApplications = availableApplications.filter(function(a) {
                    return parseInt(a.id) !== parseInt(visaAppId);
                });
                console.log('Removed from available. Remaining available:', availableApplications.length);

                updateAvailableDropdown();
                renderSelectedApplications();
                $('#applications-error').hide();

                console.log('Application added successfully. Total selected:', selectedApplications.length);
            } else {
                console.error('Application not found in availableApplications. ID:', visaAppId);
                console.log('Available applications:', availableApplications);
                $('#applications-error').text('Application not found in available list').show();
            }
            return;
        }

        // For existing invoices, use AJAX
        var addUrl = window.location.origin + '/admin/core/invoice/' + invoiceId + '/add-application/';
        $.ajax({
            url: addUrl,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ visa_application_id: visaAppId }),
            beforeSend: function(xhr) {
                var token = getCSRFToken();
                if (token) {
                    xhr.setRequestHeader("X-CSRFToken", token);
                }
            },
            success: function(response) {
                console.log('Application added via AJAX:', response);
                if (response.selected_applications) {
                    selectedApplications = response.selected_applications;
                    $.each(selectedApplications, function(i, app) {
                        app.price = parseFloat(app.price) || 0;
                    });
                }
                loadAvailableApplications(window.CLIENT_ID, invoiceId);
                renderSelectedApplications();
                $('#applications-error').hide();
            },
            error: function(xhr, status, error) {
                console.error('Error adding application:', error);
                var errorMsg = 'Error adding application';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMsg = xhr.responseJSON.error;
                }
                $('#applications-error').text(errorMsg).show();
            }
        });
    }

    // Remove application
    function removeApplication(visaAppId) {
        console.log('=== removeApplication ===');
        console.log('Application ID:', visaAppId);

        var invoiceId = window.INVOICE_ID || null;

        if (!invoiceId || invoiceId === 0) {
            // For new invoices, remove from local array
            var app = selectedApplications.find(function(a) {
                return parseInt(a.id) === parseInt(visaAppId);
            });

            if (app) {
                selectedApplications = selectedApplications.filter(function(a) {
                    return parseInt(a.id) !== parseInt(visaAppId);
                });
                availableApplications.push(app);
                updateAvailableDropdown();
                renderSelectedApplications();
            }
            return;
        }

        // For existing invoices, use AJAX
        var removeUrl = window.location.origin + '/admin/core/invoice/' + invoiceId + '/remove-application/';
        $.ajax({
            url: removeUrl,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ visa_application_id: visaAppId }),
            beforeSend: function(xhr) {
                var token = getCSRFToken();
                if (token) {
                    xhr.setRequestHeader("X-CSRFToken", token);
                }
            },
            success: function(response) {
                console.log('Application removed via AJAX:', response);
                if (response.selected_applications) {
                    selectedApplications = response.selected_applications;
                    $.each(selectedApplications, function(i, app) {
                        app.price = parseFloat(app.price) || 0;
                    });
                }
                loadAvailableApplications(window.CLIENT_ID, invoiceId);
                renderSelectedApplications();
            },
            error: function(xhr, status, error) {
                console.error('Error removing application:', error);
                alert('Error removing application: ' + error);
            }
        });
    }

    // Initialize
    function initialize() {
        console.log('=== Initializing Invoice UX ===');
        console.log('INVOICE_ID:', window.INVOICE_ID);
        console.log('CLIENT_ID:', window.CLIENT_ID);
        console.log('SELECTED_APPLICATIONS:', window.SELECTED_APPLICATIONS);

        // Detect if we're on add or change page
        var isChangePage = window.INVOICE_ID && window.INVOICE_ID !== 0;
        console.log('Is change page:', isChangePage);

        // Find client field
        var clientField = $('#id_client');
        if (clientField.length === 0) {
            clientField = $('select[name="client"]');
        }
        if (clientField.length === 0) {
            clientField = $('select[id*="client"]');
        }

        console.log('Client field found:', clientField.length > 0);
        if (clientField.length === 0) {
            console.error('Client field not found! Retrying...');
            setTimeout(initialize, 500);
            return;
        }

        var invoiceId = window.INVOICE_ID || null;
        var initialClientId = window.CLIENT_ID;

        // Client change handler - handle both native and Select2/Unfold events
        clientField.on('change', function() {
            handleClientChange($(this).val());
        });
        // Also listen for Select2 change events
        clientField.on('select2:select select2:unselect', function() {
            handleClientChange($(this).val());
        });

        function handleClientChange(clientId) {
            console.log('=== Client Changed ===');
            console.log('New Client ID:', clientId);

            window.CLIENT_ID = clientId;

            if (!clientId || clientId === '' || clientId === null) {
                var select = $('#available-applications');
                if (select.length === 0) {
                    select = $('select[name="available_applications"]');
                }
                select.empty().append('<option value="">-- Select a client first --</option>');
                select.prop('disabled', true);
                select.trigger('change');
                $('#add-application-btn, #btn_add_application').prop('disabled', true);
                availableApplications = [];
                selectedApplications = [];
                renderSelectedApplications();
                updateSubtotal(0);
                return;
            }

            if (invoiceId && invoiceId !== 0) {
                if (clientId != initialClientId) {
                    if (confirm('Changing the client will clear all selected applications. Continue?')) {
                        selectedApplications = [];
                        availableApplications = [];
                        renderSelectedApplications();
                        updateSubtotal(0);
                        initialClientId = clientId;
                    } else {
                        clientField.val(initialClientId);
                        return;
                    }
                }
            } else {
                // For new invoices, clear selections when client changes
                selectedApplications = [];
                availableApplications = [];
                renderSelectedApplications();
                updateSubtotal(0);
            }

            loadAvailableApplications(clientId, invoiceId);
        }

        // Load existing selected applications FIRST (for change page)
        if (isChangePage && window.SELECTED_APPLICATIONS) {
            try {
                var parsed = typeof window.SELECTED_APPLICATIONS === 'string'
                    ? JSON.parse(window.SELECTED_APPLICATIONS)
                    : window.SELECTED_APPLICATIONS;
                selectedApplications = parsed || [];
                $.each(selectedApplications, function(i, app) {
                    app.id = parseInt(app.id);
                    app.price = parseFloat(app.price) || 0;
                    // Ensure display name is set
                    if (!app.display && app.name) {
                        app.display = app.name;
                    }
                    if (!app.display && !app.name) {
                        app.display = 'Application #' + app.id;
                        app.name = app.display;
                    }
                });
                console.log('Loaded existing selected applications:', selectedApplications.length);
                // Render immediately so they show up
                renderSelectedApplications();
            } catch (e) {
                console.error('Error parsing selected applications:', e);
                selectedApplications = [];
                renderSelectedApplications();
            }
        } else {
            selectedApplications = [];
            renderSelectedApplications();
        }

        // Load initial data - IMMEDIATELY for change page, with delay for add page
        function loadInitialData() {
            // Try multiple ways to get the client ID
            var currentClientValue = clientField.val();
            // Also try to get from Select2 if it's being used
            if (!currentClientValue && clientField.data('select2')) {
                currentClientValue = clientField.select2('val');
            }
            // Fallback to window.CLIENT_ID
            if (!currentClientValue) {
                currentClientValue = window.CLIENT_ID;
            }

            console.log('Initial client value from field:', clientField.val());
            console.log('Initial CLIENT_ID from window:', initialClientId);
            console.log('Resolved client ID:', currentClientValue);

            if (currentClientValue && currentClientValue !== '' && currentClientValue !== null) {
                console.log('Client already selected, loading applications immediately');
                window.CLIENT_ID = currentClientValue;
                // Load available applications (this will exclude already selected ones)
                loadAvailableApplications(currentClientValue, invoiceId);
            } else if (initialClientId && initialClientId !== null) {
                console.log('Loading from window.CLIENT_ID:', initialClientId);
                window.CLIENT_ID = initialClientId;
                loadAvailableApplications(initialClientId, invoiceId);
            } else {
                // Ensure dropdown is in correct initial state
                var select = $('#available-applications');
                if (select.length === 0) {
                    select = $('select[name="available_applications"]');
                }
                if (select.length > 0) {
                    select.prop('disabled', true);
                    $('#add-application-btn, #btn_add_application').prop('disabled', true);
                }
            }
        }

        // On change page, load immediately; on add page, wait a bit for widgets
        if (isChangePage) {
            // For change page, load immediately
            console.log('Change page detected - loading data immediately');
            loadInitialData();
        } else {
            // For add page, wait a bit for any widgets to initialize
            setTimeout(loadInitialData, 300);
        }

        // Add button handler - support both IDs
        var addButton = $('#add-application-btn, #btn_add_application');
        console.log('Add button found:', addButton.length);
        if (addButton.length === 0) {
            console.error('Add button not found! Looking for #add-application-btn or #btn_add_application');
        }
        addButton.on('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('Add button clicked!');
            var select = $('#available-applications');
            if (select.length === 0) {
                select = $('select[name="available_applications"]');
            }
            if (select.length === 0) {
                console.error('Select element not found when clicking add button!');
                return;
            }
            var selectedId = select.val();
            console.log('Selected application ID:', selectedId);
            if (selectedId && selectedId !== '') {
                addApplication(selectedId);
                select.val('').trigger('change');
                updateAddButtonState();
            } else {
                console.warn('No application selected');
                $('#applications-error').text('Please select an application first').show();
                setTimeout(function() {
                    $('#applications-error').fadeOut();
                }, 2000);
            }
        });

        // Dropdown change handler - handle both native and Select2/Unfold events
        var select = $('#available-applications');
        if (select.length === 0) {
            select = $('select[name="available_applications"]');
        }
        if (select.length > 0) {
            select.on('change', function() {
                console.log('Dropdown changed, value:', $(this).val());
                updateAddButtonState();
            });
            // Also listen for Select2 change events
            select.on('select2:select select2:unselect', function() {
                console.log('Select2 changed, value:', $(this).val());
                updateAddButtonState();
            });
            // Listen for input events (some widgets use this)
            select.on('input', function() {
                updateAddButtonState();
            });
        }

        // Remove button handler (delegated)
        $(document).on('click', '.remove-btn', function() {
            var appId = $(this).data('app-id');
            removeApplication(appId);
        });

        // Recalculate when discount changes so admin sees totals immediately
        $(document).on('input change', '#id_discount', function() {
            updateSubtotal(getSelectedApplicationsTotal());
        });
        $(document).on('input change', '#id_tax_rate', function() {
            updateSubtotal(getSelectedApplicationsTotal());
        });

        // Form submit handler
        $('form').on('submit', function() {
            updateSelectedApplicationsField();
            console.log('Form submitting with', selectedApplications.length, 'applications');
        });

        updateAddButtonState();
        console.log('=== Initialization Complete ===');
    }

    // Start initialization
    $(document).ready(function() {
        initialize();
    });

})(django.jQuery || jQuery || window.$);
