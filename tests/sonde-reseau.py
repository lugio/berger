"""Ce qui doit rester FERMÉ même quand la porte du courtier est ouverte : Internet, D-Bus (trousseau),
la commande de Herdr (qui pilote tous les panneaux), le socket de Docker. Usage : python3 sonde-reseau.py"""
import os, socket
H = os.path.expanduser("~"); ko = 0
def unix(p):
    try: s = socket.socket(socket.AF_UNIX); s.connect(p); return "OUVERT"
    except OSError as e: return f"fermé ({e.errno})"
def tcp(h, port):
    try: socket.create_connection((h, port), timeout=4); return "OUVERT"
    except OSError as e: return f"fermé ({type(e).__name__})"
for nom, r in (("Internet 1.1.1.1:443", tcp("1.1.1.1", 443)), ("Internet par nom (example.com:443)", tcp("example.com", 443)),
               ("D-Bus de session (trousseau)", unix(f"/run/user/{os.getuid()}/bus")),
               ("Herdr (pilotage des panneaux)", unix(f"{H}/.config/herdr/herdr.sock")),
               ("Docker", unix("/run/docker.sock"))):
    ok = r != "OUVERT"; ko += not ok; print("ok   " if ok else "ÉCHEC", nom, "→", r)
print("----", ko, "échec(s)")
