
from django.contrib import admin
from django.urls import path, include
from auth_vk.views import VKLogin, VKAuthTest
from auth_vk.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status   
import uuid
import requests
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter, OpenApiTypes
from auth_vk import models
from auth_vk import serializers as sr
import xml.etree.ElementTree as ET
from drf_spectacular.utils import extend_schema, OpenApiExample,\
      OpenApiResponse, OpenApiTypes, OpenApiRequest
from drf_spectacular.plumbing import build_basic_type

class VKAuthTokenView(APIView):
    authentication_classes = []
    permission_classes = []
 
    @extend_schema(
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'access_token': {'type': 'string', 'example': 'abc123'},
                    'vk_id': {'type': 'integer', 'example': 12345678},
                    'first_name': {'type': 'string', 'example': 'Ivan'},
                    'last_name': {'type': 'string', 'example': 'Petrov'},
                    'phone_number': {'type': 'string', 'example': '+7123456789'},
                    'device_id': {'type': 'string', 'example': 'device123'},
                },
                'required': ['access_token', 'vk_id', 'first_name', 'last_name']
            }
        },
        responses={200: OpenApiTypes.OBJECT},
        description="Exchange VK user data from mobile for JWT tokens"
    )
    def post(self, request):
        """
        Exchange VK user data from mobile app for JWT tokens.
        The mobile app should fetch user data directly from VK API.
        
        Request: {
            "access_token": "vk_access_token",
            "vk_id": 12345678,
            "first_name": "Ivan",
            "last_name": "Petrov",
            "phone_number": "+7123456789",
            "device_id": "mobile_device_id" (optional)
        }
        """
        # Extract required fields
        access_token = request.data.get('access_token')
        vk_id = request.data.get('vk_id')
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        phone_number = request.data.get('phone_number')
        device_id = request.data.get('device_id')
        
        # Validate required fields
        if not all([access_token, vk_id, first_name, last_name]):
            missing_fields = []
            if not access_token: missing_fields.append('access_token')
            if not vk_id: missing_fields.append('vk_id')
            if not first_name: missing_fields.append('first_name')
            if not last_name: missing_fields.append('last_name')
            
            return Response(
                {'error': f'Missing required fields: {", ".join(missing_fields)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Optional validation: Verify the token is valid (lightweight check)
        # This won't cause IP address errors as we're only checking token validity
        # token_validation = self._validate_token(access_token, vk_id)
        # if token_validation.get('error'):
        #     return Response({'error': token_validation['error']}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Create VK data structure from provided fields
        vk_data = {
            'id': vk_id,
            'first_name': first_name,
            'last_name': last_name,
            'phone_number': phone_number
        }
        
        # Create or update user
        user = self._sync_user(
            vk_id=vk_id,
            email=f"{vk_id}@vk.com",  # fallback email
            vk_data=vk_data
        )
        
        # Generate JWT tokens
        tokens = self._generate_tokens(user, device_id)
        
        return Response(tokens, status=status.HTTP_200_OK)
    
    def _validate_token(self, access_token, vk_id):
        """
        Lightweight validation of the VK token.
        Just checks if the token is valid, not using it to fetch data.
        """
        try:
            response = requests.get(
                'https://api.vk.com/method/secure.checkToken',
                params={
                    'token': access_token,
                    'v': '5.131',
                    # You'll need your VK app's service token for this API call
                    'access_token': settings.VK_SERVICE_TOKEN  
                },
                timeout=5
            )
            result = response.json()
            
            # Check if the token is valid
            if 'error' in result:
                return {'error': result['error']['error_msg']}
            
            # Verify the token belongs to the claimed user
            if result['response']['user_id'] != int(vk_id):
                return {'error': 'Token does not match the provided user ID'}
                
            return {'success': True}
        except Exception as e:
            return {'error': str(e)}
    
    def _sync_user(self, vk_id, email, vk_data):
        defaults = {
            'email': email,
            'username': f'vk_{vk_id}',  
            'name': f"{vk_data['first_name']} {vk_data['last_name']}",
            'phone_number': vk_data.get('phone_number'),
            'is_active': True
        }
        user, _ = User.objects.get_or_create(vk_id=vk_id, defaults=defaults)
        return user
    
    def _generate_tokens(self, user, device_id=None):
        refresh = RefreshToken.for_user(user)
        
        if device_id:
            cache.set(f'user_{user.id}_device', device_id, timeout=60*60*24*7)
            
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.name,
              
            }
        }
    


class RefreshTokenView(APIView):
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        """
        Refresh expired access token
        Request: {
            "refresh": "your_refresh_token",
            "device_id": "mobile_device_id" 
        }
        """
        try:
            refresh_token = request.data.get('refresh')
            refresh = RefreshToken(refresh_token)
            user = User.objects.get(id=refresh['user_id'])
            
            # Verify device ID if provided
            if device_id := request.data.get('device_id'):
                cached_id = cache.get(f'user_{user.id}_device')
                if cached_id != device_id:
                    return Response(
                        {'error': 'Device mismatch'},
                        status=status.HTTP_401_UNAUTHORIZED
                    )

            new_access = str(refresh.access_token)
            return Response({'access': new_access})
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_401_UNAUTHORIZED
            )

class LogoutView(APIView):
    def post(self, request):
        """
        Invalidate refresh token
        Request: {
            "refresh": "your_refresh_token"
        }
        """
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser

class UserProfileView(APIView):
    permission_classes = [IsAuthenticated,]
    # parser_classes = [MultiPartParser]  # For file uploads (avatar)
    
    def get(self, request):
        """Get current user profile"""
        print(request.user, 'thsi is userrr')
        return Response(self._serialize_user(request.user))
    
    def put(self, request):
        """Update user profile"""
        user = request.user
        data = request.data
        print(user, 'user')
        print(data, 'data')
        
        # Basic fields update
        if 'first_name' in data:
            user.name = data['name']
        if 'last_name' in data:
            user.name = data['last_name']
        if 'middle_name' in data:
            user.name = data['middle_name']

        if 'email' in data and data['email'] != user.email:
            if User.objects.filter(email=data['email']).exists():
                return Response(
                    {'error': 'Email already in use'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            user.email = data['email']
        
        # Avatar update
        if 'avatar' in request.FILES:
            user.avatar = request.FILES['avatar']
        
        user.save()
        return Response(self._serialize_user(user))
    
    def delete(self, request):
        """Delete user account"""
        user = request.user
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    def _serialize_user(self, user):
        print('serializer user---')
        """Helper method to serialize user data"""
        return {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'middle_name': user.middle_name,
            'avatar': user.avatar if user.avatar else None
        }



from auth_vk.views import (
    ClinicViewSet,
    ServiceCategoryViewSet, ServiceViewSet,
     RealTimeSyncView,\
    MedicalBranchListView, IllnessDetailView
)
from rest_framework.routers import DefaultRouter


router = DefaultRouter()
router.register(r'clinics', ClinicViewSet, basename='clinic')

router.register(r'service-categories', ServiceCategoryViewSet, basename='service-category')
router.register(r'services', ServiceViewSet, basename='service')
# router.register(r'appointments', AppointmentViewSet, basename='appointment')





REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = ''  # If your Redis requires authentication

# SMS settings
SMS_API_ID = 'DFD034DF-40A1-A0DC-2A7E-EC368AEF9DCA'
SMS_API_URL = 'https://sms.ru/sms/send'

# OTP settings
OTP_LENGTH = 6  # Length of OTP code
OTP_EXPIRY_SECONDS = 300  # 5 minutes
MAX_OTP_ATTEMPTS = 30  # Maximum attempts allowed for OTP verification
OTP_COOLDOWN_SECONDS = 10

import redis
from django.conf import settings


def get_redis_connection():
    """Get Redis connection instance"""
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=True
    )

# utils/otp.py (Create OTP utility)
import random
import string
import requests
from django.conf import settings


def generate_otp(length=OTP_LENGTH):
    """Generate a random OTP code"""
    # Generate OTP with digits only
    return ''.join(random.choice(string.digits) for _ in range(length))

def save_otp_to_redis(phone_number, otp):
    """Save OTP to Redis with expiration"""
    redis_conn = get_redis_connection()
    # Key format: otp:{phone_number}
    redis_conn.set(f'otp:{phone_number}', otp, ex=OTP_EXPIRY_SECONDS)
    # Set attempts counter
    redis_conn.set(f'otp_attempts:{phone_number}', 0, ex=OTP_EXPIRY_SECONDS)
    # Set the cooldown flag
    redis_conn.set(f'otp_cooldown:{phone_number}', 1, ex=OTP_COOLDOWN_SECONDS)

def verify_otp(phone_number, otp):
    """Verify OTP from Redis"""
    redis_conn = get_redis_connection()
    
    # Check if max attempts reached
    attempts = redis_conn.get(f'otp_attempts:{phone_number}')
    if attempts and int(attempts) >= MAX_OTP_ATTEMPTS:
        return False, "Maximum verification attempts reached. Request a new OTP."
    
    # Get stored OTP
    stored_otp = redis_conn.get(f'otp:{phone_number}')
    
    # Increment attempts Please wait
    redis_conn.incr(f'otp_attempts:{phone_number}')
    
    if not stored_otp:
        return False, "OTP expired or not found. Request a new OTP."
    
    if stored_otp == otp:
        # Delete OTP and attempts counter on successful verification
        redis_conn.delete(f'otp:{phone_number}', f'otp_attempts:{phone_number}')
        return True, "OTP verified successfully."
    
    return False, "Invalid OTP. Please try again."

def can_send_otp(phone_number):
    """Check if user can request a new OTP (not in cooldown period)"""
    redis_conn = get_redis_connection()
    cooldown = redis_conn.get(f'otp_cooldown:{phone_number}')
    return cooldown is None

def send_sms(phone_number, message):
    """Send SMS using sms.ru API"""
    try:
        print(phone_number, 'phone number')
        if  phone_number[0] == '+':
            phone_number = phone_number[1:]
        print(SMS_API_ID, 'sms api')
        print(phone_number, 'phoneee')

        url = f"https://sms.ru/sms/send?api_id={SMS_API_ID}&to[{phone_number}]={message}&json=1"
        response = requests.get(url)
        
        
        response_data = response.json()
        print(response_data, 'response_data')
        
        if response_data.get('status') == 'OK' and response_data['sms'][phone_number].get('status') == 'OK':
            return True, "SMS sent successfully"
        else:
            error_text = response_data['sms'][phone_number].get('status_text', 'Unknown error')
            return False, f"Failed to send SMS: {error_text}"
    
    except Exception as e:
        return False, f"Error sending SMS: {str(e)}"

# serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
import re



class PhoneNumberSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    
    def validate_phone_number(self, value):
        # Basic phone validation - you may want to customize this
        if not re.match(r'^\+?[0-9]{10,15}$', value):
            raise serializers.ValidationError("Enter a valid phone number")
        return value

class OTPVerificationSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    otp = serializers.CharField(max_length=6, min_length=6)
    
    def validate_phone_number(self, value):
        # Basic phone validation - you may want to customize this
        if not re.match(r'^\+?[0-9]{10,15}$', value):
            raise serializers.ValidationError("Enter a valid phone number")
        return value



from rest_framework import serializers
from django.contrib.auth import get_user_model
from auth_vk.models import ChatRoom, Message
import re




class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone_number', 'date_of_birth', 
            'gender', 'verified', 'agreed_to_terms', 'biometric_enabled',
            'user_type', 'avatar', 'full_name', 'specialization',
            'is_available', 'medical_license', 'first_name', 'last_name', 'middle_name'
        ]
        read_only_fields = ['verified', 'user_type']
    
    def get_full_name(self, obj):
        return obj.get_full_name() or obj.name


class DoctorSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'name', 'avatar', 'full_name', 'avatar',
            'specialization', 'is_available', 'medical_license'
        ]
    
    def get_full_name(self, obj):
        return obj.get_full_name() or obj.name

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        
        print(request, 'req')
        if instance.avatar and request:
            data['avatar'] = request.build_absolute_uri(instance.avatar.url)
            print(data, 'data')
        return data


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    sender_type = serializers.CharField(source='sender.user_type', read_only=True)
    file = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'content', 'timestamp', 'is_read', 'sender', 'sender_name', 'sender_type', 'file']
        read_only_fields = ['sender', 'timestamp']
    
    def get_sender_name(self, obj):
        return obj.sender.get_full_name() or obj.sender.name
    
    def get_file(self, obj):
        request = self.context.get("request")

        if obj.file and  hasattr(obj.file, 'url'):
            return request.build_absolute_uri(obj.file.url)
        return None
    

class ChatRoomSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatRoom
        fields = [
            'id', 'patient', 'doctor', 'patient_name', 'doctor_name',
            'created_at', 'is_active', 'last_message_at', 'last_message', 'unread_count'
        ]
    
    def get_patient_name(self, obj):
        return obj.patient.get_full_name() or obj.patient.name
    
    def get_doctor_name(self, obj):
        return obj.doctor.get_full_name() or obj.doctor.name
    
    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        if last_msg:
            return {
                'content': last_msg.content,
                'timestamp': last_msg.timestamp,
                'sender_type': last_msg.sender.user_type
            }
        return None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.messages.filter(is_read=False).exclude(sender=request.user).count()
        return 0


class PhoneNumberSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    
    def validate_phone_number(self, value):
        if not re.match(r'^\+?[0-9]{10,15}$', value):
            raise serializers.ValidationError("Enter a valid phone number")
        return value


class OTPVerificationSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    otp = serializers.CharField(max_length=6, min_length=6)
    
    # def validate_phone_number(self, value):
    #     if not re.match(r'^\+?[0-9]{10,15}$', value):
    #         raise serializers.ValidationError("Enter a valid phone number")
    #     return value


class DoctorCreationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'first_name', 'last_name',
            'name', 'specialization', 'medical_license', 'phone_number'
        ]
    
    def create(self, validated_data):
        print('password save')
        password = validated_data.pop('password')
        user = User.objects.create_user(
            user_type='doctor',
            **validated_data
        )
        user.set_password(password)
        user.verified = True
        user.save()
        return user







from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model
from django.conf import settings




# Authentication Views (keeping existing OTP auth)
class RequestOTPView(APIView):
    """Request OTP for patient authentication"""
    serializer_class = PhoneNumberSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):

        print(request.data, 'data req')
        serializer = PhoneNumberSerializer(data=request.data)
        if serializer.is_valid():
            phone_number = serializer.validated_data['phone_number']
            
            # if not can_send_otp(phone_number):
            #     return Response(
            #         {"detail": "Please wait before requesting a new OTP"},
            #         status=status.HTTP_429_TOO_MANY_REQUESTS
            #     )
            
            otp = generate_otp()
          
            save_otp_to_redis(phone_number, otp)
            
            try:
                sms_message = f"Your verification code is: {otp}. Valid for 5 minutes."
                success, message = send_sms(phone_number, sms_message)
            except:
                return Response({"detail": "Error happened try again"}, status=400)
            # success, message =  "seccuses", 'code: 12345'
            
            if success:
                return Response({"detail": "OTP sent to your phone number"}, status=status.HTTP_200_OK)
            else:
                return Response({"detail": message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyOTPView(APIView):
    """
    API endpoint to verify OTP and authenticate user
    """
    serializer_class = OTPVerificationSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = OTPVerificationSerializer(data=request.data)
        if serializer.is_valid():
            phone_number = serializer.validated_data['phone_number']
            otp = serializer.validated_data['otp']
            
            # Verify OTP
            is_valid, message = verify_otp(phone_number, otp)
            
            if not is_valid:
                return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)
            
            # Find or create user with this phone number
            user, created = User.objects.get_or_create(
                phone_number=phone_number,
                defaults={
                    'username': f"user_{phone_number}",  # Generate a username
                    'email': f"{phone_number}@example.com",  # Generate a temporary email
                    'verified': True
                }
            )
            
            if not user.verified:
                user.verified = True
                user.save()
            
            # Create or get authentication token
            refresh = RefreshToken.for_user(user)
            return Response({
                "detail": "Login successful",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user_id": user.id,
                "user_type": user.user_type
            }, status=status.HTTP_200_OK)
        
       
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserProfileView(APIView):
    """
    API endpoint to get and update user profile
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    

    @extend_schema(
        request=UserSerializer,
        responses={
            200: UserSerializer,
            400: OpenApiExample(
                'Validation Error',
                value={'email': ['This field is required.']},
                response_only=True,
                status_codes=["400"],
            )
        },
        description="Partially update the authenticated user's profile"
    )
    def put(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


from django.contrib.auth import authenticate

class DoctorLoginView(APIView):
    
    """Login for doctors using username/email and password"""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        request=OpenApiTypes.OBJECT,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Valid Request',
                value={
                    'username': 'doctor1',
                    'password': 'securepassword123'
                },
                request_only=True
            ),
            OpenApiExample(
                'Success Response',
                value={
                    'detail': 'Login successful',
                    'token': 'abc123xyz',
                    'user_id': 1,
                    'user_type': 'doctor'
                },
                response_only=True
            ),
            OpenApiExample(
                'Error Response',
                value={'detail': 'Invalid credentials or not a doctor account'},
                response_only=True,
                status_codes=['401']
            )
        ]
    )

    def post(self, request):
        username_or_email = request.data.get('username')
        password = request.data.get('password')
        
        if not username_or_email or not password:
            return Response(
                {"detail": "Username/email and password are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Try to authenticate with username or email
        user = authenticate(request, username=username_or_email, password=password)
        
        if not user:
            # Try with email if username didn't work
            try:
                user_obj = User.objects.get(email=username_or_email)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                pass
        
        if user and user.user_type == 'doctor':
            refresh = RefreshToken.for_user(user)
            return Response({
                "detail": "Login successful",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user_id": user.id,
                "user_type": user.user_type
            }, status=status.HTTP_200_OK)
        
        return Response({'detail':'Wrong username of password'}, status=400)


# Chat Views
class AvailableDoctorsView(APIView):
    """Get list of available doctors for patients"""
    # permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={
            200: DoctorSerializer(many=True),
            403: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Success Response',
                value=[{
                    'id': 1,
                    'username': 'doctor1',
                    'email': 'doctor@example.com',
                    'name': 'Dr. Smith',
                    'avatar': None,
                    'full_name': 'Dr. Smith',
                    'specialization': 'Cardiology',
                    'is_available': True,
                    'medical_license': 'MD12345'
                }],
                response_only=True
            )
        ]
    )

    def get(self, request):
        # if not request.user.is_patient:
        #     return Response(
        #         {"detail": "Only patients can view available doctors"},
        #         status=status.HTTP_403_FORBIDDEN
        #     )
        
        doctors = User.objects.filter(user_type='doctor', is_available=True).order_by("first_name")
        serializer = DoctorSerializer(doctors, many=True, context={'request': request})
        return Response(serializer.data)


class ChatRoomListView(APIView):
    """Get user's chat rooms"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        if user.is_patient:
            chat_rooms = ChatRoom.objects.filter(patient=user, is_active=True)
        elif user.is_doctor:
            chat_rooms = ChatRoom.objects.filter(doctor=user, is_active=True)
        else:
            return Response(
                {"detail": "Only patients and doctors can access chats"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ChatRoomSerializer(chat_rooms, many=True, context={'request': request})
        return Response(serializer.data)


class CreateChatRoomView(APIView):
    """Create a new chat room between doctor and patient"""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        request=OpenApiTypes.OBJECT,
        responses={
            201: ChatRoomSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Valid Request',
                value={'chat_guid': 1},
                request_only=True
            ),
            OpenApiExample(
                'Success Response',
                value={
                    'id': 1,
                    'patient': 1,
                    'doctor': 2,
                    'patient_name': 'John Doe',
                    'doctor_name': 'Dr. Smith',
                    'created_at': '2023-01-01T12:00:00Z',
                    'is_active': True,
                    'last_message_at': None,
                    'last_message': None,
                    'unread_count': 0
                },
                response_only=True,
                status_codes=['201']
            )
        ]
    )
    def post(self, request):
        if not request.user.is_doctor:
            return Response(
                {"detail": "Only doctors can create chat rooms"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        chat_guid = request.data.get('chat_guid')
        if not chat_guid:
            return Response({"message": "no User found"}, status=400)
        
        try:
            patient = User.objects.get(chat_guid=chat_guid, user_type='patient')

        except Exception: 
            return Response({"message": "More than 1 user"}, status=400)
        
        
        # Check if chat room already exists
        existing_room = ChatRoom.objects.filter(
            doctor=request.user,
            patient=patient
        ).first()
        
        if existing_room:
            if not existing_room.is_active:
                existing_room.is_active = True
                existing_room.save()
            serializer = ChatRoomSerializer(existing_room, context={'request': request})
            return Response(serializer.data)
        
        # Create new chat room
        chat_room = ChatRoom.objects.create(
            doctor=request.user,
            patient=patient
        )
        
        serializer = ChatRoomSerializer(chat_room, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ChatMessagesView(APIView):
    """Get messages for a specific chat room"""
    # permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, room_id):
        try:
            chat_room = ChatRoom.objects.get(id=room_id)
        except ChatRoom.DoesNotExist:
            return Response(
                {"detail": "Chat room not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user is part of this chat
        if request.user not in [chat_room.patient, chat_room.doctor]:
            return Response(
                {"detail": "You don't have access to this chat"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        messages = chat_room.messages.all()
        
        # Mark messages as read for the current user
        unread_messages = messages.filter(is_read=False).exclude(sender=request.user)
        unread_messages.update(is_read=True)
        
        serializer = MessageSerializer(messages, context = {"request": request}, many=True)
        return Response(serializer.data)

from .notification import send_push_notification
from auth_vk.models import DeviceToken
from django.utils import timezone
from datetime import timedelta
from .firebase import firebase_admin

from firebase_admin import credentials, messaging
import os

from django.conf import settings


class SendMessageView(APIView):
    """Send a message in a chat room"""
    # permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='room_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID of the chat room'
            )
        ],
        request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'content': {'type': 'string'},
                'file': build_basic_type(OpenApiTypes.BINARY)
            },
            'required': ['content']
        }
    },
        responses={
            201: MessageSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Valid Request',
                value={'content': 'Hello doctor!'},
                request_only=True
            ),
            OpenApiExample(
                'Success Response',
                value={
                    'id': 1,
                    'content': 'Hello doctor!',
                    'timestamp': '2023-01-01T12:05:00Z',
                    'is_read': False,
                    'sender': 1,
                    'sender_name': 'John Doe',
                    'sender_type': 'patient'
                },
                response_only=True,
                status_codes=['201']
            )
        ]
    )

    def post(self, request, room_id):
        try:
            chat_room = ChatRoom.objects.get(id=room_id)
        except ChatRoom.DoesNotExist:
            return Response(
                {"detail": "Chat room not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user is part of this chat
        if request.user not in [chat_room.patient, chat_room.doctor]:
            return Response(
                {"detail": "You don't have access to this chat"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        content = request.data.get('content', '').strip()
        files = request.FILES
        if not content:
            return Response(
                {"detail": "Message content is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        uploaded_file = request.FILES.get('file')
        print(uploaded_file, 'upload file')
        if not uploaded_file:

            message = Message.objects.create(
                chat_room=chat_room,
                sender=request.user,
                content=content,
            )

        else:
            message = Message.objects.create(
                chat_room=chat_room,
                sender=request.user,
                content=content,
                file=uploaded_file
            
            )

        if not firebase_admin._apps:
            cred_path = os.path.join(settings.BASE_DIR, 'core', 'cred.json')
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        
        recipient = chat_room.doctor if request.user == chat_room.patient else chat_room.patient

        tokens = DeviceToken.objects.filter(user=recipient)
        for device in tokens:
            try:
                send_push_notification(
                    device_token=device.token,
                    title="Новое сообщение",
                    body='',
                   
                )
            except Exception as e:
                print(f"Notification error: {e}")

        # Check if recipient is active in chat (simplified)
        


        serializer = MessageSerializer(message, context = {"request": request} )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RegisterDeviceTokenView(APIView):
    permission_classes = [IsAuthenticated,]

    @extend_schema(
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'token': {'type': 'string', 'description': 'Firebase device token'},
                'device_type': {
                    'type': 'string',
                    'enum': ['android', 'ios'],
                    'default': 'android',
                    'description': 'Type of device'
                },
            },
            'required': ['token']
        }
    },)
    def post(self, request):
        token = request.data.get("token")
        device_type = request.data.get("device_type", "android")
        if not token:
            return Response({"detail": "Token required"}, status=400)
        
        DeviceToken.objects.update_or_create(
            user=request.user,
            token=token,
            defaults={"device_type": device_type}
        )
        return Response({"detail": "Token registered"})
    
# class UserProfileView(APIView):
#     """Get and update user profile"""
#     # permission_classes = [permissions.IsAuthenticated]
    
#     def get(self, request):
#         serializer = UserSerializer(request.user)
#         return Response(serializer.data)
    
#     def put(self, request):
#         serializer = UserSerializer(request.user, data=request.data, partial=True)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Admin Views
class CreateDoctorView(APIView):
    """Admin endpoint to create doctor accounts"""
    # permission_classes = [permissions.IsAuthenticated]
        
    # @extend_schema(
    #     request=DoctorCreationSerializer,
    #     responses={
    #         201: OpenApiTypes.OBJECT,
    #         400: OpenApiTypes.OBJECT,
    #         403: OpenApiTypes.OBJECT
    #     },
    #     examples=[
    #         OpenApiExample(
    #             'Valid Request',
    #             value={
    #                 'username': 'doctor1',
    #                 'email': 'doctor@example.com',
    #                 'password': 'securepassword123',
    #                 'first_name': 'John',
    #                 'last_name': 'Smith',
    #                 'name': 'Dr. John Smith',
    #                 'specialization': 'Cardiology',
    #                 'medical_license': 'MD12345',
    #                 'phone_number': '+79123456789'
    #             },
    #             request_only=True
    #         ),
    #         OpenApiExample(
    #             'Success Response',
    #             value={
    #                 'detail': 'Doctor account created successfully',
    #                 'doctor_id': 1,
    #                 'username': 'doctor1',
    #                 'email': 'doctor@example.com'
    #             },
    #             response_only=True,
    #             status_codes=['201']
    #         )
    #     ]
    # )
    serializer_class = DoctorCreationSerializer

    def post(self, request):
        # if not (request.user.is_superuser or request.user.is_admin_user):
        #     return Response(
        #         {"detail": "Only admin users can create doctor accounts"},
        #         status=status.HTTP_403_FORBIDDEN
        #     )
        
        serializer = DoctorCreationSerializer(data=request.data)
        print('serialize')
        if serializer.is_valid():
            print('before save serializer')
            doctor = serializer.save()
            return Response({
                "detail": "Doctor account created successfully",
                "doctor_id": doctor.id,
                "username": doctor.username,
                "email": doctor.email
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)





from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from datetime import datetime, timedelta, time
from django.utils import timezone
from auth_vk.models import Appointment, Clinic, DoctorSchedule
from auth_vk.serializers import (
    AppointmentCreateSerializer, 
    AppointmentSerializer,
    AvailableTimesSerializer,
    DoctorScheduleSerializer
)


def generate_time_slots(start_time, end_time, slot_duration=30):
    """Generate time slots between start and end time"""
    slots = []
    current_time = datetime.combine(datetime.today(), start_time)
    end_datetime = datetime.combine(datetime.today(), end_time)
    
    while current_time < end_datetime:
        slots.append(current_time.time())
        current_time += timedelta(minutes=slot_duration)
    
    return slots



class AvailableTimesView(APIView):
    def get(self, request):
        doctor_id = request.query_params.get('doctor_id')
        clinic_id = request.query_params.get('clinic_id')
        date_str = request.query_params.get('date')

        if not all([doctor_id, clinic_id, date_str]):
            return Response({"error": "doctor_id, clinic_id, and date are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."},
                            status=status.HTTP_400_BAD_REQUEST)

        weekday = date.weekday()

        schedules = DoctorSchedule.objects.filter(
            doctor_id=doctor_id,
            clinic_id=clinic_id,
            weekday=weekday,
            is_active=True
        )

        available_times = []
        for schedule in schedules:
            current_time = schedule.start_time
            while current_time < schedule.end_time:
                # Check if slot is not booked
                if not Appointment.objects.filter(
                    doctor_id=doctor_id,
                    clinic_id=clinic_id,
                    date=date,
                    time=current_time,
                    status__in=['pending', 'confirmed']
                ).exists():
                    available_times.append(current_time.strftime('%H:%M'))

                # Increment by 30 minutes (or your slot duration)
                current_time = (datetime.combine(date, current_time) + timedelta(minutes=30)).time()

        return Response({"available_times": available_times})
    
class CreateAppointmentView(generics.CreateAPIView):
    serializer_class = AppointmentCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(patient=self.request.user)

from django.db.models import Q
from auth_vk.filters import AppointmentFilter
from django_filters.rest_framework import DjangoFilterBackend


@extend_schema(
    parameters=[
        OpenApiParameter(name='patient_first_name', description='Patient first name', required=False, type=str),
        OpenApiParameter(name='patient_last_name', description='Patient last name', required=False, type=str),
        OpenApiParameter(name='patient_birth_date', description='Patient birth date (YYYY-MM-DD)', required=False, type=str),
        OpenApiParameter(name='patient_phone_number', description='Patient phone number', required=False, type=str),
        OpenApiParameter(name='created_at', description='Appointment created date (YYYY-MM-DD)', required=False, type=str),
    ]
)
class AppointmentListView(generics.ListAPIView):
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated,]
    filter_backends = [DjangoFilterBackend]
    filterset_class = AppointmentFilter

    def get_queryset(self):
        user = self.request.user
        # Base queryset (before filtering)
        return Appointment.objects.filter(Q(patient=user) | Q(doctor=user))
    

class SpecailizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'specialization', 'specialzation_photo']

class AppointmentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = ['clinic', 'notes', 'status']

class AppointmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return AppointmentUpdateSerializer  # <- your update-specific serializer
        return AppointmentSerializer  # <- default for retrieve and delete
    
    def get_queryset(self):
        return Appointment.objects.filter(Q(patient=self.request.user) | Q(doctor=self.request.user))
    
    def update(self, request, *args, **kwargs):
        # Forcefully add request.user as doctor into the data
        data = request.data.copy()
        data['doctor'] = request.user.id

        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


class DoctorScheduleListView(generics.ListCreateAPIView):
    serializer_class = DoctorScheduleSerializer
    
    def get_queryset(self):
        doctor_id = self.request.GET.get('doctor_id')
        clinic_id = self.request.GET.get('clinic_id')
        
        queryset = DoctorSchedule.objects.filter(is_active=True)
        
        if doctor_id:
            queryset = queryset.filter(doctor_id=doctor_id)
        if clinic_id:
            queryset = queryset.filter(clinic_id=clinic_id)
            
        return queryset

from auth_vk.serializers import ClinicSerializer

class DoctorClinicsView(APIView):
    def get(self, request, doctor_id):
        try:
            doctor = User.objects.get(id=doctor_id, user_type='doctor')
            clinics = doctor.clinics.all()
            serializer = ClinicSerializer(clinics, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "Doctor not found."}, status=status.HTTP_404_NOT_FOUND)

class SpecializationListView(APIView):
    def get(self, request, specialization=None):
        if specialization:
            try:
                doctors = User.objects.filter(specialization=specialization, user_type='doctor')
                if not doctors.exists():
                    return Response({'error': 'No doctors found for this specialization'}, status=404)
            except Exception as e:
                return Response({'error': 'An error occurred'}, status=500)
            
            serializer = SpecailizationSerializer(doctors, many=True)
            return Response(serializer.data, status=200)
        
        # Get distinct specializations with their photos
        base_url = f"{request.scheme}://{request.get_host()}"
        
        # Method 1: Get distinct specialization names only
       
        
        # Method 2: If you also need the specialization photo, get one doctor per specialization
        specializations_with_photos = []
        distinct_spec_names = (
            User.objects
            .filter(user_type='doctor', specialization__isnull=False)
            .exclude(specialization='')
            .values_list('specialization', flat=True)
            .distinct()
        )
        
        for spec_name in distinct_spec_names:
            # Get the first doctor with this specialization who has a photo
            doctor_with_photo = User.objects.filter(
                user_type='doctor', 
                specialization=spec_name,
                specialzation_photo__isnull=False
            ).exclude(specialzation_photo='').first()
            
            if doctor_with_photo:
                photo_url = None
                if doctor_with_photo.specialzation_photo:
                    photo_url = base_url + settings.MEDIA_URL + str(doctor_with_photo.specialzation_photo)
                
                specializations_with_photos.append({
                    'specialization': spec_name,
                    'specialzation_photo': photo_url
                })
            else:
                # If no doctor with photo found, still include the specialization
                specializations_with_photos.append({
                    'specialization': spec_name,
                    'specialzation_photo': None
                })
        
        return Response(specializations_with_photos, status=200)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime


class GetDoctorSchedule(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(name='clinics_id', required=True, type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='doctor_id', required=True, type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='date', required=True, type=str, location=OpenApiParameter.QUERY, description='Format: YYYY-MM-DD'),
        ],
        responses={200: OpenApiTypes.OBJECT}
    )
    def get(self, request):
        clinics_id = request.query_params.get("clinics_id")
        doctor_id = request.query_params.get("doctor_id")
        date = request.query_params.get("date")  # Expected in format "YYYY-MM-DD"

        if not (clinics_id and doctor_id and date):
            return Response({"error": "Missing clinics_id, doctor_id, or date"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Parse date to ensure valid format and build time range
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            start_date = date_obj.strftime("%Y-%m-%dT00:00:00")
            finish_date = date_obj.strftime("%Y-%m-%dT23:59:59")
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        # Build data payload for SOAP request
        data = {
            "StartDate": start_date,
            "FinishDate": finish_date,
            "Params": {
                "Property": [
                    {
                        "name": "Clinic",
                        "Value": clinics_id
                    },
                    {
                        "name": "Employees",
                        "Value": doctor_id
                    },
                    {
                        "name": "Format",
                        "Value": "JSON"
                    }
                ]
            }
        }

        # Call the SOAP service
        service = OneCWebService()
        try:
            schedule = service.get_employee_schedule(data)
            return Response(schedule, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)






from django.conf import settings
from django.conf.urls.static import static




#######################################################33333
# services.py - 1C Web Service Integration
from zeep import Client
from zeep.transports import Transport
from requests import Session
from requests.auth import HTTPBasicAuth
import json
import logging
from requests.exceptions import RequestException
from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)

class OneCWebService:
    """Service class for 1C web service integration"""
    
    def __init__(self):
        self.username = 'web'
        self.password = 'web'
        self.wsdl_url = 'http://62.245.57.52/med/ws/ws1.1cws?wsdl'
        self.client = self._get_client()
    
    def _get_client(self):
        """Initialize and return SOAP client"""
        try:
            session = Session()
            session.auth = HTTPBasicAuth(self.username, self.password)
            transport = Transport(session=session)
            return Client(wsdl=self.wsdl_url, transport=transport)
        except Exception as e:
            logger.error(f"Failed to initialize 1C client: {e}")
            raise
    
    def test_xml_parsing(self, xml_string):
        """Test method to debug XML parsing"""
        logger.info(f"Raw XML: {xml_string}")
        parsed_data = self._parse_xml_response(xml_string)
        logger.info(f"Parsed data: {parsed_data}")
        return parsed_data
    
    def get_employees_by_client_phone_v2(self, phone, request):
        """Get employees by client phone"""
        try:
            response = self.client.service.GetListEmployeesClient(Phone=phone)
            
            response_from_parse = self._parse_response(response)
            print(response_from_parse)
            for res in response_from_parse:
                

                try:

                    clinic = get_object_or_404(Clinic, uuid=res['организация'])
                except Exception as e:
                    res['clinic'] = ''

                # user = get_object_or_404(User, username=res["id"], user_type="doctor")
                
                # res['clinic'] = clinic.name
                # print('clinic')

                # res['photo'] = (
                #     request.build_absolute_uri(user.avatar.url  if user.avatar else "")
                #     )
                

            print('response from parse')
            return response_from_parse
        
        except Exception as e:

            logger.error(f"Failed to get employees by client phone {phone}: {e}")
            return []
        

    def get_employees_by_client_phone(self, phone, request):
        """Get employees by client phone"""
        try:
            response = self.client.service.GetZayavkiClient(Phone=phone)
            
            response_from_parse = self._parse_response(response)
            print(response_from_parse)
            for res in response_from_parse:
                

                try:

                    clinic = get_object_or_404(Clinic, uuid=res['организация'])
                except Exception as e:
                    res['clinic'] = ''

                # user = get_object_or_404(User, username=res["id"], user_type="doctor")
                
                # res['clinic'] = clinic.name
                # print('clinic')

                # res['photo'] = (
                #     request.build_absolute_uri(user.avatar.url  if user.avatar else "")
                #     )
                

            print('response from parse')
            return response_from_parse
        
        except Exception as e:

            logger.error(f"Failed to get employees by client phone {phone}: {e}")
            return []
    
    def get_reception_list(self, employee_id, phone):
        """Get reception list for employee and phone"""
        try:
            response = self.client.service.GetListReception(
                EmployeeID=employee_id, 
                Phone=phone
            )
            print(response, 'this is ressponse')
            response_from_parse = self._parse_response(response)
            print(response_from_parse, 'this is parse from ')
            
            return response_from_parse
        except Exception as e:
            logger.error(f"Failed to get reception list for employee {employee_id}, phone {phone}: {e}")
            return []
    
    def get_reception_info(self, guid):
        """
        Get detailed reception/visit information by GUID
        Returns parsed reception data with all available fields
        """
        try:
            response = self.client.service.GetReceptionInfo(GUID=guid)
            
            response_from_parse = self._parse_response(response)
        
            return response_from_parse
        
        except Exception as e:
            logger.error(f"Failed to get reception info for GUID {guid}: {e}")
            return {}
    
    def get_zayavok_doktora(self, guid):
        try:
            response = self.client.service.GetZayavkiDoctora(
                GUID=guid
            )

            response_from_parse = self._parse_response(response)
            
            
            return response_from_parse
        except Exception:
            raise

    def _parse_reception_info_xml(self, root):
        """
        Parse reception info XML structure - add this helper method if needed
        This handles specific structure returned by GetReceptionInfo
        """
        reception_data = {}
        
        # Define field mappings from Russian to English for reception info
        field_mapping = {
            'UID': 'id',
            'GUID': 'guid',
            'Номер': 'number',
            'ДатаВизита': 'visit_date',
            'ВремяНачала': 'start_time', 
            'ВремяОкончания': 'end_time',
            'Наименование': 'service_name',
            'Описание': 'description',
            'Статус': 'status',
            'Телефон': 'phone',
            'СотрудникID': 'employee_id',
            'СотрудникИмя': 'employee_name',
            'СотрудникФИО': 'employee_full_name',
            'КлиентID': 'client_id',
            'КлиентИмя': 'client_name',
            'КлиентФИО': 'client_full_name',
            'КлиентТелефон': 'client_phone',
            'Стоимость': 'cost',
            'СтатусОплаты': 'payment_status',
            'Примечания': 'notes',
            'Клиника': 'clinic',
            'КлиникаID': 'clinic_id',
            'Кабинет': 'room',
            'Специализация': 'specialization',
            'Услуга': 'service',
            'УслугаID': 'service_id',
            'ДатаСоздания': 'created_date',
            'ДатаИзменения': 'modified_date',
            'СозданПользователем': 'created_by',
            'ИзмененПользователем': 'modified_by',
            "ПрикрепленныйФайл": 'attached_file',
            'Файл': "file"

        }
         
        # Handle both single element and root with children
        if root.tag.split('}')[-1] in ['Визит', 'Reception', 'Прием']:
            element = root
        else:
            # Look for reception/visit element in children
            element = None
            for child in root.iter():
                tag_name = child.tag.split('}')[-1]
                if tag_name in ['Визит', 'Reception', 'Прием']:
                    element = child
                    break
            
            if element is None:
                # If no specific reception element found, parse the root
                element = root
        
        # Extract all fields from the element
        reception_data = {}
        attached_files = []

        for child in element:
            tag_name = child.tag.split('}')[-1]
            
            if tag_name == 'ПрикрепленныйФайл':
                file_info = {}
                for sub_child in child:
                    sub_tag = sub_child.tag.split('}')[-1]
                    if sub_tag == 'Название':
                        file_info['name'] = sub_child.text
                    elif sub_tag == 'Файл':
                        file_info['base64'] = sub_child.text
                if file_info:  # Only add if there's data
                    attached_files.append(file_info)
            else:
                english_key = field_mapping.get(tag_name, tag_name.lower())
                reception_data[english_key] = child.text

        # Add list of attached files to result
        if attached_files:
            reception_data['attached_files'] = attached_files
        
        # Handle date/time conversions
        if 'visit_date' in reception_data and reception_data['visit_date']:
            try:
                from datetime import datetime
                # Handle different datetime formats
                date_str = reception_data['visit_date']
                if 'T' in date_str:
                    dt = datetime.fromisoformat(date_str.replace('T', ' '))
                    reception_data['date'] = dt.date().isoformat()
                    reception_data['time'] = dt.time().isoformat()
                else:
                    # Just date
                    reception_data['date'] = date_str
            except Exception as date_error:
                logger.warning(f"Could not parse visit_date {reception_data['visit_date']}: {date_error}")
        
        # Convert numeric fields
        numeric_fields = ['cost']
        for field in numeric_fields:
            if field in reception_data and reception_data[field]:
                try:
                    reception_data[field] = float(reception_data[field])
                except (ValueError, TypeError):
                    pass  # Keep as string if conversion fails
        
        return reception_data
        
    def get_employee_schedule(self, data):
        """
        Get employee schedule with available time slots
        data should contain parameters like DateBegin, DateEnd, Clinic, EmployeeID, etc.
        Returns parsed schedule data with available time slots
        """

        try:
            print(data, 'this is data')
            response = self.client.service.GetSchedule20(**data)
            print(f"GetReserve response: {response}")
            return self._parse_schedule_response(response)
        except RequestException as e:
            logger.error(f"error in get reserve {e}")
            raise 

    def _parse_schedule_response(self, raw_data):
        """
        Parse the GetReserve response to extract schedule information
        Expected response format is JSON with ГрафикиДляСайта structure
        """
        try:
            import json
            
            # Handle both string and object responses
            if isinstance(raw_data, str):
                data = json.loads(raw_data)
            elif hasattr(raw_data, '__dict__'):
                # Convert object to dict if needed
                data = raw_data.__dict__ if hasattr(raw_data, '__dict__') else raw_data
            else:
                data = raw_data
            
            schedules = []
            
            # Navigate through the JSON structure
            if 'ГрафикиДляСайта' in data and 'ГрафикДляСайта' in data['ГрафикиДляСайта']:
                for schedule_item in data['ГрафикиДляСайта']['ГрафикДляСайта']:
                    
                    # Extract basic doctor info
                    doctor_schedule = {
                        'clinic_id': schedule_item.get('Клиника', ''),
                        'doctor_name': schedule_item.get('СотрудникФИО', ''),
                        'doctor_id': schedule_item.get('СотрудникID', ''),
                        'specialization': schedule_item.get('Специализация', ''),
                        'appointment_duration': schedule_item.get('ДлительностьПриема', ''),
                        'available_slots': [],
                        'occupied_slots': []
                    }
                    
                    # Parse available time periods
                    periods = schedule_item.get('ПериодыГрафика', {})
                    
                    # Parse available time slots
                    free_time = periods.get('СвободноеВремя', {})
                    if isinstance(free_time, dict) and 'ПериодГрафика' in free_time:
                        periods_list = free_time['ПериодГрафика']
                        if not isinstance(periods_list, list):
                            periods_list = [periods_list]
                            
                        for period in periods_list:
                            slot = {
                                'clinic_id': period.get('Клиника', ''),
                                'date': period.get('Дата', ''),
                                'start_time': period.get('ВремяНачала', ''),
                                'end_time': period.get('ВремяОкончания', ''),
                                'time_type_id': period.get('ВидВремени', '')
                            }
                            doctor_schedule['available_slots'].append(slot)
                    
                    # Parse occupied time slots (if any)
                    occupied_time = periods.get('ЗанятоеВремя', '')
                    if occupied_time and isinstance(occupied_time, dict):
                        # Similar parsing for occupied time if it has structure
                        # For now, it seems to be empty string in your example
                        pass
                    
                    schedules.append(doctor_schedule)
            
            return {
                'success': True,
                'schedules': schedules,
                'error': None
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error in GetReserve response: {e}")
            return {
                'success': False,
                'schedules': [],
                'error': f"JSON parsing error: {e}"
            }
        except Exception as e:
            logger.error(f"Error parsing GetReserve response: {e}")
            return {
                'success': False,
                'schedules': [],
                'error': str(e)
            }
        
    def _parse_response(self, response):
        """Parse 1C XML response"""
        try:
            if isinstance(response, str):
                return self._parse_xml_response(response)
            return response
        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
            return []
    
    def _parse_xml_response(self, xml_string):
        """Parse XML response and convert to Python dictionaries"""
        import xml.etree.ElementTree as ET
        print(xml_string, 'string')
        
        try:
            
            root = ET.fromstring(xml_string)
            
            # Handle different XML structures based on root element
            root_tag = root.tag.split('}')[-1]  # Remove namespace
            
            if root_tag in ['Визит', 'Reception', 'Прием']:
                # Single reception info
                print('natalya--')
                return self._parse_reception_info_xml(root)
            elif root_tag == 'Визиты' or 'Визит' in [child.tag.split('}')[-1] for child in root]:
                # Multiple visits
                return self._parse_visits_xml(root)
            elif root_tag in ['Сотрудники', 'Employees'] or 'Сотрудник' in [child.tag.split('}')[-1] for child in root]:
                # Employees
                return self._parse_employees_xml(root)
            
            elif root_tag in ['Заявки', 'Заявка'] or 'Заявка' in [child.tag.split('}')[-1] for child in root]:
                print(root, 'this is zay root')
                return self._parse_zayavki_xml(root)  # Add this line 👈
            else:
                # Generic parsing for unknown structures
                return self._parse_generic_xml(root)
            
                
        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")
            return []
        
    def _parse_visits_xml(self, root):
        """Parse visits (Визиты) XML structure"""
        visits = []
        
        ns = {'ns': 'S2'}  # Namespace mapping for 'S2'
        
        for visit_elem in root.findall('.//ns:Визит', namespaces=ns):
            visit_data = {}

            field_mapping = {
                'UID': 'id',
                'ДатаВизита': 'visit_date', 
                'Наименование': 'service_name',
                'Статус': 'status',
                'Телефон': 'phone',
                'СотрудникID': 'employee_id',
                'СотрудникИмя': 'employee_name',
                'КлиентИмя': 'client_name',
                'Стоимость': 'cost',
                'СтатусОплаты': 'payment_status',
                'Примечания': 'notes'
            }
            
            for child in visit_elem:
                tag_name = child.tag.split('}')[-1]  # Remove namespace
                english_key = field_mapping.get(tag_name, tag_name.lower())
                visit_data[english_key] = child.text
            
            # Convert date format if present
            if 'visit_date' in visit_data and visit_data['visit_date']:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(visit_data['visit_date'].replace('T', ' '))
                    visit_data['date'] = dt.date().isoformat()
                    visit_data['time'] = dt.time().isoformat()
                except:
                    pass
            
            visits.append(visit_data)
        
        return visits
    
    def _parse_zayavki_xml(self, root):
        """Parse <Заявка> or <Заявки> XML into dicts"""
        import xml.etree.ElementTree as ET
        
        print(f"Parsing zayavki XML. Root tag: {root.tag}")
        
        zayavki = []
        zayavka_elements = []
        
        # Since your root shows {S2}Заявки, we need namespace-aware search
        try:
            zayavka_elements = root.findall(".//{S2}Заявка")
            print(f"Found {len(zayavka_elements)} Заявка elements with namespace")
        except Exception as e:
            print(f"Namespace search failed: {e}")
        
        # Fallback: iterate all elements and match by tag
        if not zayavka_elements:
            for elem in root.iter():
                if elem.tag == '{S2}Заявка' or elem.tag.split('}')[-1] == 'Заявка':
                    zayavka_elements.append(elem)
            print(f"Found {len(zayavka_elements)} Заявка elements via iteration")
        
        for i, z in enumerate(zayavka_elements):
            try:
                print(f"Processing Заявка {i+1}")
                
                zayavka_data = {
                    "uid": self._get_element_text(z, "UID"),
                    "sostoyanie": self._get_element_text(z, "Состояние"),
                    "data_zayavki": self._get_element_text(z, "ДатаЗаявки"),
                    "data_nachala_zapisi": self._get_element_text(z, "ДатаНачалаЗаписи"),
                    "data_okonchaniya_zapisi": self._get_element_text(z, "ДатаОкончанияЗаписи"),
                    "patient_first_name": self._get_element_text(z, "ИмяПациента"),
                    "patient_lastname": self._get_element_text(z, "ФамилияПациента"),
                    "patient_birth_date": self._get_element_text(z, 'ДатаРожденияПациента'),
                    "patient_phone_number": self._get_element_text(z, "НомерТелефонаПациента"),
                    "doctor_uid": self._get_element_text(z, "ДокторUID"),
                    "doctor_name": self._get_element_text(z, "Доктор"),
                    "branch": self._get_element_text(z, "Филиал"),
                    "chat_guid": self._get_element_text(z, "ChatUUID"),
                }
                
                print(f"Parsed zayavka data: {zayavka_data}")
                zayavki.append(zayavka_data)
                
            except Exception as e:
                print(f"Error parsing zayavka element {i+1}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"Total parsed zayavki: {len(zayavki)}")
        return zayavki

    def _get_element_text(self, parent, tag_name):
        """Helper method to get element text, handling S2 namespace"""
        # Try with S2 namespace first
        elem = parent.find(f"{{S2}}{tag_name}")
        if elem is not None:
            return elem.text
        
        # Try direct search (no namespace)
        elem = parent.find(tag_name)
        if elem is not None:
            return elem.text
        
        # Try with namespace-agnostic search as final fallback
        for child in parent:
            if child.tag == f"{{S2}}{tag_name}" or child.tag.split('}')[-1] == tag_name:
                return child.text
        
        return None

    def _parse_employees_xml(self, root):
        """Parse employees XML structure without XPath predicates"""
        employees = []

        for emp_elem in root.iter():
            tag = emp_elem.tag.split('}')[-1]
            if tag != 'Сотрудник':
                continue

            employee_data = {}
            field_mapping = {
                'UID': 'id',
                'Имя': 'name',
                'Телефон': 'phone',
                'Фото': 'photo',
                'Должность': 'position',
                'Отдел': 'department'
            }

            for child in emp_elem:
                tag_name = child.tag.split('}')[-1]
                english_key = field_mapping.get(tag_name, tag_name.lower())
                employee_data[english_key] = child.text

            employees.append(employee_data)

        print(employees, 'this is employees')

        return employees
    
    def get_reserve(self, specialization, date_str, time_str, employee_id, clinic_id):
        """
        Call GetReserve to reserve a slot.
        Returns the GUID for the reserved slot.
        """
        print(date_str, 'date string')
        print(time_str, 'time string')

        try:
            # If datetime objects are passed directly, use them
            if isinstance(date_str, datetime):
                appointment_datetime = date_str
            elif isinstance(date_str, str):
                # Handle ISO format like "2025-07-19T15:00:00"
                if "T" in date_str:
                    date_obj = datetime.fromisoformat(date_str).date()
                else:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

                if isinstance(time_str, str):
                    if "T" in time_str:
                        time_obj = datetime.fromisoformat(time_str).time()
                    else:
                        time_obj = datetime.strptime(time_str, "%H:%M:%S").time()
                else:
                    time_obj = time_str

                appointment_datetime = datetime.combine(date_obj, time_obj)
            else:
                # If date_str is a date object and time_str is a time object
                appointment_datetime = datetime.combine(date_str, time_str)

        except Exception as e:
            print(f"Date or time parsing error: {e}")
            return {"success": False, "error": f"Date or time parsing error: {e}"}

        try:
            response = self.client.service.GetReserve(
                Specialization=specialization,
                Date=appointment_datetime,
                TimeBegin=appointment_datetime,
                EmployeeID=employee_id,
                Clinic=clinic_id
            )

            print(response, 'response from get_reserve')
            
            # Extract GUID from response if it exists
            if hasattr(response, 'УИД'):
                guid = response.УИД
            elif hasattr(response, 'guid'):
                guid = response.guid
            else:
                # Try to extract GUID from the response structure
                guid = str(response) if response else None

            ns = {'s1': 'S1'}

            # Parse the XML
            root = ET.fromstring(guid)

            # Extract the UID
            uid = root.find('s1:УИД', ns).text

            print("УИД:", uid)
                
            return {"success": True, "response": response, "uid": uid}

        except Exception as e:
            print(f"Error calling GetReserve: {e}")
            return {"success": False, "error": str(e)}
        
        
    def book_appointment(
        self,
        employee_id,
        date_str,
        time_str,
        phone,
        clinic_id,
        guid,
        first_name,
        last_name, 
        middle_name,
        comment,
        chat_guid,

    ):
        
        try:
            # If datetime objects are passed directly, use them
            if isinstance(date_str, datetime):
                appointment_datetime = date_str
            elif isinstance(date_str, str):
                # Handle ISO format like "2025-07-19T15:00:00"
                if "T" in date_str:
                    date_obj = datetime.fromisoformat(date_str).date()
                else:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

                if isinstance(time_str, str):
                    if "T" in time_str:
                        time_obj = datetime.fromisoformat(time_str).time()
                    else:
                        time_obj = datetime.strptime(time_str, "%H:%M:%S").time()
                else:
                    time_obj = time_str

                appointment_datetime = datetime.combine(date_obj, time_obj)
            else:
                # If date_str is a date object and time_str is a time object
                appointment_datetime = datetime.combine(date_str, time_str)

        except Exception as e:
            print(f"Date or time parsing error: {e}")
            return {"success": False, "error": f"Date or time parsing error: {e}"}

        """
        Finalize the appointment booking after reserve.
        """
        print(chat_guid, 'chat guid---')
        try:
            response = self.client.service.BookAnAppointment(
                EmployeeID=employee_id,

                Date=appointment_datetime,
                TimeBegin=appointment_datetime,
            
                Phone=phone,
       
                Clinic=clinic_id,
                GUID=guid,

                PatientSurname=last_name,
                PatientName=first_name,
                PatientFatherName=middle_name,

                Comment=comment,
                Email="test@gmail.com",
                Address="test",
                ChatGUID=chat_guid,


            )
            print(response, 'ress')

            parsed = self._parse_xml_response(response)
            if isinstance(parsed, list):
                parsed = parsed[0] if parsed else {}

            return {
                "success": parsed.get("Результат", "false").lower() == "true",
                "error": parsed.get("ОписаниеОшибки")
            }

        except Exception as e:
            print(e, 'error')
            logger.error(f"BookAnAppointment failed: {e}")
            return {"success": False, "error": str(e)}



    # def _parse_employees_xml(self, root):
    #     """Parse employees XML structure"""
    #     employees = []
        
    #     for emp_elem in root.findall('.//*[contains(local-name(), "Сотрудник")]'):
    #         employee_data = {}
            
    #         field_mapping = {
    #             'UID': 'id',
    #             'Имя': 'name',
    #             'Телефон': 'phone',
    #             'Фото': 'photo',
    #             'Должность': 'position',
    #             'Отдел': 'department'
    #         }
            
    #         for child in emp_elem:
    #             tag_name = child.tag.split('}')[-1]
    #             english_key = field_mapping.get(tag_name, tag_name.lower())
    #             employee_data[english_key] = child.text
            
    #         employees.append(employee_data)
        
    #     return employees
    
    def _parse_generic_xml(self, root):
        """Generic XML parser for unknown structures"""
        result = []
        
        for elem in root:
            item_data = {}
            for child in elem:
                tag_name = child.tag.split('}')[-1]
                item_data[tag_name.lower()] = child.text
            result.append(item_data)
        
        return result




class ReserveAndBookAPIView(APIView):
    permission_classes = [IsAuthenticated,]
    @extend_schema(
        request={
            "application/json": OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                name="Reserve and Book Example",
                value={
                    "specialization": "Неврология",
                    "date": "2025-07-20T00:00:00",
                    "time_begin": "0001-01-01T15:00:00",
                    "employee_id": "03104d15-20e5-11f0-a08e-047c1674176e",
                    "clinic_id": "f6b5b37d-20c6-11f0-a08e-047c1674176e",
                 
                    "comment": "Предпочтительное время"
                },
                request_only=True,
                response_only=False
            )
        ],
        responses={200: OpenApiResponse(description="Успешная бронь", response=OpenApiTypes.OBJECT)},
    )

    def post(self, request):
        date_str = request.data.get("date")
        time_str = request.data.get("time_begin")
        employee_id = request.data.get("employee_id")
        clinic_id = request.data.get("clinic_id")
        comment = request.data.get('comment')

        try:
            # Handle date parsing - support both ISO format and date-only format
            if "T" in date_str:
                appointment_date = datetime.fromisoformat(date_str).date()
            else:
                appointment_date = datetime.strptime(date_str, "%Y-%m-%d").date()

            # Handle time parsing
            if "T" in time_str:
                time_str = time_str.split("T")[1]
            
            appointment_time = datetime.strptime(time_str, "%H:%M:%S").time()

        except ValueError as e:
            return Response({"error": f"Invalid date or time format: {str(e)}"}, status=400)
        except Exception as e:
            return Response({"error": f"Date/time parsing error: {str(e)}"}, status=400)

        service = OneCWebService()
        try:

            # Step 1: Reserve
            print('get reserve ----')
            reserve_response = service.get_reserve(
                specialization="",
                date_str=appointment_date,
                time_str=appointment_time,
                employee_id=employee_id,
                clinic_id=clinic_id
            )

            uid = reserve_response["uid"]
            print(uid, 'guiiiid')
            try:
                
                doctor = User.objects.get(username=employee_id, user_type='doctor')
                clinic = Clinic.objects.get(uuid=clinic_id)
                
                Appointment.objects.create(patient=self.request.user, doctor=doctor, clinic=clinic, date=appointment_date, time=appointment_time )
            except Exception as e:
                print(e, 'this is hidden')

            # Step 2: Book
            chat_guid = uuid.uuid4()
            self.request.user.chat_guid = chat_guid
            self.request.user.save(update_fields=['chat_guid'])

            booking_response = service.book_appointment(
                employee_id=employee_id,
                date_str=appointment_date,
                time_str=appointment_time,
                phone=self.request.user.phone_number,
                clinic_id=clinic_id,
                guid=uid,
                first_name=self.request.user.first_name,
                last_name=self.request.user.last_name,
                middle_name=self.request.user.middle_name,
                comment=comment,
                chat_guid=chat_guid
            )
            print(booking_response, 'response booooooooo')
        except Exception as e:
            return Response({"message":f"Error happened {e}"}, status=400)

        return Response({"message": "Appointment booked successfully."})


# serializers.py - Django REST Framework Serializers
from rest_framework import serializers

class EmployeeSerializer(serializers.Serializer):
    """Serializer for employee data from 1C"""
    id = serializers.CharField()
    name = serializers.CharField()
    phone = serializers.CharField(required=False)
    наименование = serializers.CharField(required=False)
    фамилия = serializers.CharField(required=False)
    специализация = serializers.CharField(required=False)
    photo = serializers.CharField(required=False)
    
    class Meta:
        fields = ['id', 'name', 'phone', 'наименование', 'фамилия', 'photo']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        photo = data.get('photo')

        if photo:
            if not photo.startswith('data:image'):
                data['photo'] = f"data:image/jpeg;base64,{photo}"

        return data

    
class ReceptionSerializer(serializers.Serializer):
    """Serializer for reception data from 1C"""
    id = serializers.CharField()
    visit_date = serializers.CharField(required=False)
    date = serializers.CharField(required=False)
    time = serializers.CharField(required=False)
    service_name = serializers.CharField(required=False)
    employee_id = serializers.CharField(required=False)
    employee_name = serializers.CharField(required=False)
    client_name = serializers.CharField(required=False)
    phone = serializers.CharField(required=False)
    status = serializers.CharField(required=False)
    cost = serializers.CharField(required=False)
    payment_status = serializers.CharField(required=False)
    notes = serializers.CharField(required=False)
    
    class Meta:
        fields = [
            'id', 'visit_date', 'date', 'time', 'service_name', 
            'employee_id', 'employee_name', 'client_name', 'phone',
            'status', 'cost', 'payment_status', 'notes'
        ]

class ReceptionDetailSerializer(ReceptionSerializer):
    """Extended serializer for detailed reception view"""
    # All fields from ReceptionSerializer are already included
    pass  # No additional fields needed as base serializer now has all data

class ZayavokDoktoraSerializer(serializers.Serializer):
    uid = serializers.CharField()
    sostoyanie = serializers.CharField()
    data_zayavki = serializers.DateTimeField()
    data_nachala_zapisi = serializers.DateTimeField()
    data_okonchaniya_zapisi = serializers.DateTimeField()
    patient_first_name = serializers.CharField()
    patient_lastname = serializers.CharField()
    patient_birth_date =serializers.DateField()
    patient_phone_number = serializers.CharField()
    chat_guid = serializers.CharField()


# views.py - Django REST Framework Views
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.http import Http404


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

# views.py - Django REST Framework Views
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.http import Http404


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class EmployeeListView(APIView):
    """List all employees from 1C"""
    
    def get(self, request):
        try:
            service = OneCWebService()
            employees_data = service.get_employees()
            
            # Filter by phone if provided
            phone = request.query_params.get('phone')
            if phone:
                employees_data = service.get_employees_by_client_phone(phone, request)
            
            serializer = EmployeeSerializer(employees_data, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to fetch employees: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# class FixedDoctorInfoView(APIView):
#     """
#     Return information about a fixed doctor (by employee ID),
#     optionally using client phone to fetch filtered data.
#     """

#     def get(self, request):
#         try:
#             fixed_employee_id = '614db726-21bc-11f0-a08e-047c1674176e'
#             phone = '79655059619'

#             service = OneCWebService()

#             if phone:
#                 employees = service.get_employees_by_client_phone(phone)
#                 employees[0]
#                 print(employees[0].keys(), 'empl')
#             else:
#                 employees = service.get_employees()  # all employees
           
#             # # Find the one with the fixed ID
#             # doctor = next((emp for emp in employees if emp.get('id') == fixed_employee_id), None)
#             # print(doctor, 'this is doctor0000--')
#             # if not doctor:
#             #     return Response(
#             #         {'error': 'Doctor not found for given phone or ID'},
#             #         status=status.HTTP_404_NOT_FOUND
#             #     )

#             serializer = EmployeeSerializer(employees, many=True)
#             return Response(serializer.data, status=status.HTTP_200_OK)

#         except Exception as e:
#             return Response(
#                 {'error': f'Failed to fetch doctor info: {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )

class FaqView(generics.ListAPIView):
    queryset = models.FAQ.objects.all()
    serializer_class = sr.FaqSerializer


class GetEmployeesClientView(APIView):
    """
    Get list of employees by client phone number
    Uses OneCWebService which handles XML parsing automatically
    """
    permission_classes = [IsAuthenticated, ]
    @extend_schema(
    tags=["medkarta"],
   
    
    responses={
        200: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'data': {'type': 'array', 'items': {'type': 'object'}},
                'phone': {'type': 'string'},
                'count': {'type': 'integer'}
            }
        },
        400: {'type': 'object'},
        500: {'type': 'object'}
    },
    description='Get list of employees by client phone number.'
)
    def get(self, request):
        try:
            phone = self.request.user.phone_number
            # phone = "+79089216243"
            print('phone', phone)

            # phone = "89089216243"

            if not phone:
                return Response(
                    {'success': False, 'error': 'Phone number is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Initialize service and get parsed data
            onec_service = OneCWebService()
            employees_data = onec_service.get_employees_by_client_phone(phone, request)
            
            
            # employees_data is already parsed by _parse_xml_response method
            return Response({
                'success': True,
                'data': employees_data,
                'phone': phone,
                'count': len(employees_data) if isinstance(employees_data, list) else 0
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in GetEmployeesClientView: {e}")
            return Response({
                'success': False,
                'error': f'Service error: {str(e)}',
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetEmployeesClientV2View(APIView):
    """
    Get list of employees by client phone number
    Uses OneCWebService which handles XML parsing automatically
    """
    permission_classes = [IsAuthenticated, ]
    @extend_schema(
    tags=["medkarta"],
   
    
    responses={
        200: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'data': {'type': 'array', 'items': {'type': 'object'}},
                'phone': {'type': 'string'},
                'count': {'type': 'integer'}
            }
        },
        400: {'type': 'object'},
        500: {'type': 'object'}
    },
    description='Get list of employees by client phone number.'
)
    def get(self, request):
        try:
            phone = self.request.user.phone_number
            # phone = "+79089216243"
            print('phone', phone)

            # phone = "89089216243"

            if not phone:
                return Response(
                    {'success': False, 'error': 'Phone number is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Initialize service and get parsed data
            onec_service = OneCWebService()
            employees_data = onec_service.get_employees_by_client_phone_v2(phone, request)
            
            
            # employees_data is already parsed by _parse_xml_response method
            return Response({
                'success': True,
                'data': employees_data,
                'phone': phone,
                'count': len(employees_data) if isinstance(employees_data, list) else 0
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in GetEmployeesClientView: {e}")
            return Response({
                'success': False,
                'error': f'Service error: {str(e)}',
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetReceptionListView(APIView):
    permission_classes = [IsAuthenticated, ]
    """
    Get reception list by employee ID and phone
    Uses OneCWebService which handles XML parsing automatically
    """
    @extend_schema(
    tags=["medkarta"],
    parameters= [OpenApiParameter(name='employee_id', required=True, type=str, location=OpenApiParameter.QUERY),],
    
    responses={
        200: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'data': {'type': 'array', 'items': {'type': 'object'}},
                'employee_id': {'type': 'string'},
                'phone': {'type': 'string'},
                'count': {'type': 'integer'}
            }
        },
        400: {'type': 'object'},
        500: {'type': 'object'}
    },
    description='Get reception list by employee ID and phone.'
)
    def get(self, request):
        try:
            employee_id = request.query_params.get("employee_id")
            phone = self.request.user.phone_number
            # # phone = "79028745570"
            # phone = "79089216243"
            
            if not employee_id or not phone:
                return Response({
                    'success': False,
                    'error': 'Both employee_id and phone are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Initialize service and get parsed data
            onec_service = OneCWebService()
            reception_data = onec_service.get_reception_list(employee_id, phone)
            
            # reception_data is already parsed by _parse_xml_response method
            return Response({
                'success': True,
                'data': reception_data,
                'employee_id': employee_id,
                'phone': phone,
                'count': len(reception_data) if isinstance(reception_data, list) else 0
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in GetReceptionListView: {e}")
            return Response({
                'success': False,
                'error': f'Service error: {str(e)}',
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetReceptionInfoView(APIView):
    """
    Get reception info by GUID
    You need to add this method to your OneCWebService class
    """
    @extend_schema(
    tags=["medkarta"],
    parameters= [OpenApiParameter(name='guid', required=True, type=str, location=OpenApiParameter.QUERY),],
    
    responses={
        200: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'data': {'type': 'object'},
                'guid': {'type': 'string'}
            }
        },
        400: {'type': 'object'},
        500: {'type': 'object'}
    },
    description='Get reception information by GUID.'
)
    def get(self, request):
        try:
            guid = request.query_params.get('guid')
            
            if not guid:
                return Response({
                    'success': False,
                    'error': 'GUID is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Initialize service and get parsed data
            onec_service = OneCWebService()
            reception_info = onec_service.get_reception_info(guid)
            
            return Response({
                'success': True,
                'data': reception_info,
                'guid': guid
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in GetReceptionInfoView: {e}")
            return Response({
                'success': False,
                'error': f'Service error: {str(e)}',
                'data': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        
class GetZayavokDoktora(APIView):
    permission_classes = [IsAuthenticated,]

    @extend_schema(
    tags=["medkarta"],
    
    
    responses={
        200: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'data': {'type': 'object'},
                'guid': {'type': 'string'}
            }
        },
        400: {'type': 'object'},
        500: {'type': 'object'}
    },
    description='Get reception information by GUID.'
)
    def get(self, request):
      

        client = OneCWebService()

        zayavki = client.get_zayavok_doktora(self.request.user.username)
        
        return Response(ZayavokDoktoraSerializer(zayavki, many=True).data)


from auth_vk.models import News
from auth_vk.serializers import NewsSerializer

class NewsListView(generics.ListAPIView):
    queryset = News.objects.all()
    serializer_class = NewsSerializer




urlpatterns = [
    # Employee endpoints
 
    # Reception endpoints
    # path('reception-employees/', FixedDoctorInfoView.as_view() ),

    # path('receptions/', ReceptionListView.as_view(), name='reception-list'),
    # path('receptions/<str:reception_id>/', ReceptionDetailView.as_view(), name='reception-detail'),
    
    # User summary endpoint
   
    path('faq/', FaqView.as_view()),

    path("device-token/", RegisterDeviceTokenView.as_view(), name='device-token'),

    path("get-doctor-schedule/", GetDoctorSchedule.as_view(), name = 'get-doctor-schedle'),

    path('get-zayovok-doktora/', GetZayavokDoktora.as_view(), name='get-zayavok')
]

urlpatterns += [
    path('admin/', admin.site.urls),
    path('auth/', VKAuthTokenView.as_view(), name='vk-auth'),
    path('refresh/', RefreshTokenView.as_view(), name='token-refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    # path('user/', UserProfileView.as_view(), name='user-profile'),
]

urlpatterns += [
    # YOUR PATTERNS
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    # Optional UI:
    path('schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

urlpatterns += [
    path("book-appointment-v2/", ReserveAndBookAPIView.as_view())
]

urlpatterns += [
    path('', include(router.urls)),
    path('realtime-sync/', RealTimeSyncView.as_view(), name='realtime-sync'),
    path('specializations/', SpecializationListView.as_view(), name='specializations-list'),
    path('specializations/<str:specialization>/', SpecializationListView.as_view(), name='specializations-detail'),
    path('banners/', NewsListView.as_view(), name='news')
]

urlpatterns += [
    # Authentication
    path('auth/request-otp/', RequestOTPView.as_view(), name='request-otp'),
    path('auth/verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('auth/doctor-login/', DoctorLoginView.as_view(), name='doctor-login'),
    path('auth/profile/', UserProfileView.as_view(), name='user-profile'),
    
    # Chat system
    path('doctors/available/', AvailableDoctorsView.as_view(), name='available-doctors'),
    path('chats/', ChatRoomListView.as_view(), name='chat-rooms'),
    path('chats/create/', CreateChatRoomView.as_view(), name='create-chat'),
    path('chats/<int:room_id>/messages/', ChatMessagesView.as_view(), name='chat-messages'),
    path('chats/<int:room_id>/send/', SendMessageView.as_view(), name='send-message'),
    
    path('create-doctor/', CreateDoctorView.as_view(), name='create-doctor'),
]

urlpatterns += [
    path('doctors/<int:doctor_id>/clinics/', DoctorClinicsView.as_view(), name='doctor-clinics'),
]


urlpatterns += [
    # Appointment URLs
    path('appointments/', AppointmentListView.as_view(), name='appointment-list'),
    path('appointments/create/', CreateAppointmentView.as_view(), name='appointment-create'),
    path('appointments/<int:pk>/', AppointmentDetailView.as_view(), name='appointment-detail'),
    

    # Doctor schedules
    path('doctor-schedules/', DoctorScheduleListView.as_view(), name='doctor-schedules'),
    ##########
    path('employees-client/', GetEmployeesClientView.as_view(), name='get_employees_client_cbv'),
    path('employees-client-v2/', GetEmployeesClientV2View.as_view()),
    path('reception-list/', GetReceptionListView.as_view(), name='get_reception_list_cbv'),
    path('reception-info/', GetReceptionInfoView.as_view(), name='get_reception_info_cbv'),
    

] +  static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

