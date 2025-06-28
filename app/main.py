import os
import requests
import urllib.parse
from pydantic import BaseModel
from fake_useragent import UserAgent
from fastapi import FastAPI, HTTPException
from bs4 import BeautifulSoup

app = FastAPI(title="TempEmailAPI", description="API for generating temporary Gmail addresses and retrieving messages via Emailnator")

ua = UserAgent()

# Headers matching csrf_test.py for Emailnator requests
headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en-US,en;q=0.5',
    'cache-control': 'no-cache',
    'content-type': 'application/json',
    'origin': 'https://www.emailnator.com',
    'pragma': 'no-cache',
    'priority': 'u=1, i',
    'referer': 'https://www.emailnator.com/',
    'sec-ch-ua': '"Brave";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
    'sec-ch-ua-arch': '"x86"',
    'sec-ch-ua-bitness': '"64"',
    'sec-ch-ua-full-version-list': '"Brave";v="137.0.0.0", "Chromium";v="137.0.0.0", "Not/A)Brand";v="24.0.0.0"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-model': '""',
    'sec-ch-ua-platform': '"Windows"',
    'sec-ch-ua-platform-version': '"19.0.0"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'sec-gpc': '1',
    'user-agent': ua.random,
    'x-requested-with': 'XMLHttpRequest',
}

class MessageRequest(BaseModel):
    email: str

class MessageDetailsRequest(BaseModel):
    email: str
    message_id: str

def get_cookies_csrf():
    session = requests.Session()
    session.headers.update(headers)
    response = session.get('https://www.emailnator.com/')
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch CSRF token")
    
    csrf_token = None
    for cookie in session.cookies:
        if cookie.name == 'XSRF-TOKEN':
            csrf_token = cookie.value
    if not csrf_token:
        raise HTTPException(status_code=500, detail="CSRF token not found")
    
    return session, csrf_token

@app.post("/generate-email", summary="Generate a temporary Gmail address")
async def generate_email():
    session, csrf_token = get_cookies_csrf()
    decoded_token = urllib.parse.unquote(csrf_token)
    session.headers['X-XSRF-TOKEN'] = decoded_token
    
    # Hardcode "dotGmail" internally
    response = session.post('https://www.emailnator.com/generate-email', json={"email": ["dotGmail"]})
    if response.status_code == 200:
        try:
            email_data = response.json()
            email = email_data.get("email", [None])[0]
            if email:
                return {"email": email}
            raise HTTPException(status_code=500, detail="Failed to generate email")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error parsing email: {str(e)}")
    raise HTTPException(status_code=response.status_code, detail="Failed to generate email")

@app.post("/message-list", summary="Retrieve message list for an email")
async def get_message_list(request: MessageRequest):
    session, csrf_token = get_cookies_csrf()
    decoded_token = urllib.parse.unquote(csrf_token)
    session.headers['X-XSRF-TOKEN'] = decoded_token
    
    response = session.post('https://www.emailnator.com/message-list', json={"email": request.email})
    if response.status_code == 200:
        try:
            data = response.json()
            messages = data.get('messageData', []) if isinstance(data, dict) else data
            return {"messages": messages}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error parsing message list: {str(e)}")
    raise HTTPException(status_code=response.status_code, detail="Failed to fetch message list")

@app.post("/message-details", summary="Retrieve detailed information for a specific message")
async def get_message_details(request: MessageDetailsRequest):
    session, csrf_token = get_cookies_csrf()
    decoded_token = urllib.parse.unquote(csrf_token)
    session.headers['X-XSRF-TOKEN'] = decoded_token
    
    response = session.post('https://www.emailnator.com/message-list', json={"email": request.email, "messageID": request.message_id})
    print("Raw response text:", response.text)  # Debug log
    print("\nStatus (message details):", response.status_code)
    
    if response.status_code == 200:
        try:
            if not response.text.strip():  # Check if response is empty
                raise HTTPException(status_code=404, detail="No message details available")
            
            # Attempt to parse JSON response
            data = response.json()
            message_data = data.get('messageData', [{}])[0] if isinstance(data, dict) and 'messageData' in data else {}
            
            # Extract fields from JSON (adjust keys based on actual response)
            message_id = request.message_id
            from_value = message_data.get('from', 'Unknown')
            subject = message_data.get('subject', 'No Subject')
            time_value = message_data.get('time', 'Unknown Time')
            raw_content = response.text  # Raw response text
            
            # Refine content using BeautifulSoup
            soup = BeautifulSoup(raw_content, 'html.parser')
            for script in soup(["script", "style"]):
                script.decompose()
            refined_content = ' '.join(soup.get_text().split())
            
            return {
                "message_id": message_id,
                "from": from_value,
                "subject": subject,
                "time": time_value,
                "refined_content": refined_content,
                "raw_content": raw_content
            }
        except ValueError:  # Handle non-JSON response
            raise HTTPException(status_code=500, detail="Invalid response format from Emailnator")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing message details: {str(e)}")
    raise HTTPException(status_code=response.status_code, detail="Failed to fetch message details")
