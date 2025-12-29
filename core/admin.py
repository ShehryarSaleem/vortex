from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from unfold.admin import ModelAdmin
from unfold.decorators import display
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import redirect, render, get_object_or_404
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.forms import ModelForm
from django import forms
from decimal import Decimal
from .models import Client, VisaApplication, Payment, Pricing, Invoice, InvoiceApplication, InvoiceOtherPayment
from .admin_site import admin_site


# Custom Form for Payment
class PaymentForm(ModelForm):
    """Custom form for Payment with amount auto-populated based on visa type (if visa application is linked)."""

    class Meta:
        model = Payment
        fields = "__all__"
        widgets = {
            'amount': forms.NumberInput(attrs={
                'step': '0.01',
            }),
            'discount': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0.00',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make amount required and editable
        if 'amount' in self.fields:
            self.fields['amount'].required = True
            self.fields['amount'].help_text = "Enter payment amount. If a visa application is selected, the amount will be auto-populated based on visa type pricing."

        # Configure discount fields
        if 'discount' in self.fields:
            self.fields['discount'].required = False
            self.fields['discount'].help_text = "Enter discount amount (in same currency as payment). Leave as 0.00 if no discount applies."

        if 'discount_type' in self.fields:
            self.fields['discount_type'].required = False
            self.fields['discount_type'].help_text = "Select the type of discount applied (if any)."

        # Get visa type from visa_application if available
        visa_type = None

        # First, try to get from instance's visa_application
        if self.instance and self.instance.visa_application_id:
            try:
                visa_app = self.instance.visa_application
                if visa_app:
                    visa_type = visa_app.visa_type
            except VisaApplication.DoesNotExist:
                pass

        # If not found, try to get from initial data
        if not visa_type and 'visa_application' in self.initial:
            visa_app_id = self.initial.get('visa_application')
            if visa_app_id:
                try:
                    visa_app = VisaApplication.objects.get(pk=visa_app_id)
                    visa_type = visa_app.visa_type
                except (VisaApplication.DoesNotExist, ValueError, TypeError):
                    pass

        # If still not found, try to get from form data (POST request)
        if not visa_type and args and len(args) > 0:
            form_data = args[0]
            if isinstance(form_data, dict):
                visa_app_id = form_data.get('visa_application')
                if visa_app_id:
                    try:
                        visa_app = VisaApplication.objects.get(pk=visa_app_id)
                        visa_type = visa_app.visa_type
                    except (VisaApplication.DoesNotExist, ValueError, TypeError):
                        pass

        # Auto-populate amount and currency based on visa type (only if not already set)
        if visa_type and 'amount' in self.fields:
            price = Pricing.get_price_for_visa_type(visa_type)
            try:
                pricing = Pricing.objects.get(visa_type=visa_type, is_active=True)
                currency = pricing.currency
            except Pricing.DoesNotExist:
                currency = "GBP"

            # Set amount if not already set (for new payments or if amount is empty)
            if not self.instance.amount or not self.instance.pk:
                self.initial['amount'] = price
                self.fields['amount'].initial = price

            # Set currency
            if 'currency' in self.fields:
                self.initial['currency'] = currency
                self.fields['currency'].initial = currency

    def clean(self):
        """Validate discount fields."""
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        discount = cleaned_data.get('discount') or Decimal('0.00')
        discount_type = cleaned_data.get('discount_type')

        # Validate discount doesn't exceed amount
        if amount and discount:
            if discount > amount:
                raise forms.ValidationError({
                    'discount': 'Discount cannot exceed the payment amount.'
                })

        # Validate discount and discount_type consistency
        if discount and discount > 0:
            if not discount_type:
                raise forms.ValidationError({
                    'discount_type': 'Discount type is required when a discount is applied.'
                })
        elif discount_type and (not discount or discount == 0):
            raise forms.ValidationError({
                'discount': 'Discount amount is required when discount type is selected.'
            })

        return cleaned_data


# Custom Form for VisaApplication Inline to match main form styling
class VisaApplicationInlineForm(ModelForm):
    """Custom form for VisaApplication inline - only shows Visa Type and Location."""

    class Meta:
        model = VisaApplication
        fields = ["visa_type", "appointment_location"]
        widgets = {
            "appointment_location": forms.TextInput(attrs={"placeholder": "Enter location (e.g., Embassy name, city)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default stage to "initial" for new applications
        if not self.instance.pk:
            self.instance.stage = "initial"
        # Make visa_type required
        self.fields["visa_type"].required = True
        # Make location optional but recommended
        self.fields["appointment_location"].required = False
        # Change label to just "Location" for simplicity
        self.fields["appointment_location"].label = "Location"


# Inline Admin Classes for Client
class VisaApplicationInline(admin.TabularInline):
    """Inline admin for VisaApplications in Client admin - shows only Visa Type and Location."""
    model = VisaApplication
    form = VisaApplicationInlineForm
    extra = 1  # Show at least one form when adding a new client
    min_num = 1  # Require at least one visa application
    verbose_name = "Visa Application"
    verbose_name_plural = "Visa Applications"
    fields = [
        "visa_type",
        "appointment_location",  # Location field
    ]
    readonly_fields = []
    show_change_link = True
    can_delete = True

    def get_formset(self, request, obj=None, **kwargs):
        """Override to add custom validation (only when editing, not adding)."""
        formset = super().get_formset(request, obj, **kwargs)
        # Note: Validation removed since inline is not shown on add page
        # Users can add visa applications after creating the client
        return formset


class PaymentInline(admin.TabularInline):
    """Inline admin for Payments in Client admin."""
    model = Payment
    extra = 0
    fields = ["amount", "currency", "payment_status", "payment_received_date", "created_at"]
    readonly_fields = ["created_at"]
    show_change_link = True


class VisaApplicationCaseFilter(SimpleListFilter):
    title = "Case status"
    parameter_name = "case_status"

    def lookups(self, request, model_admin):
        return [
            ("pending", "Pending"),
            ("completed", "Decision received"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "pending":
            return queryset.exclude(stage="decision_received")
        if self.value() == "completed":
            return queryset.filter(stage="decision_received")
        return queryset


class InvoiceOutstandingFilter(SimpleListFilter):
    title = "Outstanding"
    parameter_name = "outstanding"

    def lookups(self, request, model_admin):
        return [
            ("yes", "Outstanding"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(status__in=["sent", "overdue"])
        return queryset




@admin.register(Client, site=admin_site)
class ClientAdmin(ModelAdmin):
    """
    Admin interface for Client model using Django Unfold.
    Follows the design pattern from Unfold demo.
    """

    # Inlines - No inlines on add page, only shown on edit page
    inlines = [VisaApplicationInline, PaymentInline]

    def get_inline_instances(self, request, obj=None):
        """Show inlines only when editing existing client, not when adding."""
        if obj is None:
            # Adding new client - no inlines shown
            return []
        else:
            # Editing existing client - show both Visa Applications and Payments
            inline_instances = []
            visa_inline = VisaApplicationInline(self.model, self.admin_site)
            payment_inline = PaymentInline(self.model, self.admin_site)
            inline_instances.append(visa_inline)
            inline_instances.append(payment_inline)
            return inline_instances

    # List Display
    list_display = [
        "id",
        "full_name_display",
        "email",
        "phone",
        "nationality",
        "client_status_badge",
        "passport_number",
        "created_at",
        "actions_column",
    ]

    # List Display Links
    list_display_links = ["id", "full_name_display"]

    # Search Fields
    search_fields = [
        "first_name",
        "last_name",
        "email",
        "phone",
        "passport_number",
        "nationality",
        "country_of_residence",
    ]

    # List Filters
    list_filter = [
        "client_status",
        "nationality",
        "country_of_residence",
        "lead_source",
        "preferred_contact_method",
        "created_at",
    ]

    # Fieldsets for Add/Edit Form
    fieldsets = (
        (
            "Personal Information",
            {
                "fields": (
                    ("first_name", "last_name"),
                    "email",
                    "phone",
                    "date_of_birth",
                ),
                "classes": ("wide",),
            },
        ),
        (
            "Passport Information",
            {
                "fields": (
                    "passport_number",
                    "passport_file",
                ),
            },
        ),
        (
            "Location Information",
            {
                "fields": (
                    "nationality",
                    "country_of_residence",
                ),
            },
        ),
        (
            "Contact & Lead Information",
            {
                "fields": (
                    "preferred_contact_method",
                    "lead_source",
                ),
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "client_status",
                ),
                "description": "Note: Visa Type is managed in the Visa Applications section below.",
            },
        ),
        (
            "Notes",
            {
                "fields": (
                    "notes",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    # Readonly Fields (will be dynamically set based on edit mode)
    readonly_fields = [
        "first_name",
        "last_name",
        "email",
        "phone",
        "date_of_birth",
        "passport_number",
        "passport_file",
        "nationality",
        "country_of_residence",
        "preferred_contact_method",
        "lead_source",
        "client_status",
        "notes",
        "created_at",
        "updated_at",
    ]

    # Date Hierarchy
    date_hierarchy = "created_at"

    # List Per Page
    list_per_page = 25

    # Show Full Result Count
    show_full_result_count = True

    # Custom Display Methods
    @display(description="Full Name", ordering="last_name")
    def full_name_display(self, obj):
        """Display full name with link to detail page."""
        url = reverse("admin:core_client_change", args=[obj.pk])
        return format_html(
            '<a href="{}" style="font-weight: 600; color: #2563eb;">{}</a>',
            url,
            obj.full_name,
        )

    @display(description="Status", ordering="client_status")
    def client_status_badge(self, obj):
        """Display client status as a colored badge."""
        status_colors = {
            "new": "#3b82f6",      # Blue
            "previous": "#10b981", # Green
        }
        color = status_colors.get(obj.client_status, "#6b7280")
        return format_html(
            '<span style="display: inline-block; padding: 4px 12px; '
            'background-color: {}; color: white; border-radius: 12px; '
            'font-size: 12px; font-weight: 500;">{}</span>',
            color,
            obj.get_client_status_display(),
        )

    @display(description="Actions")
    def actions_column(self, obj):
        """Display quick action buttons."""
        change_url = reverse("admin:core_client_change", args=[obj.pk])
        return format_html(
            '<a href="{}" class="button" style="padding: 4px 8px; '
            'background: #2563eb; color: white; text-decoration: none; '
            'border-radius: 4px; font-size: 12px;">View</a>',
            change_url,
        )

    def get_readonly_fields(self, request, obj=None):
        """Make all fields readonly by default unless edit mode is enabled."""
        if obj is None:  # Creating new object - allow editing
            return ["created_at", "updated_at"]

        # Check if edit mode is enabled via query parameter
        edit_mode = request.GET.get("edit", "0") == "1"

        if edit_mode:
            # Edit mode - only timestamps are readonly
            return ["created_at", "updated_at"]
        else:
            # View mode - all fields are readonly
            return [
                "first_name",
                "last_name",
                "email",
                "phone",
                "date_of_birth",
                "passport_number",
                "passport_file",
                "nationality",
                "country_of_residence",
                "preferred_contact_method",
                "lead_source",
                "client_status",
                "notes",
                "created_at",
                "updated_at",
            ]

    def change_view(self, request, object_id, form_url="", extra_context=None):
        """Override change_view to handle edit mode."""
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)

        # Always set these variables to avoid template errors
        extra_context["edit_mode"] = False
        extra_context["show_edit_button"] = False
        extra_context["edit_url"] = ""
        extra_context["invoice_url"] = ""

        if obj:
            edit_mode = request.GET.get("edit", "0") == "1"

            # Prevent POST requests in view mode (redirect to edit mode if trying to save)
            if request.method == "POST" and not edit_mode:
                edit_url = reverse("admin:core_client_change", args=[object_id])
                return HttpResponseRedirect(f"{edit_url}?edit=1")

            extra_context["edit_mode"] = edit_mode
            extra_context["show_edit_button"] = not edit_mode

            # Add edit button URL
            if not edit_mode:
                edit_url = reverse("admin:core_client_change", args=[object_id])
                extra_context["edit_url"] = f"{edit_url}?edit=1"

        return super().change_view(request, object_id, form_url, extra_context)

    def response_change(self, request, obj):
        """Redirect to view mode after saving."""
        if "_save" in request.POST or "_continue" in request.POST:
            # After saving, redirect to view mode (without edit parameter)
            return HttpResponseRedirect(
                reverse("admin:core_client_change", args=[obj.pk])
            )
        return super().response_change(request, obj)

    # Customize the form
    def get_form(self, request, obj=None, **kwargs):
        """Customize the form."""
        form = super().get_form(request, obj, **kwargs)
        return form

    # Customize queryset
    def get_queryset(self, request):
        """Optimize queryset with select_related and prefetch_related."""
        qs = super().get_queryset(request)
        return qs.select_related()

    # Customize list view
    def changelist_view(self, request, extra_context=None):
        """Add extra context to list view."""
        extra_context = extra_context or {}
        extra_context["title"] = "Clients"
        return super().changelist_view(request, extra_context)


# Custom Form for VisaApplication to handle conditional fields
class VisaApplicationForm(ModelForm):
    """Custom form for VisaApplication with conditional appointment and decision fields."""

    class Meta:
        model = VisaApplication
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Get client from form data or instance
        client = None
        if args and len(args) > 0 and isinstance(args[0], dict):
            # Form data provided (POST request)
            client_id = args[0].get('client', None)
            if client_id:
                try:
                    client = Client.objects.get(pk=client_id)
                except (Client.DoesNotExist, ValueError, TypeError):
                    pass
        elif self.instance and self.instance.pk:
            # Existing instance
            client = self.instance.client

        # Filter visa_type choices to exclude types the client already has
        # Only apply this when creating a new application (not editing existing)
        # This provides server-side filtering as a fallback if JavaScript fails
        if "visa_type" in self.fields and client and not (self.instance and self.instance.pk):
            # Get existing visa types for this client
            existing_visa_types = VisaApplication.objects.filter(
                client=client
            ).values_list('visa_type', flat=True)

            # Get all visa type choices
            visa_type_choices = list(self.fields["visa_type"].choices)

            # Filter out visa types that already exist for this client
            available_choices = [
                (value, label) for value, label in visa_type_choices
                if value not in existing_visa_types
            ]

            # Update the choices
            self.fields["visa_type"].choices = available_choices

            # If no available choices, show a message
            if not available_choices:
                self.fields["visa_type"].help_text = "This client already has applications for all available visa types."

        # Get stage value from form data or instance
        stage_value = None
        if args and len(args) > 0 and isinstance(args[0], dict):
            # Form data provided (POST request)
            stage_value = args[0].get('stage', None)
        elif self.instance and self.instance.pk:
            # Existing instance
            stage_value = self.instance.stage
        else:
            # New instance - default to "initial"
            stage_value = "initial"

        # Make appointment fields required when stage is appointment_scheduled
        if stage_value == "appointment_scheduled":
            if "appointment_date" in self.fields:
                self.fields["appointment_date"].required = True
            if "appointment_location" in self.fields:
                self.fields["appointment_location"].required = True

        # Decision fields - JavaScript will handle show/hide
        # Backend validation will be handled in clean method
        # Only set if fields exist (they might be readonly and not in self.fields)
        if "decision" in self.fields:
            self.fields["decision"].required = False
        if "decision_date" in self.fields:
            self.fields["decision_date"].required = False

    def clean(self):
        """Validate decision fields when stage is decision_received and prevent duplicate visa applications."""
        cleaned_data = super().clean()
        stage = cleaned_data.get("stage")
        client = cleaned_data.get("client")
        visa_type = cleaned_data.get("visa_type")

        # Prevent duplicate visa applications for the same client and visa type
        # Only check when creating a new application (not editing existing)
        # Note: Frontend JavaScript filters the dropdown, but we keep this as a safety net
        if client and visa_type and not (self.instance and self.instance.pk):
            existing_application = VisaApplication.objects.filter(
                client=client,
                visa_type=visa_type
            ).exclude(pk=self.instance.pk if self.instance else None).first()

            if existing_application:
                # Silently prevent duplicate - the frontend should have filtered this out
                # But if someone bypasses the frontend, we still prevent it
                raise forms.ValidationError({
                    "visa_type": "This visa type is not available for this client. Please select a different visa type."
                })

        if stage == "decision_received":
            # Require decision and decision_date when stage is decision_received
            if not cleaned_data.get("decision"):
                raise forms.ValidationError({
                    "decision": "Decision is required when stage is 'Decision Received'."
                })
            if not cleaned_data.get("decision_date"):
                raise forms.ValidationError({
                    "decision_date": "Decision date is required when stage is 'Decision Received'."
                })

        return cleaned_data


@admin.register(VisaApplication, site=admin_site)
class VisaApplicationAdmin(ModelAdmin):
    """
    Admin interface for VisaApplication model using Django Unfold.
    """

    form = VisaApplicationForm
    inlines = []  # Payment inline removed - now managed separately

    class Media:
        js = (
            'admin/js/visa_application_conditional.js',
            'admin/js/visa_application_duplicate_prevention.js',
        )
        css = {
            'all': ('css/admin_inline_custom.css',)
        }

    def get_urls(self):
        """Add custom URL for AJAX endpoint."""
        urls = super().get_urls()
        custom_urls = [
            path(
                'get-existing-visa-types/',
                self.admin_site.admin_view(self.get_existing_visa_types),
                name='core_visaapplication_get_existing_visa_types',
            ),
        ]
        return custom_urls + urls

    def get_existing_visa_types(self, request):
        """AJAX endpoint to get existing visa types for a client."""
        if request.method != 'GET':
            return JsonResponse({'error': 'Method not allowed'}, status=405)

        client_id = request.GET.get('client_id')
        if not client_id:
            return JsonResponse({'error': 'client_id is required'}, status=400)

        try:
            client = Client.objects.get(pk=client_id)
            existing_types = list(VisaApplication.objects.filter(
                client=client
            ).values_list('visa_type', flat=True))
            return JsonResponse({'existing_types': existing_types})
        except Client.DoesNotExist:
            return JsonResponse({'error': 'Client not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    # List Display
    list_display = [
        "id",
        "client_name",
        "visa_type",
        "stage_badge",
        "appointment_date",
        "decision_badge",
        "assigned_agent",
        "created_at",
        "actions_column",
    ]

    # List Display Links
    list_display_links = ["id", "client_name"]

    # Search Fields
    search_fields = [
        "client__first_name",
        "client__last_name",
        "client__email",
        "client__passport_number",
        "visa_type",
        "assigned_agent",
    ]

    # List Filters
    list_filter = [
        "stage",
        "visa_type",
        "decision",
        VisaApplicationCaseFilter,
        "assigned_agent",
        "appointment_date",
        "created_at",
    ]

    # Fieldsets for Add/Edit Form
    fieldsets = (
        (
            "Client & Visa Information",
            {
                "fields": (
                    "client",
                    "visa_type",
                ),
            },
        ),
        (
            "Application Stage",
            {
                "fields": (
                    "stage",
                    "assigned_agent",
                ),
            },
        ),
        (
            "Appointment Information",
            {
                "fields": (
                    "appointment_date",
                    "appointment_location",
                ),
                "description": "Required when stage is 'Appointment Scheduled'",
            },
        ),
        (
            "Decision Information",
            {
                "fields": (
                    "decision",
                    "decision_date",
                    "decision_notes",
                ),
                "classes": ("decision-info-section",),
            },
        ),
        (
            "Notes",
            {
                "fields": (
                    "notes",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
        )

    # Readonly Fields (will be dynamically set based on edit mode)
    readonly_fields = [
        "client",
        "visa_type",
        "stage",
        "assigned_agent",
        "appointment_date",
        "appointment_location",
        "decision",
        "decision_date",
        "decision_notes",
        "notes",
        "created_at",
        "updated_at",
    ]

    # Date Hierarchy
    date_hierarchy = "created_at"

    # List Per Page
    list_per_page = 25

    # Note: Client is shown as dropdown list (not raw_id_fields)

    # Custom Display Methods
    @display(description="Client", ordering="client__last_name")
    def client_name(self, obj):
        """Display client name with link."""
        url = reverse("admin:core_client_change", args=[obj.client.pk])
        return format_html(
            '<a href="{}" style="font-weight: 600; color: #2563eb;">{}</a>',
            url,
            obj.client.full_name,
        )

    @display(description="Stage", ordering="stage")
    def stage_badge(self, obj):
        """Display application stage as a colored badge."""
        stage_colors = {
            "initial": "#6b7280",  # Gray
            "document_collected": "#3b82f6",  # Blue
            "payment_requested": "#f59e0b",  # Amber
            "payment_received": "#10b981",  # Green
            "appointment_scheduled": "#8b5cf6",  # Purple
            "appointment_attended": "#06b6d4",  # Cyan
            "waiting_for_decision": "#f97316",  # Orange
            "decision_received": "#ec4899",  # Pink
        }
        color = stage_colors.get(obj.stage, "#6b7280")
        return format_html(
            '<span style="display: inline-block; padding: 4px 12px; '
            'background-color: {}; color: white; border-radius: 12px; '
            'font-size: 12px; font-weight: 500;">{}</span>',
            color,
            obj.get_stage_display(),
        )

    @display(description="Decision", ordering="decision")
    def decision_badge(self, obj):
        """Display decision as a colored badge."""
        if not obj.decision:
            return format_html(
                '<span style="display: inline-block; padding: 4px 12px; '
                'background-color: #6b7280; color: white; border-radius: 12px; '
                'font-size: 12px; font-weight: 500;">Not Set</span>'
            )
        decision_colors = {
            "approved": "#10b981",  # Green
            "rejected": "#ef4444",  # Red
        }
        color = decision_colors.get(obj.decision, "#6b7280")
        return format_html(
            '<span style="display: inline-block; padding: 4px 12px; '
            'background-color: {}; color: white; border-radius: 12px; '
            'font-size: 12px; font-weight: 500;">{}</span>',
            color,
            obj.get_decision_display(),
        )

    @display(description="Actions")
    def actions_column(self, obj):
        """Display quick action buttons."""
        change_url = reverse("admin:core_visaapplication_change", args=[obj.pk])
        return format_html(
            '<a href="{}" class="button" style="padding: 4px 8px; '
            'background: #2563eb; color: white; text-decoration: none; '
            'border-radius: 4px; font-size: 12px;">View</a>',
            change_url,
        )

    def get_readonly_fields(self, request, obj=None):
        """Make all fields readonly by default unless edit mode is enabled."""
        if obj is None:  # Creating new object - allow editing
            return ["created_at", "updated_at"]

        # Check if edit mode is enabled via query parameter
        edit_mode = request.GET.get("edit", "0") == "1"

        if edit_mode:
            # Edit mode - only timestamps are readonly
            return ["created_at", "updated_at"]
        else:
            # View mode - all fields are readonly
            return [
                "client",
                "visa_type",
                "stage",
                "assigned_agent",
                "appointment_date",
                "appointment_location",
                "decision",
                "decision_date",
                "decision_notes",
                "notes",
                "created_at",
                "updated_at",
            ]

    def change_view(self, request, object_id, form_url="", extra_context=None):
        """Override change_view to handle edit mode."""
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)

        # Always set these variables to avoid template errors
        extra_context["edit_mode"] = False
        extra_context["show_edit_button"] = False
        extra_context["edit_url"] = ""
        extra_context["invoice_url"] = ""

        if obj:
            edit_mode = request.GET.get("edit", "0") == "1"

            # Prevent POST requests in view mode (redirect to edit mode if trying to save)
            if request.method == "POST" and not edit_mode:
                edit_url = reverse(
                    f"{admin_site.name}:core_visaapplication_change", args=[object_id]
                )
                return HttpResponseRedirect(f"{edit_url}?edit=1")

            extra_context["edit_mode"] = edit_mode
            extra_context["show_edit_button"] = not edit_mode

            # Add edit button URL
            if not edit_mode:
                edit_url = reverse(
                    f"{admin_site.name}:core_visaapplication_change", args=[object_id]
                )
                extra_context["edit_url"] = f"{edit_url}?edit=1"

            # Add invoice URL - link to latest invoice if present, otherwise open the builder.
            invoice = (
                Invoice.objects.filter(visa_applications=obj)
                .order_by("-invoice_date", "-created_at")
                .first()
            )
            if invoice:
                invoice_url = reverse(
                    f"{admin_site.name}:core_invoice_change", args=[invoice.pk]
                )
            else:
                invoice_url = (
                    reverse(f"{admin_site.name}:core_invoice_builder")
                    + f"?client={obj.client.pk}"
                )
            extra_context["invoice_url"] = invoice_url

        return super().change_view(request, object_id, form_url, extra_context)

    def response_change(self, request, obj):
        """Redirect to view mode after saving."""
        if "_save" in request.POST or "_continue" in request.POST:
            # After saving, redirect to view mode (without edit parameter)
            return HttpResponseRedirect(
                reverse(f"{admin_site.name}:core_visaapplication_change", args=[obj.pk])
            )
        return super().response_change(request, obj)

    # Customize queryset
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related("client")

    # Custom Display Methods for Payment Section
    @display(description="Payment Information")
    def payment_info(self, obj):
        """Display payment information for this visa application."""
        if obj and obj.pk:
            # Get payments for this visa application
            payments = Payment.objects.filter(visa_application=obj).order_by('-created_at')

            if not payments.exists():
                return format_html(
                    '<div style="padding: 1rem; background-color: #f9fafb; border-radius: 0.375rem; border: 1px solid #e5e7eb;">'
                    '<p style="margin: 0; color: #6b7280;">No payments recorded for this visa application.</p>'
                    '</div>'
                )

            html = '<div style="padding: 1rem; background-color: #f9fafb; border-radius: 0.375rem; border: 1px solid #e5e7eb;">'

            for payment in payments:
                status_colors = {
                    "pending": "#6b7280",
                    "requested": "#f59e0b",
                    "received": "#10b981",
                    "refunded": "#ef4444",
                }
                status_color = status_colors.get(payment.payment_status, "#6b7280")

                html += format_html(
                    '<div style="margin-bottom: 1rem; padding: 0.75rem; background-color: white; border-radius: 0.375rem; border: 1px solid #e5e7eb;">'
                    '<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; margin-bottom: 0.5rem;">'
                    '<div><strong>Amount:</strong> {}</div>'
                    '<div><strong>Currency:</strong> {}</div>'
                    '<div><strong>Status:</strong> <span style="display: inline-block; padding: 2px 8px; background-color: {}; color: white; border-radius: 4px; font-size: 0.75rem;">{}</span></div>'
                    '<div><strong>Method:</strong> {}</div>'
                    '</div>'
                    '<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; margin-bottom: 0.5rem;">'
                    '<div><strong>Requested Date:</strong> {}</div>'
                    '<div><strong>Received Date:</strong> {}</div>'
                    '</div>'
                    '<div style="margin-top: 0.5rem;"><strong>Transaction ID:</strong> {}</div>'
                    '<div style="margin-top: 0.5rem;"><strong>Notes:</strong> {}</div>'
                    '</div>',
                    f"{payment.amount}",
                    payment.currency,
                    status_color,
                    payment.get_payment_status_display(),
                    payment.get_payment_method_display() if payment.payment_method else "N/A",
                    payment.payment_requested_date.strftime("%Y-%m-%d") if payment.payment_requested_date else "N/A",
                    payment.payment_received_date.strftime("%Y-%m-%d") if payment.payment_received_date else "N/A",
                    payment.transaction_id or "N/A",
                    payment.notes or "No notes",
                )

            html += '</div>'
            return format_html(html)
        else:
            # On add page, show message that payment will be created after saving
            return format_html(
                '<div style="padding: 1rem; background-color: #f9fafb; border-radius: 0.375rem; border: 1px solid #e5e7eb;">'
                '<p style="margin: 0; color: #6b7280;">Payment information will be available after saving the visa application.</p>'
                '</div>'
            )


# Payment admin removed - all payment functionality is now handled through Invoice management
# @admin.register(Payment)
# class PaymentAdmin(ModelAdmin):
#     """
#     Admin interface for Payment model using Django Unfold.
#     Separate page for managing payments.
#     """
#
#     form = PaymentForm
#
#     # List Display
#     list_display = [
#         "client_name",
#         "visa_application_link",
#         "invoice_link",
#         "amount",
#         "currency",
#         "payment_status_badge",
#         "payment_method",
#         "payment_received_date",
#         "created_at",
#         "actions_column",
#     ]
#
#     # List Display Links
#     list_display_links = ["client_name"]
#
#     # Search Fields
#     search_fields = [
#         "client__first_name",
#         "client__last_name",
#         "client__email",
#         "client__passport_number",
#         "transaction_id",
#         "visa_application__id",
#     ]
#
#     # List Filters
#     list_filter = [
#         "payment_status",
#         "payment_method",
#         "currency",
#         "payment_received_date",
#         "created_at",
#     ]
#
#     # Fieldsets for Add/Edit Form
#     fieldsets = (
#         (
#             "Client & Visa Application",
#             {
#                 "fields": (
#                     "client",
#                     "visa_application",
#                 ),
#             },
#         ),
#         (
#             "Payment Information",
#             {
#                 "fields": (
#                     ("amount", "currency"),
#                     ("discount", "discount_type"),
#                     ("payment_status", "payment_method"),
#                 ),
#                 "description": "Final amount (after discount) will be calculated automatically and displayed below.",
#             },
#         ),
#         (
#             "Payment Dates",
#             {
#                 "fields": (
#                     ("payment_requested_date", "payment_received_date"),
#                 ),
#             },
#         ),
#         (
#             "Transaction Details",
#             {
#                 "fields": (
#                     "transaction_id",
#                     "notes",
#                 ),
#             },
#         ),
#         (
#             "Timestamps",
#             {
#                 "fields": (
#                     "created_at",
#                     "updated_at",
#                 ),
#                 "classes": ("collapse",),
#             },
#         ),
#     )
#
#     # Readonly Fields
#     readonly_fields = ["created_at", "updated_at"]
#
#     # Date Hierarchy
#     date_hierarchy = "created_at"
#
#     # List Per Page
#     list_per_page = 25
#
#     # Custom Display Methods
#     @display(description="Client", ordering="client__last_name")
#     def client_name(self, obj):
#         """Display client name with link."""
#         url = reverse("admin:core_client_change", args=[obj.client.pk])
#         return format_html(
#             '<a href="{}" style="font-weight: 600; color: #2563eb;">{}</a>',
#             url,
#             obj.client.full_name,
#         )
#
#     @display(description="Visa Application")
#     def visa_application_link(self, obj):
#         """Display visa application with visa type name and link if available."""
#         if obj.visa_application:
#             url = reverse("admin:core_visaapplication_change", args=[obj.visa_application.pk])
#             visa_type_display = obj.visa_application.get_visa_type_display()
#             return format_html(
#                 '<a href="{}" style="font-weight: 600; color: #2563eb;">{}</a>',
#                 url,
#                 visa_type_display,
#             )
#         return format_html('<span style="color: #6b7280;">Not linked</span>')
#
#     @display(description="Invoice")
#     def invoice_link(self, obj):
#         """Display invoice link if available."""
#         if hasattr(obj, 'invoice') and obj.invoice:
#             url = reverse("admin:core_invoice_change", args=[obj.invoice.pk])
#             return format_html(
#                 '<a href="{}" style="font-weight: 600; color: #10b981;">{}</a>',
#                 url,
#                 obj.invoice.invoice_number,
#             )
#         return format_html('<span style="color: #6b7280;">No invoice</span>')
#
#     @display(description="Status", ordering="payment_status")
#     def payment_status_badge(self, obj):
#         """Display payment status as a colored badge."""
#         status_colors = {
#             "pending": "#6b7280",      # Gray
#             "requested": "#f59e0b",     # Amber
#             "received": "#10b981",      # Green
#             "refunded": "#ef4444",      # Red
#         }
#         color = status_colors.get(obj.payment_status, "#6b7280")
#         return format_html(
#             '<span style="display: inline-block; padding: 4px 12px; '
#             'background-color: {}; color: white; border-radius: 12px; '
#             'font-size: 12px; font-weight: 500;">{}</span>',
#             color,
#             obj.get_payment_status_display(),
#         )
#
#     @display(description="Actions")
#     def actions_column(self, obj):
#         """Display quick action buttons."""
#         change_url = reverse("admin:core_payment_change", args=[obj.pk])
#         return format_html(
#             '<a href="{}" class="button" style="padding: 4px 8px; '
#             'background: #2563eb; color: white; text-decoration: none; '
#             'border-radius: 4px; font-size: 12px;">View</a>',
#             change_url,
#         )
#
#     @display(description="Client Details")
#     def client_info_display(self, obj):
#         """Display detailed client information."""
#         if not obj or not obj.pk:
#             return format_html('<p style="color: #6b7280;">Client information will be available after selecting a client.</p>')
#
#         client = obj.client
#         client_url = reverse("admin:core_client_change", args=[client.pk])
#
#         return format_html(
#             '<div style="background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin-bottom: 20px;">'
#             '<div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 16px;">'
#             '<div>'
#             '<h3 style="margin: 0 0 12px 0; font-size: 18px; font-weight: 600; color: #111827;">'
#             '<a href="{}" style="color: #2563eb; text-decoration: none;">{}</a>'
#             '</h3>'
#             '<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; font-size: 14px;">'
#             '<div><strong style="color: #6b7280;">Email:</strong> <span style="color: #374151;">{}</span></div>'
#             '<div><strong style="color: #6b7280;">Phone:</strong> <span style="color: #374151;">{}</span></div>'
#             '<div><strong style="color: #6b7280;">Nationality:</strong> <span style="color: #374151;">{}</span></div>'
#             '<div><strong style="color: #6b7280;">Country of Residence:</strong> <span style="color: #374151;">{}</span></div>'
#             '<div><strong style="color: #6b7280;">Passport Number:</strong> <span style="color: #374151;">{}</span></div>'
#             '<div><strong style="color: #6b7280;">Client Status:</strong> <span style="color: #374151;">{}</span></div>'
#             '</div>'
#             '</div>'
#             '</div>'
#             '</div>',
#             client_url,
#             client.full_name,
#             client.email,
#             client.phone,
#             client.nationality,
#             client.country_of_residence,
#             client.passport_number,
#             client.get_client_status_display(),
#         )
#
#     class Media:
#         js = (
#             'admin/js/payment_admin_autofill.js',
#         )
#
#
#     # Customize queryset
#     def get_queryset(self, request):
#         """Optimize queryset."""
#         qs = super().get_queryset(request)
#         return qs.select_related("client", "visa_application")
#
#     # Auto-populate amount based on visa_application when creating new payment
#     def get_form(self, request, obj=None, **kwargs):
#         """Customize the form to auto-populate amount from visa application."""
#         form = super().get_form(request, obj, **kwargs)
#
#         # If creating new payment and visa_application is selected
#         if obj is None and 'visa_application' in form.base_fields:
#             # Make amount field editable (not readonly) since it's a separate page
#             if 'amount' in form.base_fields:
#                 form.base_fields['amount'].required = True
#                 form.base_fields['amount'].help_text = "Enter payment amount. If a visa application is selected, the amount will be auto-populated based on visa type pricing."
#
#         return form
#
#     def add_view(self, request, form_url='', extra_context=None):
#         """Override add_view to pre-select client from URL parameter."""
#         extra_context = extra_context or {}
#
#         # Get client ID from URL parameter
#         client_id = request.GET.get('client')
#         if client_id:
#             try:
#                 client = Client.objects.get(pk=client_id)
#                 extra_context['preselected_client'] = client
#                 # Pre-fill initial data
#                 if hasattr(self, 'form') or 'form' in extra_context:
#                     # This will be handled in the form's initial data
#                     pass
#             except Client.DoesNotExist:
#                 pass
#
#         return super().add_view(request, form_url, extra_context)
#
#     def get_changeform_initial_data(self, request):
#         """Set initial data for new payment form."""
#         initial = super().get_changeform_initial_data(request)
#
#         # Pre-select client from URL parameter
#         client_id = request.GET.get('client')
#         if client_id:
#             initial['client'] = client_id
#
#         # Pre-select visa application from URL parameter
#         visa_application_id = request.GET.get('visa_application')
#         if visa_application_id:
#             initial['visa_application'] = visa_application_id
#
#         return initial


# PaymentAdmin class commented out - all payment functionality is now handled through Invoice management
# The entire PaymentAdmin class has been removed from admin interface


@admin.register(Pricing, site=admin_site)
class PricingAdmin(ModelAdmin):
    """
    Admin interface for Pricing model using Django Unfold.
    """

    # List Display
    list_display = [
        "id",
        "visa_type_display",
        "amount",
        "currency",
        "is_active",
        "created_at",
        "updated_at",
    ]

    # List Display Links
    list_display_links = ["id", "visa_type_display"]

    # Search Fields
    search_fields = [
        "visa_type",
    ]

    # List Filters
    list_filter = [
        "is_active",
        "currency",
        "visa_type",
        "created_at",
    ]

    # Fieldsets for Add/Edit Form
    fieldsets = (
        (
            "Pricing Information",
            {
                "fields": (
                    "visa_type",
                    ("amount", "currency"),
                    "is_active",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    # Readonly Fields
    readonly_fields = ["created_at", "updated_at"]

    # List Per Page
    list_per_page = 25

    # Custom Display Methods
    @display(description="Visa Type", ordering="visa_type")
    def visa_type_display(self, obj):
        """Display visa type with formatting."""
        return obj.get_visa_type_display()

    def get_readonly_fields(self, request, obj=None):
        """Make visa_type readonly when editing existing pricing."""
        if obj:  # Editing existing object
            return ["visa_type", "created_at", "updated_at"]
        return ["created_at", "updated_at"]


# Custom Form for Invoice
class InvoiceForm(ModelForm):
    """Custom form for Invoice - visa applications are managed via AJAX, not form fields."""

    class Meta:
        model = Invoice
        fields = "__all__"
        exclude = ['visa_applications']  # Exclude from form since we manage via custom UI

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make client required
        if 'client' in self.fields:
            self.fields['client'].required = True


@admin.register(Invoice, site=admin_site)
class InvoiceAdmin(ModelAdmin):
    """
    Admin interface for Invoice model using Django Unfold.
    """

    change_list_template = "admin/core/invoice/change_list.html"
    form = InvoiceForm

    # List Display
    list_display = [
        "invoice_number",
        "client_name",
        "visa_applications_display",
        "total_amount",
        "currency",
        "status_badge",
        "invoice_date",
        "due_date",
        "created_at",
        "actions_column",
    ]

    # List Display Links
    list_display_links = ["invoice_number", "client_name"]

    # Search Fields
    search_fields = [
        "invoice_number",
        "client__first_name",
        "client__last_name",
        "client__email",
        "client__passport_number",
    ]

    # List Filters
    list_filter = [
        "status",
        InvoiceOutstandingFilter,
        "currency",
        "invoice_date",
        "due_date",
        "created_at",
    ]

    # Fieldsets for Add/Edit Form
    fieldsets = (
        (
            "Invoice Information",
            {
                "fields": (
                    "invoice_number",
                    ("invoice_date", "due_date"),
                    "status",
                ),
            },
        ),
        (
            "Client",
            {
                "fields": (
                    "client",
                ),
                "description": "Select a client, then add visa applications using the interface below.",
            },
        ),
        (
            "Financial Information",
            {
                "fields": (
                    ("subtotal", "currency"),
                    "discount",
                    ("tax_rate", "tax_amount"),
                    "total_amount",
                ),
            },
        ),
        (
            "Payment & Status",
            {
                "fields": (
                    "payment",
                    ("sent_date", "paid_date"),
                ),
            },
        ),
        (
            "Additional Information",
            {
                "fields": (
                    "notes",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    # Readonly Fields
    readonly_fields = ["created_at", "updated_at", "tax_amount", "total_amount", "subtotal"]

    # Filter Horizontal removed - using custom UI with through model
    # filter_horizontal = ["visa_applications"]

    # List Per Page
    list_per_page = 25

    # Custom Methods
    @display(description="Client", ordering="client__first_name")
    def client_name(self, obj):
        """Display client name with link."""
        url = reverse("admin:core_client_change", args=[obj.client.pk])
        return format_html(
            '<a href="{}" style="font-weight: 600; color: #2563eb;">{}</a>',
            url,
            obj.client.full_name,
        )

    @display(description="Visa Applications")
    def visa_applications_display(self, obj):
        """Display visa applications with links."""
        apps = obj.visa_applications.all()
        if not apps:
            return format_html('<span style="color: #6b7280;">No applications</span>')

        links = []
        for app in apps:
            url = reverse("admin:core_visaapplication_change", args=[app.pk])
            visa_type = app.get_visa_type_display()
            links.append(
                format_html(
                    '<a href="{}" style="color: #2563eb; margin-right: 8px;">{}</a>',
                    url,
                    visa_type,
                )
            )
        return format_html("".join(links))

    @display(description="Status", ordering="status")
    def status_badge(self, obj):
        """Display status with colored badge."""
        status_colors = {
            "draft": "#6b7280",
            "sent": "#3b82f6",
            "paid": "#10b981",
            "overdue": "#ef4444",
            "cancelled": "#9ca3af",
        }
        color = status_colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="display: inline-block; padding: 4px 12px; background-color: {}; color: white; border-radius: 12px; font-size: 12px; font-weight: 600;">{}</span>',
            color,
            obj.get_status_display(),
        )

    @display(description="Actions")
    def actions_column(self, obj):
        """Display action buttons."""
        view_url = reverse("admin:core_invoice_change", args=[obj.pk])
        preview_url = reverse("admin:core_invoice_preview", args=[obj.pk])
        pdf_url = reverse("admin:core_invoice_pdf", args=[obj.pk])

        return format_html(
            '<a href="{}" class="button" style="margin-right: 8px;">View</a>'
            '<a href="{}" class="button" target="_blank" style="margin-right: 8px;">Preview</a>'
            '<a href="{}" class="button" target="_blank">PDF</a>',
            view_url,
            preview_url,
            pdf_url,
        )

    @display(description="Visa Applications")
    def visa_applications_section(self, obj):
        """Display visa applications selection interface."""
        invoice_id = obj.pk if obj and obj.pk else 0
        client_id = obj.client.pk if obj and obj.client else 0

        # Get selected applications from instance variable set in change_view/add_view
        selected_apps_json = getattr(self, '_selected_applications_json', '[]')

        return format_html(
            '<div class="invoice-applications-section">'
            '<input type="hidden" id="selected-applications-data" name="selected_applications_data" value="">'
            '<div class="applications-selector" style="display: flex; align-items: flex-end; gap: 10px; margin-bottom: 15px;">'
            '<div style="flex: 1;">'
            '<label class="block font-semibold mb-2 text-font-important-light text-sm dark:text-font-important-dark mb-2">Visa Applications</label>'
            '<select id="available-applications" name="available_applications" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px;">'
            '<option value="">-- Select a client first --</option>'
            '</select>'
            '<div id="applications-error" class="error-message" style="display: none; color: #dc3545; font-size: 12px; margin-top: 5px;"></div>'
            '</div>'
            '<button type="button" id="add-application-btn" disabled style="padding: 8px 16px; background: #007cba; color: white; border: none; border-radius: 4px; cursor: pointer; white-space: nowrap; font-size: 14px; height: fit-content;">+ Add</button>'
            '</div>'
            '<div class="selected-applications" style="margin-top: 15px;">'
            '<h3 style="margin: 0 0 10px 0; font-size: 14px; font-weight: 600;">Selected Applications</h3>'
            '<div id="selected_applications_container">'
            '<div class="empty-state" style="text-align: center; padding: 20px; color: #6b7280; font-size: 14px;">'
            '<p style="margin: 0;">No applications selected. Select a client and add applications above.</p>'
            '</div>'
            '</div>'
            '</div>'
            '<script>'
            'window.INVOICE_ID = {};'
            'window.CLIENT_ID = {};'
            'window.SELECTED_APPLICATIONS = {};'
            '</script>'
            '</div>',
            invoice_id,
            client_id if client_id else 'null',
            selected_apps_json
        )

    def get_urls(self):
        """Add custom URLs for invoice actions."""
        urls = super().get_urls()
        # IMPORTANT: String-based paths must come BEFORE integer-based paths
        # to prevent Django from trying to match strings as invoice IDs
        custom_urls = [
            # String-based endpoints (must come first)
            path(
                "builder/",
                self.admin_site.admin_view(self.builder_view),
                name="core_invoice_builder",
            ),
            path(
                "<int:invoice_id>/builder/",
                self.admin_site.admin_view(self.builder_view),
                name="core_invoice_builder_edit",
            ),
            path(
                "available-applications/",
                self.admin_site.admin_view(self.get_available_applications),
                name="core_invoice_get_available_applications",
            ),
            # Redirect old endpoint name for backward compatibility (handles cached requests)
            path(
                "get-available-applications/",
                self.admin_site.admin_view(self.redirect_to_available_applications),
                name="core_invoice_get_available_applications_old",
            ),
            path(
                "get-visa-prices/",
                self.admin_site.admin_view(self.get_visa_prices),
                name="core_invoice_get_visa_prices",
            ),
            # Integer-based endpoints (come after string paths)
            path(
                "<int:invoice_id>/preview/",
                self.admin_site.admin_view(self.invoice_preview),
                name="core_invoice_preview",
            ),
            path(
                "<int:invoice_id>/pdf/",
                self.admin_site.admin_view(self.invoice_pdf),
                name="core_invoice_pdf",
            ),
            path(
                "<int:invoice_id>/send/",
                self.admin_site.admin_view(self.invoice_send),
                name="core_invoice_send",
            ),
            path(
                "<int:invoice_id>/add-application/",
                self.admin_site.admin_view(self.add_application),
                name="core_invoice_add_application",
            ),
            path(
                "<int:invoice_id>/remove-application/",
                self.admin_site.admin_view(self.remove_application),
                name="core_invoice_remove_application",
            ),
        ]
        return custom_urls + urls

    def builder_view(self, request, invoice_id=None):
        """Standalone invoice builder page to keep UI simple."""
        from django.contrib import messages
        from django.utils import timezone
        from datetime import datetime

        clients = Client.objects.all().order_by("first_name", "last_name")

        selected_client_id = request.POST.get("client") or request.GET.get("client")
        selected_app_ids = request.POST.getlist("visa_applications") if request.method == "POST" else []
        tax_rate_value = request.POST.get("tax_rate", "0")
        due_date_value = request.POST.get("due_date", "")
        notes_value = request.POST.get("notes", "")
        items_payload = request.POST.get("items_json", "[]")
        other_payments_payload = request.POST.get("other_payments_json", "[]")
        status_value = request.POST.get("status") or "draft"
        errors = []
        items_data = []
        other_payments_data = []
        invoice_obj = None
        status_choices = [choice[0] for choice in Invoice.INVOICE_STATUS_CHOICES]

        # If editing, load current invoice and prefill defaults
        if invoice_id:
            try:
                invoice_obj = Invoice.objects.get(pk=invoice_id)
                if request.method != "POST":
                    selected_client_id = str(invoice_obj.client.pk)
                    tax_rate_value = str(invoice_obj.tax_rate)
                    due_date_value = invoice_obj.due_date.isoformat() if invoice_obj.due_date else ""
                    notes_value = invoice_obj.notes or ""
                    status_value = invoice_obj.status
                else:
                    if not request.POST.get("status"):
                        status_value = invoice_obj.status

                    # Build items payload from existing applications
                    import json
                    items_list = []
                    applications = list(invoice_obj.invoice_applications.select_related("visa_application"))
                    discount_total = invoice_obj.discount or Decimal("0")
                    discount_share = (discount_total / len(applications)) if applications else Decimal("0")
                    for ia in applications:
                        app = ia.visa_application
                        items_list.append({
                            "id": app.pk,
                            "name": f"{app.get_visa_type_display()} - {app.get_stage_display()}",
                            "price": float(ia.unit_price),
                            "currency": invoice_obj.currency or "GBP",
                            "discount": float(discount_share) if discount_share else 0,
                        })
                    items_payload = json.dumps(items_list)

                    other_payments_payload = json.dumps([
                        {"description": op.description, "amount": float(op.amount)}
                        for op in invoice_obj.other_payments.all()
                    ])
            except Invoice.DoesNotExist:
                errors.append("Invoice not found for editing.")
                invoice_obj = None

        if request.method == "POST":
            client = None
            try:
                client = Client.objects.get(pk=selected_client_id)
            except Client.DoesNotExist:
                errors.append("Selected client was not found.")

            if items_payload:
                try:
                    import json
                    items_data = json.loads(items_payload)
                except Exception:
                    errors.append("Could not read invoice items. Please add them again.")
            else:
                errors.append("Add at least one visa application item.")

            if other_payments_payload:
                try:
                    import json
                    other_payments_data = json.loads(other_payments_payload)
                except Exception:
                    errors.append("Could not read other payments. Please add them again.")

            try:
                tax_rate_decimal = Decimal(tax_rate_value or "0")
            except Exception:
                tax_rate_decimal = Decimal("0")
                errors.append("Invalid tax rate.")

            if status_value not in status_choices:
                status_value = invoice_obj.status if invoice_obj else "draft"

            # Parse due date
            due_date = None
            if due_date_value:
                try:
                    due_date = datetime.strptime(due_date_value, "%Y-%m-%d").date()
                except ValueError:
                    errors.append("Invalid due date format. Use YYYY-MM-DD.")

            if not errors and client:
                is_edit = invoice_obj is not None
                if is_edit:
                    invoice = invoice_obj
                    invoice.client = client
                    invoice.due_date = due_date
                    invoice.tax_rate = tax_rate_decimal
                    invoice.notes = notes_value
                    invoice.status = status_value
                else:
                    invoice = Invoice.objects.create(
                        client=client,
                        invoice_date=timezone.now().date(),
                        due_date=due_date,
                        tax_rate=tax_rate_decimal,
                        status=status_value or "draft",
                        notes=notes_value,
                    )

                detected_currency = None
                created_items = 0
                discount_total = Decimal("0.00")

                # Clear existing items when editing
                if is_edit:
                    InvoiceApplication.objects.filter(invoice=invoice).delete()
                    InvoiceOtherPayment.objects.filter(invoice=invoice).delete()

                # Attach applications and store prices
                for item in items_data:
                    app_id = item.get("id")
                    item_discount = item.get("discount", 0)
                    try:
                        item_discount = Decimal(str(item_discount or "0"))
                        if item_discount < 0:
                            item_discount = Decimal("0")
                    except Exception:
                        item_discount = Decimal("0")

                    try:
                        visa_app = VisaApplication.objects.get(pk=app_id, client=client)
                    except VisaApplication.DoesNotExist:
                        errors.append(f"Visa application {app_id} not found for this client.")
                        continue

                    price = Pricing.get_price_for_visa_type(visa_app.visa_type)
                    if item_discount > price:
                        item_discount = price
                    discount_total += item_discount
                    InvoiceApplication.objects.create(
                        invoice=invoice,
                        visa_application=visa_app,
                        unit_price=price,
                    )
                    created_items += 1
                    # If pricing carries currency, remember it
                    try:
                        pricing = Pricing.objects.get(visa_type=visa_app.visa_type, is_active=True)
                        detected_currency = detected_currency or pricing.currency
                    except Pricing.DoesNotExist:
                        pass

                if errors or created_items == 0:
                    if not is_edit:
                        invoice.delete()
                else:
                    for payment_item in other_payments_data:
                        description = (payment_item.get("description") or "").strip()
                        raw_amount = payment_item.get("amount")
                        if not description:
                            continue
                        try:
                            amount = Decimal(str(raw_amount or "0"))
                        except Exception:
                            amount = Decimal("0")
                        if amount <= 0:
                            continue
                        InvoiceOtherPayment.objects.create(
                            invoice=invoice,
                            description=description,
                            amount=amount,
                        )

                    invoice.discount = discount_total
                    if detected_currency and invoice.currency != detected_currency:
                        invoice.currency = detected_currency

                    invoice.calculate_totals()
                    if is_edit:
                        messages.success(request, f"Invoice {invoice.invoice_number} updated successfully.")
                    else:
                        messages.success(request, f"Invoice {invoice.invoice_number} created successfully.")

                    if "_addanother" in request.POST:
                        if selected_client_id:
                            return redirect(f"{reverse('admin:core_invoice_builder')}?client={selected_client_id}")
                        return redirect("admin:core_invoice_builder")
                    if "_continue" in request.POST:
                        return redirect("admin:core_invoice_builder_edit", invoice.pk)
                    return redirect("admin:core_invoice_changelist")

        context = {
            **self.admin_site.each_context(request),
            "title": "Create Invoice" if not invoice_obj else f"Edit Invoice {invoice_obj.invoice_number}",
            "clients": clients,
            "selected_client_id": selected_client_id,
            "preselected_app_ids": selected_app_ids,
            "tax_rate_value": tax_rate_value,
            "due_date_value": due_date_value,
            "notes_value": notes_value,
            "items_payload": items_payload or "[]",
            "other_payments_payload": other_payments_payload or "[]",
            "errors": errors,
            "invoice_obj": invoice_obj,
            "status_choices": Invoice.INVOICE_STATUS_CHOICES,
            "status_value": status_value,
        }
        return render(request, "admin/core/invoice/builder.html", context)

    def redirect_to_available_applications(self, request):
        """Redirect old endpoint name to new endpoint for backward compatibility."""
        from django.http import HttpResponseRedirect
        from urllib.parse import urlencode

        # Preserve query parameters
        query_string = request.GET.urlencode()
        new_url = f"/admin/core/invoice/available-applications/"
        if query_string:
            new_url += f"?{query_string}"
        return HttpResponseRedirect(new_url)

    def get_available_applications(self, request):
        """AJAX endpoint to get available visa applications for a client."""
        from django.http import JsonResponse
        import logging

        logger = logging.getLogger(__name__)
        client_id = request.GET.get('client_id')
        invoice_id = request.GET.get('invoice_id', '0')

        if not client_id:
            logger.warning('get_available_applications called without client_id')
            return JsonResponse({'error': 'client_id is required'}, status=400)

        try:
            client = Client.objects.get(pk=client_id)
            logger.info(f'Loading applications for client {client_id}: {client.full_name}')

            # Get all visa applications for this client
            visa_apps = VisaApplication.objects.filter(client=client).select_related('client').order_by('-created_at')

            # If editing existing invoice, exclude already added applications
            selected_ids = set()
            if invoice_id and invoice_id != '0':
                try:
                    invoice = Invoice.objects.get(pk=invoice_id)
                    selected_ids = set(invoice.invoice_applications.values_list('visa_application_id', flat=True))
                    logger.info(f'Excluding {len(selected_ids)} already selected applications for invoice {invoice_id}')
                except Invoice.DoesNotExist:
                    logger.warning(f'Invoice {invoice_id} not found, not excluding any applications')
                    pass

            apps_data = []
            # Get currency from client's invoice or default to GBP
            currency = "GBP"
            if invoice_id and invoice_id != '0':
                try:
                    invoice = Invoice.objects.get(pk=invoice_id)
                    currency = invoice.currency
                except Invoice.DoesNotExist:
                    pass

            for app in visa_apps:
                if app.pk not in selected_ids:
                    try:
                        price = Pricing.get_price_for_visa_type(app.visa_type)
                        price_float = float(price) if price else 0.0
                        # Get currency from pricing if available
                        try:
                            pricing = Pricing.objects.get(visa_type=app.visa_type, is_active=True)
                            currency = pricing.currency
                        except Pricing.DoesNotExist:
                            pass
                    except Exception as e:
                        logger.warning(f'Error getting price for visa type {app.visa_type}: {e}')
                        price_float = 0.0

                    apps_data.append({
                        'id': app.pk,
                        'name': f"{app.get_visa_type_display()} - {app.get_stage_display()}",
                        'price': f"{price_float:.2f}",
                        'currency': currency
                    })

            logger.info(f'Returning {len(apps_data)} available applications for client {client_id}')
            return JsonResponse({
                'client_id': int(client_id),
                'available_applications': apps_data
            })
        except Client.DoesNotExist:
            logger.error(f'Client {client_id} not found')
            return JsonResponse({'error': 'Client not found'}, status=404)
        except ValueError as e:
            logger.error(f'Invalid client_id format: {client_id}, error: {e}')
            return JsonResponse({'error': 'Invalid client ID format'}, status=400)
        except Exception as e:
            logger.exception(f'Error in get_available_applications: {e}')
            return JsonResponse({'error': str(e)}, status=500)

    def add_application(self, request, invoice_id):
        """AJAX endpoint to add a visa application to an invoice."""
        from django.http import JsonResponse
        import json

        try:
            invoice = Invoice.objects.get(pk=invoice_id)
        except Invoice.DoesNotExist:
            return JsonResponse({'error': 'Invoice not found'}, status=404)

        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)

        try:
            data = json.loads(request.body)
            visa_app_id = data.get('visa_application_id')

            if not visa_app_id:
                return JsonResponse({'error': 'visa_application_id is required'}, status=400)

            # Validate visa application belongs to same client
            try:
                visa_app = VisaApplication.objects.get(pk=visa_app_id)
                if visa_app.client != invoice.client:
                    return JsonResponse({'error': 'Visa application does not belong to this client'}, status=400)
            except VisaApplication.DoesNotExist:
                return JsonResponse({'error': 'Visa application not found'}, status=404)

            # Check if already added
            if InvoiceApplication.objects.filter(invoice=invoice, visa_application=visa_app).exists():
                return JsonResponse({'error': 'Application already added to invoice'}, status=400)

            # Get current price
            price = Pricing.get_price_for_visa_type(visa_app.visa_type)

            # Create InvoiceApplication
            invoice_app = InvoiceApplication.objects.create(
                invoice=invoice,
                visa_application=visa_app,
                unit_price=price
            )

            # Recalculate totals
            invoice.calculate_totals()

            # Get updated selected applications
            selected_apps = []
            for ia in invoice.invoice_applications.all():
                selected_apps.append({
                    'id': ia.visa_application.pk,
                    'display': f"{ia.visa_application.get_visa_type_display()} - {ia.visa_application.get_stage_display()}",
                    'price': float(ia.unit_price)
                })

            return JsonResponse({
                'success': True,
                'selected_applications': selected_apps,
                'subtotal': float(invoice.subtotal),
                'total': float(invoice.total_amount)
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def remove_application(self, request, invoice_id):
        """AJAX endpoint to remove a visa application from an invoice."""
        from django.http import JsonResponse
        import json

        try:
            invoice = Invoice.objects.get(pk=invoice_id)
        except Invoice.DoesNotExist:
            return JsonResponse({'error': 'Invoice not found'}, status=404)

        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)

        try:
            data = json.loads(request.body)
            visa_app_id = data.get('visa_application_id')

            if not visa_app_id:
                return JsonResponse({'error': 'visa_application_id is required'}, status=400)

            # Remove InvoiceApplication
            InvoiceApplication.objects.filter(
                invoice=invoice,
                visa_application_id=visa_app_id
            ).delete()

            # Recalculate totals
            invoice.calculate_totals()

            # Get updated selected applications
            selected_apps = []
            for ia in invoice.invoice_applications.all():
                selected_apps.append({
                    'id': ia.visa_application.pk,
                    'display': f"{ia.visa_application.get_visa_type_display()} - {ia.visa_application.get_stage_display()}",
                    'price': float(ia.unit_price)
                })

            return JsonResponse({
                'success': True,
                'selected_applications': selected_apps,
                'subtotal': float(invoice.subtotal),
                'total': float(invoice.total_amount)
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def get_visa_prices(self, request):
        """AJAX endpoint to get prices for visa applications."""
        from django.http import JsonResponse
        visa_app_ids = request.GET.getlist('visa_applications[]')

        prices = {}
        total = 0

        for visa_app_id in visa_app_ids:
            try:
                visa_app = VisaApplication.objects.get(pk=visa_app_id)
                price = Pricing.get_price_for_visa_type(visa_app.visa_type)
                prices[visa_app_id] = float(price)
                total += float(price)
            except (VisaApplication.DoesNotExist, ValueError):
                continue

        return JsonResponse({
            'prices': prices,
            'total': total
        })

    def invoice_preview(self, request, invoice_id):
        """Preview invoice in HTML."""
        invoice = get_object_or_404(Invoice, pk=invoice_id)
        context = self._build_invoice_context(invoice)
        context["title"] = f"Invoice {invoice.invoice_number}"
        return render(request, "admin/core/invoice/preview.html", context)

    def invoice_pdf(self, request, invoice_id):
        """Generate and download PDF invoice."""
        from django.http import HttpResponse
        from django.template.loader import render_to_string

        invoice = get_object_or_404(Invoice, pk=invoice_id)
        context = self._build_invoice_context(invoice, request=request)
        context["title"] = f"Invoice {invoice.invoice_number}"

        html = render_to_string("admin/core/invoice/preview_pdf.html", context)
        try:
            from weasyprint import HTML
        except Exception:
            return HttpResponse(
                "PDF generation is not available. Install WeasyPrint and reload.",
                status=500,
                content_type="text/plain",
            )

        pdf = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
        return response

    def _build_invoice_context(self, invoice, request=None):
        from django.templatetags.static import static

        def currency_symbol(code):
            if code == "GBP":
                return "£"
            if code == "USD":
                return "$"
            if code == "EUR":
                return "€"
            return code + " "

        items = []
        for invoice_app in invoice.invoice_applications.select_related("visa_application"):
            app = invoice_app.visa_application
            items.append({
                "description": f"{app.get_visa_type_display()} - {app.get_stage_display()}",
                "price": invoice_app.unit_price,
                "qty": 1,
                "total": invoice_app.unit_price,
            })

        for other_payment in invoice.other_payments.all():
            items.append({
                "description": other_payment.description,
                "price": other_payment.amount,
                "qty": 1,
                "total": other_payment.amount,
            })

        blank_rows = max(0, 2 - len(items))

        logo_url = static("admin/img/invoice_logo.png")
        css_url = static("admin/css/invoice.css")
        if request is not None:
            logo_url = request.build_absolute_uri(logo_url)
            css_url = request.build_absolute_uri(css_url)

        return {
            "invoice": invoice,
            "invoice_items": items,
            "blank_rows": range(blank_rows),
            "currency_symbol": currency_symbol(invoice.currency),
            "contact_email": "contact@vortexease.com",
            "site_url": "https://vortexease.com",
            "terms_url": "https://vortexease.com/terms-and-conditions/",
            "logo_url": logo_url,
            "css_url": css_url,
        }

    def invoice_send(self, request, invoice_id):
        """Send invoice via email."""
        from django.contrib import messages
        from django.core.mail import EmailMessage
        from django.template.loader import render_to_string
        from django.utils import timezone
        from django.conf import settings

        invoice = get_object_or_404(Invoice, pk=invoice_id)

        if invoice.status != "draft":
            messages.error(
                request,
                f"Invoice can only be sent from Draft status. Current status: {invoice.get_status_display()}."
            )
            return redirect("admin:core_invoice_change", invoice_id)

        context = self._build_invoice_context(invoice, request=request)
        context["title"] = f"Invoice {invoice.invoice_number}"
        html = render_to_string("admin/core/invoice/preview_pdf.html", context)
        try:
            from weasyprint import HTML
        except Exception:
            messages.error(request, "PDF generation is not available. Install WeasyPrint and reload.")
            return redirect("admin:core_invoice_change", invoice_id)

        pdf_bytes = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()

        subject = f"Invoice {invoice.invoice_number}"
        body = (
            f"Dear {invoice.client.full_name},\n\n"
            f"Please find your invoice {invoice.invoice_number} attached.\n\n"
            "Thank you,\nVortex Ease"
        )

        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=[invoice.client.email],
        )
        email.attach(f"invoice_{invoice.invoice_number}.pdf", pdf_bytes, "application/pdf")

        try:
            email.send(fail_silently=False)
        except Exception as exc:
            messages.error(request, f"Failed to send invoice email: {exc}")
            return redirect("admin:core_invoice_change", invoice_id)

        invoice.sent_date = timezone.now()
        invoice.status = "sent"
        invoice.save()
        messages.success(request, f"Invoice {invoice.invoice_number} sent successfully.")
        return redirect("admin:core_invoice_change", invoice_id)

    def get_form(self, request, obj=None, **kwargs):
        """Customize form to auto-calculate totals."""
        form = super().get_form(request, obj, **kwargs)

        # Note: visa_applications is excluded from form and managed via custom UI (visa_applications_section)

        # Make subtotal readonly and add help text
        if 'subtotal' in form.base_fields:
            form.base_fields['subtotal'].help_text = "Subtotal is automatically calculated based on selected visa applications."

        # Handle visa application from URL parameter
        visa_app_id = request.GET.get('visa_application')
        if visa_app_id and not obj:
            # Store for later use in save_related
            form._visa_application_id = visa_app_id

        return form

    def add_view(self, request, form_url="", extra_context=None):
        """Redirect to builder for add flow."""
        from urllib.parse import urlencode
        params = request.GET.urlencode()
        url = reverse("admin:core_invoice_builder")
        if params:
            url = f"{url}?{params}"
        return redirect(url)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        """Redirect edit flow to builder."""
        from urllib.parse import urlencode
        params = request.GET.urlencode()
        try:
            int(object_id)
        except (ValueError, TypeError):
            return super().change_view(request, object_id, form_url, extra_context)

        url = reverse("admin:core_invoice_builder_edit", args=[object_id])
        if params:
            url = f"{url}?{params}"
        return redirect(url)

    class Media:
        js = (
            '/static/admin/js/invoice_new_ux.js',
        )
        css = {
            'all': ('/static/css/admin_inline_custom.css',)
        }

    def save_model(self, request, obj, form, change):
        """Override save to auto-calculate totals and handle selected applications for new invoices."""
        super().save_model(request, obj, form, change)

        # For new invoices, create InvoiceApplication records from hidden field
        if not change and obj.pk:
            selected_apps_data = request.POST.get('selected_applications_data', '')
            if selected_apps_data:
                import json
                try:
                    selected_apps = json.loads(selected_apps_data)
                    for app_data in selected_apps:
                        try:
                            visa_app = VisaApplication.objects.get(pk=app_data.get('id'))
                            # Validate client match
                            if visa_app.client == obj.client:
                                unit_price = Decimal(str(app_data.get('price', 0)))
                                InvoiceApplication.objects.create(
                                    invoice=obj,
                                    visa_application=visa_app,
                                    unit_price=unit_price
                                )
                        except (VisaApplication.DoesNotExist, ValueError, KeyError) as e:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.warning(f"Error creating InvoiceApplication: {e}")
                    # Recalculate totals after adding applications
                    obj.calculate_totals()
                except json.JSONDecodeError:
                    pass

        # Recalculate totals after save (applications are managed via AJAX endpoints)
        if obj.pk:
            obj.calculate_totals()

    def get_changeform_initial_data(self, request):
        """Pre-populate form with client and visa application from URL parameters."""
        initial = super().get_changeform_initial_data(request)

        client_id = request.GET.get('client')
        if client_id:
            initial['client'] = client_id

        visa_application_id = request.GET.get('visa_application')
        if visa_application_id:
            # For many-to-many, we need to set it after save
            initial['_visa_application'] = visa_application_id

        # Set invoice date to today
        from django.utils import timezone
        initial['invoice_date'] = timezone.now().date()

        return initial

    def save_related(self, request, form, formsets, change):
        """Handle visa applications from URL parameter."""
        super().save_related(request, form, formsets, change)

        obj = form.instance
        if obj.pk and not change:  # Only for new invoices
            visa_app_id = request.GET.get('visa_application')
            if visa_app_id:
                from .models import VisaApplication
                try:
                    visa_app = VisaApplication.objects.get(pk=visa_app_id)
                    obj.visa_applications.add(visa_app)
                    obj.calculate_totals()
                except VisaApplication.DoesNotExist:
                    pass
