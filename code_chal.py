import hashlib
import base64
import secrets
import string
import urllib.parse

# Generate a secure random string for code_verifier
def generate_code_verifier(length=64):
    # Use secrets module for cryptographically strong random values
    return secrets.token_urlsafe(length)

# Generate code_challenge from code_verifier using SHA-256
def generate_code_challenge(code_verifier):
    sha256_hash = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    # Base64 URL encode and remove padding
    code_challenge = base64.urlsafe_b64encode(sha256_hash).decode('utf-8').rstrip("=")
    return code_challenge

# Generate PKCE parameters
code_verifier = generate_code_verifier()
code_challenge = generate_code_challenge(code_verifier)

print(f"code_verifier: {code_verifier}")
print(f"code_challenge: {code_challenge}")

client_id = "53532182"
redirect_uri = f"vk{client_id}://vk.com/blank.html"
# Make sure to URL-encode the redirect URI
encoded_redirect_uri = urllib.parse.quote(redirect_uri, safe='')
state = secrets.token_urlsafe(16)  # Use a cryptographically secure random string
scope = "email"

auth_url = f"https://id.vk.com/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={scope}&state={state}&code_challenge={code_challenge}&code_challenge_method=S256"

print(auth_url)