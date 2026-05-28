
import os
import anthropic
from notion_client import Client as NotionClient
from flask import Flask, request, jsonify
from twilio.rest import Client as TwilioClient
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
notion = NotionClient(auth=NOTION_API_KEY)
twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def add_task_to_notion(task_name, status="To Do", priority="Medium", area="Professional"):
    try:
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "Task": {"title": [{"text": {"content": task_name}}]},
                "Status": {"select": {"name": status}},
                "Priority": {"select": {"name": priority}},
                "Area": {"select": {"name": area}},
            }
        )
        return f"Task {task_name} successfully added to Notion!"
    except Exception as e:
        return f"Error adding task: {str(e)}"

system_prompt = """
You are Kai, the personal and professional AI assistant of Caio Fernandes.

ABOUT CAIO:
- Brazilian, lives in Brazil
- Project Leader at Volkswagen since 2012
- Manages multitasked teams and delivers project updates to high-level management and stakeholders
- Currently learning to code and building his own AI agent (you!)

YOUR ROLE:
You are Caio right hand across:
1. Personal life organization
2. Professional work at Volkswagen
3. Learning and self development

TASK MANAGEMENT:
When Caio mentions something that sounds like a task, extract it and add it to Notion using the add_task tool.

IMPORTANT FOR WHATSAPP:
- Keep responses concise and clear, WhatsApp is a mobile chat
- Use short paragraphs, avoid long walls of text
- Use emojis sparingly but naturally
- If a response would be very long, summarize and offer to go deeper

TRUTH AND ACCURACY RULES:
1. UNCERTAINTY: If not fully certain, say I am not sure, but...
2. SOURCES: Never invent references.
3. STATISTICS: Flag uncertain numbers.
4. RECENT EVENTS: Warn when info may be outdated.
5. PEOPLE AND QUOTES: Never attribute quotes unless certain.
6. CODE AND TECHNICAL: Never invent function names or syntax.
7. LOGIC GAPS: Ask clarifying questions instead of assuming.

PERSONALITY:
- Friendly and warm by default
- Professional and direct when needed
- Never waste Caio time
- Respond in the same language Caio uses
"""

tools = [
    {
        "name": "add_task",
        "description": "Adds a task to Caio Notion task manager",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_name": {"type": "string", "description": "The name of the task"},
                "priority": {"type": "string", "enum": ["High", "Medium", "Low"]},
                "area": {"type": "string", "enum": ["Professional", "Personal", "Learning"]}
            },
            "required": ["task_name"]
        }
    }
]

conversation_histories = {}

def chat(session_id, user_message):
    if session_id not in conversation_histories:
        conversation_histories[session_id] = []

    history = conversation_histories[session_id]
    history.append({"role": "user", "content": user_message})

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system_prompt,
        tools=tools,
        messages=history
    )

    final_response = ""
    for block in response.content:
        if block.type == "text":
            final_response += block.text
        elif block.type == "tool_use":
            if block.name == "add_task":
                args = block.input
                result = add_task_to_notion(
                    task_name=args["task_name"],
                    priority=args.get("priority", "Medium"),
                    area=args.get("area", "Professional")
                )
                final_response += f" {result}"

    history.append({"role": "assistant", "content": response.content})
    return final_response

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    incoming_msg = request.values.get("Body", "").strip()
    sender = request.values.get("From", "")

    response_text = chat(sender, incoming_msg)

    resp = MessagingResponse()
    resp.message(response_text)
    return str(resp)

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "Kai is online!"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
