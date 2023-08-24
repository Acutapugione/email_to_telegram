from dataclasses import dataclass
import email
from email.utils import parseaddr
import json
import os
import logging
from typing import List, Optional, Tuple
import time

import telebot
from imapclient import IMAPClient
from dotenv import load_dotenv


class SettingExceptions(Exception):
    """Indicates that there is some problem with setting json file."""
    pass


@dataclass(frozen=True)
class SettingFromJsonFileEmail:
    """Stores setting for Email Operations."""
    host: str
    username: str
    password: str
    special_senders: List[str]


@dataclass(frozen=True)
class SettingsFromJsonFileTgBot:
    """Stores setting for Telegram Bot Operations."""
    tgbot_token: str
    tgbot_chat_id: str


def get_env_variables() -> Tuple[float, str]:
    """Get environment settings."""

    load_dotenv()  # read .env file

    try:
        repeat_timeout = float(os.getenv("REPEAT_TIMEOUT", 15))  # repeat our program main function every N seconds
    except TypeError as ex:
        logging.error("TIMEOUT should be float of integer!")
        raise ex

    json_settings_filename = os.getenv("JSON_SETTINGS_FILENAME", ".secret.json")

    return repeat_timeout, json_settings_filename


def get_settings_from_json_file(
        filename: Optional[str] = None,
        encoding: Optional[str] = None,
) -> Tuple[SettingFromJsonFileEmail, SettingsFromJsonFileTgBot]:
    """Reads settings from json settings file. File should have correct structure."""
    if filename is None:
        filename = ".secret.json"

    if encoding is None:
        encoding = "UTF8"

    with open(filename, mode="r", encoding=encoding) as f:
        data = json.load(f)

        mail_settings_storage = data.get("mail", None)
        if mail_settings_storage is None:
            raise SettingExceptions("No mail settings in file")

        bot_settings_storage = data.get("bot", None)
        if bot_settings_storage is None:
            raise SettingExceptions("No bot settings in file")

        email_settings = SettingFromJsonFileEmail(
            host=mail_settings_storage.get("host", ""),
            username=mail_settings_storage.get("username", ""),
            password=mail_settings_storage.get("password", ""),
            special_senders=mail_settings_storage.get("special_senders", []),
        )

        bot_settings = SettingsFromJsonFileTgBot(
            tgbot_token=bot_settings_storage.get("token", ""),
            tgbot_chat_id=bot_settings_storage.get("chat_id", ""),
        )

        return email_settings, bot_settings


def process_messages_from_one_sender(
        sender: str,
        tgbot_chat_id: str,
        server: IMAPClient,
        bot: telebot.TeleBot,
) -> None:
    """
    Checks if there are any new messages from sender in email box.
    Reads new messages. Send them to TgBot. Marks message as read.
    """
    messages = server.search(["UNSEEN", ["FROM", sender]])

    logging.info(f"Started processing messages from {sender}")
    if not messages:
        logging.info(f"Finished processing messages from {sender}")
        return

    for uid, message_data in server.fetch(messages, "RFC822").items():
        msg = email.message_from_bytes(message_data[b"RFC822"])
        sender = parseaddr(msg.get("From"))[1]

        if msg.is_multipart:
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode("utf-8")
                    break
            else:
                body = "No text/plain was found in multipart email!"
                logging.warning("No text/plain was found in multipart email!")
        else:
            body = msg.get_payload(decode=True).decode("utf-8")

        text = f"{sender} wrote: {body}"

        if len(text) > 4096:  # Telegram bot can't send message longer than!
            text = text[0:4095]
            logging.warning("Message text was too long and was cut!")

        bot.send_message(chat_id=tgbot_chat_id, text=text)  # send email message to tgbot
        server.set_flags(messages, "\\SEEN")  # mark email message as SEEN
        logging.info(f"Message {text[0:200]} was successfully sent to TG Bot.")

    logging.info(f"Successfully Finished processing messages from {sender}")


def main() -> None:
    repeat_timeout, filename = get_env_variables()
    email_settings, bot_settings = get_settings_from_json_file(filename=filename, encoding="utf8")
    bot = telebot.TeleBot(bot_settings.tgbot_token)

    while True:
        server = IMAPClient(email_settings.host)
        server.login(email_settings.username, email_settings.password)
        logging.info("Successfully logged in email server")
        try:
            logging.info("Started working with messages in email server")
            server.select_folder("INBOX", readonly=False)
            for sender in email_settings.special_senders:
                logging.info(f"Started working with messages from {sender}")
                process_messages_from_one_sender(
                    sender=sender, tgbot_chat_id=bot_settings.tgbot_chat_id, server=server, bot=bot
                )
                logging.info(f"Finished working with messages from {sender}")

            logging.info("Successfully finished working with messages in email server")
        finally:
            server.logout()
            logging.info("Successfully logged out from email server")

        time.sleep(repeat_timeout)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        encoding="utf8",
    )
    try:
        main()
    except KeyboardInterrupt:
        logging.info("The app was gracefully stopped!")
    except Exception as ex:
        logging.error(ex)
        raise ex
