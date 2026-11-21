from __future__ import annotations
import os, threading, time, webbrowser, socket
from pathlib import Path
from dotenv import load_dotenv
import uvicorn
ROOT=Path(__file__).resolve().parent
load_dotenv(ROOT/'.env')
host=os.getenv('APP_HOST','127.0.0.1')
base_port=int(os.getenv('APP_PORT','8765'))
def available(port):
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
        try: sock.bind((host,port)); return True
        except OSError: return False
def open_browser(port):
    time.sleep(1.5)
    webbrowser.open(f'http://{host}:{port}')
if __name__=='__main__':
    port=base_port
    while not available(port) and port<base_port+30: port+=1
    if port>=base_port+30:
        raise SystemExit('No available local port found in configured range. Close another app or adjust APP_PORT in .env.')
    if port!=base_port: print(f'Port {base_port} is busy; Evident Engine will use {port}.')
    threading.Thread(target=open_browser,args=(port,),daemon=True).start()
    uvicorn.run('app:app',host=host,port=port,reload=False)
