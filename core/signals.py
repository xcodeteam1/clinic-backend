from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from auth_vk.models import News, DeviceToken
import os
import firebase_admin
from firebase_admin import credentials, messaging

def send_push_notification(device_token, title, body):
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        token=device_token,
    )
    messaging.send(message)

@receiver(post_save, sender=News)
def send_news_created_notification(sender, instance, created, **kwargs):
    if created:
        # Initialize Firebase app only once
        if not firebase_admin._apps:
            cred_path = os.path.join(settings.BASE_DIR, 'core', 'cred.json')
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)

        # Fetch all device tokens to send to all users
        # tokens = DeviceToken.objects.filter(user__user_type='patient')
        tokens = DeviceToken.objects.all()
        print(tokens, 'tokens')
        for device in tokens:
            
            try:
                send_push_notification(
                    device_token=device.token,
                    title=instance.name,
                    body=instance.description
                )
            except Exception as e:
                print(f"Notification error: {e}")