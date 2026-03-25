import os
import subprocess
import time
import psycopg2
import psycopg2.extras
from contextlib import contextmanager

# --- DB 설정 (환경변수 우선, 없으면 기본값) ---
DB_HOST = os.getenv("DB_HOST", "snowman-rds.cr8kguie4i7g.ap-northeast-2.rds.amazonaws.com")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "!postgres01")

# SSH 터널 사용 여부 (로컬 개발용, EC2에서는 False)
USE_SSH_TUNNEL = os.getenv("USE_SSH_TUNNEL", "true").lower() == "true"

# --- SSH 터널 설정 (로컬 전용) ---
SSH_HOST = os.getenv("SSH_HOST", "54.116.93.66")
SSH_USER = os.getenv("SSH_USER", "ec2-user")
SSH_KEY  = os.getenv("SSH_KEY", os.path.join(os.path.expanduser("~"), "Desktop", "DX_go", "snowman-pemkey.pem"))
LOCAL_PORT = 15432

_tunnel_proc = None


def _is_port_open(port):
    """로컬 포트가 열려있는지 확인."""
    import socket
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=1)
        s.close()
        return True
    except (ConnectionRefusedError, OSError):
        return False


def start_tunnel():
    """SSH 터널을 subprocess로 시작. 끊어졌으면 재시작."""
    global _tunnel_proc

    if not USE_SSH_TUNNEL:
        return

    if _tunnel_proc and _tunnel_proc.poll() is None and _is_port_open(LOCAL_PORT):
        return

    if _tunnel_proc:
        try:
            _tunnel_proc.terminate()
            _tunnel_proc.wait(timeout=3)
        except Exception:
            pass

    cmd = [
        "ssh", "-i", SSH_KEY,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-N", "-L", f"{LOCAL_PORT}:{DB_HOST}:{DB_PORT}",
        f"{SSH_USER}@{SSH_HOST}",
    ]
    _tunnel_proc = subprocess.Popen(cmd)
    for _ in range(20):
        time.sleep(0.5)
        if _is_port_open(LOCAL_PORT):
            break
    print(f"[db] SSH tunnel started -> localhost:{LOCAL_PORT}")


def stop_tunnel():
    """SSH 터널 종료."""
    global _tunnel_proc
    if _tunnel_proc and _tunnel_proc.poll() is None:
        _tunnel_proc.terminate()
        _tunnel_proc.wait()
        print("[db] SSH tunnel stopped")
        _tunnel_proc = None


def get_connection():
    """PostgreSQL 연결을 반환."""
    if USE_SSH_TUNNEL:
        start_tunnel()
        host = "127.0.0.1"
        port = LOCAL_PORT
    else:
        host = DB_HOST
        port = DB_PORT

    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    conn.autocommit = False
    return conn


@contextmanager
def get_db():
    """DB 연결 context manager — commit/rollback 자동 처리."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
