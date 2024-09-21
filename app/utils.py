from dotenv import load_dotenv
load_dotenv()

import os
import tempfile
from google.cloud import storage
import google.generativeai as genai

storage_client = storage.Client()
bucket_name = os.getenv('GOOGLE_CLOUD_STORAGE_BUCKET')
print(f"bucker name ENV: {bucket_name}")  


genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel("gemini-1.5-flash")

def classify_image(image_data: bytes) -> str:
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
            temp_file.write(image_data)
            temp_file_path = temp_file.name

        myfile = genai.upload_file(temp_file_path)
        result = model.generate_content(
            [myfile, "\n\n", "answer in 3 letters only - 'cat', 'dog' or 'non'"]
        )

        classification = result.text.strip().lower()
        os.unlink(temp_file_path)

        return 'non' if classification not in ['cat', 'dog', 'non'] else classification
    except Exception as e:
        print(f"Error in classification: {str(e)}")
        return 'non'

def upload_to_storage(batch_id, filename, image_data):
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f"{batch_id}/{filename}")
    blob.upload_from_string(image_data)
