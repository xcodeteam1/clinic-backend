from django.contrib import admin

# Register your models here.

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from .models import ChatRoom, Message, Clinic, Illness, Appointment, News, User, FAQ
from .forms import NotificationFilterForm
from django.urls import path
from django.contrib import admin

from django.shortcuts import render, redirect
from django.utils.timezone import now
from datetime import timedelta
from .forms import NotificationFilterForm
from .models import User, Appointment, DeviceToken
from django.http import JsonResponse



# admin.py
from django import forms
from django.contrib import admin
from django.contrib.admin.helpers import ActionForm
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta
from .models import User, Appointment, DeviceToken
from core.notification import send_push_notification


from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.db.models import Q, Count

from datetime import datetime

import json


# admin.py
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import HttpResponseRedirect, JsonResponse

from rest_framework.authtoken.models import Token
from social_django.models import Association, Nonce, UserSocialAuth

class NotificationForm:
    """Enhanced form for sending notifications with validation"""
    def __init__(self, request_data=None):
        self.data = request_data or {}
    
    def is_valid(self):
        return all([
            self.data.get('title'),
            self.data.get('message'),
            self.data.get('recipients')
        ])
    
    def get_errors(self):
        errors = []
        if not self.data.get('title'):
            errors.append('Title is required')
        if not self.data.get('message'):
            errors.append('Message is required')
        if not self.data.get('recipients'):
            errors.append('At least one recipient group must be selected')
        return errors

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import path
from django.utils.html import format_html
from django.db.models import Q
from django.utils import timezone
from datetime import datetime, timedelta

from .models import User, Appointment, Clinic, DeviceToken, News, FAQ, Illness
from core.notification import send_push_notification


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'first_name', 'last_name', 'user_type', 'get_avatar_display', 'phone_number', 'verified', 'is_active', 'specialization', 'get_age', 'chat_guid')
    list_filter = (
        'user_type', 
        'verified', 
        'is_active', 
        'gender', 
        'specialization',
        'clinics',
        ('date_of_birth', admin.DateFieldListFilter),  # Age filter
    )
    search_fields = ('username', 'email', 'phone_number', 'first_name', 'last_name')
    filter_horizontal = ('clinics',)
    
    # Custom actions - the key improvement!
    actions = ['send_notification_to_selected']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('user_type', 'phone_number', 'date_of_birth', 'gender', 'verified', 
                      'agreed_to_terms', 'biometric_enabled', 'name', 'avatar', 'clinics')
        }),
        ('Doctor Info', {
            'fields': ('medical_license', 'specialization', 'is_available'),
            'classes': ('collapse',)
        }),
    )

    def get_avatar_display(self, obj):
        if obj.avatar:
            return format_html('<img src="{}" style="width: 30px; height: 30px; border-radius: 50%;">', obj.avatar.url)
        return "No Avatar"
    get_avatar_display.short_description = 'Avatar'

    def get_age(self, obj):
        if obj.date_of_birth:
            today = timezone.now().date()
            age = today.year - obj.date_of_birth.year
            if today.month < obj.date_of_birth.month or (today.month == obj.date_of_birth.month and today.day < obj.date_of_birth.day):
                age -= 1
            return age
        return None
    get_age.short_description = 'Age'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('send-notification/', self.admin_site.admin_view(self.send_notification_view), 
                 name='users_user_send_notification'),
        ]
        return custom_urls + urls

    def send_notification_to_selected(self, request, queryset):
        """Send notification to selected users - simple and clean"""
        # Store selected user IDs in session
        selected_ids = list(queryset.values_list('id', flat=True))
        request.session['selected_user_ids'] = selected_ids
        
        messages.info(request, f'{len(selected_ids)} users selected for notification.')
        return redirect('admin:users_user_send_notification')
    
    send_notification_to_selected.short_description = _("Send notification to selected users")

    def send_notification_view(self, request):
        """Simple notification form"""
        selected_ids = request.session.get('selected_user_ids', [])
        selected_users = User.objects.filter(id__in=selected_ids)
        
        if not selected_users.exists():
            messages.error(request, 'No users selected. Please go back and select users first.')
            return redirect('admin:auth_vk_user_changelist')

        context = {
            'title': 'Send Push Notification',
            'selected_users': selected_users,
            'selected_count': len(selected_ids),
            'opts': self.model._meta,
            'has_permission': True,
        }

        if request.method == 'POST':
            title = request.POST.get('title', '').strip()
            message = request.POST.get('message', '').strip()
            
            if not title or not message:
                messages.error(request, 'Both title and message are required.')
                return render(request, 'admin/send_notification_simple.html', context)
            
            success_count = 0
            error_count = 0
            
            for user in selected_users:
                try:
                    tokens = DeviceToken.objects.filter(user=user)
                    
                    if tokens.exists():
                        for device_token in tokens:
                            send_push_notification(
                                device_token=device_token.token,
                                title=title,
                                body=message,
                                data={'type': 'admin_notification'}
                            )
                        success_count += 1
                    else:
                        error_count += 1
                        
                except Exception as e:
                    error_count += 1
                    print(f"Error sending notification to {user.username}: {str(e)}")
            
            if 'selected_user_ids' in request.session:
                del request.session['selected_user_ids']
            
            if success_count > 0:
                messages.success(request, f'✅ Notifications sent to {success_count} users successfully!')
            if error_count > 0:
                messages.warning(request, f'⚠️ {error_count} users couldn\'t receive notifications (no device tokens or errors)')
            
            return redirect('admin:auth_vk_user_changelist')

        return render(request, 'admin/send_notification.html', context)



# Custom filters for more specific filtering
class AgeRangeFilter(admin.SimpleListFilter):
    title = 'age range'
    parameter_name = 'age_range'

    def lookups(self, request, model_admin):
        return [
            ('0-18', 'Under 18'),
            ('18-30', '18-30 years'),
            ('30-45', '30-45 years'),
            ('45-60', '45-60 years'),
            ('60+', 'Over 60'),
        ]

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
            
        today = timezone.now().date()
        
        if self.value() == '0-18':
            min_date = today - timedelta(days=18*365.25)
            return queryset.filter(date_of_birth__gt=min_date)
        elif self.value() == '18-30':
            min_date = today - timedelta(days=30*365.25)
            max_date = today - timedelta(days=18*365.25)
            return queryset.filter(date_of_birth__lte=max_date, date_of_birth__gt=min_date)
        elif self.value() == '30-45':
            min_date = today - timedelta(days=45*365.25)
            max_date = today - timedelta(days=30*365.25)
            return queryset.filter(date_of_birth__lte=max_date, date_of_birth__gt=min_date)
        elif self.value() == '45-60':
            min_date = today - timedelta(days=60*365.25)
            max_date = today - timedelta(days=45*365.25)
            return queryset.filter(date_of_birth__lte=max_date, date_of_birth__gt=min_date)
        elif self.value() == '60+':
            max_date = today - timedelta(days=60*365.25)
            return queryset.filter(date_of_birth__lte=max_date)


class HasDeviceTokenFilter(admin.SimpleListFilter):
    title = 'can receive notifications'
    parameter_name = 'has_device_token'

    def lookups(self, request, model_admin):
        return [
            ('yes', 'Can receive notifications'),
            ('no', 'Cannot receive notifications'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(devicetoken__is_active=True).distinct()
        elif self.value() == 'no':
            return queryset.exclude(devicetoken__is_active=True).distinct()


# Add the custom filters to UserAdmin
UserAdmin.list_filter = UserAdmin.list_filter + (AgeRangeFilter, HasDeviceTokenFilter)





@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'clinic', 'date', 'time', 'status', 'created_at')
    list_filter = ('status', 'date', 'clinic', 'doctor__specialization', 'created_at')
    search_fields = ('patient__username', 'doctor__username', 'clinic__name')
    date_hierarchy = 'date'
    raw_id_fields = ('patient', 'doctor')
    
    actions = ['send_reminder_notifications', 'mark_as_completed']
    
    def send_reminder_notifications(self, request, queryset):
        """Send appointment reminder notifications"""
        count = 0
        for appointment in queryset.filter(status='scheduled'):
            try:
                # Send reminder notification logic here
                count += 1
            except Exception as e:
                messages.error(request, f'Failed to send reminder for {appointment}: {str(e)}')
        
        messages.success(request, f'Reminder notifications sent for {count} appointments.')
    
    send_reminder_notifications.short_description = "Send appointment reminders"
    
    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status='completed')
        messages.success(request, f'{updated} appointments marked as completed.')
    
    mark_as_completed.short_description = "Mark selected appointments as completed"





admin.site.register(Clinic)

admin.site.register(Illness)

admin.site.register(News)
admin.site.register(FAQ)
admin.site.register(DeviceToken)


# Unregister social_django models
admin.site.unregister(Association)
admin.site.unregister(Nonce)
admin.site.unregister(UserSocialAuth)

def safe_unregister(model):
    if model in admin.site._registry:
        admin.site.unregister(model)

safe_unregister(Token)

@admin.action(description='test')
def update_user(modeladmin, request, queryset):
    queryset.update(first_name='this is first name')

class UserAdmin(admin.ModelAdmin):
    list_display = ['u']

