import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class AlertWebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/alerts":
            self.send_error(404, "Not Found")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        print("\n=== Alertmanager notification ===")
        print(json.dumps(payload, indent=2))
        print("=================================\n", flush=True)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")


def main():
    server = HTTPServer(("0.0.0.0", 8080), AlertWebhookHandler)

    print("Webhook receiver listening on port 8080", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
