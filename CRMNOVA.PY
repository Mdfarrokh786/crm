
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime
import re

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def authenticate_google_drive():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def create_output_directory(base_url):
    parsed_url = urlparse(base_url)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    folder_name = sanitize_filename(f"{parsed_url.netloc}_{timestamp}")
    os.makedirs(folder_name, exist_ok=True)
    return folder_name

def download_image(url, folder):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        filename = sanitize_filename(os.path.basename(urlparse(url).path) or "image.jpg")
        path = os.path.join(folder, filename)
        with open(path, 'wb') as f:
            f.write(response.content)
        print(f"[+] Downloaded: {filename}")
    except Exception as e:
        print(f"[!] Failed to download {url}: {e}")

def scrape_assets(url, folder):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        img_tags = soup.find_all('img')
        print(f"[+] Found {len(img_tags)} images. Starting download...")
        for img in img_tags:
            src = img.get('src')
            if src:
                full_url = urljoin(url, src)
                download_image(full_url, folder)

        for link in soup.find_all('a', href=True):
            if link['href'].endswith('.pdf'):
                pdf_url = urljoin(url, link['href'])
                filename = os.path.basename(pdf_url)
                path = os.path.join(folder, filename)
                r = requests.get(pdf_url, stream=True)
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
                print(f"[+] Downloaded PDF: {filename}")

        return folder
    except Exception as e:
        print(f"[!] Error scraping assets: {e}")
        return None

def upload_folder_to_drive(folder_path, drive_service):
    folder_metadata = {
        'name': os.path.basename(folder_path),
        'mimeType': 'application/vnd.google-apps.folder'
    }
    folder = drive_service.files().create(body=folder_metadata, fields='id').execute()
    folder_id = folder.get('id')
    print(f"[✓] Created Drive folder: {folder_path}")

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        file_metadata = {'name': filename, 'parents': [folder_id]}
        media = MediaFileUpload(file_path, resumable=True)
        drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"[✓] Uploaded: {filename}")

if __name__ == "__main__":
    business_url = input("Enter the business website URL (with https://): ").strip()
    local_folder = create_output_directory(business_url)
    downloaded_folder = scrape_assets(business_url, local_folder)
    if downloaded_folder:
        service = authenticate_google_drive()
        upload_folder_to_drive(downloaded_folder, service)
