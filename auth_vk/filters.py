import django_filters
from . import models

class AppointmentFilter(django_filters.FilterSet):
    patient_first_name = django_filters.CharFilter(field_name='patient__first_name', lookup_expr="icontains")
    patient_last_name = django_filters.CharFilter(field_name='patient__last_name', lookup_expr='icontains')
    patient_birth_date = django_filters.DateFilter(field_name='patient__birth_date')
    patient_phone_number = django_filters.CharFilter(field_name='patient__phone_number', lookup_expr='icontains')
    created_at = django_filters.DateFilter(field_name='created_at', lookup_expr='date')

    class Meta:
        model = models.Appointment
        fields = []

