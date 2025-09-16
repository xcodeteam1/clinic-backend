import requests

# Your variables extracted from the URL
code = "vk2.a.F0LO8d-zP6zNVoB1RlcEJGtjqO6_ev5xKv8cgu7BtYMsleDi941iAM8hq6b65IhjZlEQWEj6VCcep7y8DJbyXrfrdYj9BZqmYmglr6Z6TZ2y7qleQdIQ1wHiPmxq2tvIqA5JqSka23x7HwAPjikj-ZJ5J1dXTgBAoBJq59g1ikd1bV2UL66Cv-xJc39tQSQKz87vJcE563PJC1X3cWkCCTaDCNCRrwEKz2v2T2_QMPA"
device_id = "Fp824huM_fV13NsIl45YUiGKuB4iLqkcjFtamDDv4Esag8QCUQwoaky1bcHfjWx7OloAZDoYrYl4ONaFyVGxYQ"
redirect_uri = "vk53521481://vk.com/blank.html"
code_verifier = "5o8DeZeBWISP6WL2dKegiUwqYLAvsjv3DsqQdDapkVxDExOR_Lcx6Yedufezp8k13d3fMG-yiLz_GqG0siLAoA"

# API endpoint
url = "https://id.vk.com/oauth2/auth"

# Prepare the data to exchange the authorization code
data = {
    "grant_type": "authorization_code",
    "client_id": "53521481",  # Your VK app client ID
    "redirect_uri": redirect_uri,
    "code": code,
    "code_verifier": code_verifier,
    "device_id": device_id
}

# Send the POST request to exchange the code for an access token
response = requests.post(url, data=data)

# Check the response
print(response.status_code, 'Response:')
print(response.json())  # Print the JSON response
