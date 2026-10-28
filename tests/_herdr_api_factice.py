"""Adaptateur socket des anciens faux Herdr : corps sur stdin, jamais dans leurs argv."""
import atexit
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading


def installer(env):
    chemin = str(Path(env['FAUX_HERDR']) / 'api.sock')
    so = None
    try:
        so = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)            # interdit dans certains bacs : même NON JOUÉ
        so.bind(chemin); so.listen()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe: probe.connect(chemin)
    except OSError:
        if so is not None: so.close()
        print('NON JOUÉ : API Herdr factice (AF_UNIX indisponible dans ce bac)')
        raise SystemExit(0)
    env['BERGER_HERDR_SOCKET'] = chemin
    atexit.register(so.close)

    def traiter(conn):
        with conn:
            try:
                with conn.makefile('rb') as flux: brut = flux.readline(1048577)
                if not brut: return
                req = json.loads(brut)
                if req['method'] != 'agent.prompt': raise ValueError('méthode inattendue')
                r = subprocess.run([env['BERGER_HERDR'], 'agent', 'prompt'],
                                   input=json.dumps(req['params']), env=env, text=True,
                                   capture_output=True, timeout=15)
                rep = json.loads(r.stdout) if r.returncode == 0 else {'error': {'code': 'refus'}}
                rep['id'] = req['id']
            except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
                rep = {'id': 'berger', 'error': {'code': 'refus'}}
            try: conn.sendall((json.dumps(rep)+'\n').encode())
            except OSError: pass

    def servir():
        while True:
            try: conn, _ = so.accept()
            except OSError: return
            threading.Thread(target=traiter, args=(conn,), daemon=True).start()
    threading.Thread(target=servir, daemon=True).start()
    return env
