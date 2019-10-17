import time
import signal
import subprocess


def test_app():
    p = subprocess.Popen(
        'declaracad', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for i in range(20):
        time.sleep(1)
        if i == 10:
            p.send_signal(signal.SIGINT)
        p.poll()
        if p.returncode is not None:
            break
    stdout, stderr = p.communicate()
    #for line in stdout.split(b"\n"):
    #    print(stdout)
    assert b'Workbench stopped' in stdout
