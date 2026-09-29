#!/usr/bin/env python3
"""Keyboard controller for the Tang Mega Pro Dock racing game (USB CDC)."""
import argparse
import time
import tkinter as tk
from tkinter import messagebox
import serial
from serial.tools import list_ports

KEYS={'Left':1,'a':1,'q':1,'Right':2,'d':2,'Up':4,'w':4,'z':4,
      'Down':8,'s':8,'space':8,'Return':16}


def find_port():
    ports=[p.device for p in list_ports.comports() if (p.vid,p.pid)==(0x359f,0x2011)]
    if len(ports)!=1:
        raise RuntimeError(f'Il faut une console USB 359f:2011 ; ports trouvés : {ports}. Utiliser --port si nécessaire.')
    return ports[0]


class Controller:
    def __init__(self,root,port):
        self.root=root
        self.dev=serial.Serial(port,115200,timeout=0,write_timeout=.2,exclusive=True)
        self.keys=set();self.releases={};self.pending=bytearray();self.closed=False
        self.last_poll=0.;self.started=False
        root.title('Mega Coast — manette USB');root.geometry('600x340');root.configure(bg='#102039')
        tk.Label(root,text='MEGA COAST',fg='#ffdb69',bg='#102039',font=('Sans',25,'bold')).pack(pady=(22,8))
        tk.Label(root,text='Le jeu s’affiche sur le LCD de la console.',fg='white',bg='#102039',font=('Sans',12)).pack()
        tk.Label(root,text='Entrée : départ / nouvelle course\n← → : direction   ↑ : accélérer\n↓ ou Espace : freiner\nAZERTY : ZQSD   ·   QWERTY : WASD',fg='white',bg='#102039',font=('Sans',13),justify='left').pack(pady=16)
        self.status=tk.StringVar(value=f'Connexion à {port}…')
        tk.Label(root,textvariable=self.status,fg='#96d9e9',bg='#102039',wraplength=560,font=('Sans',10)).pack(pady=5)
        tk.Label(root,text='Gardez cette fenêtre active pour conduire. Échap : quitter.',fg='#c8dce0',bg='#102039',font=('Sans',10)).pack()
        root.bind('<KeyPress>',self.press);root.bind('<KeyRelease>',self.release)
        root.bind('<FocusOut>',self.focus_out);root.protocol('WM_DELETE_WINDOW',self.close)
        self.dev.write(b'XR');root.after(20,self.tick)

    def press(self,event):
        key=event.keysym if event.keysym in KEYS else event.keysym.lower()
        if event.keysym=='Escape':self.close();return
        if key in self.releases:self.root.after_cancel(self.releases.pop(key))
        if key in KEYS:self.keys.add(key)

    def release(self,event):
        key=event.keysym if event.keysym in KEYS else event.keysym.lower()
        # X11 autorepeat emits Release/Press pairs. Delay the release so the
        # matching press cancels it; physical release still clears promptly.
        if key in self.releases:self.root.after_cancel(self.releases[key])
        self.releases[key]=self.root.after(12,lambda:self.release_now(key))

    def release_now(self,key):
        self.releases.pop(key,None);self.keys.discard(key)

    def focus_out(self,event):
        self.keys.clear()
        if not self.closed:
            try:self.dev.write(b'\x80')
            except serial.SerialException:self.close()

    def tick(self):
        if self.closed:return
        try:
            self.pending.extend(self.dev.read(self.dev.in_waiting))
            while b'\n\r' in self.pending:
                line,_,self.pending=self.pending.partition(b'\n\r')
                text=line.decode('ascii',errors='replace').strip()
                if 'FAIL' in text or 'TRAP' in text:raise RuntimeError(text)
                if text.startswith('RACE READY'):self.started=True
                if text.startswith('RACE STATUS'):
                    values=dict(item.split('=',1) for item in text.split()[2:] if '=' in item)
                    speed=int(values.get('speed','0'))*36//100
                    self.status.set(f"{speed} km/h  ·  {int(values.get('distance','0'))//10} / 6000 m  ·  Chocs : {values.get('hits','0')}")
            if self.started:
                mask=0
                for key in self.keys:mask|=KEYS[key]
                self.dev.write(bytes([0x80|mask]))
                if time.monotonic()-self.last_poll>.5:
                    self.dev.write(b'H');self.last_poll=time.monotonic()
        except (serial.SerialException,OSError,RuntimeError) as e:
            self.close();messagebox.showerror('Console USB',str(e));return
        self.root.after(40,self.tick)

    def close(self):
        if self.closed:return
        self.closed=True
        try:self.dev.write(b'\x80X')
        except (serial.SerialException,OSError):pass
        self.dev.close();self.root.destroy()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port')
    args=parser.parse_args();port=args.port or find_port()
    root=tk.Tk();Controller(root,port);root.mainloop()


if __name__=='__main__':main()
