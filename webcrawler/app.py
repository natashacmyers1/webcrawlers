from http.server import BaseHTTPRequestHandler, HTTPServer
import os

PORT = int(os.getenv("PORT", "8000"))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Hello from Python in Docker \\xF0\\x9F\\x91\\x8B\\n")

def run():
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Server listening on {PORT}")
    server.serve_forever()

if __name__ == "__main__":
    run()
