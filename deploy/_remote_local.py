import sys, paramiko
HOST, PORT, USER, PASSWORD = "203.117.117.196", 2333, "root", "njupt@NJ-5353"
def client():
    c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30,
              banner_timeout=30, auth_timeout=30); return c
def run(cmd, timeout=900):
    c = client()
    try:
        _i,o,e = c.exec_command(cmd, timeout=timeout)
        return o.channel.recv_exit_status(), o.read().decode("utf-8","replace"), e.read().decode("utf-8","replace")
    finally: c.close()
def put(l, r):
    c = client()
    try:
        s = c.open_sftp(); s.put(l, r); s.close()
    finally: c.close()
if __name__ == "__main__":
    if sys.argv[1] == "put":
        put(sys.argv[2], sys.argv[3]); print("uploaded")
    else:
        code,o,e = run(sys.argv[1]); print("EXIT",code); print(o)
        if e: print("STDERR:", e)
