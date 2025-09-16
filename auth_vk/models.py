from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .utils import save_base64_image

from django.utils.translation import gettext_lazy as _
from auth_vk.integrations.client import OneCClient
from django.core.exceptions import ValidationError
from datetime import datetime, time, timedelta
import logging
from django.db import transaction


logger = logging.getLogger(__name__)

class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('patient', _('Patient')),
        ('doctor', _('Doctor')),
        ('admin', _('Admin')),
    )
    
    GENDER_CHOICES = (
        ('M', _('Male')),
        ('F', _('Female')),
        ('O', _('Other')),
    )
    
    # User type field
    user_type = models.CharField(_('User Type'), max_length=10, choices=USER_TYPE_CHOICES, default='patient')
    first_name = models.CharField(_('First Name'), max_length=128, blank=True, null=True)
    last_name = models.CharField(_('Last Name'), max_length=128, blank=True, null=True)
    middle_name = models.CharField(_('Middle Name'), max_length=128, blank=True, null=True)
    
    # Existing fields
    phone_number = models.CharField(_('Phone Number'), max_length=20, blank=True, null=True)
    date_of_birth = models.DateField(_('Date of Birth'), null=True, blank=True)
    gender = models.CharField(_('Gender'), max_length=1, choices=GENDER_CHOICES, null=True, blank=True)
    verified = models.BooleanField(_('Verified'), default=False)
    agreed_to_terms = models.BooleanField(_('Agreed to Terms'), default=False)
    biometric_enabled = models.BooleanField(_('Biometric Enabled'), default=False)
    employee_id = models.CharField(_('Employee ID'), max_length=128, null=True, blank=True)
    specialzation_photo = models.ImageField(upload_to="uploads/", blank=True, null=True)
    
    
    # Fields for token-based authentication
    vk_id = models.BigIntegerField(_('VK ID'), unique=True, null=True, blank=True)
    name = models.CharField(_('Name'), max_length=150, blank=True)
    external_id = models.CharField(_('External ID'), max_length=100, null=True, blank=True)
    
    # Doctor specific fields
    medical_license = models.CharField(_('Medical License'), max_length=100, blank=True, null=True, help_text=_("Medical license number for doctors"))
    specialization = models.CharField(_('Specialization'), max_length=200, blank=True, null=True, help_text=_("Doctor's specialization"))
    is_available = models.BooleanField(_('Is Available (for chat)'), default=True, help_text=_("Is doctor available for chat"))
    clinics = models.ManyToManyField(
        'Clinic', 
        related_name='doctors',
        blank=True,
        verbose_name=_('Clinics')
    )
    avatar = models.ImageField(_('Avatar'), upload_to='uploads/', blank=True, null=True)
    chat_guid = models.CharField(max_length=255, blank=True, null=True)
    
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []
    
   

    class Meta:
        db_table = 'auth_user'
        verbose_name = _('User')
        verbose_name_plural = _('Users')
    
    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_user_type_display()})"
    
    @property
    def is_patient(self):
        return self.user_type == 'patient'
    
    @property
    def is_doctor(self):
        return self.user_type == 'doctor'
    
    @property
    def is_admin_user(self):
        return self.user_type == 'admin'


    @classmethod
    def sync_doctors_from_1c(cls):
        try:
            client = OneCClient()
            doctors = client.get_doctors_realtime()
            
            success_count = 0
            error_count = 0
            deleted_count = 0
            
            # Get all UUIDs from the incoming data (stored in username field)
            incoming_uuids = set()
            for doctor_data in doctors:
                # The UUID from 1C API (stored in username field in DB)
                if 'external_id' in doctor_data and doctor_data['external_id']:
                    incoming_uuids.add(doctor_data['external_id'])
            
            logger.info(f"Processing {len(doctors)} doctors from external system")
            logger.info(f"Incoming UUIDs count: {len(incoming_uuids)}")
            logger.info(f"Sample incoming UUIDs: {list(incoming_uuids)[:5]}")
            
            # DOCTOR PROCESSING SECTION
            for doctor_data in doctors:
                try:
                    # Extract clinic UUIDs first (if they exist)
                    clinic_uuids = doctor_data.pop('clinics', [])
                    
                    # Get the UUID that will be used as username
                    doctor_uuid = doctor_data.get('external_id')
                    if not doctor_uuid:
                        logger.warning("Doctor data missing external_id, skipping")
                        error_count += 1
                        continue
                    
                    # Set user type for all doctors
                    doctor_data['user_type'] = 'doctor'
                    
                    # Process base64 photos
                    base64_photo = doctor_data.pop('photo', None) 
                    photo_specialization = doctor_data.pop("photo_specialization", None)
                    
                    avatar_file = None
                    photo_specialization_file = None
                    
                    # Convert base64 images to files
                    if base64_photo:
                        try:
                            avatar_file = save_base64_image(base64_photo)
                            logger.info(f"Avatar file created: {avatar_file.name if avatar_file else 'None'}")
                        except Exception as e:
                            logger.error(f"Error processing avatar for doctor {doctor_uuid}: {e}")

                    if photo_specialization:
                        try:
                            photo_specialization_file = save_base64_image(photo_specialization)
                            logger.info(f"Specialization photo file created: {photo_specialization_file.name if photo_specialization_file else 'None'}")
                        except Exception as e:
                            logger.error(f"Error processing specialization photo for doctor {doctor_uuid}: {e}")

                    # Remove external_id from doctor_data since we're using it as username
                    external_id_value = doctor_data.pop('external_id')
                    
                    # Create or update user using username (UUID) as the unique identifier
                    user, created = cls.objects.update_or_create(
                        username=external_id_value,  # UUID stored in username field
                        defaults={
                            **doctor_data,  # All other data from 1C
                            'external_id': external_id_value,  # Also store in external_id field for reference
                        }
                    )
                    
                    action = "Created" if created else "Updated"
                    logger.info(f"{action} doctor: {user.username} (UUID: {user.username})")

                    # Handle avatar file upload
                    if avatar_file:
                        try:
                            if user.avatar and hasattr(user.avatar, 'delete'):
                                user.avatar.delete(save=False)
                            
                            user.avatar.save(avatar_file.name, avatar_file, save=True)
                            logger.info(f"Avatar saved for {user.username}")
                            
                            # Close file to free memory
                            if hasattr(avatar_file, 'close'):
                                avatar_file.close()
                        except Exception as e:
                            logger.error(f"Error saving avatar for {user.username}: {e}")

                    # Handle specialization photo upload
                    if photo_specialization_file:
                        try:
                            if user.specialzation_photo and hasattr(user.specialzation_photo, 'delete'):
                                user.specialzation_photo.delete(save=False)
                            
                            user.specialzation_photo.save(photo_specialization_file.name, photo_specialization_file, save=True)
                            logger.info(f"Specialization photo saved for {user.username}")
                            
                            # Close file to free memory
                            if hasattr(photo_specialization_file, 'close'):
                                photo_specialization_file.close()
                        except Exception as e:
                            logger.error(f"Error saving specialization photo for {user.username}: {e}")

                    # Link clinics with better error handling
                    if clinic_uuids:
                        if isinstance(clinic_uuids, str):
                            # Single UUID string - convert to list
                            clinic_uuids = [clinic_uuids]
                        elif not isinstance(clinic_uuids, (list, tuple)):
                            # Some other type - log warning and skip
                            logger.warning(f"Unexpected clinics data type {type(clinic_uuids)}: {clinic_uuids}")
                            clinic_uuids = []
                            
                    if clinic_uuids:
                        try:
                            # Use apps.get_model to avoid circular imports
                            
                            
                            clinics = Clinic.objects.filter(uuid__in=clinic_uuids)
                            print(clinics, 'clinics to set')
                            print(user.username, ' user', user.first_name, user.last_name)
                            
                            if clinics.exists():
                                user.clinics.set(clinics)
                                logger.info(f"Linked {clinics.count()} clinics to {user.username}")

                            else:
                                logger.warning(f"No valid clinics found for UUIDs: {clinic_uuids}")
                        except Exception as e:
                            logger.error(f"Error linking clinics for {user.username}: {e}")
                    
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    doctor_id = doctor_data.get('external_id', 'Unknown')
                    logger.error(f"Error processing doctor {doctor_id}: {e}")
            
            # DELETE SECTION - Remove doctors not present in 1C data
            try:
                with transaction.atomic():
                    # First, let's see what we're working with
                    all_doctors_count = cls.objects.filter(user_type='doctor').count()
                    logger.info(f"Total doctors in database before deletion: {all_doctors_count}")
                    
                    # Get current UUIDs in database
                    current_uuids = set(
                        cls.objects.filter(user_type='doctor')
                        .values_list('username', flat=True)
                    )
                    logger.info(f"Current UUIDs in database: {len(current_uuids)}")
                    logger.info(f"Sample current UUIDs: {list(current_uuids)[:5]}")
                    
                    # Find UUIDs that should be deleted
                    uuids_to_delete = current_uuids - incoming_uuids
                    logger.info(f"UUIDs to delete: {len(uuids_to_delete)}")
                    logger.info(f"UUIDs to delete: {uuids_to_delete}")
                    
                    if uuids_to_delete:
                        # Get doctors that should be deleted
                        doctors_to_delete_query = cls.objects.filter(
                            user_type='doctor',
                            username__in=uuids_to_delete
                        )
                        
                        doctors_to_delete_count = doctors_to_delete_query.count()
                        logger.info(f"Doctors marked for deletion: {doctors_to_delete_count}")
                        
                        if doctors_to_delete_count > 0:
                            # Get the actual records that will be deleted (for logging)
                            doctors_to_delete_info = list(
                                doctors_to_delete_query.values('id', 'username', 'external_id', 'first_name', 'last_name')
                            )
                            
                            logger.info("Doctors to be deleted:")
                            for doctor_info in doctors_to_delete_info:
                                name = f"{doctor_info.get('first_name', '')} {doctor_info.get('last_name', '')}".strip()
                                logger.info(f"  - ID: {doctor_info['id']}, Name: {name}, Username (UUID): {doctor_info['username']}")
                            
                            # Delete associated files first
                            logger.info("Deleting associated files...")
                            for doctor in doctors_to_delete_query.iterator():
                                try:
                                    if doctor.avatar:
                                        logger.info(f"Deleting avatar for {doctor.username}")
                                        doctor.avatar.delete(save=False)
                                    if doctor.specialzation_photo:
                                        logger.info(f"Deleting specialization photo for {doctor.username}")
                                        doctor.specialzation_photo.delete(save=False)
                                except Exception as e:
                                    logger.error(f"Error deleting files for doctor {doctor.username}: {e}")
                            
                            # Perform the actual deletion
                            deleted_count, deleted_details = doctors_to_delete_query.delete()
                            
                            logger.info(f"Delete operation completed. Deleted count: {deleted_count}")
                            logger.info(f"Delete details: {deleted_details}")
                            
                            # Verify deletion worked
                            remaining_count = cls.objects.filter(user_type='doctor').count()
                            expected_remaining = all_doctors_count - doctors_to_delete_count
                            
                            logger.info(f"Doctors remaining after deletion: {remaining_count}")
                            logger.info(f"Expected remaining: {expected_remaining}")
                            
                            if remaining_count != expected_remaining:
                                logger.warning(f"DELETION VERIFICATION FAILED! Expected {expected_remaining}, got {remaining_count}")
                            else:
                                logger.info("Deletion verified successfully")
                        
                    else:
                        logger.info("No doctors to delete")
                        
            except Exception as e:
                logger.error(f"Error in deletion process: {e}")
                # Don't re-raise here, just log the error
                logger.exception("Full deletion error traceback:")
                    
            logger.info(f"Sync completed: {success_count} successful, {error_count} errors, {deleted_count} deleted")
            return {'success': success_count, 'errors': error_count, 'deleted': deleted_count}
            
        except Exception as e:
            logger.error(f"Critical error in sync_doctors_from_1c: {e}")
            logger.exception("Full error traceback:")
            return {'success': 0, 'errors': 1, 'deleted': 0}
    


class ChatRoom(models.Model):
    """Chat room between patient and doctor"""
    patient = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='patient_chats',
        limit_choices_to={'user_type': 'patient'},
        verbose_name=_('Patient')
    )
    doctor = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='doctor_chats',
        limit_choices_to={'user_type': 'doctor'},
        verbose_name=_('Doctor')
    )
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    is_active = models.BooleanField(_('Is Active'), default=True)
    last_message_at = models.DateTimeField(_('Last Message At'), null=True, blank=True)
    
    class Meta:
        unique_together = ('patient', 'doctor')
        ordering = ['-last_message_at', '-created_at']
        verbose_name = _('Chat Room')
        verbose_name_plural = _('Chat Rooms')
    
    def __str__(self):
        return f"Chat: {self.patient.get_full_name()} - {self.doctor.get_full_name()}"


class Message(models.Model):
    """Messages in chat rooms"""
    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages', verbose_name=_('Chat Room'))
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages', verbose_name=_('Sender'))
    content = models.TextField(_('Content'), blank=True, null=True)
    file = models.FileField(_('File'), upload_to='uploads/', blank=True, null=True)
    timestamp = models.DateTimeField(_('Timestamp'), auto_now_add=True)
    is_read = models.BooleanField(_('Is Read'), default=False)
    
    class Meta:
        ordering = ['timestamp']
        verbose_name = _('Message')
        verbose_name_plural = _('Messages')
    
    def __str__(self):
        return f"{self.sender.get_full_name()}: {self.content[:50]}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update last message time in chat room
        self.chat_room.last_message_at = self.timestamp
        self.chat_room.save(update_fields=['last_message_at'])
    

from django.core.files.base import ContentFile

class Clinic(models.Model):
    uuid = models.CharField(_('UUID'), max_length=100, unique=True)
    name = models.CharField(_('Name'), max_length=255)
    photo = models.ImageField(upload_to='uploads/', null=True, blank=True)
    address = models.TextField(_('Address'), blank=True)
    phone = models.CharField(_('Phone'), max_length=20, blank=True)
    email = models.EmailField(_('Email'), blank=True)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = _('Clinic')
        verbose_name_plural = _('Clinics')

    
    def __str__(self):
        return self.name
    
    @classmethod
    def sync_from_1c(cls):
        try:
            client = OneCClient()
            clinics = client.get_clinics_realtime()
            
            
            success_count = 0
            error_count = 0
            deleted_count = 0
            
            # Get all UUIDs from the incoming data
            incoming_uuids = set()
            processed_clinics = []
            
            for clinic_data in clinics:

                try:
                    # Process the photo if it exists
                    if 'photo' in clinic_data and clinic_data['photo']:
                        clinic_data['photo'] = save_base64_image(clinic_data['photo'])
                    
                    incoming_uuids.add(clinic_data['uuid'])
                    processed_clinics.append(clinic_data)
                    
                except Exception as e:
                    error_count += 1
                    print(f"Error processing clinic {clinic_data.get('uuid', 'Unknown')}: {e}")
            
            # Create or update clinics
            for clinic_data in processed_clinics:
                try:
                    clinic, created = cls.objects.update_or_create(
                        uuid=clinic_data['uuid'],
                        defaults=clinic_data
                    )
                    
                    action = "Created" if created else "Updated"
                    print(f"{action} clinic: {clinic.name} (uuid: {clinic.uuid})")
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    print(f"Error saving clinic {clinic_data.get('uuid', 'Unknown')}: {e}")
            
            # Delete clinics that are no longer in the external system
            try:
                clinics_to_delete = cls.objects.exclude(uuid__in=incoming_uuids)
                
                if clinics_to_delete.exists():
                    deleted_clinics = list(clinics_to_delete.values_list('name', 'uuid'))
                    deleted_count = clinics_to_delete.count()
                    
                    # Delete associated photos before deleting the records
                    for clinic in clinics_to_delete:
                        try:
                            if clinic.photo:
                                clinic.photo.delete(save=False)
                        except Exception as e:
                            print(f"Error deleting photo for clinic {clinic.name}: {e}")
                    
                    clinics_to_delete.delete()
                    
                    print(f"Deleted {deleted_count} clinics that no longer exist in external system:")
                    for name, uuid in deleted_clinics:
                        print(f"  - {name} (uuid: {uuid})")
                else:
                    print("No clinics to delete")
                    
            except Exception as e:
                print(f"Error deleting obsolete clinics: {e}")
            
            print(f"Clinic sync completed: {success_count} successful, {error_count} errors, {deleted_count} deleted")
            return {'success': success_count, 'errors': error_count, 'deleted': deleted_count}
            
        except Exception as e:
            print(f"Critical error in sync_from_1c: {e}")
            return {'success': 0, 'errors': 1, 'deleted': 0}


class Specialization(models.Model):
    name = models.CharField(_('Name'), max_length=255, blank=True, null=True)
    description = models.TextField(_('Description'), blank=True)
    
    class Meta:
        verbose_name = _('Specialization')
        verbose_name_plural = _('Specializations')

    def __str__(self):
        return self.name



class ServiceCategory(models.Model):
    name = models.CharField(_('Name'), max_length=255)
    description = models.TextField(_('Description'), blank=True)
    
    class Meta:
        verbose_name = _('Service Category')
        verbose_name_plural = _('Service Categories')

    def __str__(self):
        return self.name

class Service(models.Model):
    name = models.CharField(_('Name'), max_length=255)
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, verbose_name=_('Category'))
    description = models.TextField(_('Description'), blank=True)
    price = models.DecimalField(_('Price'), max_digits=10, decimal_places=2)
    duration = models.DurationField(_('Duration'))  # Expected duration of the service
    # External ID for 1C integration
    external_id = models.CharField(_('External ID'), max_length=100, null=True, blank=True, unique=True)
    
    class Meta:
        verbose_name = _('Service')
        verbose_name_plural = _('Services')

    def __str__(self):
        return self.name


class Appointment(models.Model):
    STATUS_CHOICES = (
        ('pending', _('Pending')),
        ('confirmed', _('Confirmed')),
        ('cancelled', _('Cancelled')),
        ('completed', _('Completed')),
    )
    
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='patient_appointments', verbose_name=_('Patient'))
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='doctor_appointments', verbose_name=_('Doctor'))
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, verbose_name=_('Clinic'))
    date = models.DateField(_('Date'))
    time = models.TimeField(_('Time'))
    notes = models.TextField(_('Notes'), blank=True)
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    external_id = models.CharField(_('External ID'), max_length=100, null=True, blank=True, unique=True)

    from django.utils import timezone

    def clean(self):
        if self.date and self.time:
            appointment_datetime = datetime.combine(self.date, self.time)

            # Make appointment_datetime timezone-aware
            if timezone.is_naive(appointment_datetime):
                appointment_datetime = timezone.make_aware(appointment_datetime)

            if appointment_datetime <= timezone.now():
                raise ValidationError(_("Cannot schedule appointments in the past"))

        if self.doctor and self.clinic:
            if not self.doctor.clinics.filter(id=self.clinic.id).exists():
                raise ValidationError(_("Doctor does not work at this clinic"))
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _('Appointment')
        verbose_name_plural = _('Appointments')

    def __str__(self):
        return f"{self.patient.username} - {self.doctor} - {self.date} {self.time}"

class DeviceToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='device_tokens', verbose_name=_('User'))
    token = models.CharField(_('Token'), max_length=255)
    device_type = models.CharField(_('Device Type'), max_length=20)  # 'ios', 'android'
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Device Token')
        verbose_name_plural = _('Device Tokens')

    def __str__(self):
        return f"{self.user} - {self.device_type}"



class FAQ(models.Model):
    question = models.CharField(_('Question'), max_length=255)
    answer = models.TextField(_('Answer'))
    category = models.CharField(_('Category'), max_length=100)
    order = models.IntegerField(_('Order'), default=0)
    
    class Meta:
        verbose_name = _('FAQ')
        verbose_name_plural = _('FAQs')

    def __str__(self):
        return self.question

class Illness(models.Model):
    name = models.CharField(_('Name'), max_length=255, unique=True)
    description = models.TextField(_('Description'), blank=True)
    severity_level = models.CharField(
        _('Severity Level'),
        max_length=20,
        choices=[
            ('mild', _('Mild')),
            ('moderate', _('Moderate')),
            ('severe', _('Severe')),
            ('critical', _('Critical'))
        ],
        default='mild'
    )

    doctors = models.ManyToManyField(User, related_name='illnesses_doctor', blank=True, verbose_name=_('Doctors'))


    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = _('Illness')
        verbose_name_plural = _('Illnesses')


class DoctorSchedule(models.Model):
    WEEKDAYS = [
        (0, _('Monday')),
        (1, _('Tuesday')),
        (2, _('Wednesday')),
        (3, _('Thursday')), # Corrected typo: Changed the second 'Wednesday' to 'Thursday'
        (4, _('Friday')),
        (5, _('Saturday')),
        (6, _('Sunday')), # Changed to Sunday from the original 7, assuming 0-6 for weekdays
    ]
    
    doctor = models.ForeignKey(
        'User', 
        on_delete=models.CASCADE, 
        related_name='schedules',
        verbose_name=_('Doctor')
    )
    clinic = models.ForeignKey(
        'Clinic', 
        on_delete=models.CASCADE,
        related_name='doctor_schedules',
        verbose_name=_('Clinic')
    )
    weekday = models.IntegerField(_('Weekday'), choices=WEEKDAYS)
    start_time = models.TimeField(_('Start Time'))
    end_time = models.TimeField(_('End Time'))
    is_active = models.BooleanField(_('Is Active'), default=True)
    
    class Meta:
        unique_together = ['doctor', 'clinic', 'weekday']
        verbose_name = _('Doctor Schedule')
        verbose_name_plural = _('Doctor Schedules')
    
    def __str__(self):
        return f"{self.doctor} - {self.get_weekday_display()} ({self.start_time}-{self.end_time})"


class News(models.Model):
    name = models.CharField(_('Name'), max_length=255)
    description = models.TextField(_('Description'))
    file = models.FileField(_('File'), upload_to='uploads/', blank=True, null=True)

    class Meta:
        verbose_name = _('News')
        verbose_name_plural = _('News')


class NotificationLog(models.Model):
    """Model to log sent notifications"""
    title = models.CharField(_('Title'), max_length=200)
    message = models.TextField(_('Message'))
    notification_type = models.CharField(_('Notification Type'), max_length=50, choices=[
        ('general', _('General')),
        ('appointment', _('Appointment')),
        ('health_tip', _('Health Tip')),
        ('emergency', _('Emergency')),
        ('promotion', _('Promotion')),
    ], default='general')
    priority = models.CharField(_('Priority'), max_length=20, choices=[
        ('low', _('Low')),
        ('normal', _('Normal')),
        ('high', _('High')),
        ('urgent', _('Urgent')),
    ], default='normal')
    
    # Recipient information
    recipient_count = models.IntegerField(_('Recipient Count'), default=0)
    successful_deliveries = models.IntegerField(_('Successful Deliveries'), default=0)
    failed_deliveries = models.IntegerField(_('Failed Deliveries'), default=0)
    
    # Filtering criteria used
    filter_criteria = models.JSONField(_('Filter Criteria'), blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    sent_at = models.DateTimeField(_('Sent At'), null=True, blank=True)
    scheduled_for = models.DateTimeField(_('Scheduled For'), null=True, blank=True)
    
    # Sender information
    sent_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, 
                               related_name='sent_notifications', verbose_name=_('Sent By'))
    
    status = models.CharField(_('Status'), max_length=20, choices=[
        ('draft', _('Draft')),
        ('scheduled', _('Scheduled')),
        ('sending', _('Sending')),
        ('sent', _('Sent')),
        ('failed', _('Failed')),
    ], default='draft')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Notification Log')
        verbose_name_plural = _('Notification Logs')
    
    def __str__(self):
        return f"{self.title} - {self.recipient_count} recipients"


class NotificationRecipient(models.Model):
    """Model to track individual notification deliveries"""
    notification_log = models.ForeignKey(NotificationLog, on_delete=models.CASCADE, 
                                       related_name='recipients', verbose_name=_('Notification Log'))
    user = models.ForeignKey('User', on_delete=models.CASCADE, verbose_name=_('User'))
    device_token = models.CharField(_('Device Token'), max_length=255, blank=True)
    
    # Delivery status
    delivered = models.BooleanField(_('Delivered'), default=False)
    delivery_time = models.DateTimeField(_('Delivery Time'), null=True, blank=True)
    error_message = models.TextField(_('Error Message'), blank=True)
    
    # User interaction
    opened = models.BooleanField(_('Opened'), default=False)
    opened_at = models.DateTimeField(_('Opened At'), null=True, blank=True)
    clicked = models.BooleanField(_('Clicked'), default=False)
    clicked_at = models.DateTimeField(_('Clicked At'), null=True, blank=True)
    
    class Meta:
        unique_together = ['notification_log', 'user']
        verbose_name = _('Notification Recipient')
        verbose_name_plural = _('Notification Recipients')
    
    def __str__(self):
        return f"{self.notification_log.title} -> {self.user.username}"