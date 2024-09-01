from nylas import Client
from nylas.models.messages import ListMessagesQueryParams
from nylas.models.contacts import ListContactsQueryParams
import boto3
import os

nylas = Client(api_key=os.environ.get('NYLAS_API_KEY'))

# bedrock configuration be sure to create your knowledge base beforehand
region_name = os.environ.get('AWS_REGION')
model_arn = os.environ.get('BEDROCK_MODEL_ARN')
kb_id = os.environ.get('KNOWLEDGE_BASE_ID')
bedrock_agent_runtime_client = boto3.client("bedrock-agent-runtime", region_name=region_name)

# generate a response asking our RAG with the email content
def ask_bedrock_llm_with_knowledge_base(query: str) -> str:
    response = bedrock_agent_runtime_client.retrieve_and_generate(
        input={'text': query},
        retrieveAndGenerateConfiguration={
            'type': 'KNOWLEDGE_BASE',
            'knowledgeBaseConfiguration': {
                'knowledgeBaseId': kb_id,
                'modelArn': model_arn
            }
        }
    )
    return response.get('output', {}).get('text', 'No generated text found.')

# get this message if webhook nylas message.created is configured otherwise just pull the last message
def fetch_latest_message(nylas_client: Client, grant_id: str) -> list:
    query_params = ListMessagesQueryParams({'limit': 1})
    messages, _, _ = nylas_client.messages.list(grant_id, query_params)
    return messages

# you can fetch the contacts per company or description for this example we only have one contact
def fetch_contact(nylas_client: Client, grant_id: str) -> list:
    query_params = ListContactsQueryParams({'limit': 1})
    contacts, _, _ = nylas_client.contacts.list(grant_id, query_params)
    return contacts

def send_message(nylas_client: Client, grant_id: str, subject: str, body: str, recipient: str):
    request_body = {
        "subject": subject,
        "body": body,
        "to": [{"email": recipient}]
    }
    nylas_client.messages.send(grant_id, request_body=request_body)

def process_messages():
    grant_id = os.environ.get('NYLAS_GRANT_ID')
    messages = fetch_latest_message(nylas, grant_id)

    for message in messages:
        print(f"{message.subject}")
        response = ask_bedrock_llm_with_knowledge_base(message.subject)

        if "i could not find an exact answer to the question" in response.lower():
            contacts = fetch_contact(nylas, grant_id)
            for contact in contacts:
                send_message(
                    nylas,
                    grant_id,
                    f"Please {contact.given_name}, your help is needed with the following requirement",
                    message.subject,
                    contact.emails[0].email
                )
        else:
            send_message(
                nylas,
                grant_id,
                "Answer from RAG Model",
                response,
                os.environ.get('SUPPORT_EMAIL_N1')
            )


process_messages()
