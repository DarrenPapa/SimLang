import os
import requests

# Base URL for the package manager
base_url = "https://chasedevelopmentgroup.pythonanywhere.com"

def get(version, name):
    search_url = f"{base_url}/packages/{version}/{name}"
    response = requests.get(search_url)
    return response.json()

def upload(version, name, content, data=None):
    md = {
        "file":content,
        "metadata":data or {}
    }
    requests.post(f"{base_url}/packages/{version}/{name}",data=metadata)

def print_response(data):
    if "error" in data:
        print("Error:",data['error'])
    if "message" in data:
        print("Message:",data['message'])

