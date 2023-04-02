import email
import telebot
import json
from email.utils import parseaddr
from imapclient import IMAPClient
import time

with open(".secret.json", "r", encoding="UTF8") as _:
    data = json.load(_)

    username = data.get("mail").get("username")
    password = data.get("mail").get("password")

    token = data.get("bot").get("token")
    special_senders = data.get("mail").get("special_senders")
    chat_id = data.get("bot").get("chat_id")

TIMEOUT = 15
HOST = "imap.gmail.com"

bot = telebot.TeleBot(token)
while True:
    server = IMAPClient(HOST)
    server.login(username, password)
    notifications = []
    try:
        server.select_folder("INBOX", readonly=False)
        for sender in special_senders:
            messages = server.search(["UNSEEN", ["FROM", sender]])
            text = ""
            if messages:
                text = f"{sender} wrote:\n"
                print(f"processing messages from {sender}")
                for uid, message_data in server.fetch(messages, "RFC822").items():
                    msg = email.message_from_bytes(message_data[b"RFC822"])
                    body = ""
                    sender = parseaddr(msg.get("From"))[1]

                    if msg.is_multipart:
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode("utf-8")
                                break
                    else:
                        body = msg.get_payload(decode=True).decode("utf-8")
                    text += f"{body}"

                notifications.append(text)
                server.set_flags(messages, "\\SEEN")
        if len(notifications) > 0:
            bot.send_message(chat_id=chat_id, text="".join(notifications))
        time.sleep(TIMEOUT)

    except KeyboardInterrupt:
        break
    except Exception as e:
        print(e)
        break
