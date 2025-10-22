import os
from threading import Thread

from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
import google.generativeai as genai


# Load environment variables from .env file
load_dotenv()

processed_ids = set()

# Define Google API Key and Set Gemini Pro Model
google_api_key = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=google_api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

# Initialize a Web Client with the Slack bot token from the environment variables
slack_token = os.getenv('SLACK_BOT_TOKEN')
client = WebClient(token=slack_token)

# Get BOT_USER_ID from environment variables
BOT_USER_ID = os.getenv('BOT_USER_ID')
app = Flask(__name__)


@app.route('/')
def health_check():
    """Health check endpoint."""
    return "Gemini Slack Bot is running!"


def handle_event_async(data):
    """Handle Slack event asynchronously to avoid blocking."""

    thread = Thread(target=handle_event, args=(data,), daemon=True)
    thread.start()


def handle_event(data):
    """Process Slack event data."""

    event = data["event"]
    print(f'Received Event Text: {event["text"]}')

    # Check if the event is a message without a subtype (excluding bot messages, etc.)

    if "text" in event and event["type"] == "message" and event.get("subtype") is None:
        # Ignore messages from the bot itself
        if event.get("user") == BOT_USER_ID:
            return

        # Handle direct message or app mention
        if event["channel"].startswith('D') or event.get("channel_type") == 'im':
            # Handle direct message event
            try:
                gemini = model.generate_content(event["text"])
                textout = gemini.text.replace("**", "*")
                print(textout)
                response = client.chat_postMessage(
                    channel=event["channel"],
                    text=textout,
                    mrkdwn=True
                )
            except SlackApiError as e:
                print(f"Error posting message: {e.response['error']}")

    elif event["type"] == "app_mention" and event.get("client_msg_id") not in processed_ids:
        try:
            gemini = model.generate_content(event["text"])
            textout = gemini.text.replace("**", "*")
            print(textout)
            response = client.chat_postMessage(
                channel=event["channel"],
                text=textout,
                mrkdwn=True
            )
            processed_ids.add(event.get("client_msg_id"))
        except SlackApiError as e:
            print(f"Error posting message: {e.response['error']}")


@app.route('/gemini', methods=['GET'])
def helloworld():
    """
    Return a response with the generated text using the Gemini Pro model with the input "Hi".
    """
    if request.method == 'GET':
        gemini = model.generate_content("Hi")
        return gemini.text


@app.route("/slack/events", methods=["POST"])
def slack_events():
    """
    Handle Slack events, such as app mentions and direct messages.

    When a challenge is received, return the challenge response.
    When an event is received, handle the event asynchronously.

    Returns an empty response with a 200 status code.
    """

    data = request.json
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})

    if "event" in data:
        handle_event_async(data)

    return "", 200


if __name__ == "__main__":
    app.run(debug=True)
