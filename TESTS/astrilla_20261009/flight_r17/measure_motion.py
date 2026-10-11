import sys,ctypes,math,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tools'));from render_astrilla import Scene
class F(ctypes.Structure):_fields_=[(k,ctypes.c_float)for k in ['x','y','dx','dy','size','heading','pitch','bank','px','py','pz','vx','vy','vz','scale']]
s=Scene();s.lib.flight_probe.argtypes=[ctypes.c_float,ctypes.c_uint,ctypes.POINTER(F)];s.lib.pursuit_probe.argtypes=[ctypes.c_uint,ctypes.c_int,ctypes.POINTER(F)];s.lib.basis_probe.argtypes=[ctypes.c_float]*3+[ctypes.POINTER(ctypes.c_float)]
report={}
for kind in ['battle','pursuit']:
 actors=[]
 for ship in (range(9) if kind=='battle' else range(2)):
  previous=None;last_rate=None;maxima=[0]*5;zmin=999;zmax=0;low=999;visible=0;face=back=0;slipmax=0
  for t in range(1650) if kind=='battle' else range(8800,13750):
   f=F()
   if kind=='battle':s.lib.flight_probe(t/55,ship,ctypes.byref(f))
   else:s.lib.pursuit_probe(t,ship,ctypes.byref(f))
   basis=(ctypes.c_float*9)();s.lib.basis_probe(f.heading,f.pitch,f.bank,basis)
   zmin=min(zmin,f.pz);zmax=max(zmax,f.pz);speed=math.sqrt(f.vx*f.vx+f.vy*f.vy+f.vz*f.vz);low=min(low,speed);maxima[0]=max(maxima[0],abs(f.bank)*360/256)
   if 0<f.x<400 and 0<f.y<240:
    visible+=1;face+=basis[2]<-.8;back+=basis[2]>.8
   if kind=='battle':slipmax=max(slipmax,math.degrees(math.acos(max(-1,min(1,(basis[0]*f.vx+basis[1]*f.vy+basis[2]*f.vz)/speed)))))
   if previous and (kind=='battle' or (t-8800)%550):
    rates=[]
    for off in [0,3,6]:
     dot=sum(basis[off+i]*previous[1][off+i] for i in range(3));rates.append(math.degrees(math.acos(max(-1,min(1,dot))))*55)
    rate=(f.bank-previous[0].bank)*360/256*55
    maxima[1]=max(maxima[1],rates[0]);maxima[2]=max(maxima[2],max(rates));maxima[3]=max(maxima[3],abs(rate))
    if last_rate is not None:maxima[4]=max(maxima[4],abs(rate-last_rate)*55)
    last_rate=rate
   else:last_rate=None
   previous=(f,list(basis))
  actors.append(dict(ship=ship,zmin=zmin,zmax=zmax,min_speed=low,bank=maxima[0],nose_rate=maxima[1],axis_rate=maxima[2],roll_rate=maxima[3],roll_accel=maxima[4],slip=slipmax,visible=visible,front=face,rear=back))
 report[kind]=actors
out=Path('TESTS/astrilla_20261009/flight_r17/motion_metrics.json');out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
