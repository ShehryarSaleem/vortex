// JavaScript fallback to ensure Unfold styling is applied to payment fields
(function($) {
    'use strict';

    if (!$) {
        return;
    }

    function applyUnfoldStylingToPaymentFields() {
        // Find all payment-related fields in inline groups
        $('.inline-group .stacked input, .inline-group .stacked select, .inline-group .stacked textarea').each(function() {
            var $field = $(this);
            // Skip hidden, checkbox, and radio inputs
            if ($field.attr('type') === 'hidden' ||
                $field.attr('type') === 'checkbox' ||
                $field.attr('type') === 'radio') {
                return;
            }

            // Apply Unfold's exact styling classes
            // Match: border border-base-200 rounded-default shadow-xs text-sm px-3 py-2
            $field.addClass('border border-base-200 font-medium rounded-default shadow-xs text-sm px-3 py-2');

            // Apply inline styles as fallback to ensure they work
            // Force border color with maximum specificity - ensure NOT white
            $field.css({
                'border': '1px solid rgb(229, 231, 235)', // border-base-200 - gray, NOT white
                'border-color': 'rgb(229, 231, 235)', // Force border color
                'border-top-color': 'rgb(229, 231, 235)', // Force each side
                'border-right-color': 'rgb(229, 231, 235)',
                'border-bottom-color': 'rgb(229, 231, 235)',
                'border-left-color': 'rgb(229, 231, 235)',
                'background-color': 'rgb(255, 255, 255)', // bg-white
                'border-radius': '0.375rem', // rounded-default
                'padding': '0.5rem 0.75rem', // px-3 py-2
                'font-size': '0.875rem', // text-sm
                'font-weight': '500', // font-medium
                'box-shadow': '0 1px 2px 0 rgba(0, 0, 0, 0.05)', // shadow-xs
                'width': '100%',
                'max-width': '100%',
                'box-sizing': 'border-box',
                'color': 'rgb(17, 24, 39)', // text-font-default-light
                'outline': 'none', // Remove default browser outline
                'margin': '0' // Remove any margins
            });

            // Remove any white border classes
            $field.removeClass('border-white');

            // For selects, add appearance-none and padding-right for arrow
            if ($field.is('select')) {
                $field.css({
                    '-webkit-appearance': 'none',
                    '-moz-appearance': 'none',
                    'appearance': 'none',
                    'padding-right': '2rem' // pr-8!
                });
            }
        });
    }

    // Run on document ready
    $(document).ready(function() {
        // Apply immediately
        applyUnfoldStylingToPaymentFields();

        // Also apply after a short delay to catch dynamically loaded fields
        setTimeout(applyUnfoldStylingToPaymentFields, 500);
        setTimeout(applyUnfoldStylingToPaymentFields, 1000);
    });

    // Also run when formset is added (for dynamic inlines)
    if (typeof django !== 'undefined' && django.jQuery) {
        django.jQuery(document).on('formset:added', function() {
            setTimeout(applyUnfoldStylingToPaymentFields, 100);
        });
    }

    // ============================================
    // TWO-COLUMN LAYOUT FOR PAYMENT INLINE
    // Adds class to payment inline fieldsets for CSS Grid layout
    // ============================================
    function setupPaymentTwoColumnLayout() {
        // Find payment inline fieldsets
        $('.inline-group .stacked fieldset.module').each(function() {
            var $fieldset = $(this);
            var $formRows = $fieldset.find('.form-row');

            // Check if this is a payment inline by looking for payment-related fields
            var hasPaymentFields = false;
            $formRows.each(function() {
                var $row = $(this);
                var fieldId = $row.find('input, select, textarea').first().attr('id') || '';
                if (fieldId.indexOf('amount') !== -1 ||
                    fieldId.indexOf('currency') !== -1 ||
                    fieldId.indexOf('payment') !== -1 ||
                    fieldId.indexOf('transaction') !== -1) {
                    hasPaymentFields = true;
                    return false; // break
                }
            });

            if (!hasPaymentFields) {
                return; // Skip if not a payment inline
            }

            // Add a class to identify this as a payment inline
            $fieldset.addClass('payment-inline-two-column');

            // Mark readonly timestamp fields to span full width
            $formRows.each(function() {
                var $row = $(this);
                var fieldId = $row.find('input, select, textarea').first().attr('id') || '';
                var $input = $row.find('input, select, textarea').first();

                // Check if field is readonly
                if ($input.prop('readonly') || $input.prop('disabled') ||
                    fieldId.indexOf('created_at') !== -1 ||
                    fieldId.indexOf('updated_at') !== -1) {
                    $row.addClass('two-column-full');
                }
            });
        });
    }

    // Remove "#1" from "Payment:#1" header, keep just "Payment"
    function fixPaymentHeader() {
        // Remove the inline_label span that contains "#1"
        $('.inline-group .stacked h3 .inline_label').each(function() {
            var $label = $(this);
            var text = $label.text().trim();
            // If it contains "#1" or any number, remove it
            if (text.indexOf('#') !== -1 || /^\d+$/.test(text)) {
                $label.remove();
            }
        });

        // Also remove the colon after "Payment" if it exists
        $('.inline-group .stacked h3').each(function() {
            var $header = $(this);
            var html = $header.html();
            // Remove trailing colon and whitespace before inline_label
            if (html && html.indexOf('Payment:') !== -1) {
                html = html.replace(/Payment:\s*/g, 'Payment');
                $header.html(html);
            }
        });
    }

    // Run on document ready
    $(document).ready(function() {
        setupPaymentTwoColumnLayout();
        fixPaymentHeader();

        // Also run after a delay to catch dynamically loaded fields
        setTimeout(function() {
            setupPaymentTwoColumnLayout();
            fixPaymentHeader();
        }, 500);
        setTimeout(function() {
            setupPaymentTwoColumnLayout();
            fixPaymentHeader();
        }, 1000);
    });

    // Also run when formset is added
    if (typeof window.django !== 'undefined' && window.django.jQuery) {
        window.django.jQuery(document).on('formset:added', function() {
            setTimeout(setupPaymentTwoColumnLayout, 100);
        });
    }
})(window.django && window.django.jQuery ? window.django.jQuery : (window.jQuery || window.$));
