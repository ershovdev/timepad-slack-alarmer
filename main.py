import logging
from logging import Formatter
from logging.handlers import RotatingFileHandler
import os
from dotenv import load_dotenv
import json
import hmac, hashlib
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from flask import Flask, request

app = Flask(__name__)

formatter = Formatter('%(asctime)s %(levelname)s: %(message)s '
                      '[in %(pathname)s:%(lineno)d]')
file_handler = RotatingFileHandler('info.log', maxBytes=10000000, backupCount=3)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)

slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
slack_bot_channel_id = os.getenv("SLACK_BOT_CHANNEL_ID")
secret_url_path = os.getenv("SECRET_URL_PATH")
secret_timepad_phrase = os.getenv("SECRET_TIMEPAD_PHRASE")

client = WebClient(token=slack_bot_token)


@app.before_request
def log_request_info():
    app.logger.debug('Headers\n----\n%s', request.headers)
    app.logger.debug('Body\n---\n%s', request.get_data())


@app.route('/{}'.format(secret_url_path), methods=["POST"])
def timepad_webhook():
    update = request.get_json()

    sig = request.headers.get('X-Hub-Signature') or ''
    sig_gen = hmac.new(str.encode(secret_timepad_phrase), request.get_data(), hashlib.sha1).hexdigest()

    if sig != ("sha1=" + sig_gen):
        response = json.dumps({'message': 'Authentication Required'})
        return response, 401

    try:
        client.chat_postMessage(
            channel=slack_bot_channel_id,
            text=json.dumps(update, ensure_ascii=False) + '\n' + sig + '\n' + sig_gen
        )
    except SlackApiError as e:
        assert e.response["error"]

    return "OK"


if __name__ == '__main__':
    load_dotenv()
    app.run()
