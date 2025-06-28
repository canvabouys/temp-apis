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
