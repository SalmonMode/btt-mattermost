#!/usr/bin/env python3
import getpass
import os
import websockets
import ssl
import asyncio
import socket
import sqlite3
import json
import configparser

import daemon
from mattermostdriver import (
    Driver,
    Websocket,
)

config = configparser.ConfigParser()
config.read("/etc/mattermost_daemon/config.ini")

mattermost_settings = config["mattermost"]
login_id = mattermost_settings.get("login_id", None)
password = mattermost_settings.get("password", None)
mfa_token = mattermost_settings.get("mfa_token", None)
scheme = mattermost_settings.get("scheme", "https")
token = mattermost_settings.get("token", None)
url = mattermost_settings.get("url", None)


options = {
    "basepath": "/api/v4",
    "debug": True,
    "login_id":login_id,
    "mfa_token": mfa_token,
    "password": password,
    "port": 443,
    "scheme": scheme,
    "timeout": 30,
    "token": token,
    "url": url,
    "verify": True,
}


user = getpass.getuser()


stdout_loc = f"/tmp/com.{user}.mattermost/stdout"
stderr_loc = f"/tmp/com.{user}.mattermost/stderr"


user_id = None


class CustomWebsocket(Websocket):

    async def connect(self, event_handler):
        """
        Connect to the websocket and authenticate it.
        When the authentication has finished, start the loop listening for messages,
        sending a ping to the server to keep the connection alive.

        :param event_handler: Every websocket event will be passed there. Takes one argument.
        :type event_handler: Function(message)
        :return:
        """
        self.context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
        if not self.options["verify"]:
            self.context.verify_mode = ssl.CERT_NONE

        scheme = "wss://"
        if self.options["scheme"] != "https":
            scheme = "ws://"
            self.context = None

        self.url = "{scheme:s}{url:s}:{port:s}{basepath:s}/websocket".format(
            scheme=scheme,
            url=self.options["url"],
            port=str(self.options["port"]),
            basepath=self.options["basepath"]
        )

        websocket = await websockets.connect(
            self.url,
            ssl=self.context,
        )

        await self._authenticate_websocket(websocket, event_handler)
        await self._start_loop(websocket, event_handler)

    async def _start_loop(self, websocket, event_handler):
        while True:
            try:
                await super()._start_loop(websocket, event_handler)
            except (websockets.exceptions.ConnectionClosed, socket.gaierror):
                while True:
                    try:
                        websocket = await websockets.connect(self.url, ssl=self.context)
                        await self._authenticate_websocket(websocket, event_handler)
                    except (websockets.exceptions.ConnectionClosed, socket.gaierror, ConnectionResetError):
                        await asyncio.sleep(10)
                        continue
                    else:
                        break
                continue



db_loc = f"/tmp/com.{user}.mattermost/channels.db"

os.makedirs(os.path.dirname(db_loc), exist_ok=True)



os.makedirs(os.path.dirname(stdout_loc), exist_ok=True)

conn = sqlite3.connect(db_loc)

cur = conn.cursor()

cur.execute("""
    CREATE TABLE IF NOT EXISTS channels (
        channel_id VARCHAR(26) PRIMARY KEY,
        mentions INTEGER DEFAULT 0
    );
""")

conn.commit()
conn.close()


def create_channel_if_not_exists(cur, conn, channel_id):
    cur.execute(f"INSERT OR IGNORE INTO channels (channel_id, mentions) VALUES ('{channel_id}', 0);")
    conn.commit()


def mark_channel_viewed(cur, conn, channel_id):
    cur.execute(f"update channels set mentions = 0 where channel_id = '{channel_id}';")
    conn.commit()


def increment_channel_mention_count(cur, conn, channel_id):
    cur.execute(f"update channels set mentions = mentions + 1 where channel_id = '{channel_id}';")
    conn.commit()


async def my_event_handler(message):
    message = message.encode("ascii", errors="ignore")
    message = json.loads(message)
    print(message)
    conn = sqlite3.connect(db_loc)
    cur = conn.cursor()
    global user_id
    event = message.get("event", False)
    if not event:
        conn.close()
        return True

    if event == "hello":
        user_id = message["broadcast"]["user_id"]
        conn.close()
        return True

    channel_id = message.get("data", {}).get("channel_id", "")
    channel_id = channel_id or message.get("broadcast", {}).get("channel_id", "")
    if channel_id:
        create_channel_if_not_exists(cur, conn, channel_id)
    else:
        conn.close()
        return True

    if event == "channel_viewed":
        mark_channel_viewed(cur, conn, channel_id)
    elif event == "posted":
        if isinstance(message["data"]["post"], str):
            message["data"]["post"] = json.loads(message["data"]["post"])
        sender_id = message["data"]["post"]["user_id"]
        if sender_id == user_id:
            mark_channel_viewed(cur, conn, channel_id)
        else:
            mentions = message.get("data", {}).get("mentions", []) or []
            omitted_users = message.get("broadcast", {}).get("omit_users", []) or []
            if user_id in mentions and user_id not in omitted_users:
                increment_channel_mention_count(cur, conn, channel_id)
    conn.close()


with open (stdout_loc, "w+") as stdout:

    with open (stderr_loc, "w+") as stderr:

        with daemon.DaemonContext(stdout=stdout, stderr=stderr):

            d = Driver(options=options)

            d.login()

            d.init_websocket(my_event_handler, websocket_cls=CustomWebsocket)
