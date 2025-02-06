import httpx
from typing import Optional, List, Union
from pydantic import EmailStr
import os

from models import Inbox, CreateInbox, Emails, Email, SendEmail


class AgentMail:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

    def create_inbox(self, username: Optional[str] = None, domain: Optional[str] = None):
        body = CreateInbox(username=username, domain=domain)
        response = httpx.post(f"{self.base_url}/inboxes", json=body.model_dump(exclude_none=True), headers=self.headers).raise_for_status()
        return Inbox(**response.json())

    def delete_inbox(self, address: str):
        response = httpx.delete(f"{self.base_url}/inboxes/{address}", headers=self.headers).raise_for_status()
        return response.status_code

    def get_emails(self, address: str):
        response = httpx.get(f"{self.base_url}/inboxes/{address}/emails", headers=self.headers).raise_for_status()
        return Emails(**response.json())

    def get_email(self, address: str, id: str):
        response = httpx.get(f"{self.base_url}/inboxes/{address}/emails/{id}", headers=self.headers).raise_for_status()
        return Email(**response.json())

    def get_sent_emails(self, address: str):
        response = httpx.get(f"{self.base_url}/inboxes/{address}/sent", headers=self.headers).raise_for_status()
        return Emails(**response.json())

    def get_sent_email(self, address: str, id: str):
        response = httpx.get(f"{self.base_url}/inboxes/{address}/sent/{id}", headers=self.headers).raise_for_status()
        return Email(**response.json())

    def send_email(
        self,
        address: str,
        to: Optional[Union[EmailStr, List[EmailStr]]] = None,
        cc: Optional[Union[EmailStr, List[EmailStr]]] = None,
        bcc: Optional[Union[EmailStr, List[EmailStr]]] = None,
        subject: Optional[str] = None,
        text: Optional[str] = None,
    ):
        body = SendEmail(to=to, cc=cc, bcc=bcc, subject=subject, text=text)
        response = httpx.post(f"{self.base_url}/inboxes/{address}/sent", json=body.model_dump(exclude_none=True), headers=self.headers).raise_for_status()
        return response.status_code

    def reply_to_email(
        self,
        address: str,
        id: str,
        to: Optional[Union[EmailStr, List[EmailStr]]] = None,
        cc: Optional[Union[EmailStr, List[EmailStr]]] = None,
        bcc: Optional[Union[EmailStr, List[EmailStr]]] = None,
        subject: Optional[str] = None,
        text: Optional[str] = None,
    ):
        body = SendEmail(to=to, cc=cc, bcc=bcc, subject=subject, text=text)
        response = httpx.post(f"{self.base_url}/inboxes/{address}/emails/{id}/reply", json=body.model_dump(exclude_none=True), headers=self.headers).raise_for_status()
        return response.status_code
