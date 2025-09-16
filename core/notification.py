# notifications.py
from firebase_admin import messaging


# notifications.py
import logging
from django.core.mail import send_mail
from django.conf import settings
from firebase_admin import messaging
from typing import List, Dict, Optional
from auth_vk.models import User, NotificationLog

def send_push_notification(device_token, title, body, data=None):
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        token=device_token,
        data=data or {}
    )
    response = messaging.send(message)
    return response



# class NotificationService:
#     """Enhanced notification service with multiple delivery methods"""
    
#     @staticmethod
#     def send_push_notification(user: User, title: str, body: str, data: Dict = None) -> Dict:
#         """Send push notification via Firebase"""
#         results = {
#             'success_count': 0,
#             'failure_count': 0,
#             'errors': []
#         }
        
#         # Get active device tokens for user
#         device_tokens = Device.objects.filter(
#             user=user, 
#             is_active=True
#         ).values_list('token', flat=True)
        
#         if not device_tokens:
#             results['errors'].append(f'No active device tokens found for user {user.username}')
#             results['failure_count'] += 1
#             return results
        
#         for token in device_tokens:
#             try:
#                 message = messaging.Message(
#                     notification=messaging.Notification(title=title, body=body),
#                     token=token,
#                     data=data or {},
#                     android=messaging.AndroidConfig(
#                         notification=messaging.AndroidNotification(
#                             color='#007cba',
#                             sound='default',
#                         )
#                     ),
#                     apns=messaging.APNSConfig(
#                         payload=messaging.APNSPayload(
#                             aps=messaging.Aps(sound='default')
#                         )
#                     )
#                 )
                
#                 response = messaging.send(message)
                
#                 # Log successful notification
#                 NotificationLog.objects.create(
#                     user=user,
#                     title=title,
#                     message=body,
#                     delivery_method='push',
#                     status='sent'
#                 )
                
#                 results['success_count'] += 1
#                 logger.info(f'Push notification sent to {user.username}: {response}')
                
#             except messaging.UnregisteredError:
#                 # Token is invalid, deactivate it
#                 Device.objects.filter(token=token).update(is_active=False)
#                 results['errors'].append(f'Invalid token deactivated for {user.username}')
#                 results['failure_count'] += 1
                
#             except Exception as e:
#                 error_msg = str(e)
#                 results['errors'].append(f'Failed to send push to {user.username}: {error_msg}')
#                 results['failure_count'] += 1
                
#                 # Log failed notification
#                 NotificationLog.objects.create(
#                     user=user,
#                     title=title,
#                     message=body,
#                     delivery_method='push',
#                     status='failed',
#                     error_message=error_msg
#                 )
                
#                 logger.error(f'Push notification failed for {user.username}: {error_msg}')
        
#         return results
    
#     @staticmethod
#     def send_email_notification(user: User, title: str, body: str, html_content: str = None) -> bool:
#         """Send email notification"""
#         try:
#             if not user.email:
#                 logger.warning(f'No email address for user {user.username}')
#                 return False
            
#             send_mail(
#                 subject=title,
#                 message=body,
#                 from_email=settings.DEFAULT_FROM_EMAIL,
#                 recipient_list=[user.email],
#                 html_message=html_content,
#                 fail_silently=False
#             )
            
#             # Log successful notification
#             NotificationLog.objects.create(
#                 user=user,
#                 title=title,
#                 message=body,
#                 delivery_method='email',
#                 status='sent'
#             )
            
#             logger.info(f'Email sent to {user.username} at {user.email}')
#             return True
            
#         except Exception as e:
#             error_msg = str(e)
            
#             # Log failed notification
#             NotificationLog.objects.create(
#                 user=user,
#                 title=title,
#                 message=body,
#                 delivery_method='email',
#                 status='failed',
#                 error_message=error_msg
#             )
            
#             logger.error(f'Email failed for {user.username}: {error_msg}')
#             return False
    
#     @staticmethod
#     def send_bulk_notifications(users: List[User], title: str, body: str, 
#                               notification_type: str = 'general', 
#                               methods: List[str] = None,
#                               data: Dict = None) -> Dict:
#         """Send notifications to multiple users with multiple methods"""
        
#         if methods is None:
#             methods = ['push', 'email']
        
#         total_results = {
#             'users_processed': 0,
#             'total_sent': 0,
#             'total_failed': 0,
#             'method_results': {},
#             'errors': []
#         }
        
#         for method in methods:
#             total_results['method_results'][method] = {
#                 'success_count': 0,
#                 'failure_count': 0,
#                 'errors': []
#             }
        
#         for user in users:
#             total_results['users_processed'] += 1
            
#             for method in methods:
#                 try:
#                     if method == 'push':
#                         result = NotificationService.send_push_notification(user, title, body, data)
#                         total_results['method_results']['push']['success_count'] += result['success_count']
#                         total_results['method_results']['push']['failure_count'] += result['failure_count']
#                         total_results['method_results']['push']['errors'].extend(result['errors'])
                        
#                     elif method == 'email':
#                         success = NotificationService.send_email_notification(user, title, body)
#                         if success:
#                             total_results['method_results']['email']['success_count'] += 1
#                         else:
#                             total_results['method_results']['email']['failure_count'] += 1
                            
#                 except Exception as e:
#                     error_msg = f'Error sending {method} to {user.username}: {str(e)}'
#                     total_results['errors'].append(error_msg)
#                     total_results['method_results'][method]['errors'].append(error_msg)
                   
#         # Calculate totals
#         for method_data in total_results['method_results'].values():
#             total_results['total_sent'] += method_data['success_count']
#             total_results['total_failed'] += method_data['failure_count']
        
#         return total_results
    

