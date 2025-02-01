import os
import time
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
from flask_socketio import SocketIO, emit, join_room
from PIL import Image
import base64
import io

# Initialize Flask & SocketIO with WebSocket only (using default transport)
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# Default Mode
MODE = "live"

# Folder to store screenshots
SCREENSHOT_FOLDER = "screenshots"
os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)

# Track last screenshot timestamp
last_screenshot_time = 0

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

# Route to serve screenshot images
@app.route("/screenshots/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(SCREENSHOT_FOLDER, filename)

# Gallery route: list all screenshots with a delete button for each
@app.route("/gallery")
def gallery():
    images = os.listdir(SCREENSHOT_FOLDER)
    # Optionally, sort images (e.g., newest first)
    images.sort(reverse=True)
    return render_template("gallery.html", images=images)

# Route to delete an image; using POST to avoid accidental deletions
@app.route("/delete_image", methods=["POST"])
def delete_image():
    filename = request.form.get("filename")
    if filename:
        file_path = os.path.join(SCREENSHOT_FOLDER, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"✅ Deleted image: {filename}")
            return jsonify({"status": "success"}), 200
        else:
            return jsonify({"status": "error", "message": "File not found"}), 404
    return jsonify({"status": "error", "message": "No filename provided"}), 400

@socketio.on('connect')
def on_connect():
    print("✅ Client connected")

@socketio.on('disconnect')
def on_disconnect():
    print("❌ Client disconnected")

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
        # Live mode: broadcast the frame to all viewers
        emit("frame", data, room="viewers")
    elif MODE == "screenshot":
        # Screenshot mode: save one image every 60 seconds
        current_time = time.time()
        if current_time - last_screenshot_time >= 60:
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
    print(f"🔥 Server running in {MODE.upper()} mode on http://0.0.0.0:8000")
    socketio.run(app, host='0.0.0.0', port=8000, debug=True)
