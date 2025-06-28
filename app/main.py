import os
import requests
import urllib.parse
from pydantic import BaseModel
from fake_useragent import UserAgent
from fastapi import FastAPI, HTTPException
from bs4 import BeautifulSoup
import tenacity
import logging

app = FastAPI(title="TempEmailAPI", description="API for generating temporary Gmail addresses and retrieving messages via Emailnator")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ua = UserAgent()

user_agents = [
    # Chrome - Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',

    # Chrome - macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 12_6_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',

    # Chrome - Android
    'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 12; Samsung Galaxy S21) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36',

    # Firefox - Windows/macOS/Linux
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0',

    # Safari - macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 12_6_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 11_7_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6 Safari/605.1.15',

    # Safari - iPhone
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',

    # Edge - Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.2792.90',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.2762.67',

    # Edge - macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 12_6_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.2762.67',

    # Opera - Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 OPR/114.0.0.0',

    # Opera - macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 12_6_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 OPR/113.0.0.0',

    # Samsung Internet - Android
    'Mozilla/5.0 (Linux; Android 13; SAMSUNG SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/21.0 Chrome/129.0.0.0 Mobile Safari/537.36',

    # UC Browser - Android
    'Mozilla/5.0 (Linux; U; Android 12; en-US; Redmi Note 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36 UCBrowser/13.5.0.1306',

    # Brave - Windows (appears like Chrome, but optionally detectable)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',

    # Vivaldi - Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Vivaldi/6.4.3160.49'
]

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
    'user-agent': random.choice(user_agents),
    'x-requested-with': 'XMLHttpRequest',
}

class MessageRequest(BaseModel):
    email: str

class MessageDetailsRequest(BaseModel):
    email: str
    message_id: str

@tenacity.retry(
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
    before_sleep=tenacity.before_sleep_logging(logger, logging.INFO),
    retry=tenacity.retry_if_exception_type((requests.RequestException, HTTPException)),
    after=tenacity.after_log(logger, logging.WARNING)
)
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
            
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract fields from subject-header div
            subject_header = soup.find('div', id='subject-header')
            if subject_header:
                from_value = subject_header.find('b', string='From: ').next_sibling.strip() if subject_header.find('b', string='From: ') else 'Unknown'
                subject = subject_header.find('b', string='Subject: ').next_sibling.strip() if subject_header.find('b', string='Subject: ') else 'No Subject'
                time_value = subject_header.find('b', string='Time: ').next_sibling.strip() if subject_header.find('b', string='Time: ') else 'Unknown Time'
            else:
                from_value = 'Unknown'
                subject = 'No Subject'
                time_value = 'Unknown Time'
            
            # Raw content is the full response text
            raw_content = response.text
            
            # Refine content by removing scripts, styles, and normalizing whitespace
            for script in soup(["script", "style"]):
                script.decompose()
            refined_content = ' '.join(soup.get_text().split())
            
            return {
                "id": request.message_id,
                "from": from_value,
                "subject": subject,
                "time": time_value,
                "refined_content": refined_content
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing message details: {str(e)}")
    raise HTTPException(status_code=response.status_code, detail="Failed to fetch message details")
