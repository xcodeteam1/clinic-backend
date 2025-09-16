# from zeep import Client
# from zeep.wsse.username import UsernameToken

# # Create the client with WSDL
# client = Client('http://62.245.57.52/med/ws/ws1.1cws&wsdl')

# # Add username to the SOAP header (without password)
# header = {
#     'Username': 'глб'  # Replace with actual username
# }

# # Make the request with custom header
# clinics = client.service.GetListClinic(_soapheaders=[header])
# print(clinics)



# from zeep import Client
# from requests import Session
# from requests_ntlm import HttpNtlmAuth
# from zeep.transports import Transport

# username = 'глб'
# password = '' 

# session = Session()
# session.auth = HttpNtlmAuth(username, password)

# wsdl_url = 'http://62.245.57.52/med/ws/ws1.1cws?wsdl'
# client = Client(wsdl=wsdl_url, transport=Transport(session=session))

# print(client.service._operations)
