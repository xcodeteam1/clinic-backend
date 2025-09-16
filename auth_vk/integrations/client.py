import logging
import zeep
from django.conf import settings
from zeep import Client
from zeep.transports import Transport
from requests import Session
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException
import xml.etree.ElementTree as ET


logger = logging.getLogger(__name__)

class OneCClient:
    def __init__(self):
        self.wsdl_url = 'http://62.245.57.52/med/ws/ws1.1cws?wsdl'
        self.username = 'backup'
        self.password = '123'
        self.client = self._create_client()
        self.timeout = 2  # seconds

    def _create_client(self):
        print('Connecting to 1C SOAP API')
        session = Session()
        session.auth = HTTPBasicAuth(self.username, self.password)
        transport = Transport(session=session)
        print('Creating SOAP client')
                
        return Client(wsdl=self.wsdl_url, transport=transport)

    def _handle_response(self, response):
        if not response.Результат:
            error_msg = response.ОписаниеОшибки or "Unknown error"
            raise Exception(f"1C Error: {error_msg}")
        return response

    def get_clinics_realtime(self):
        try:
            print('connetion to get list clinic')
            response = self.client.service.GetListClinic()

            return self._parse_clinics(response)
        except Exception as e:
            logger.error(f"1C Clinic fetch failed: {str(e)}")
            raise

    def get_doctors_realtime(self):
        try:
            response = self.client.service.GetListEmployees()
            
            return self._parse_doctors(response)
        except Exception as e:
            logger.error(f"1C Doctors fetch failed: {str(e)}")
            raise

    def create_appointment_realtime(self, data):
        try:
            response = self.client.service.BookAnAppointment(
                **data,
                _soapheaders={'Timeout': self.timeout}
            )
            return self._handle_response(response)
        except RequestException as e:
            logger.error(f"1C Appointment creation failed: {str(e)}")
            raise


    def _parse_clinics(self, raw_data):
        

        root = ET.fromstring(raw_data)
        clinics = []
     
        for clinic in root.findall('{S1}Клиника'):
            try:

                name = clinic.find('{S1}Наименование').text
                print(name)
                uid = clinic.find('{S1}УИД').text
                print(uid)
                photo = clinic.find("{S1}Фото").text

                with open("tessst.txt", 'a+') as f:
                    f.write(photo)
                    f.write('\n\n\n\n\n\n Helllo \n\n\n\n\n\n')


                clinics.append({
                    'uuid': uid,
                    'name': name,
                    'photo': photo

                })
            except Exception as e:
                print("Error here for photo detect", e)

        return clinics

    def _parse_doctors(self, raw_data):
        doctors = []
        root = ET.fromstring(raw_data)

        ns = {'ns': 'S2'}  # Namespace dictionary

        for doctor in root.findall('.//ns:Сотрудник', ns):
            uid = doctor.find('ns:UID', ns)
            first_name = doctor.find('ns:Имя', ns)
            last_name = doctor.find('ns:Фамилия', ns)
            middle_name = doctor.find('ns:Отчество', ns)
            specialization = doctor.find('ns:Специализация', ns)
            photo = doctor.find('ns:Фото', ns)
            clinic = doctor.find("ns:Организация", ns)

            photo_specialization = doctor.find("ns:ФотоСпециализации", ns)

            print(photo_specialization, 'specialization--- photo')


            
            # description = doctor.find('ns:КраткоеОписание', ns)
            # rating = doctor.find('ns:СреднийРейтинг', ns)
            # appointment_duration = doctor.find('ns:ДлительностьПриема', ns)

            if uid is None or not uid.text:
                continue

            doctors.append({
                'external_id': uid.text.strip(),
                'first_name': first_name.text.strip() if first_name is not None and first_name.text else "",
                'last_name': last_name.text.strip() if last_name is not None and last_name.text else "",
                'middle_name': middle_name.text.strip() if middle_name is not None and middle_name.text else "",
                'specialization': specialization.text.strip() if specialization is not None and specialization.text else "",
                'photo': photo.text.strip() if photo is not None and photo.text else None,
                "clinics": clinic.text.strip().strip()  if clinic is not None and clinic.text else "",
                "photo_specialization": photo_specialization.text.strip() if photo_specialization is not None and photo_specialization.text else ""
                # 'description': description.text.strip() if description is not None and description.text else "",
                # 'rating': float(rating.text.strip()) if rating is not None and rating.text else None,
                # 'appointment_duration': int(appointment_duration.text.strip()) if appointment_duration is not None and appointment_duration.text else None,
            })

        return doctors


