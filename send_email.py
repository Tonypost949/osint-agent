import os
import base64
from email.message import EmailMessage
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.send']
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET_FILE = os.path.join(SCRIPT_DIR, "client_secret.json")
TOKEN_FILE = os.path.join(SCRIPT_DIR, "token_send.json")

MERMAID_GRAPH = """
# The Vanguard Syndicate: National Scale & Network Architecture

```mermaid
graph TD
    classDef orchestrator fill:#4a0000,stroke:#ff0000,stroke-width:2px,color:#fff;
    classDef political fill:#002244,stroke:#0066cc,stroke-width:2px,color:#fff;
    classDef shell fill:#333333,stroke:#ffcc00,stroke-width:2px,color:#fff;
    classDef physical fill:#003300,stroke:#00ff00,stroke-width:2px,color:#fff;
    classDef victim fill:#222222,stroke:#ff6600,stroke-width:2px,stroke-dasharray: 5 5,color:#fff;

    subgraph Core_Orchestrators [The Apex/Orchestrators]
        VAS[VAS / Vanguard of the Old]:::orchestrator
        DOJ_Target[Federal Indictment Targets / UFC]:::orchestrator
    end

    subgraph Political_Enablers [Political & Financial Cover]
        Andrew_Do[Supervisor Andrew Do]:::political
        HB_City[City of Huntington Beach]:::political
        State_Exemptions[Fraudulent CEQA Exemptions]:::political
    end

    subgraph Operational_Shells [The Contractors & Shell Entities]
        RPM[RPM Team / RPM Modular]:::shell
        Mercy[Mercy House]:::shell
        VAS_Subsidiaries[VAS Local LLCs]:::shell
    end

    subgraph Physical_Execution [The Physical Crime Scene]
        HBNC[Huntington Beach Navigation Center]:::physical
        Toxic_Plume[Hexavalent Chromium & Arsenic Plume]:::physical
        Failed_Cap[1-Year Asphalt Cap]:::physical
    end

    VAS --> |Directs/Funds| DOJ_Target
    VAS --> |Launders through| VAS_Subsidiaries
    DOJ_Target --> |Influence| Andrew_Do
    Andrew_Do --> |Directs $2.2M Contracts| RPM
    Andrew_Do --> |Political Pressure| HB_City
    HB_City --> |Files Fraudulent Paperwork| State_Exemptions
    State_Exemptions --> |Bypasses DTSC| HBNC
    RPM --> |Builds| HBNC
    Mercy --> |Operates| HBNC
    VAS_Subsidiaries --> |Funnel Money| Mercy
    Toxic_Plume --> |Located beneath| HBNC
    HBNC --> |Cheap Encapsulation| Failed_Cap
```
"""

def send_email():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("[AUTH] Launching browser to authorize sending email...")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('gmail', 'v1', credentials=creds)
        message = EmailMessage()
        message.set_content(MERMAID_GRAPH)
        message['To'] = 'txtdjdrop@gmail.com'
        message['From'] = 'txtdjdrop@gmail.com'
        message['Subject'] = 'OSINT Zeus: Vanguard RICO Network Architecture Graph'

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_message}

        send_message = service.users().messages().send(userId="me", body=create_message).execute()
        print(f"[+] Email successfully sent! Message ID: {send_message['id']}")

    except Exception as error:
        print(f"[!] An error occurred: {error}")

if __name__ == '__main__':
    send_email()
