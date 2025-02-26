import asyncio
import websockets
import json
from agentmail import AgentMail  # Import the AgentMail client
from dotenv import load_dotenv
import os
load_dotenv()

async def connect_to_agent(email_address: str):
    uri = f"ws://localhost:8000/ws/{email_address}"
    client = AgentMail(api_key= os.getenv("AGENTMAIL_PROD_API_KEY"))



    async with websockets.connect(uri) as websocket:
        print(f"Connected to agent for {email_address}")
        print("Waiting for new emails...")
        while True:
            try:
                # Checking for new emails
                messages = client.messages.list(
                    inbox_id=email_address,

                )
                
                # If there are new emails, send notification through websocket
                if messages.messages:
                    print(f"Found {len(messages.messages)} emails")

                    # creating our own message / notification type sending it to our own server.
                    notification = {
                        "type": "new_email",
                        "data": {
                            "email_address": email_address,
                            "emails": [{"id": message.message_id, "subject": message.subject} for message in messages.messages]
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
    email_address = "testfinal@agentmail.to"
    print("Starting email monitor...")
    asyncio.run(connect_to_agent(email_address))
