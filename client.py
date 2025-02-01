import socketio
import pyautogui
import base64
import io
import time

# 🔗 Backend server URL (Update this for deployment)
SERVER_URL = 'https://whoareyouman.pythonanywhere.com'

# Create a Socket.IO client instance with WebSocket transport
sio = socketio.Client(reconnection=True, reconnection_attempts=9999, reconnection_delay=3, transports=['websocket'])

@sio.event
def connect():
    print("✅ Connected to server")
    sio.emit('init', {'role': 'client'})

@sio.event
def disconnect():
    print("❌ Disconnected from server. Attempting to reconnect...")

def attempt_reconnect():
    """ Tries to reconnect with exponential backoff """
    retry_delay = 3  # Start with 3 seconds
    max_delay = 60   # Cap at 60 seconds

    while not sio.connected:
        try:
            print(f"🔄 Trying to reconnect... (Waiting {retry_delay}s)")
            sio.connect(SERVER_URL, wait=True, transports=['websocket'])  # 🔄 Force WebSocket
            print("✅ Reconnected successfully!")
            return
        except Exception as e:
            print(f"⚠️ Reconnect failed: {e}")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_delay)  # ⏳ Exponential backoff

def capture_and_send(interval=2, quality=30):
    """
    Captures the screen and sends frames with specified interval and quality.
    - interval: Time (seconds) between frames
    - quality: JPEG quality (1-100); lower means more compression
    """
    print("📡 Sending screen frames...")

    while True:
        if not sio.connected:
            print("🚫 Connection lost, attempting to reconnect...")
            attempt_reconnect()

        try:
            # Capture the screen
            screenshot = pyautogui.screenshot()

            buffer = io.BytesIO()
            screenshot.save(buffer, format='JPEG', quality=quality)  # Save as JPEG for compression

            # Encode the screenshot to Base64
            img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')

            # Emit the frame to the server
            sio.emit('frame', {'image': img_str})
            print("🖥️ Frame sent")

            time.sleep(interval)  # Adjust frame rate
        except Exception as e:
            print(f"⚠️ Error capturing/sending frame: {e}")

if __name__ == '__main__':
    attempt_reconnect()  # Ensure connection at startup
    capture_and_send(interval=1, quality=30)  # Adjust as needed
