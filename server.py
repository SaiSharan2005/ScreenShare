import os
import time
import threading
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from PIL import Image
import base64
import io

# Initialize Flask & SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

# ⛔ Force long polling to work on PythonAnywhere
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*", logger=True, engineio_logger=True)

# 🔥 Default Mode
MODE = "live"

# Folder to store screenshots
SCREENSHOT_FOLDER = "screenshots"
if not os.path.exists(SCREENSHOT_FOLDER):
    os.makedirs(SCREENSHOT_FOLDER)

# 🕒 Track last screenshot timestamp
last_screenshot_time = 0  # Store the last screenshot time


@app.route("/")
def index():
    """ Renders the main page """
    return render_template("index.html")


@app.route("/set_mode", methods=["GET"])
def set_mode():
    """ Change the mode dynamically via a GET request """
    global MODE
    new_mode = request.args.get("mode")

    if new_mode in ["live", "screenshot"]:
        MODE = new_mode
        print(f"✅ Mode changed to: {MODE.upper()}")
        return jsonify({"status": "success", "mode": MODE}), 200
    else:
        return jsonify({"status": "error", "message": "Invalid mode. Use 'live' or 'screenshot'"}), 400


@socketio.on('init')
def handle_init(data):
    """ Handles client connection and assigns roles """
    role = data.get('role')
    if role == 'viewer':
        join_room('viewers')
        print("👀 Viewer connected")
    elif role == 'client':
        print("📡 Screen-sender client connected")
    else:
        print("❌ Unknown role:", role)


@socketio.on("frame")
def handle_frame(data):
    """ Handles incoming frames from the client """
    global last_screenshot_time

    if MODE == "live":
        # 📡 LIVE Mode: Broadcast to all viewers
        emit("frame", data, room="viewers")

    elif MODE == "screenshot":
        # 📸 SCREENSHOT Mode: Save the frame every 60 seconds
        current_time = time.time()
        if current_time - last_screenshot_time >= 60:  # Only save if 60 sec passed
            save_screenshot(data['image'])
            last_screenshot_time = current_time


def save_screenshot(image_base64):
    """ Saves received frame as a screenshot """
    try:
        img_data = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(img_data))
        filename = f"{SCREENSHOT_FOLDER}/screenshot_{int(time.time())}.png"
        img.save(filename)
        print(f"✅ Screenshot saved: {filename}")
    except Exception as e:
        print(f"❌ Error saving screenshot: {e}")


if __name__ == "__main__":
    print(f"🔥 Server running in {MODE.upper()} mode on http://0.0.0.0:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
