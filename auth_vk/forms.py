from django import forms
from auth_vk.models import Clinic, User
from datetime import date

class NotificationFilterForm(forms.Form):
    title = forms.CharField(label='Notification Title', max_length=100)
    message = forms.CharField(label='Notification Body', widget=forms.Textarea)
    clinic = forms.ModelChoiceField(queryset=Clinic.objects.all(), required=False)
    specialization = forms.CharField(required=False)
    appointment_from = forms.DateField(required=False)
    appointment_to = forms.DateField(required=False)
    min_age = forms.IntegerField(required=False)
    max_age = forms.IntegerField(required=False)
    only_never_appointed = forms.BooleanField(required=False)