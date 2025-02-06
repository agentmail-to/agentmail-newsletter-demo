import asyncio
import websockets
import json
from client import AgentMail  # Import the AgentMail client
from dotenv import load_dotenv
import os
load_dotenv()

async def connect_to_agent(email_address: str):
    uri = f"ws://localhost:8000/ws/{email_address}"
    client = AgentMail(base_url="https://api.agentmail.to/v0", api_key= os.getenv("AGENTMAIL_PROD_API_KEY"))

    async with websockets.connect(uri) as websocket:
        print(f"Connected to agent for {email_address}")
        print("Waiting for new emails...")
        while True:
            try:
                # Check for new emails
                # print("Checking for new emails...")
                emails = client.get_emails(email_address)
                
                # If there are new emails, send notification through websocket
                if emails.emails:
                    print(f"Found {len(emails.emails)} emails")

                    # creating our own message / notification type sending it to our own server.
                    notification = {
                        "type": "new_email",
                        "data": {
                            "email_address": email_address,
                            "emails": [{"id": email.id, "subject": email.subject} for email in emails.emails]
                        }
                    }
                    print(f"Sending notification: {notification}")
                    await websocket.send(json.dumps(notification))
                    print(f"Notified agent about new email(s)")

                    # Wait for response from agent
                    response = await websocket.recv()
                    response_data = json.loads(response)
                    print(f"Received response from agent: {response}")
                
                    if response_data.get('status') == 'success':
                        print("Email processing completed successfully. Closing connection.")
                        return  
                else:
                    # print("No emails found")
                    await asyncio.sleep(5)

            except websockets.ConnectionClosed:
                print("Connection closed")
                break
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(5) 

if __name__ == "__main__":
    email_address = "test_substack@agentmail.to"
    print("Starting email monitor...")
    asyncio.run(connect_to_agent(email_address))