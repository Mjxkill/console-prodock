#ifndef ASTRILLA_FLIGHT_H
#define ASTRILLA_FLIGHT_H
// Positions, velocities and accelerations exist in 3D before projection.
// Uniform cubic B-splines are C2 even at knots and closed-loop boundaries.
typedef struct {as3_vec p,v,a;} as_orbit;
typedef struct {as_motion m;float size,heading,pitch,bank;as3_vec position,velocity;float scale;} as_flight;
typedef struct {as3_vec position;float yaw;as3_vec velocity;float yaw_rate;} as_follow_camera;
static as3_vec as_yaw(as3_vec p,float yaw){
 float sn=af_sin(yaw),cs=af_cos(yaw);return (as3_vec){cs*p.x-sn*p.z,p.y,sn*p.x+cs*p.z};
}
static as3_vec as_camera_point(as3_vec p,as_follow_camera camera){
 p.x-=camera.position.x;p.y-=camera.position.y;p.z-=camera.position.z;return as_yaw(p,camera.yaw);
}
static as_flight as_project_flight(as3_vec p,as3_vec velocity,as3_vec nose,float bank,float scale){
 float d=200.f/p.z;
 as_motion m={200.f+p.x*d,120.f+p.y*d,d*(velocity.x-p.x*velocity.z/p.z),d*(velocity.y-p.y*velocity.z/p.z)};
 return (as_flight){m,520.f*scale/p.z,as_heading(nose.x,nose.y),as_heading(as3_sqrt(nose.x*nose.x+nose.y*nose.y),nose.z),bank,p,velocity,scale};
}
static as_flight as_flight_pose(as_motion m,float size,float dsize,float bank){
 float z=520.f/size;as3_vec p={(m.x-200.f)*z/200.f,(m.y-120.f)*z/200.f,z};
 as3_vec v={(m.dx-(m.x-200.f)*dsize/size)*z/200.f,(m.dy-(m.y-120.f)*dsize/size)*z/200.f,-z*dsize/size};
 return as_project_flight(p,v,v,bank,1);
}
static int as_flight_draw(gpu_v1_context *c,as_flight f,unsigned enemy,float throttle,unsigned t){
 return as3_ship_at(c,f.position,f.scale,f.heading,f.pitch,f.bank,enemy,throttle,t);
}
static int as_flight_shot(gpu_v1_context *c,as_flight pose,float age,unsigned color){
 as3_vec f,w,up;as3_basis(pose.heading,pose.pitch,pose.bank,&f,&w,&up);
 float start=pose.scale*1.3f+age*1.5f,end=start+2.5f;
 if(f.z<0){float limit=(pose.position.z-.5f)/-f.z;if(start>=limit)return 1;if(end>limit)end=limit;}
 as3_vec a={pose.position.x+f.x*start,pose.position.y+f.y*start,pose.position.z+f.z*start};
 as3_vec b={pose.position.x+f.x*end,pose.position.y+f.y*end,pose.position.z+f.z*end};
 return as_beam(c,200.f+200.f*a.x/a.z,120.f+200.f*a.y/a.z,200.f+200.f*b.x/b.z,120.f+200.f*b.y/b.z,.8f,color,230);
}
static as_orbit as_spline(const as3_vec points[12],float seconds,float period){
 float phase=seconds*12.f/period;int knot=(int)phase;if(phase<knot)--knot;float u=phase-knot,v=1.f-u;
 float b[3][4]={{v*v*v/6.f,(3*u*u*u-6*u*u+4)/6.f,(-3*u*u*u+3*u*u+3*u+1)/6.f,u*u*u/6.f},
  {-.5f*v*v,1.5f*u*u-2*u,-1.5f*u*u+u+.5f,.5f*u*u},{v,3*u-2,1-3*u,u}};
 as_orbit o={{0,0,0},{0,0,0},{0,0,0}};as3_vec *dst[3]={&o.p,&o.v,&o.a};
 for(unsigned d=0;d<3;++d)for(unsigned j=0;j<4;++j){int index=(knot+(int)j)%12;if(index<0)index+=12;
  as3_vec p=points[index];dst[d]->x+=b[d][j]*p.x;dst[d]->y+=b[d][j]*p.y;dst[d]->z+=b[d][j]*p.z;}
 float rate=12.f/period;o.v.x*=rate;o.v.y*=rate;o.v.z*=rate;o.a.x*=rate*rate;o.a.y*=rate*rate;o.a.z*=rate*rate;
 return o;
}
static as_orbit as_space_orbit(float seconds,unsigned ship){
 static const as3_vec route[2][12]={
  {{-10,-.4f,22},{-10,0,14},{-10,.4f,7},{-6,1,4},{0,1.2f,3.5f},{7,.7f,5},{10,0,12},{8,-1,21},{4,-1.7f,28},{-3,-1,29},{-8,.3f,27},{-10,.5f,24}},
  {{-12,0,24},{-8,-2,17},{-5,-3,9},{2,-1,4},{8,1,6},{10,3,14},{4,1,22},{-4,-2,24},{-9,-3,18},{-4,0,11},{3,2,15},{0,1,26}}};
 float period=10.5f+(ship%5)*.83f,offset=ship*1.71f;
 as_orbit o=as_spline(route[(ship/2)%2],seconds+offset,period);
 float mirror=ship&1?-1.f:1.f,spread=.75f+(ship%3)*.1f,depth=1.f+(ship%3)*.07f;
 o.p.x=o.p.x*mirror*spread+((int)(ship%3)-1)*1.1f;o.v.x*=mirror*spread;o.a.x*=mirror*spread;
 o.p.y+=((int)(ship%4)-1)*.65f;o.p.z=o.p.z*depth+.7f;o.v.z*=depth;o.a.z*=depth;
 return o;
}
static float as_orbit_bank(as_orbit o){
 float horizontal=as3_sqrt(o.v.x*o.v.x+o.v.z*o.v.z);
 if(horizontal<.01f)return 0;
 // Lateral acceleration asks for bank. atan bounds it below 90 degrees;
 // filtering the request produces a progressive entry and exit.
 return -as_heading(.95f,(o.v.z*o.a.x-o.v.x*o.a.z)/horizontal);
}
static as_orbit as_race_orbit(float seconds,unsigned enemy);
static float as_smooth_bank(float seconds,unsigned ship,unsigned race){
 // Smooth the steering request itself with a C2 spline. Differentiating an
 // instantaneous atan(acceleration) gave violent rolls at curvature reversals.
 float step=race?1.f:1.1f,q=(seconds+.5f)/step;int k=(int)q;if(q<k)--k;
 float u=q-k,v=1-u,b[4]={v*v*v/6.f,(3*u*u*u-6*u*u+4)/6.f,(-3*u*u*u+3*u*u+3*u+1)/6.f,u*u*u/6.f},bank=0;
 for(unsigned j=0;j<4;++j){float at=(k+(int)j-2)*step;
  bank+=b[j]*as_orbit_bank(race?as_race_orbit(at,ship):as_space_orbit(at,ship));}
 return bank;
}
static as_flight as_space_flight(float seconds,unsigned ship,float scale){
 as_orbit o=as_space_orbit(seconds,ship),lead=as_space_orbit(seconds+.34f,ship);
 float bank=as_smooth_bank(seconds,ship,0);
 // Nose leads momentum during a turn: a visible sideslip, then the velocity
 // catches up along the C2 arc. No orientation snapped directly to a waypoint.
 return as_project_flight(o.p,o.v,lead.v,bank,scale);
}
static as_flight as_dogfight_flight(float seconds,unsigned ship,float *phase){
 *phase=seconds;return as_space_flight(seconds,ship,ship==8?1.08f:.55f+(ship%3)*.13f);
}
static as_motion as_dogfight(float seconds,unsigned ship,float *phase){return as_dogfight_flight(seconds,ship,phase).m;}
static as_follow_camera as_race_camera(unsigned t){
 float sec=(float)(t-8800)/55.f;unsigned shot=as_ground_shot(t);
 static const float views[9]={0,48,128,-48,0,88,-92,0,128};
 float yaw=views[shot%9]+8.f*af_sin(sec*4.f),distance=15.f+2.f*af_sin(sec*8.f);
 float sn=af_sin(yaw),cs=af_cos(yaw);
 float yaw_rate=32.f*.024543693f*.024543693f*af_cos(sec*4.f),speed=16.f*.024543693f*af_cos(sec*8.f);
 return (as_follow_camera){{-sn*distance,-1.5f,sec*12.f-cs*distance},yaw,
  {-cs*yaw_rate*distance-sn*speed,0,12.f+sn*yaw_rate*distance-cs*speed},yaw_rate};
}
static as_orbit as_race_orbit(float seconds,unsigned enemy){
 static const as3_vec course[12]={{-4,0,-2},{-4,-.5f,2},{0,-1.3f,5},{5,-.7f,3},{6,.3f,-1},{2,1,-4},
  {-5,.6f,-3},{-7,-.8f,1},{-3,-1.4f,4},{5,-.2f,3},{4,.7f,0},{0,.5f,-3}};
 // The pursuer reacts later, then takes an independent evasive line. Both
 // continue forward in the same world at 12 units/s behind the camera rig.
 float lag=enemy?0:.48f;as_orbit o=as_spline(course,seconds-lag,9.8f);
 float a=seconds*31.f+(enemy?13.f:106.f),rate=31.f*.024543693f,amp=enemy?.65f:1.1f;
 o.p.x+=amp*af_sin(a);o.v.x+=amp*rate*af_cos(a);o.a.x-=amp*rate*rate*af_sin(a);
 o.p.z+=seconds*12.f+(enemy?1.7f:-2.5f);o.v.z+=12.f;
 return o;
}
static as_flight as_pursuit_flight(unsigned t,int enemy){
 float sec=(float)(t-8800)/55.f;as_orbit o=as_race_orbit(sec,enemy),lead=as_race_orbit(sec+.26f,enemy);
 float bank=as_smooth_bank(sec,enemy,1);
 as_follow_camera camera=as_race_camera(t);as3_vec relative={o.v.x-camera.velocity.x,o.v.y-camera.velocity.y,o.v.z-camera.velocity.z};
 as3_vec position=as_camera_point(o.p,camera),velocity=as_yaw(relative,camera.yaw);
 velocity.x-=position.z*camera.yaw_rate;velocity.z+=position.x*camera.yaw_rate;
 return as_project_flight(position,velocity,as_yaw(lead.v,camera.yaw),bank,enemy?.92f:1.05f);
}
static as_motion as_pursuit(unsigned t,int enemy){return as_pursuit_flight(t,enemy).m;}
#endif
