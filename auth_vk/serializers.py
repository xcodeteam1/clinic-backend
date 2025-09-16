# API implementation for accounts app
from rest_framework import serializers, viewsets, permissions, status
from rest_framework.response import Response

from .models import User, Appointment, Clinic, Specialization, ServiceCategory,\
      Service, Message, ChatRoom, Illness
from . import models


class UserSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'phone_number', 
                 'date_of_birth', 'gender', 'biometric_enabled', 'avatar', 'specialization')
        read_only_fields = ('username',)

    def get_avatar(self, obj):
        request = self.context.get("context")
        if obj.avatar:
            return request.build_absolute_uri(obj.avatar.url)
        return None



class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'phone_number', 'date_of_birth', 'gender', 
                  'email', 'password', 'agreed_to_terms')
    
    def create(self, validated_data):
        # Create username based on phone number
        username = validated_data['phone_number']
        validated_data['username'] = username
        
        # Create new user
        user = User.objects.create_user(
            username=username,
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone_number=validated_data['phone_number'],
            date_of_birth=validated_data.get('date_of_birth'),
            gender=validated_data.get('gender'),
            agreed_to_terms=validated_data.get('agreed_to_terms', False)
        )
        return user
    

# API implementation for appointments app
from rest_framework import serializers, viewsets, permissions, filters

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend

class ClinicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinic
        fields = '__all__'

class SpecializationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialization
        fields = '__all__'



class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = '__all__'

class ServiceSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Service
        fields = ('id', 'name', 'category', 'category_name', 'description', 'price', 'duration')
    
    def get_category_name(self, obj):
        return obj.category.name

# class AppointmentSerializer(serializers.ModelSerializer):
#     doctor_name = serializers.SerializerMethodField()
#     clinic_name = serializers.SerializerMethodField()
#     service_name = serializers.SerializerMethodField()
    
#     class Meta:
#         model = Appointment
#         fields = ('id', 'patient', 'doctor', 'doctor_name', 'service', 'service_name', 
#                  'clinic', 'clinic_name', 'date', 'time', 'status', 'created_at')
#         read_only_fields = ('status', 'created_at')
    
#     def get_doctor_name(self, obj):
#         return f"{obj.doctor.first_name} {obj.doctor.last_name}"
    
#     def get_clinic_name(self, obj):
#         return obj.clinic.name
    
#     def get_service_name(self, obj):
#         return obj.service.name
    


# API implementation for chat app
from rest_framework import serializers, viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action

from django.db.models import Q, Max, Count, F, Value, BooleanField
from django.db.models.functions import Coalesce

class ChatRoomSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    doctor_specialization = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatRoom
        fields = ('id', 'patient', 'doctor', 'type', 'status', 'created_at', 'updated_at',
                 'last_message', 'unread_count', 'doctor_name', 'doctor_specialization')
        read_only_fields = ('created_at', 'updated_at', 'patient')
    
    def get_last_message(self, obj):
        last_message = obj.messages.order_by('-created_at').first()
        if last_message:
            return {
                'content': last_message.content,
                'created_at': last_message.created_at,
                'is_from_doctor': last_message.is_from_doctor
            }
        return None
    
    def get_unread_count(self, obj):
        user = self.context['request'].user
        if user.is_staff:  # For staff/doctors
            return obj.messages.filter(is_from_doctor=False, read=False).count()
        else:  # For patients
            return obj.messages.filter(is_from_doctor=True, read=False).count()
    
    def get_doctor_name(self, obj):
        if obj.doctor:
            return f"Dr. {obj.doctor.first_name} {obj.doctor.last_name}"
        return None
    
    # def get_doctor_specialization(self, obj):
    #     if obj.doctor:
    #         return obj.doctor.specialization.name
    #     return None




class ClinicSerializer(serializers.ModelSerializer):
    doctors_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Clinic
        fields = ['id', 'uuid', 'name', 'address', 'phone', 'email', 'photo',
                 'doctors_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
    
    def get_doctors_count(self, obj):
        return obj.doctors.filter(is_active=True).count()
    


class IllnessSerializer(serializers.ModelSerializer):
    treatable_by_specializations = SpecializationSerializer(many=True, read_only=True)
    treatable_by_specialization_ids = serializers.PrimaryKeyRelatedField(
        queryset=Specialization.objects.all(),
        many=True,
        write_only=True,
        source='treatable_by_specializations'
    )
    doctors_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Illness
        fields = ['id', 'name', 'description', 'severity_level',
                 'treatable_by_specializations', 'treatable_by_specialization_ids',
                 'doctors_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
    
    def get_doctors_count(self, obj):
        return obj.doctors.filter(is_active=True).count()





from rest_framework import serializers
from datetime import datetime, timedelta, time
from django.utils import timezone
from .models import Appointment, Clinic, DoctorSchedule


class TimeSlotSerializer(serializers.Serializer):
    time = serializers.TimeField()
    is_available = serializers.BooleanField()
    appointment_id = serializers.IntegerField(required=False, allow_null=True)


class AvailableTimesSerializer(serializers.Serializer):
    date = serializers.DateField()
    doctor_id = serializers.IntegerField()
    clinic_id = serializers.IntegerField()
    available_times = TimeSlotSerializer(many=True, read_only=True)
    working_hours = serializers.DictField(read_only=True)


class AppointmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)
    
    class Meta:
        model = Appointment
        fields = [
            'id', 'patient', 'patient_name', 'doctor', 'doctor_name', 
            'clinic', 'clinic_name', 'date', 'time', 'status', 
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['patient', 'created_at', 'updated_at']

    def get_patient_name(self, obj):
        print(obj.patient, 'patient')
        print(obj.patient.get_full_name(), 'hereeeee')
        return obj.patient.get_full_name()
    
    def get_doctor_name(self, obj):
        return obj.doctor.get_full_name()

from .models import News

class NewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = News
        fields = "__all__"

# serializers.py

from rest_framework import serializers
from .models import Appointment, DoctorSchedule
from datetime import datetime
from django.utils import timezone
from django.utils.timezone import make_aware, is_naive


class AppointmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = ['doctor', 'clinic', 'date', 'time', 'notes']

    def validate(self, data):
        doctor = data.get('doctor')
        clinic = data.get('clinic')
        date = data.get('date')
        time_slot = data.get('time')

        if doctor and clinic and not doctor.clinics.filter(id=clinic.id).exists():
            raise serializers.ValidationError("Doctor does not work at this clinic.")

        if date and time_slot:
            appointment_datetime = datetime.combine(date, time_slot)
            
            # Make timezone-aware if needed
            if is_naive(appointment_datetime):
                appointment_datetime = make_aware(appointment_datetime)

            if appointment_datetime <= timezone.now():
                raise serializers.ValidationError("Cannot schedule appointments in the past.")
        print(doctor, 'this is doctor serializer')
        if Appointment.objects.filter(
            doctor=doctor.id,
            clinic=clinic,
            date=date,
            time=time_slot,
            status__in=['pending', 'confirmed']
        ).exists():
            raise serializers.ValidationError("This time slot is already booked.")
        print('this is not appintment')
        # weekday = date.weekday()
        # has_schedule = DoctorSchedule.objects.filter(
        #     doctor=doctor.id,
        #     clinic=clinic,
        #     weekday=weekday,
        #     is_active=True,
        #     start_time__lte=time_slot,
        #     end_time__gte=time_slot
        # ).exists()

        # if not has_schedule:
        #     raise serializers.ValidationError("Doctor is not available at this time.")

        return data


class DoctorScheduleSerializer(serializers.ModelSerializer):
    weekday_name = serializers.CharField(source='get_weekday_display', read_only=True)
    doctor_name = serializers.CharField(source='doctor.full_name', read_only=True)
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)
    
    class Meta:
        model = DoctorSchedule
        fields = [
            'id', 'doctor', 'doctor_name', 'clinic', 'clinic_name',
            'weekday', 'weekday_name', 'start_time', 'end_time', 'is_active'
        ]

class FaqSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.FAQ
        fields = '__all__'

    