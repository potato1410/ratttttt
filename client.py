# client/client.py
import socket
import threading
import pyautogui
import tkinter as tk
from tkinter import messagebox, simpledialog
import io
from PIL import ImageGrab
import time
import requests
import json
import os
import sys

# Configuration
SERVER_HOST = '169.254.27.190'  # Replace with your server domain or IP
SERVER_PORT = 9999
STUN_SERVER = 'stun.l.google.com:19302'  # Google's public STUN server
SCREEN_UPDATE_INTERVAL = 0.2  # seconds between screen updates
CONFIG_FILE = 'client_config.json'

def get_public_ip():
    """Get the client's public IP address"""
    try:
        response = requests.get('https://api.ipify.org?format=json')
        return response.json()['ip']
    except:
        return "Unknown"

def load_config():
    """Load configuration from file"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    
    # Default config
    return {
        "server_host": SERVER_HOST,
        "server_port": SERVER_PORT,
        "client_id": "",
        "password": ""
    }

def save_config(config):
    """Save configuration to file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def capture_screen():
    """Capture the screen and return it as JPEG bytes"""
    screen = ImageGrab.grab()
    buffer = io.BytesIO()
    screen.save(buffer, format='JPEG', quality=50)  # Lower quality for faster transmission
    return buffer.getvalue()

def send_screen_continuously(s):
    """Send screen updates continuously"""
    while True:
        try:
            img = capture_screen()
            s.sendall(len(img).to_bytes(8, 'big') + img)
            time.sleep(SCREEN_UPDATE_INTERVAL)
        except:
            break

def popup(message):
    """Display a popup message"""
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo("Message", message)
    root.destroy()

def listen_for_commands(s):
    """Listen for and execute commands from the server"""
    while True:
        try:
            command = s.recv(1024).decode()
            if command.startswith('move'):
                _, x, y = command.split()
                pyautogui.moveTo(int(x), int(y))
            elif command.startswith('click'):
                pyautogui.click()
            elif command.startswith('rightclick'):
                pyautogui.rightClick()
            elif command.startswith('doubleclick'):
                pyautogui.doubleClick()
            elif command.startswith('key'):
                _, key = command.split(' ', 1)
                pyautogui.press(key)
            elif command.startswith('type'):
                _, text = command.split(' ', 1)
                pyautogui.write(text)
            elif command.startswith('msg'):
                _, msg = command.split(" ", 1)
                threading.Thread(target=popup, args=(msg,), daemon=True).start()
            elif command == 'ping':
                s.send('pong'.encode())
        except Exception as e:
            print(f"Error: {e}")
            break

def connect_to_server():
    """Connect to the control server"""
    config = load_config()
    
    # GUI setup for connection
    connect_root = tk.Tk()
    connect_root.title("Remote Access Client")
    connect_root.geometry("400x300")
    
    # Connection info
    frame = tk.Frame(connect_root)
    frame.pack(pady=10)
    
    tk.Label(frame, text="Server:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    server_entry = tk.Entry(frame, width=30)
    server_entry.insert(0, config["server_host"])
    server_entry.grid(row=0, column=1, padx=5, pady=5)
    
    tk.Label(frame, text="Port:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    port_entry = tk.Entry(frame, width=30)
    port_entry.insert(0, str(config["server_port"]))
    port_entry.grid(row=1, column=1, padx=5, pady=5)
    
    tk.Label(frame, text="Client ID:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
    id_entry = tk.Entry(frame, width=30)
    id_entry.insert(0, config["client_id"])
    id_entry.grid(row=2, column=1, padx=5, pady=5)
    
    tk.Label(frame, text="Password:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
    pass_entry = tk.Entry(frame, width=30, show="*")
    pass_entry.insert(0, config["password"])
    pass_entry.grid(row=3, column=1, padx=5, pady=5)
    
    # Status
    status_var = tk.StringVar(value=f"Public IP: {get_public_ip()}")
    status_label = tk.Label(connect_root, textvariable=status_var, anchor="w")
    status_label.pack(fill=tk.X, padx=10, pady=5)
    
    connection = {"socket": None}
    
    def start_connection():
        """Attempt connection with current settings"""
        try:
            # Update config
            config["server_host"] = server_entry.get()
            config["server_port"] = int(port_entry.get())
            config["client_id"] = id_entry.get()
            config["password"] = pass_entry.get()
            save_config(config)
            
            # Connect
            status_var.set("Connecting...")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((config["server_host"], config["server_port"]))
            
            # Send authentication
            auth_data = f"AUTH:{config['client_id']}:{config['password']}".encode()
            s.send(auth_data)
            
            # Wait for auth response
            response = s.recv(1024).decode()
            if response == "AUTH_OK":
                status_var.set("Connected! Starting remote access...")
                connection["socket"] = s
                connect_root.after(1000, connect_root.destroy)
            else:
                status_var.set(f"Authentication failed: {response}")
                s.close()
                
        except Exception as e:
            status_var.set(f"Connection error: {e}")
    
    connect_button = tk.Button(connect_root, text="Connect", command=start_connection)
    connect_button.pack(pady=10)
    
    connect_root.mainloop()
    return connection["socket"]

def main():
    """Main entry point"""
    print("Starting Remote Access Client...")
    
    # Connect to server
    client_socket = connect_to_server()
    if not client_socket:
        print("Connection failed")
        return
    
    print("Connected - starting remote access service")
    
    # Start command listener
    cmd_thread = threading.Thread(target=listen_for_commands, args=(client_socket,), daemon=True)
    cmd_thread.start()
    
    # Start screen sender
    screen_thread = threading.Thread(target=send_screen_continuously, args=(client_socket,), daemon=True)
    screen_thread.start()
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Client shutting down")
    finally:
        if client_socket:
            client_socket.close()

if __name__ == "__main__":
    main()
