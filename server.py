# import os
# import time
# from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
# from flask_socketio import SocketIO, emit, join_room
# from PIL import Image
# import base64
# import io

# # Initialize Flask & SocketIO with WebSocket only (using default transport)
# app = Flask(__name__)
# app.config['SECRET_KEY'] = 'secret!'
# socketio = SocketIO(app, cors_allowed_origins="*")

# # Default Mode
# MODE = "live"

# # Folder to store screenshots
# SCREENSHOT_FOLDER = "screenshots"
# os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)

# # Track last screenshot timestamp
# last_screenshot_time = 0

# @app.route("/test")
# def index():
#     """ Renders the main page """
#     return render_template("index.html")

# @app.route("/set_mode", methods=["GET"])
# def set_mode():
#     """ Change the mode dynamically via a GET request """
#     global MODE
#     new_mode = request.args.get("mode")
#     if new_mode in ["live", "screenshot"]:
#         MODE = new_mode
#         print(f"✅ Mode changed to: {MODE.upper()}")
#         return jsonify({"status": "success", "mode": MODE}), 200
#     else:
#         return jsonify({"status": "error", "message": "Invalid mode. Use 'live' or 'screenshot'"}), 400

# # Route to serve screenshot images
# @app.route("/screenshots/<path:filename>")
# def uploaded_file(filename):
#     return send_from_directory(SCREENSHOT_FOLDER, filename)

# # Gallery route: list all screenshots with a delete button for each
# @app.route("/gallery")
# def gallery():
#     images = os.listdir(SCREENSHOT_FOLDER)
#     # Optionally, sort images (e.g., newest first)
#     images.sort(reverse=True)
#     return render_template("gallery.html", images=images)

# # Route to delete an image; using POST to avoid accidental deletions
# @app.route("/delete_image", methods=["POST"])
# def delete_image():
#     filename = request.form.get("filename")
#     if filename:
#         file_path = os.path.join(SCREENSHOT_FOLDER, filename)
#         if os.path.exists(file_path):
#             os.remove(file_path)
#             print(f"✅ Deleted image: {filename}")
#             return jsonify({"status": "success"}), 200
#         else:
#             return jsonify({"status": "error", "message": "File not found"}), 404
#     return jsonify({"status": "error", "message": "No filename provided"}), 400

# @socketio.on('connect')
# def on_connect():
#     print("✅ Client connected")

# @socketio.on('disconnect')
# def on_disconnect():
#     print("❌ Client disconnected")

# @socketio.on('init')
# def handle_init(data):
#     """ Handles client connection and assigns roles """
#     role = data.get('role')
#     if role == 'viewer':
#         join_room('viewers')
#         print("👀 Viewer connected")
#     elif role == 'client':
#         print("📡 Screen-sender client connected")
#     else:
#         print("❌ Unknown role:", role)

# @socketio.on("frame")
# def handle_frame(data):
#     """ Handles incoming frames from the client """
#     global last_screenshot_time
#     if MODE == "live":
#         # Live mode: broadcast the frame to all viewers
#         emit("frame", data, room="viewers")
#     elif MODE == "screenshot":
#         # Screenshot mode: save one image every 60 seconds
#         current_time = time.time()
#         if current_time - last_screenshot_time >= 60:
#             save_screenshot(data['image'])
#             last_screenshot_time = current_time

# def save_screenshot(image_base64):
#     """ Saves received frame as a screenshot """
#     try:
#         img_data = base64.b64decode(image_base64)
#         img = Image.open(io.BytesIO(img_data))
#         filename = f"{SCREENSHOT_FOLDER}/screenshot_{int(time.time())}.png"
#         img.save(filename)
#         print(f"✅ Screenshot saved: {filename}")
#     except Exception as e:
#         print(f"❌ Error saving screenshot: {e}")

# if __name__ == "__main__":
#     print(f"🔥 Server running in {MODE.upper()} mode on http://0.0.0.0:8000")
#     socketio.run(app, host='0.0.0.0', port=8000, debug=True)


# server.py
import os
import time
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from threading import Lock

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET", "change_me")
socketio = SocketIO(app, cors_allowed_origins="*", ping_interval=10, ping_timeout=30)

# Pre-shared token for demo. In production use per-client tokens or JWTs.
SERVER_TOKEN = os.environ.get("SERVER_TOKEN", "super_secret_token")

# clients: client_id -> {sid, token, last_seen, controller_sid}
clients = {}
clients_lock = Lock()

@app.route("/")
def index():
    return render_template("viewer.html")  # Simple control UI

@app.route("/clients")
def list_clients():
    with clients_lock:
        return jsonify({cid: {"last_seen": info["last_seen"], "connected": True} for cid, info in clients.items()})

# ---------- Socket.IO events ----------

@socketio.on("connect")
def on_connect():
    print("Socket connected:", request.sid)

@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    print("Socket disconnected:", sid)
    with clients_lock:
        # Remove any client records matching this sid
        to_remove = [cid for cid, info in clients.items() if info["sid"] == sid]
        for cid in to_remove:
            del clients[cid]
            print(f"Client {cid} removed (disconnected)")

@socketio.on("init")
def on_init(data):
    """
    data:
      - role: "client" or "viewer"
      - client_id (for client)
      - token
    """
    role = data.get("role")
    token = data.get("token")
    sid = request.sid

    # Simple authentication: token must match SERVER_TOKEN for both client and viewer
    if token != SERVER_TOKEN:
        emit("auth_error", {"message": "invalid token"})
        socketio.disconnect(sid)
        return

    if role == "client":
        client_id = data.get("client_id")
        if not client_id:
            emit("auth_error", {"message": "client_id required"})
            socketio.disconnect(sid)
            return
        with clients_lock:
            clients[client_id] = {"sid": sid, "token": token, "last_seen": time.time(), "controller_sid": None}
        join_room(f"client:{client_id}")
        print(f"Registered client {client_id} (sid={sid})")
        emit("init_ack", {"status": "ok", "client_id": client_id})
    elif role == "viewer":
        join_room("viewers")
        emit("init_ack", {"status": "ok"})
        print(f"Viewer connected (sid={sid})")
    else:
        emit("auth_error", {"message": "unknown role"})
        socketio.disconnect(sid)

@socketio.on("ping_client")
def on_ping(data):
    client_id = data.get("client_id")
    with clients_lock:
        if client_id in clients:
            clients[client_id]["last_seen"] = time.time()
            emit("pong", {"client_id": client_id}, room=clients[client_id]["sid"])
            return jsonify({"status": "ok"})
    emit("error", {"message": "client not found"})

# Viewer requests control of a client
@socketio.on("request_control")
def on_request_control(data):
    client_id = data.get("client_id")
    viewer_sid = request.sid
    with clients_lock:
        if client_id not in clients:
            emit("control_response", {"status": "error", "message": "client not found"})
            return
        client_sid = clients[client_id]["sid"]
    # Send request to client. client will reply with control_response event
    emit("control_request", {"viewer_sid": viewer_sid}, room=client_sid)
    emit("control_response", {"status": "pending", "message": "request_sent"})

# Client answers control request
@socketio.on("control_response")
def on_control_response(data):
    """
    data: { viewer_sid: <sid>, accepted: True/False }
    """
    viewer_sid = data.get("viewer_sid")
    accepted = data.get("accepted", False)
    # Find client_id for this sid
    sid = request.sid
    client_id = None
    with clients_lock:
        for cid, info in clients.items():
            if info["sid"] == sid:
                client_id = cid
                break
        if not client_id:
            emit("error", {"message": "unknown client"})
            return

        if accepted:
            clients[client_id]["controller_sid"] = viewer_sid
            emit("control_granted", {"client_id": client_id}, room=viewer_sid)
            print(f"Control granted for viewer {viewer_sid} on client {client_id}")
        else:
            emit("control_denied", {"client_id": client_id}, room=viewer_sid)
            print(f"Control denied for viewer {viewer_sid} on client {client_id}")

# Viewer sends control commands - server forwards to the client
@socketio.on("control_cmd")
def on_control_cmd(data):
    """
    From viewer:
      data: { client_id: ..., cmd: "move", args: {...} }
    Server verifies the viewer is controller then forwards to client.
    """
    viewer_sid = request.sid
    client_id = data.get("client_id")
    cmd = data.get("cmd")
    args = data.get("args", {})

    if not client_id or not cmd:
        emit("error", {"message": "invalid control command"})
        return

    with clients_lock:
        info = clients.get(client_id)
        if not info or info.get("controller_sid") != viewer_sid:
            emit("error", {"message": "not authorized or client offline"})
            return
        client_sid = info["sid"]

    # Forward command to client
    emit("control_cmd", {"cmd": cmd, "args": args}, room=client_sid)

# Viewer can release control
@socketio.on("release_control")
def on_release_control(data):
    client_id = data.get("client_id")
    viewer_sid = request.sid
    with clients_lock:
        info = clients.get(client_id)
        if info and info.get("controller_sid") == viewer_sid:
            info["controller_sid"] = None
            emit("control_released", {"client_id": client_id}, room=info["sid"])
            emit("released", {"status": "ok"})
            print(f"Viewer {viewer_sid} released control of {client_id}")

if __name__ == "__main__":
    print("Starting server on :8000 (development)")
    socketio.run(app, host="0.0.0.0", port=8000, debug=True)
