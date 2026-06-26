from __future__ import annotations

import socket

import uvicorn

from app.config import APP_VERSION, settings


def local_lan_ips() -> list[str]:
    ips: set[str] = set()
    try:
        hostname = socket.gethostname()
        for item in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            ip = item[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass

    # UDP trick to discover the primary outbound LAN IP without sending traffic.
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        if not ip.startswith("127."):
            ips.add(ip)
    except OSError:
        pass

    return sorted(ips)


def print_startup_urls() -> None:
    host = settings.host
    port = settings.port
    print(f"\nPolymarket OP Console v{APP_VERSION}")
    print(f"Binding host: {host}")
    print("Security:     Auth required; security headers enabled; configurable ALLOWED_HOSTS")
    print(f"Local URL:    http://127.0.0.1:{port}")
    if host in {"0.0.0.0", "::"}:
        ips = local_lan_ips()
        if ips:
            print("LAN URLs:")
            for ip in ips:
                print(f"  http://{ip}:{port}")
        else:
            print("LAN URL:      Use your machine's LAN IP, for example http://<your-lan-ip>:%s" % port)
    else:
        print("LAN access disabled unless HOST=0.0.0.0 or HOST=<LAN IP>.")
    if "*" in settings.allowed_hosts:
        print("Allowed hosts: * (LAN-friendly; set ALLOWED_HOSTS for stricter deployment)")
    else:
        print("Allowed hosts: " + ", ".join(settings.allowed_hosts))
    print("Press Ctrl+C to stop.\n")


if __name__ == "__main__":
    print_startup_urls()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.reload)
