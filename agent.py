from langchain_openai import ChatOpenAI
from browser_use import Agent, BrowserConfig, Browser
from browser_use.browser.context import BrowserContextConfig
from playwright.async_api import BrowserContext
from dotenv import load_dotenv
from browser_use.controller.service import Controller
from client import AgentMail
from typing import Optional, List
from fastapi import FastAPI, WebSocket

from fastapi.middleware.cors import CORSMiddleware
import os




load_dotenv()

llm = ChatOpenAI(model="gpt-4o")


# Basic configuration
config = BrowserConfig(
    headless=True,
    disable_security=True,
    chrome_instance_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    new_context_config=BrowserContextConfig(
        wait_for_network_idle_page_load_time=3.0,
        browser_window_size={'width': 1280, 'height': 1100},
    )
)

class EmailManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.agents: Dict[str, Agent] = {}

    async def connect(self, email_address: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[email_address] = websocket
        
        # Create agent instance for this connection
        self.agents[email_address] = Agent(
           task=f"""You are Agent Kelly, an email and web assistant. Your personal email url is {email_address}
        You must follow these strict rules:
        1. ALWAYS use the provided tool calls for ANY email operations - never try to access emails directly via URLs
        2. Use 'Get all emails' tool to check for new emails
        3. When you receive emails, first get their IDs from the emails.emails list returned by 'Get all emails'
        4. When you find the Newsletter Signup Request email, read it by calling 'Get email content' with the email ID.
        5. Use the browser-aware 'Sign up for newsletter' tool for each brand's website. When you do scroll to the very bottom of the page, usually 5000px. The newsletter signup button is usually there.
        6. Be sure to not click the check box to confirm before clicking submit since it is already checked.
        6. Use 'reply_to_email' tool to reply to the original email with promotions. Use the original email ID you used earlier. For new lines, don't use double slash n. Use a single slash n. In the message, say that you are subscribed to the newsletter, and will be forwarding the best deals that align with the user's interests in the future.
        
        Your goal is to:
        1. Monitor your inbox for a Newsletter Signup Request email
        2. When found, sign up for the requested fashion brand newsletters
        3. Reply with a kind email using the reply_to_email tool with the original email ID and titled 'Best Promotions' including a summary of each of the brands emails.

        
        Remember: You must ONLY interact with emails through the provided tools.
        Example workflow:
        1. emails = Get all emails
        2. if emails.emails exists and has items:
           - email_id = emails.emails[0].id
           - Use 'Get specific email' with email_id to read it
        
        Remember: Never call 'Get all emails' repeatedly without processing the results.
        """,
            llm=llm,
            use_vision=True, 
            save_conversation_path=f"logs/conversation_{email_address}.json",
            browser=browser,
            controller=controller
        )

    

    async def disconnect(self, email_address: str):
        if email_address in self.active_connections:
            del self.active_connections[email_address]
        if email_address in self.agents:
            del self.agents[email_address]

    async def process_email_update(self, email_address: str, data: dict):
        if email_address in self.agents:
            agent = self.agents[email_address]
            await agent.run()

email_manager = EmailManager()

browser = Browser()
controller = Controller()
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()


client = AgentMail(base_url="https://api.agentmail.to/v0", api_key=os.getenv("AGENTMAIL_PROD_API_KEY"))

@controller.action('Create new email inbox')
def create_inbox(username: Optional[str] = None) -> str:
    result = client.create_inbox(username)
    return f"Created inbox: {result.address}"

@controller.action('Delete email inbox')
def delete_inbox(address: str) -> str:
    result = client.delete_inbox(address)
    return f"Deleted inbox: {address}"

@controller.action('Get all emails from inbox')
def get_emails(address: str) -> str:
    emails = client.get_emails(address)
    if not emails.emails:
        return "No emails found in inbox"
    
    email_ids = [email.id for email in emails.emails]
    return f"Retrieved {len(emails.emails)} emails from {address} with IDs: {email_ids}"

@controller.action('Get specific email by ID')
def get_email(address: str, id: str) -> str:
    email = client.get_email(address, id)
    return f"Retrieved email: {email.subject}"

@controller.action('Get email content')
def get_email_content(address: str, id: str) -> str:
    email = client.get_email(address, id)
    return f"Retrieved email content: {email.text}"

@controller.action('Get all sent emails')
def get_sent_emails(address: str) -> str:
    emails = client.get_sent_emails(address)
    print(emails)
    return f"Retrieved {len(emails.emails)} sent emails from {address}"

@controller.action('Get specific sent email')
def get_sent_email(address: str, id: str) -> str:
    email = client.get_sent_email(address, id)
    return f"Retrieved sent email: {email.subject}"

@controller.action('Send new email')
def send_email( address: str, to: Optional[List[str]] = None, cc: Optional[List[str]] = None, bcc: Optional[List[str]] = None, subject: Optional[str] = None, text: Optional[str] = None
):
    client.send_email(
        address,
        to=to,
        cc=cc,
        bcc=bcc,
        subject=subject,
        text=text
    )
    return f"Sent email from {address} to {to}"

@controller.action('Reply to existing email')
def reply_to_email(address: str,
    id: str,
    to: Optional[List[str]] = None,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    subject: Optional[str] = None,
    text: Optional[str] = None,):
    client.reply_to_email(
        address,
        id,
        to=to,
        cc=cc,
        bcc=bcc,
        subject=subject,
        text=text
    )
    return f"Replied to email {id} from {address}"

@controller.action('Sign up for newsletter', requires_browser=True)
async def sign_up_newsletter(email: str, website: str, browser: Browser) -> str:
    page = browser.get_current_page()
    await page.goto(website)
    return f"Signed up for newsletter at {website} using {email}"

@app.websocket("/ws/{email_address}")
async def websocket_endpoint(websocket: WebSocket, email_address: str):
    await email_manager.connect(email_address, websocket)
    try:
        while True:
            print("Waiting for WebSocket message...")
            data = await websocket.receive_json()
            print(f"Received data: {data}")

            if data.get('type') == 'new_email':
                print(f"Processing new email update for {email_address}")
                await email_manager.process_email_update(email_address, data)
                # Send confirmation back to client
                await websocket.send_json({
                    "status": "success",
                    "message": "Email processed successfully"
                })
                print("Processing complete, closing connection")
                await websocket.close()
                break  # Exit the loop
    except Exception as e:
        print(f"Error in websocket connection: {e}")
    finally:
        await email_manager.disconnect(email_address)

# # HTTP endpoint to manually start monitoring an email
# @app.post("/monitor/{email_address}")
# async def start_monitoring(email_address: str):
#     # Initial run of the agent
#     if email_address in email_manager.agents:
#         agent = email_manager.agents[email_address]
#         await agent.run()
#     return {"status": "monitoring_started", "email": email_address}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
        

# brands = ['Louis Vuitton', 'Baccarat', 'Givenchy']
# email = 'testbrands@agentmail.to'

