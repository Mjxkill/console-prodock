#!/usr/bin/env python3
"""Instrument a source snapshot for controlled, warmed-up GPU measurements."""
from pathlib import Path
import sys
root=Path(sys.argv[1]);v=root/'src/video.c';h=root/'include/video.h';m=root/'src/main.c'
s=v.read_text();header=h.read_text()
if 'ui_pixels' not in header:
 header=header.replace('uint16_t palette[256];','uint16_t palette[256];uint8_t font[256*112];').replace('unsigned ui_width,ui_height;uint8_t *ui;','unsigned ui_width,ui_height;uint8_t *ui,*ui_pixels;uint32_t ui_hash[2];unsigned ui_bytes[2];')
 s=s.replace('struct prodock_palette palette;memcpy','memcpy(v->font,data+LUMA_FONT_OFFSET,sizeof(v->font));\n struct prodock_palette palette;memcpy').replace('const uint8_t *font=v->mem+LUMA_ASSET_BASE+LUMA_FONT_OFFSET','const uint8_t *font=v->font')
 s=s.replace('if(host){v->pixels=malloc(width*height*2);','v->ui_pixels=malloc(width*height);if(!v->ui_pixels)return -1;\n if(host){v->pixels=malloc(width*height*2);')
 s=s.replace('v->ui=v->mem+base;','v->ui=v->ui_pixels;').replace('v->ui=v->mem+bottom;','v->ui=v->ui_pixels+width*48;').replace('v->ui=v->mem+off;','v->ui=v->ui_pixels+width*88;')
 s=s.replace('unsigned width=v->width*2;unsigned dark=','unsigned width=v->width*2,used=width*88;unsigned dark=')
 s=s.replace('layer(v,2,off,0,56,width,h);','layer(v,2,off,0,56,width,h);used+=width*h;')
 s=s.replace('  layer(v,2,off,0,56,width,h);used+=width*h;\n }\n}', '  layer(v,2,off,0,56,width,h);used+=width*h;\n }\n unsigned page=v->frames&1;uint32_t hash=luma_crc(v->ui_pixels,used);if(hash!=v->ui_hash[page]||used!=v->ui_bytes[page]){memcpy(v->mem+base,v->ui_pixels,used);v->ui_hash[page]=hash;v->ui_bytes[page]=used;}\n}')
 s=s.replace('const uint8_t *src=v->mem+offset;', 'const uint8_t *src=v->ui_pixels+offset-(6*1024*1024+(v->frames&1)*1024*1024);')
 s=s.replace('free(v->pixels);if(v->mem)', 'free(v->pixels);free(v->ui_pixels);if(v->mem)')
 s=s.replace('static int region(LumaVideo *v,unsigned index)','int luma_video_prepare(LumaVideo *v,unsigned index)').replace('if(region(v,g->world_index))','if(luma_video_prepare(v,g->world_index))')
 header=header.replace('void luma_render','int luma_video_prepare(LumaVideo *v,unsigned world);\nvoid luma_render')
header=header.replace('unsigned ui_width,','double background_seconds,scene_seconds,hud_seconds,submit_seconds,present_seconds;struct prodock_display_info measured;\n unsigned ui_width,')
header=header.replace('int luma_video_prepare','void luma_video_measure_begin(LumaVideo *v);\nint luma_video_prepare')
s=s.replace(' background(v,g,cx,cy);', ' double phase=video_clock();background(v,g,cx,cy);v->background_seconds+=video_clock()-phase;phase=video_clock();')
s=s.replace(' hud(v,g);', ' v->scene_seconds+=video_clock()-phase;phase=video_clock();hud(v,g);v->hud_seconds+=video_clock()-phase;')
s=s.replace('return;}flush(v);checked(v,PRODOCK_PRESENT,&v->scene);v->frames++;','return;}phase=video_clock();flush(v);v->submit_seconds+=video_clock()-phase;phase=video_clock();checked(v,PRODOCK_PRESENT,&v->scene);v->present_seconds+=video_clock()-phase;v->frames++;')
s+='\nvoid luma_video_measure_begin(LumaVideo *v){v->background_seconds=v->scene_seconds=v->hud_seconds=v->submit_seconds=v->present_seconds=0;v->commands=0;v->max_sprites=0;if(!v->host)checked(v,PRODOCK_DISPLAY_INFO,&v->measured);}\n'
s=s.replace('int bad=0;\n if(header', 'int bad=0;double read_seconds=0,decode_seconds=0,crc_seconds=0;\n if(header')
s=s.replace('size_t n=fread(packed,1,header[2],f);bad=', 'double phase=video_clock();size_t n=fread(packed,1,header[2],f);read_seconds=video_clock()-phase;bad=')
s=s.replace('if(!bad)bad=unpack(packed,n,data,expected);','if(!bad){phase=video_clock();bad=unpack(packed,n,data,expected);decode_seconds=video_clock()-phase;}')
s=s.replace('unsigned actual=luma_crc(data,expected);','phase=video_clock();unsigned actual=luma_crc(data,expected);crc_seconds=video_clock()-phase;')
s=s.replace('cpu_seconds=%.3f\\n",path,expected,video_clock()-start);','cpu_seconds=%.3f read=%.3f decode=%.3f crc=%.3f\\n",path,expected,video_clock()-start,read_seconds,decode_seconds,crc_seconds);')
v.write_text(s);h.write_text(header)
s=m.read_text().replace('unsigned limit=0,start_world=0','unsigned limit=0,start_world=0,warmup=0')
s=s.replace('else if(i+1<argc&&!strcmp(argv[i],"--world"))','else if(i+1<argc&&!strcmp(argv[i],"--warmup")){if(number(argv[++i],&warmup))return 2;}\n  else if(i+1<argc&&!strcmp(argv[i],"--world"))')
if 'luma_video_prepare(&video' not in s:s=s.replace(' signal(SIGTERM,stop);',' if(luma_video_prepare(&video,game.world_index)){luma_video_close(&video);return 1;}\n signal(SIGTERM,stop);')
s=s.replace('video.frames<limit)', 'video.frames<limit+warmup)')
s=s.replace(' while(!stopping', ' double simulation_seconds=0;luma_video_measure_begin(&video);\n while(!stopping')
if 'pending_pressed|=' in s:s=s.replace('  pending_pressed|=', '  double sim_start=now();pending_pressed|=')
else:s=s.replace('  updates+=luma_frame_steps', '  double sim_start=now();updates+=luma_frame_steps')
s=s.replace('  luma_render(&video,&game);', '  simulation_seconds+=now()-sim_start;luma_render(&video,&game);\n  if(warmup&&video.frames==warmup){printf("LUMA_WARMUP frames=%u seconds=%.3f\\n",warmup,now()-start);luma_video_measure_begin(&video);start=now();updates=0;simulation_seconds=0;}\n  if(!host&&video.frames>warmup&&(video.frames-warmup)%120==0){printf("LUMA_MEASURE frames=%u seconds=%.3f fps=%.2f\\n",video.frames-warmup,now()-start,(video.frames-warmup)/fmax(now()-start,.001));fflush(stdout);}')
s=s.replace('double elapsed=now()-start;printf','double elapsed=now()-start;unsigned measured_frames=video.frames>warmup?video.frames-warmup:0;printf')
s=s.replace('video.frames,elapsed,video.frames/fmax(elapsed,.001)', 'measured_frames,elapsed,measured_frames/fmax(elapsed,.001)')
needle=' printf("LUMA_RESULT'
report=''' printf("LUMA_TIMING simulation=%.6f background_cpu=%.6f scene_cpu=%.6f hud_cpu=%.6f submit=%.6f present=%.6f\\n",simulation_seconds,video.background_seconds,video.scene_seconds,video.hud_seconds,video.submit_seconds,video.present_seconds);
 printf("LUMA_DRIVER feed_us=%u wait_us=%u cache_us=%u present_us=%u text_us=%u\\n",video.last.feed_us-video.measured.feed_us,video.last.wait_us-video.measured.wait_us,video.last.cache_us-video.measured.cache_us,video.last.present_us-video.measured.present_us,video.last.text_us-video.measured.text_us);
'''
assert needle in s;s=s.replace(needle,report+needle);m.write_text(s)
