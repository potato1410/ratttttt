# client/client.py
import socket
import threading
import pyautogui
import tkinter as tk
from tkinter import messagebox
import io
from PIL import ImageGrab
import time

SERVER_HOST = '169.254.27.190'  # Replace with your PC's IP
SERVER_PORT = 9999
SCREEN_UPDATE_INTERVAL = 0.2  # seconds between screen updates

def capture_screen():
    screen = ImageGrab.grab()
    buffer = io.BytesIO()
    screen.save(buffer, format='JPEG', quality=50)  # Lower quality for faster transmission
    return buffer.getvalue()

def send_screen_continuously(s):
    while True:
        try:
            img = capture_screen()
            s.sendall(len(img).to_bytes(8, 'big') + img)
            time.sleep(SCREEN_UPDATE_INTERVAL)
        except:
            break

def listen():
    s = socket.socket()
    s.connect((SERVER_HOST, SERVER_PORT))
    
    # Start sending screen updates
    screen_thread = threading.Thread(target=send_screen_continuously, args=(s,), daemon=True)
    screen_thread.start()
    
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
        except Exception as e:
            print(f"Error: {e}")
            break

def popup(message):
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo("Message", message)
    root.destroy()

if __name__ == "__main__":
    listen()