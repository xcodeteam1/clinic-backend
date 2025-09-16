# firebase.py
import firebase_admin
from firebase_admin import credentials, messaging
import os

from django.conf import settings
print(settings.BASE_DIR)
cred_path = os.path.join(settings.BASE_DIR, 'core', 'cred.json')
print(cred_path, 'cred path')
cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)


# def send_fcm_notification(token, title, body, data=None):
#     message = messaging.Message(
#         notification=messaging.Notification(
#             title=title,
#             body=body
#         ),
#         token=token,
#         data=data or {},  # Optional data payload
#     )
#     response = messaging.send(message)
#     return response


# send_fcm_notification(
#     token='cKODxYYtRN6eOyPmIh0k0m:APA91bEga3yYaEuhhYYkHNZ1nEQUsU0FHUlp4WqRLmat4433agSHBTaXWasKgXfh1z8xpRfp7Wd208Ww2Mw_xiP51ZHsBsOdGU1yswA2-HFCT60FJLO51-g',
#     title='Hello!',
#     body='This is a test message.',
#     data={"key1": "value1", "key2": "value2"}
# )
