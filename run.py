from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from time import sleep

import asyncio
from requests import Session
from beam_interactive import start
from beam_interactive import proto
from math import copysign


browser = webdriver.Firefox()
global game_elem

path = "https://beam.pro/api/v1"
auth = {
    "username": "USERNAME",
    "password": "PASSWORD"
}

threshold = 0.8  # the percent of viewers required to take an action

joy_to_dir = [
    {
        1:  "RIGHT",
        -1: "LEFT"
    },
    {
        1:  "DOWN",
        -1: "UP"
    }
]


def load_game(browser):
    print("Loading browser...")
    sleep(1)  # To allow the browser to start basic processes.
    print("Loaded!")

    browser.get("git.io/2048")

    global game_elem
    game_elem = browser.find_element_by_class_name("game-container")


def login(session, username, password):
    """Log into the Beam servers via the API."""
    auth = dict(username=username, password=password)
    return session.post(path + "/users/login", auth).json()


def get_tetris(session, channel):
    """Retrieve interactive connection information."""
    return session.get(path + "/tetris/{id}/robot".format(id=channel)).json()


def on_error(error, conn):
    print('Oh no, there was an error!')
    print(error.message)


def progress(target, code, progress):
    update = proto.ProgressUpdate()
    prog = update.progress.add()
    prog.target = prog.__getattribute__(target)
    prog.code = code
    prog.progress = progress
    return update


def on_report(report, conn):
    keys = list()
    updates = list()

    for joystick in report.joystick:
        if abs(joystick.info.mean) > threshold:
            d = joy_to_dir[joystick.axis][copysign(1, joystick.info.mean)]
            keys.append(d)
            update = progress(
                "JOYSTICK",
                joystick.axis,
                min(0.999, abs(joystick.info.mean / threshold))
            )
        else:
            update = progress("JOYSTICK", joystick.axis, 0)
            updates.append(update)

    for update in updates:
        conn.send(update)

    for key in keys:
        print("SENDING KEYPRESS:", key)
        game_elem.send_keys(Keys().__getattribute__(key))


loop = asyncio.get_event_loop()


@asyncio.coroutine
def connect():
    session = Session()
    channel_id = login(session, **auth)['channel']['id']
    print("channel_id")

    data = get_tetris(session, channel_id)

    conn = yield from start(data['address'], channel_id, data['key'], loop)

    handlers = {
        proto.id.error: on_error,
        proto.id.report: on_report
    }

    while (yield from conn.wait_message()):
        decoded, packet_bytes = conn.get_packet()
        packet_id = proto.id.get_packet_id(decoded)

        if decoded is None:
            print('We got a bunch of unknown bytes.')
            print(packet_id)
        elif packet_id in handlers:
            handlers[packet_id](decoded, conn)
        else:
            print("We got packet {} but didn't handle it!".format(packet_id))

    conn.close()


try:
    load_game(browser)
    loop.run_until_complete(connect())
except KeyboardInterrupt:
    print("Disconnected. All lasers are now off. Have a nice day!")
finally:
    loop.close()
