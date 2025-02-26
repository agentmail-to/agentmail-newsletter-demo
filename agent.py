from langchain_openai import ChatOpenAI
from browser_use import Agent, BrowserConfig, Browser
from browser_use.browser.context import BrowserContextConfig
from playwright.async_api import BrowserContext
from dotenv import load_dotenv
from browser_use.controller.service import Controller
from typing import Optional, List
from fastapi import FastAPI, WebSocket

from fastapi.middleware.cors import CORSMiddleware
import os

from agentmail import AgentMail


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
         # Clear any existing log file
        log_path = f"logs/conversation_{email_address}.json"
        if os.path.exists(log_path):
            os.remove(log_path)
        
        # Create agent instance for this connection
        self.agents[email_address] = Agent(
           task=f"""You are Agent Kelly, an email and web assistant. Your personal email url is {email_address}
        Do not attempt to create your own inbox. You already have one.
        You must follow these strict rules:
        1. ALWAYS use the provided tool calls for ANY email operations - never try to access emails directly via URLs
        2. Use 'Get all messages' tool to check for new emails
        3. When you receive messages, first get their IDs from the messages.messages list returned by 'Get all messages'
        4. Loop through each message and check message.subject and if the word Newsletter is in the subject use this email address to get the message content
            - save this original message.from field - this is who you'll reply to later
            - save this original message_id for replying later
        5. When you find the Newsletter Signup Request message, read it by calling 'Get message content' with the message ID.
        6. DO NOT go to the substack website. Directly search the newsletter name + 'signup' in google and sign up for the top link
        7. After signing up, there will be a second screen asking you to sign up to donate. Select the fourth option which means none. Then just click through skipping and then finally maybe later. Don't close the tab until you see the confirmation that you are subscribed.'
        8. Be sure to not click the check box to confirm before clicking submit since it is already checked.
        9. Use 'reply_to_message' tool to reply to the newsletter signup request message saying you succesfully signed up and will keep the user updated with everything they requested to be kept to up to date with. Use the original message ID you used earlier. For new lines, don't use double slash n. Use a single slash n. In the message, say that you are subscribed to the newsletter, and will be forwarding the best deals that align with the user's interests in the future.
            - Use ONLY inbox_id and message_id parameters from the newsletter signup request when replying
            - make sure to reply to the original sender
            - DO NOT reply to the welcome email or your own inbox. 
            - Include a confirmation message about the subscription        
            - use the newsletter signup request messages message.from as the to address here. It should never be your own. And you shouldn't you assume and create one.
        Your goal is to:
        1. Monitor your inbox for a Newsletter Signup Request email
        2. When found, sign up for the requested fashion brand newsletters
        3. Reply with a kind email using the reply_to_message tool with the original message ID. and titled 'Best Promotions' including a summary of the newsletter on LLMs.
        
        Remember: You must ONLY interact with emails through the provided tools.
        Example workflow:
        1. messages = Get all messages
        2. if messages.messages exists and has items:
           - message_id = messages.messages[0].message_id
           - Use 'Get specific message' with message_id to read it
        
        Remember: Never call 'Get all messages' repeatedly without processing the results.
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


client = AgentMail(api_key=os.getenv("AGENTMAIL_PROD_API_KEY"))

@controller.action('Create new inbox')
def create_inbox() -> str:
    result = client.inboxes.create()
    return f"Created inbox: {result.address}"

@controller.action('Delete inbox')
def delete_inbox(inbox_id: str) -> str:
    client.inboxes.delete(inbox_id=inbox_id)
    return f"Deleted inbox: {inbox_id}"

@controller.action('Get all messages from inbox')
def get_messages(inbox_id: str) -> str:
    messages = client.messages.list(
        inbox_id=inbox_id,
       
    )
    if not messages.messages:
        return "No messages found in inbox"
    
    message_ids = []
    for msg in messages.messages:
        message_ids.append(msg.message_id)
    return f"Retrieved {len(message_ids)} messages from {inbox_id} with IDs: {message_ids}"

@controller.action('Get message by ID')
def get_message(inbox_id: str, message_id: str) -> str:
    message = client.messages.get(inbox_id = inbox_id, message_id=message_id)
    return f"Retrieved message: {message.subject}"

@controller.action('Get message content')
def get_message(inbox_id: str, message_id: str) -> str:
    message = client.messages.get(inbox_id = inbox_id, message_id=message_id)
    return f"Retrieved message: {message.text}"

@controller.action('Send new message')
def send_message(
    inbox_id: str,
    to: List[str],
    subject: Optional[str] = None,
    text: Optional[str] = None,
    html: Optional[str] = None,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None
):
    
    client.messages.send(
        inbox_id=inbox_id,
        to=to,
        subject=subject or "",
        text=text or "",
        html=html or "",
        cc=cc or [],
        bcc=bcc or []
    )
    return f"Sent message from {inbox_id} to {to}"

@controller.action('Reply to message')
def reply_to_message(
    inbox_id: str,
    message_id: str,
    text: Optional[str] = None,
    html: Optional[str] = None,
    to: Optional[str] = None,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None
):
    client.messages.reply(
        inbox_id=inbox_id,
        message_id=message_id,
        text=text or "",
        html=html or "",
        to=to or "",
        cc=cc or [],
        bcc=bcc or [],
    )
    return f"Replied to message {message_id}"

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
