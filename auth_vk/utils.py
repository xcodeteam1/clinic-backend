import base64
import uuid
from django.core.files.base import ContentFile

def save_base64_image(base64_str, filename_prefix='avatar'):
    """
    Converts base64 image to Django File object and returns it.
    """
    try:
        
        
        # If the base64 includes a header like "data:image/jpeg;base64,...", remove it
        if "base64," in base64_str:
            base64_str = base64_str.split("base64,")[1]
        
        decoded_img = base64.b64decode(base64_str)
        file_name = f"{filename_prefix}_{uuid.uuid4().hex[:8]}.jpg"
        
        return ContentFile(decoded_img, name=file_name)
    except Exception as e:
        with open("file_test.txt", "a+") as f:
            f.write(base64_str)
          

        print(f"Failed to convert base64 image: {e}")
        return None
