from zeep import Client
from zeep.transports import Transport
from requests import Session
from requests.auth import HTTPBasicAuth
from pprint import pprint

# Authentication
username = 'web'
password = 'web'

# Set up session
session = Session()
session.auth = HTTPBasicAuth(username, password)
transport = Transport(session=session)
print('working')
# Load WSDL
wsdl = 'http://62.245.57.52/med/ws/ws1.1cws?wsdl'
client = Client(wsdl=wsdl, transport=transport)

# # Print available operations
# print("Available operations:")
# for service in client.wsdl.services.values():
#     print(f"Service: {service.name}")
#     for port in service.ports.values():
#         print(f" Port: {port.name}")
#         for operation in port.binding._operations.values():
#             print(f"  Operation: {operation.name}")


def get_zayavki_client():
    zayavki = client.service.GetZayavkiClient("998978516060")
    print(zayavki)

get_zayavki_client()

def get_employees():
    try:
        # Get list of employees
        print('get list employee')
        employees = client.service.GetListEmployees()
       
        with open("test.docx", "w") as f:
            f.write(str(employees))
        
        # Print raw response structure first to understand it
        print("\nRaw employee response structure:")
      
        
        # Process employees (assuming it returns Сотрудники structure)
        if hasattr(employees, 'Сотрудник'):
            print("\nEmployee Details:")
            for employee in employees.Сотрудник:
                print(f"\nUID: {employee.UID}")
                print(f"Name: {employee.Наименование}")
                print(f"Full Name: {employee.Фамилия} {employee.Имя} {employee.Отчество}")
                print(f"Specialization: {employee.Специализация}")
                print(f"Organization: {employee.Организация}")
                # print(f"Photo: {'Exists' if employee.Фото else 'None'}")
                # print(f"Rating: {employee.СреднийРейтинг}")
                # print(f"Description: {employee.КраткоеОписание}")
                
                # # Print services if available
                # if hasattr(employee, 'ОсновныеУслуги'):
                #     print("Services:")
                #     for service in employee.ОсновныеУслуги.ОсновнаяУслуга:
                #         print(f" - {service.UID} (Duration: {service.Продолжительность})")
                
                # print(f"Appointment Duration: {employee.ДлительностьПриема}")
                
        return employees
    except Exception as e:
        print(f"Error getting employees: {e}")
        return None

# Call the function
# print('before employee')
# employees_data = get_employees()
# print(employees_data, 'employees data')


def get_clinics():
    try:
        clinics = client.service.GetListClinic()
        
        print("\nRaw clinic response structure:")
        pprint(clinics)
        
        if hasattr(clinics, 'Клиника'):
            print("\nClinic Details:")
            for clinic in clinics.Клиника:
                print(f"\nUID: {clinic.UID}")
                print(f"Name: {clinic.Наименование}")
                print(f"Description: {clinic.Описание}")
                print(f"Phone: {clinic.Телефон}")
                print(f"Email: {clinic.Email}")
                print(f"Website: {clinic.Сайт}")
                print(f"Photo: {'Exists' if clinic.Фото else 'None'}")
                print(f"Coordinates: {clinic.Широта}, {clinic.Долгота}")
                
                # Print employees if available
                if hasattr(clinic, 'Сотрудники'):
                    print("Employee UIDs:")
                    for emp in clinic.Сотрудники:
                        print(f" - {emp.UID}")
                
        return clinics
    except Exception as e:
        print(f"Error getting clinics: {e}")
        return None

# clinics_data = get_clinics()
# print(clinics_data, 'clinics_data')
# import xml.etree.ElementTree as ET
# from datetime import datetime, timedelta

# def get_schedule(days=7):
#     try:
#         start_date = datetime.now()
#         end_date = start_date + timedelta(days=days)
        
#         schedule = client.service.GetSchedule(
#             StartDate=start_date,
#             FinishDate=end_date
#         )
        
#         print("\nSchedule Data:")
#         if hasattr(schedule, 'ГрафикДляСайта'):
#             for doctor_schedule in schedule.ГрафикДляСайта:
#                 print(f"\nDoctor: {doctor_schedule.СотрудникФИО} (ID: {doctor_schedule.СотрудникID})")
#                 print(f"Clinic: {doctor_schedule.Клиника}")
#                 print(f"Specialization: {doctor_schedule.Специализация}")
#                 print(f"Appointment Duration: {doctor_schedule.ДлительностьПриема}")
                
#                 # Print free time slots
#                 if hasattr(doctor_schedule.ПериодыГрафика, 'СвободноеВремя'):
#                     print("Free Time Slots:")
#                     for slot in doctor_schedule.ПериодыГрафика.СвободноеВремя.ПериодГрафика:
#                         print(f" - {slot.ВремяНачала} to {slot.ВремяОкончания}")
                
#                 # Print busy time slots
#                 if hasattr(doctor_schedule.ПериодыГрафика, 'ЗанятоеВремя'):
#                     print("Busy Time Slots:")
#                     for slot in doctor_schedule.ПериодыГрафика.ЗанятоеВремя.ПериодГрафика:
#                         print(f" - {slot.ВремяНачала} to {slot.ВремяОкончания}")
        
#         return schedule
#     except Exception as e:
#         print(f"Error getting schedule: {e}")
#         return None

# schedule_data = get_schedule()
# # print(schedule_data)


# def get_list_reception(employee_id, client_phone_number='79655059619'):
#     if employee_id and client_phone_number:
       
#             # Add parameters as needed based on the WSDL
        
#         services = client.service.GetListReception(
#             EmployeeID='614db726-21bc-11f0-a08e-047c1674176e',
#             Phone='79655059619',
#             # Params=params
#         )
#         print(services)

#         if hasattr(services, 'Визиты'):
#             for service in services.Визиты:
#                 print('service', service)


# services = get_list_reception("614db726-21bc-11f0-a08e-047c1674176e")   


# def get_services(clinic_uid=None):
#     try:
#         # Create params structure if needed
#         params = None
#         if clinic_uid:
#             factory = client.type_factory('ns2')
#             params = factory.Structure()
#             # Add parameters as needed based on the WSDL
        
#         services = client.service.GetNomenclatureAndPrices(
#             Clinic=clinic_uid if clinic_uid else "",
#             Params=params
#         )
        
#         print("\nServices Data:")
#         if hasattr(services, 'Каталог'):
#             for service in services.Каталог:
#                 print(f"\nUID: {service.UID}")
#                 print(f"Name: {service.Наименование}")
#                 print(f"Article: {service.Артикул}")
#                 print(f"Price: {service.Цена}")
#                 print(f"Duration: {service.Продолжительность}")
#                 print(f"Type: {service.Вид}")
#                 print(f"Parent: {service.Родитель}")
#                 print(f"Is Folder: {service.ЭтоПапка}")
        
#         return services
#     except Exception as e:
#         print(f"Error getting services: {e}")
#         return None

# services_data = get_services()
# # print(services_data)

# def book_appointment(employee_id, patient_info, time_slot, clinic_uid):
#     try:
#         appointment_result = client.service.BookAnAppointment(
#             EmployeeID=employee_id,
#             PatientSurname=patient_info['surname'],
#             PatientName=patient_info['name'],
#             PatientFatherName=patient_info['father_name'],
#             Date=time_slot['date'],
#             TimeBegin=time_slot['start_time'],
#             Comment=patient_info.get('comment', ''),
#             Phone=patient_info['phone'],
#             Email=patient_info.get('email', ''),
#             Address=patient_info.get('address', ''),
#             Clinic=clinic_uid,
#             GUID=patient_info.get('guid', '')  # Generate a unique GUID if needed
#         )
        
#         print("\nAppointment Result:")
#         pprint(appointment_result)
        
#         if appointment_result.Результат:
#             print(f"Success! Appointment UID: {appointment_result.УИД}")
#         else:
#             print(f"Error: {appointment_result.ОписаниеОшибки}")
        
#         return appointment_result
#     except Exception as e:
#         print(f"Error booking appointment: {e}")
#         return None


# # Example usage:
# # patient_info = {
# #     'surname': 'Ivanov',
# #     'name': 'Ivan',
# #     'father_name': 'Ivanovich',
# #     'phone': '+79123456789',
# #     'email': 'ivanov@example.com'
# # }
# # time_slot = {
# #     'date': datetime.now().date(),
# #     'start_time': datetime.now().time()
# # }
# # book_appointment("EMPLOYEE_UID", patient_info, time_slot, "CLINIC_UID")
# def _parse_doctors(self, raw_data):
#         doctors = []
#         root = ET.fromstring(raw_data)

#         ns = {'ns': 'S2'}  # Namespace dictionary

#         for doctor in root.findall('.//ns:Сотрудник', ns):
#             uid = doctor.find('ns:UID', ns)
#             first_name = doctor.find('ns:Имя', ns)
#             last_name = doctor.find('ns:Фамилия', ns)
#             middle_name = doctor.find('ns:Отчество', ns)
#             specialization = doctor.find('ns:Специализация', ns)
#             photo = doctor.find('ns:Фото', ns)
#             clinic = doctor.find("ns:Организация", ns)
#             print('clinic here:', clinic)
#             # description = doctor.find('ns:КраткоеОписание', ns)
#             # rating = doctor.find('ns:СреднийРейтинг', ns)
#             # appointment_duration = doctor.find('ns:ДлительностьПриема', ns)

#             if uid is None or not uid.text:
#                 continue

#             doctors.append({
#                 'external_id': uid.text.strip(),
#                 'first_name': first_name.text.strip() if first_name is not None and first_name.text else "",
#                 'last_name': last_name.text.strip() if last_name is not None and last_name.text else "",
#                 'middle_name': middle_name.text.strip() if middle_name is not None and middle_name.text else "",
#                 'specialization': specialization.text.strip() if specialization is not None and specialization.text else "",
#                 'photo': photo.text.strip() if photo is not None and photo.text else None,
#                 "clinics": clinic.text.strip().strip()  if clinic is not None and clinic.text else ""


# import uuid
# from datetime import datetime
# from pprint import pprint

# def get_recention_list():
#     response = client.service.GetListReception(
#         EmployeeID="9a5ec22d-20e5-11f0-a08e-047c1674176e",
#         Phone="79655059619"
                                               
#                                                )
#     print("reception LIST: ",response)

# def get_reception_info():
#     response = client.service.GetReceptionInfo(GUID="c2c9072b-3ccc-4a0f-8834-f91794a4781f1")
#     print("reception INFO: ",response)

# def get_zayavki_doktora(employee_id):
#     response = client.service.GetZayavkiDoctora()
#     print("zayavka Doktora: ",response)

# def get_employees_by_client_phone():
#     response = client.service.GetListEmployeesClient(
#         Phone="78943993343")
#     print("emploees client: ",response)


# get_employees_by_client_phone()
# get_reception_info()




# def get_reserve(employee_id, clini_id, date_reserve, time_to_begin):
#     appointment_datetime = datetime.combine(date_reserve, time_to_begin)
#     print(appointment_datetime, 'appintment time')
#     result = client.service.GetReserve(
#         Specialization="Неврология",
#         Date=appointment_datetime,
#         TimeBegin=appointment_datetime,
#         EmployeeID=employee_id,
#         Clinic=clini_id

#     )
#     print(result, 'resultt')
#     root = ET.fromstring(result)

#     ns = {'ns': 'S2'}  # Namespace dictionary
#     data = root.find(".//ns:ОтветНаЗаписьССайта")
#     guid = data.find('ns:УИД', ns)


#         employee_id (str): UID of the doctor/employee.
#         clinic_uid (str): UID of the clinic.
#         patient_info (dict): Patient details including name, surname, etc.
#         appointment_date (datetime.date): Date of the appointment.
#         appointment_time (datetime.time): Start time of the appointment.

#     Returns:
#         Response from the SOAP service (dict or object), or None on error.
#     """
#     try:
     

#         # Combine date and time into a full datetime object
#         appointment_datetime = datetime.combine(appointment_date, appointment_time)
#         print(f"Appointment DateTime: {appointment_datetime}")
#         print(appointment_datetime.isoformat(), 'iso format')
        
#         response = client.service.BookAnAppointment(
#             EmployeeID=employee_id,
#             PatientSurname=patient_info['surname'],
#             PatientName=patient_info['name'],
#             PatientFatherName=patient_info['father_name'],
#             Date=appointment_datetime,
#             TimeBegin=appointment_datetime,
#             Comment=patient_info.get('comment', ''),
#             Phone=str(patient_info['phone']),
#             Email=patient_info.get('email', ''),
#             Address=patient_info.get('address', ''),
#             Clinic=clinic_uid,
#             GUID=guid_for_appointment
#         )

#         print("\n📅 Appointment Booking Result:")
#         pprint(response)

#         if hasattr(response, 'Результат') and response.Результат:
#             print(f"✅ Success! Appointment UID: {response.УИД}")
#             return response
#         else:
#             error_desc = getattr(response, 'ОписаниеОшибки', 'Unknown error')
#             print(f"❌ Failed to book appointment: {error_desc}")
#             return response
        
#     except Exception as e:
#         print(f"❗ Error during appointment booking: {e}")
#         return None

# import json


# from zeep import Client
# from zeep.helpers import serialize_object

# def get_doctor_spare_times(start_date: datetime, finish_date: datetime, clinic_id: str, employee_ids: list):
#     # Prepare the Params structure
#     params = {
#         'Property': [
#             {
#                 'name': 'Clinic',
#                 'Value': clinic_id
#             },
#             {
#                 'name': 'Employees',
#                 'Value': ';'.join(employee_ids)
#             },
#             {
#                 'name': 'Format',
#                 'Value': 'JSON'  # Or 'ZipJSON'/'ZipXML' depending on server support
#             }
#         ]
#     }

#     try:
#         response = client.service.GetSchedule20(
#             StartDate=start_date.isoformat(),
#             FinishDate=finish_date.isoformat(),
#             Params=params
#         )
#         print(response, 'response')

#         # Deserialize and parse JSON if format is JSON
#         import json
#         if isinstance(response, str):
#             data = json.loads(response)
#         else:
#             data = serialize_object(response)

#         # Extract free times
#         spare_times = []
#         for schedule in data.get("ГрафикиДляСайта", []):
#             employee_id = schedule.get("СотрудникID")
#             free_periods = schedule.get("ПериодыГрафика", {}).get("СвободноеВремя", [])
#             for period in free_periods:
#                 spare_times.append({
#                     "employee_id": employee_id,
#                     "clinic_id": period.get("Клиника"),
#                     "date": period.get("Дата"),
#                     "start": period.get("ВремяНачала"),
#                     "end": period.get("ВремяОкончания")
#                 })

#         return spare_times

#     except Exception as e:
#         print(f"Error fetching schedule: {e}")
#         return []
    
# clinic_id = "f12ae8ed-20f0-11f0-a08e-047c1674176e"  # example clinic UUID
# employee_ids = [
#     "03104d15-20e5-11f0-a08e-047c1674176e",
#     "033ba940-2402-11f0-a08e-047c1674176e"
# ]
# start = datetime(2025, 6, 16)
# end = datetime(2025, 6, 16, 23, 59)
# print(";asldfjjjjjjjjjjjjjjjjjjjjjjjjjjjjjj\nsladkfjasldfkj\nasdlfjk")
# spare_times = get_doctor_spare_times(start, end, clinic_id, employee_ids)
# for time in spare_times:
#     print(time)



# employee_id = "03104d15-20e5-11f0-a08e-047c1674176e"
# clinic_uid = "f6b5b37d-20c6-11f0-a08e-047c1674176e"

# patient_info = {
#     'surname': 'TEST',
#     'name': 'TEST',
#     'father_name': 'TEST',
#     'phone': '1234567',  # Changed to string format
#     'email': 'test@example.com',
#     'address': 'Test',
#     'comment': 'TEST TEST TEST'
# }
# from datetime import date, time

# appointment_date = datetime(2025, 8, 23).date()
# appointment_time = time(14, 0)



# guid_for_appointment = get_reserve(employee_id=employee_id, clini_id=clinic_uid, date_reserve=appointment_date, time_to_begin=appointment_time)
# print(guid_for_appointment)
# response_of_appointment = make_appointment(employee_id, clinic_uid, patient_info, appointment_date, appointment_time, guid_for_appointment)
# print(response_of_appointment, 'response_of_appointment')  # Fixed typo in variable name
# print(client.service.BookAnAppointment.__doc__, 'client.service.BookAnAppointment.__doc__')


# from zeep import Client
# from zeep.helpers import serialize_object
# from lxml import etree

# # Prepare your client as usual
# wsdl = 'http://62.245.57.52/med/ws/ws1.1cws?wsdl'
# client = Client(wsdl=wsdl, transport=transport)

# # Create the appointment datetime
# from datetime import datetime, time, date

# appointment_datetime = datetime.combine(
#     date(2025, 5, 23),
#     time(10, 0)
# )

# # Prepare patient info
# patient_info = {
#     'surname': 'TEST',
#     'name': 'TEST',
#     'father_name': 'TEST',
#     'phone': '1234567',
#     'email': 'test@example.com',
#     'address': 'Test',
#     'comment': 'TEST TEST TEST'
# }

# guid = str(uuid.uuid4())

# # Create SOAP message without sending
# soap_message = client.create_message(
#     client.service,
#     'BookAnAppointment',
#     EmployeeID="5f4497db-2404-11f0-a08e-047c1674176e",
#     PatientSurname=patient_info['surname'],
#     PatientName=patient_info['name'],
#     PatientFatherName=patient_info['father_name'],
#     Date=appointment_datetime.isoformat(),
#     TimeBegin=appointment_datetime.isoformat(),
#     Comment=patient_info.get('comment', ''),
#     Phone=str(patient_info['phone']),
#     Email=patient_info.get('email', ''),
#     Address=patient_info.get('address', ''),
#     Clinic="4f9c225f-2e29-11ec-80e5-001e67144a64",
#     GUID=guid
# )

# # Print the XML
# print("\n📤 XML Request to 1C:")
# print(etree.tostring(soap_message, pretty_print=True).decode())
# get_employees()
# response = client.service.GetListEmployeesClient(Phone="89089216243")

# with open("test1.docx", "w") as f:
#         f.write(str(response))



