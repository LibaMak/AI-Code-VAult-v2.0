import subprocess
import threading
import time
import webbrowser
import http.server
import socketserver
import os
import sys

PORT_STATIC = 8000
PORT_STREAMLIT = 8501

def serve_static():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT_STATIC), Handler) as httpd:
        print(f"🔥 Zero-Latency Landing Portal hosted at http://localhost:{PORT_STATIC}")
        httpd.serve_forever()

def main():
    print("Initializing Enterprise Architecture...")
    
    # 1. Start the static zero-latency frontend
    static_thread = threading.Thread(target=serve_static, daemon=True)
    static_thread.start()

    # 2. Launch the Streamlit backend on standard 8501
    print(f"🚀 Booting up Streamlit Backend on Port {PORT_STREAMLIT}...")
    streamlit_process = subprocess.Popen([
        sys.executable, "-m", "streamlit", "run", "streamlit_app.py",
        f"--server.port={PORT_STREAMLIT}",
        "--server.headless=true"
    ])

    # Give Streamlit a second to warm up its sockets
    time.sleep(2)
    
    # 3. Open the static entry point for the user
    url = f"http://localhost:{PORT_STATIC}/index.html"
    print(f"🌐 Opening Browser exactly at {url}")
    webbrowser.open(url)

    # 4. Keep alive blocking loop
    try:
        streamlit_process.wait()
    except KeyboardInterrupt:
        print("\nTerminating architecture gracefully...")
        streamlit_process.terminate()

if __name__ == "__main__":
    main()
