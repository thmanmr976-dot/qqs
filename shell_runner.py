#!/usr/bin/env python3
"""Foreground supervisor. Its process group owns only this selected shell."""
import json
import os
import selectors
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

STOP=False

def request_stop(signum,frame):
    global STOP
    STOP=True


def members():
    group=os.getpgrp();result=[]
    for path in Path('/proc').iterdir():
        if not path.name.isdigit() or int(path.name)==os.getpid():continue
        try:
            fields=(path/'stat').read_text().rsplit(')',1)[1].split()
            if fields[0]!='Z' and int(fields[2])==group:result.append(int(path.name))
        except (OSError,ValueError,IndexError):pass
    return result


def client(command):
    return subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=2)


def has_surface(pids):
    try:
        def visible(value):
            if isinstance(value,dict):
                if value.get('pid') in pids and not value.get('hidden',False):
                    return bool(value.get('mapped',False) or (value.get('w',0)>0 and value.get('h',0)>0))
                return any(visible(child) for child in value.values())
            return isinstance(value,list) and any(visible(child) for child in value)
        for kind in ('layers','clients'):
            data=subprocess.run(['hyprctl','-j',kind],capture_output=True,text=True,timeout=1)
            if data.returncode==0 and visible(json.loads(data.stdout)):return True
    except (OSError,ValueError,subprocess.TimeoutExpired):pass
    return False


def main(spec):
    global STOP
    plan=json.loads(Path(spec).read_text());child=None;leave_children=False
    signal.signal(signal.SIGTERM,request_stop);signal.signal(signal.SIGINT,request_stop)
    command=plan['command'];backend=plan['backend']
    print('INFO: qqs backend: '+backend,flush=True)
    try:
        if backend=='eww':
            control=[command[0],'--config',plan['eww_config'],'--force-wayland','--no-daemonize']
            if client(control+['ping']).returncode==0:raise RuntimeError('An Eww instance already uses this configuration. Stop that instance first; qqs will not take ownership of it.')
        child=subprocess.Popen(command,cwd=plan['cwd'],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        os.set_blocking(child.stdout.fileno(),False)
        selector=selectors.DefaultSelector();selector.register(child.stdout,selectors.EVENT_READ)
        started=time.monotonic();ready=False;tail='';eww_open=False;last_ping=0;last_surface=0
        check_surface=plan.get('require_window') and os.environ.get('HYPRLAND_INSTANCE_SIGNATURE') and shutil.which('hyprctl')
        while not STOP:
            for key,_ in selector.select(.1):
                chunk=os.read(key.fileobj.fileno(),65536)
                if chunk:
                    sys.stdout.buffer.write(chunk);sys.stdout.buffer.flush();tail=(tail+chunk.decode(errors='replace'))[-64000:]
                else:selector.unregister(key.fileobj)
            code=child.poll()
            if code is not None and plan.get('transient') and (code==0 or code==1 and not any(word in tail.lower() for word in ('error','failed','not found','invalid'))):
                leave_children=True;return 0
            if code is not None and code!=0:raise RuntimeError(f'Shell launcher exited with code {code}.')
            if code==0 and not members():
                raise RuntimeError('Launcher exited without a running shell. Use a foreground command or a qqs-shell.json profile; detached daemons cannot be supervised safely.')
            if backend=='eww' and not eww_open and time.monotonic()-last_ping>.25:
                last_ping=time.monotonic()
                if client(control+['ping']).returncode==0:
                    result=client(control+['open-many',*plan['eww_windows']])
                    if result.returncode:raise RuntimeError('Eww could not open the selected windows: '+result.stdout)
                    eww_open=True
                elif time.monotonic()-started>8:raise RuntimeError('Eww daemon did not become reachable.')
            if not ready:
                match=plan.get('ready_text','')
                usable=False
                if backend=='eww':usable=eww_open
                elif match:usable=match in tail
                elif check_surface:
                    if time.monotonic()-last_surface>.3:
                        last_surface=time.monotonic();usable=has_surface(set(members()))
                else:usable=(time.monotonic()-started)*1000>=plan.get('grace_ms',1200)
                if usable:print('QQS_READY',flush=True);ready=True
        return 0
    except Exception as error:
        print('QQS_ERROR: '+str(error),flush=True)
        return 1
    finally:
        if child is not None and not leave_children:
            signal.signal(signal.SIGTERM,signal.SIG_IGN)
            try:os.killpg(os.getpgrp(),signal.SIGTERM)
            except ProcessLookupError:pass
            deadline=time.monotonic()+2
            while members() and time.monotonic()<deadline:time.sleep(.03)
            if members():os.killpg(os.getpgrp(),signal.SIGKILL)
            try:child.wait(timeout=.5)
            except subprocess.TimeoutExpired:pass

if __name__=='__main__':sys.exit(main(sys.argv[1]))
