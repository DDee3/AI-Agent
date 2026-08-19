import os
from flask import Flask, render_template
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google import genai
from dotenv import load_dotenv

# Load local .env if it exists
load_dotenv()

# Initialize the Flask application
app = Flask(__name__)

# Define the required scope for reading Gmail
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Initialize Gemini Client using the environment variable
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ai_client = genai.Client(api_key=GEMINI_API_KEY)

def get_gmail_service():
    """Authenticate and connect to the Gmail API."""
    creds = None
    
    # Define the absolute directory path where your script lives
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    token_path = os.path.join(BASE_DIR, 'token.json')
    creds_path = os.path.join(BASE_DIR, 'credentials.json')
    
    # token.json stores the user's access and refresh tokens
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    # If there are no valid credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
            
    return build('gmail', 'v1', credentials=creds)

def analyze_email_with_gemini(sender, subject, body):
    """Analyze emails using Gemini AI."""
    prompt = f"""
    Please analyze the following email. If the sender or subject is related to "Testbird" (or TestBird Testing/Invitation), set the priority to "URGENT / HIGH PRIORITY".

    Format exactly like this:
    Priority: [Level]
    Summary: [Brief summary]
    Action: [What to do next]

    --- Email Details ---
    Sender: {sender}
    Subject: {subject}
    Body Snippet: {body}
    """
    
    response = ai_client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt,
    )
    return response.text

# Define what happens when a user visits the home page route ('/')
@app.route('/')
def index():
    service = get_gmail_service()
    
    # Fetch up to 3 unread emails
    results = service.users().messages().list(userId='me', q='is:unread', maxResults=3).execute()
    messages = results.get('messages', [])

    # List to store processed email data for the frontend
    email_data_list = [] 

    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
        headers = msg_data['payload']['headers']
        
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        snippet = msg_data.get('snippet', '')

        # Ask AI to analyze the email
        analysis = analyze_email_with_gemini(sender, subject, snippet)
        
        # Append the data to our list
        email_data_list.append({
            'sender': sender,
            'subject': subject,
            'analysis': analysis
        })

    # Render the HTML template and pass the email data to it
    return render_template('index.html', emails=email_data_list)

if __name__ == '__main__':
    # Run the Flask web server
    app.run(debug=True)