from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from allauth.socialaccount.models import SocialAccount
from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from allauth.socialaccount.providers.vk.views import VKOAuth2Adapter
# Create your views here.
# views.py
from . import models
from . import serializers as sr

from auth_vk.models import ChatRoom, Message
import requests
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response   
from rest_framework import status
from rest_framework import permissions, viewsets
from auth_vk.serializers import UserSerializer, RegisterSerializer, ClinicSerializer, ServiceCategorySerializer, ServiceSerializer, AppointmentSerializer
from .models import Illness, Clinic, Service, Appointment, ServiceCategory
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, filters
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from .models import Specialization, Clinic, Illness
from .serializers import (
    SpecializationSerializer, ClinicSerializer, 
     IllnessSerializer
)

from django.contrib.auth import authenticate

from rest_framework.decorators import action

from .models import User


from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import generics, status
from requests.exceptions import RequestException



def vk_login(request):
    access_token = request.GET.get('access_token')

    if not access_token:
        return JsonResponse({'error': 'No access token'}, status=400)

    # Step 1: Get user info from VK
    response = requests.get('https://api.vk.com/method/users.get', params={
        'access_token': access_token,
        'v': '5.131',
        'fields': 'email',
    })

    data = response.json()
    if 'error' in data:
        return JsonResponse({'error': data['error']}, status=400)

    vk_user = data['response'][0]
    vk_id = vk_user['id']
    email = request.GET.get('email', f'{vk_id}@vk.com')  # Optional: fetch separately if needed

    # Step 2: Authenticate or create user
    user, created = User.objects.get_or_create(username=f'vk_{vk_id}', defaults={'email': email})
    # Optionally add login/session/token here

    return JsonResponse({'status': 'ok', 'user_id': user.id})

class VKLogin(SocialLoginView):
    adapter_class = VKOAuth2Adapter
    callback_url = 'https://b6fd-91-90-219-133.ngrok-free.app/auth/vk/callback/'
    client_class = OAuth2Client


# Add this endpoint to test the authentication flow
class VKAuthTest(APIView):
    def post(self, request, *args, **kwargs):
        access_token = request.data.get('access_token')
        
        if not access_token:
            return Response({"error": "Access token is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify token with VK
        vk_response = requests.get(
            'https://api.vk.com/method/users.get',
            params={
                'access_token': access_token,
                'v': '5.131',
                'fields': 'id,first_name,last_name,photo_200,email'
            }
        )
        
        try:
            vk_data = vk_response.json()
            if 'error' in vk_data:
                return Response({"error": vk_data['error']}, status=status.HTTP_400_BAD_REQUEST)
            
            user_info = vk_data['response'][0]
            
            # Here you would typically create or fetch the user
            # and generate your app's authentication token
            
            return Response({
                "success": True,
                "user_info": user_info,
                # "token": your_app_token
            })
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)




######################################################################################

# models.py for accounts app




class MedicalBranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Illness
        fields = ['id', 'name', 'description']

class IllnessDetailSerializer(serializers.ModelSerializer):
    doctors = UserSerializer(many=True, read_only=True)

    class Meta:
        model = Illness
        fields = ['id', 'name', 'description', 'doctors']

class MedicalBranchListView(generics.ListAPIView):
    queryset = Illness.objects.all()
    serializer_class = MedicalBranchSerializer
    


class IllnessDetailView(generics.RetrieveAPIView):
    queryset = Illness.objects.all()
    serializer_class = IllnessDetailSerializer
    lookup_field = 'id'

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return RegisterSerializer
        return UserSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return super().get_permissions()
    
    def get_queryset(self):
        # Ensure users can only see their own data
        if self.request.user.is_staff:
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)
    
    @action(detail=False, methods=['post'])
    def login(self, request):
        phone_number = request.data.get('phone_number')
        password = request.data.get('password')
        
        # Find user by phone number
        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Authenticate using username (phone number) and password
        user = authenticate(username=user.username, password=password)
        
        if user:
            # Create token
            from rest_framework.authtoken.models import Token
            token, created = Token.objects.get_or_create(user=user)
            
            return Response({
                'token': token.key,
                'user': UserSerializer(user).data
            })
        
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def logout(self, request):
        from rest_framework.authtoken.models import Token
        try:
            request.user.auth_token.delete()
        except:
            pass
        return Response(status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def toggle_biometric(self, request):
        user = request.user
        user.biometric_enabled = not user.biometric_enabled
        user.save()
        return Response({'biometric_enabled': user.biometric_enabled})


class ClinicViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Clinic.objects.all()
    serializer_class = ClinicSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['name']
    search_fields = ['name', 'address']

class ClinicsByDoctorViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ClinicSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['doctor']
    search_fields = ['name', 'address']
    
    def get_queryset(self):
        doctor_id = self.kwargs.get('doctor_id')
        return Clinic.objects.filter(doctors__id=doctor_id)


class ServiceCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ServiceCategory.objects.all()
    serializer_class = ServiceCategorySerializer

class ServiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category']
    search_fields = ['name', 'description']


class AppointmentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = ['status', 'notes']


from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q


class ClinicViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Clinic.objects.all()
    serializer_class = ClinicSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['name']
    search_fields = ['name', 'address']


  
    search_fields = ['first_name', 'last_name']

class ServiceCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ServiceCategory.objects.all()
    serializer_class = ServiceCategorySerializer

class ServiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category']
    search_fields = ['name', 'description']



from rest_framework.views import APIView
from rest_framework.response import Response

class RealTimeSyncView(APIView):
    def post(self, request):
        try:
            print('Starting data synchronization...')
            
            # Sync clinics first (doctors might depend on clinics)
            clinic_result = Clinic.sync_from_1c()
            print(f"Clinic sync result: {clinic_result}")
            
            # Then sync doctors
            doctor_result = User.sync_doctors_from_1c()
            print(f"Doctor sync result: {doctor_result}")
            
            return Response({
                "detail": "Successfully synchronized clinics and doctors",
                "clinics": clinic_result,
                "doctors": doctor_result
            })
        except Exception as e:
            print(f"Error in sync_data_task: {e}")

            return Response({"error": str(e)})
        
        



class ClinicViewSet(viewsets.ModelViewSet):
    queryset = Clinic.objects.all()
    serializer_class = ClinicSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'address', 'uuid']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


    
    @action(detail=True, methods=['get'])
    def doctors(self, request, pk=None):
        """Get all doctors working at this clinic"""
        clinic = self.get_object()
        doctors = clinic.doctors.filter(is_active=True).order_by('first_name')
        serializer = UserSerializer(doctors, many=True, context = {"context": self.request})
        return Response(serializer.data)



# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

router.register(r'clinics', views.ClinicViewSet)


urlpatterns = [
    path('api/', include(router.urls)),
]
