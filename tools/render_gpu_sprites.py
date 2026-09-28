#!/usr/bin/env python3
"""Render exact G4 LCD pixels from the firmware textures and descriptors."""
import argparse
from pathlib import Path
from render_gpu_layers import ROOT,render

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pose',type=int,choices=(0,1,2),default=0)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--hardware-log',type=Path)
    args=parser.parse_args()
    render(args.pose,args.output or ROOT/f'TESTS/images/gpu_g4_pose{args.pose}_expected.png',args.hardware_log,sprites=True)
