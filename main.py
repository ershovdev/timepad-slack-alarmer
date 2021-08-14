import logging
import os
from dotenv import load_dotenv
import json

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from flask import Flask, request

app = Flask(__name__)

slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
slack_bot_channel_id = os.getenv("SLACK_BOT_CHANNEL_ID")
secret_url_path = os.getenv("SECRET_URL_PATH")
secret_timepad_phrase = os.getenv("SECRET_TIMEPAD_PHRASE")

client = WebClient(token=slack_bot_token)


@app.route('/{}'.format(secret_url_path), methods=["POST"])
def timepad_webhook():
    update = request.get_json()

    try:
        client.chat_postMessage(
            channel=slack_bot_channel_id,
            text=json.dumps(update, ensure_ascii=False)
        )
    except SlackApiError as e:
        assert e.response["error"]

    return "OK"


if __name__ == '__main__':
    load_dotenv()
    logging.basicConfig(level=logging.DEBUG)
    app.run()
