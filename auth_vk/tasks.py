from celery import shared_task
from django.http import JsonResponse


@shared_task
def sync_data_task():
    from auth_vk.models import Clinic, User
    try:
        print('Starting data synchronization...')
        
        # Sync clinics first (doctors might depend on clinics)
        clinic_result = Clinic.sync_from_1c()
        print(f"Clinic sync result: {clinic_result}")
        
        # Then sync doctors
        doctor_result = User.sync_doctors_from_1c()
        print(f"Doctor sync result: {doctor_result}")
        
        return {
            "detail": "Successfully synchronized clinics and doctors",
            "clinics": clinic_result,
            "doctors": doctor_result
        }
    except Exception as e:
        print(f"Error in sync_data_task: {e}")
        return {"error": str(e)}