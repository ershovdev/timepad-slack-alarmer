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
    app.logger.info('\n\n\nHeaders\n----\n%s', request.headers)
    app.logger.info('Body\n---\n%s', json.dumps(request.get_data(as_text=True), indent=4))


@app.route('/{}'.format(secret_url_ticket_path), methods=["POST"])
def timepad_ticket_webhook():
    if not is_timepad_sign_valid(request):
        return json.dumps({'message': 'Authentication Required'}), 401

    update = request.get_json()
    status = update['status_raw']

    if not is_event_status_allowed(status):
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
    if not is_timepad_sign_valid(request):
        return json.dumps({'message': 'Authentication Required'}), 401

    update = request.get_json()
    status = update['status']['name']

    if not is_event_status_allowed(status):
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
    event_name_formatted = f"*{timepad_json['event']['name']}*\n"

    answers = timepad_json['tickets'][0]['answers']
    student_data_formatted = f":student: {answers['name']} {answers['surname']} ({answers['mail']})\n"

    final_price = timepad_json['payment']['amount']
    discount = timepad_json['payment']['discount']

    price_formatted = f'{final_price}₽'

    if discount != 0:
        price_formatted = f'{price_formatted} ({final_price + discount}₽ - {discount}₽)'

    price_formatted = f':dollar: {price_formatted}\n'

    status_formatted = f"Статус: {timepad_json['status']['title']}\n"

    promocodes = ', '.join(timepad_json.get('promocodes', []))
    promocodes_formatted = ''
    if promocodes:
        promocodes_formatted = f'Промокоды: {promocodes}\n'

    referer = timepad_json.get('referer')
    utm_formatted = ''
    if referer:
        utm_formatted = f"_utm_campaign: {referer['campaign']}_\n" \
                        f"_utm_medium: {referer['medium']}_\n" \
                        f"_utm_source: {referer['source']}_\n"

    return f'{event_name_formatted}' \
           f'{student_data_formatted}' \
           f'{price_formatted}' \
           f'{status_formatted}' \
           f'{promocodes_formatted}' \
           f'{utm_formatted}'


def is_timepad_sign_valid(request):
    sig = request.headers.get('X-Hub-Signature') or ''
    sig_gen = hmac.new(str.encode(secret_timepad_phrase), request.get_data(), hashlib.sha1).hexdigest()

    return sig == ("sha1=" + sig_gen)


def is_event_status_allowed(status):
    return status in ['paid', 'paid_ur']


if __name__ == '__main__':
    load_dotenv()
    app.run()
