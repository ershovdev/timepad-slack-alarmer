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
secret_url_ticket_path = os.getenv("SECRET_URL_TICKET_PATH")
secret_url_order_path = os.getenv("SECRET_URL_ORDER_PATH")
secret_timepad_phrase = os.getenv("SECRET_TIMEPAD_PHRASE")

client = WebClient(token=slack_bot_token)


@app.before_request
def log_request_info():
    app.logger.info('Headers\n----\n%s', request.headers)
    app.logger.info('Body\n---\n%s', request.get_data())


@app.route('/{}'.format(secret_url_ticket_path), methods=["POST"])
def timepad_ticket_webhook():
    update = request.get_json()

    sig = request.headers.get('X-Hub-Signature') or ''
    sig_gen = hmac.new(str.encode(secret_timepad_phrase), request.get_data(), hashlib.sha1).hexdigest()

    if sig != ("sha1=" + sig_gen):
        response = json.dumps({'message': 'Authentication Required'})
        return response, 401

    status = update['status_raw']

    if status not in ['paid', 'paid_ur']:
        return "OK", 200

    try:
        message = get_ticket_slack_message(update)

        client.chat_postMessage(
            channel=slack_bot_channel_id,
            text=message
        )
    except SlackApiError as e:
        assert e.response["error"]

    return "OK", 200


def get_ticket_slack_message(timepad_json):
    name = timepad_json['name']
    surname = timepad_json['surname']
    email = timepad_json['email']
    status = timepad_json['status']
    price = timepad_json['price_nominal']
    event_name = timepad_json['event_name']

    return """
*%s*
:dollar: %s₽
:student: %s %s (%s)
Статус: %s""" % (event_name, price, name, surname, email, status)


@app.route('/{}'.format(secret_url_order_path), methods=["POST"])
def timepad_order_webhook():
    update = request.get_json()

    sig = request.headers.get('X-Hub-Signature') or ''
    sig_gen = hmac.new(str.encode(secret_timepad_phrase), request.get_data(), hashlib.sha1).hexdigest()

    if sig != ("sha1=" + sig_gen):
        response = json.dumps({'message': 'Authentication Required'})
        return response, 401

    status = update['status']['name']

    if status not in ['paid', 'paid_ur']:
        return "OK", 200

    try:
        message = get_order_slack_message(update)

        client.chat_postMessage(
            channel=slack_bot_channel_id,
            text=message
        )
    except SlackApiError as e:
        app.logger.error()
        assert e.response["error"]

    return "OK", 200


def get_order_slack_message(timepad_json):
    event_name = timepad_json['event']['name']

    final_price = timepad_json['payment']['amount']
    discount = timepad_json['payment']['discount']

    if discount == 0:
        price_formatted = str(final_price) + '₽'
    else:
        price_formatted = "%d₽ (%d₽ - %d₽)" % (final_price, final_price+discount, discount)

    answers = timepad_json['tickets'][0]['answers']

    name = answers['name']
    surname = answers['surname']
    email = answers['mail']

    student_data_formatted = "%s %s (%s)" % (name, surname, email)

    status_name = timepad_json['status']['title']

    promocodes = ', '.join(timepad_json['promocodes'])
    promocodes_formatted = '' if promocodes == '' else 'Промокоды: ' + promocodes

    return """
*%s*
:student: %s
:dollar: %s
%s
Статус: %s""" % (event_name, student_data_formatted, price_formatted, promocodes_formatted, status_name)


if __name__ == '__main__':
    load_dotenv()
    app.run()
