/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef PRODOCK_DASHBOARD_H
#define PRODOCK_DASHBOARD_H
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include "prodock-uapi.h"
/* The debug grid goes directly to VGA8x16 tiles: glyphs are CP437, not UTF-8.
 * All measurements below are counters/status, never invented utilization. */
struct pd_sd_stats {
    uint64_t sectors, read_sectors, written_sectors;
    int present, counters_valid;
};
enum { PD_BLACK=0, PD_AMBER=3, PD_GREY=7, PD_DIM=8,
       PD_RED=9, PD_GREEN=10, PD_CYAN=14, PD_WHITE=15 };
static void pd_cell(struct prodock_debug_text *t,unsigned x,unsigned y,unsigned ch,unsigned fg,unsigned bg)
{
    if(x<100 && y<15)t->cells[y*100+x]=(ch&255)|((fg&15)<<8)|((bg&15)<<12);
}
static void pd_label(struct prodock_debug_text *t,unsigned x,unsigned y,unsigned width,
                     unsigned fg,unsigned bg,const char *fmt,...)
{
    char text[101];va_list ap;
    va_start(ap,fmt);vsnprintf(text,sizeof(text),fmt,ap);va_end(ap);
    for(unsigned i=0;i<width && i<sizeof(text)-1 && text[i];++i)pd_cell(t,x+i,y,(unsigned char)text[i],fg,bg);
}
static void pd_rule(struct prodock_debug_text *t,unsigned x,unsigned y,unsigned width)
{
    for(unsigned i=0;i<width;++i)pd_cell(t,x+i,y,196,PD_DIM,PD_BLACK);
}
static void pd_panel(struct prodock_debug_text *t,unsigned x,unsigned width,const char *title)
{
    pd_rule(t,x,2,width);pd_rule(t,x,13,width);
    pd_cell(t,x,2,218,PD_DIM,0);pd_cell(t,x+width-1,2,191,PD_DIM,0);
    pd_cell(t,x,13,192,PD_DIM,0);pd_cell(t,x+width-1,13,217,PD_DIM,0);
    for(unsigned y=3;y<13;++y) {
        pd_cell(t,x,y,179,PD_DIM,0);pd_cell(t,x+width-1,y,179,PD_DIM,0);
    }
    pd_label(t,x+2,2,width-4,PD_CYAN,0," %s ",title);
}
static void pd_light(struct prodock_debug_text *t,unsigned x,unsigned y,unsigned colour,
                     unsigned width,const char *text)
{
    pd_cell(t,x,y,254,colour,0);
    pd_label(t,x+2,y,width-2,colour==PD_DIM?PD_GREY:PD_WHITE,0,"%s",text);
}
static void pd_bar(struct prodock_debug_text *t,unsigned x,unsigned y,unsigned width,
                   double value,double maximum,unsigned colour,int valid)
{
    double ratio=valid && maximum>0?value/maximum:0;
    if(!(ratio>=0))ratio=0;
    if(ratio>1)ratio=1;
    unsigned filled=(unsigned)(ratio*width+.5);
    for(unsigned i=0;i<width;++i)
        pd_cell(t,x+i,y,i<filled?219:176,i<filled?colour:PD_DIM,0);
}
static void pd_quantity(char *out,size_t n,uint64_t sectors)
{
    double kib=sectors*.5;
    if(kib>=1048576)snprintf(out,n,"%.1f Gio",kib/1048576);
    else if(kib>=1024)snprintf(out,n,"%.1f Mio",kib/1024);
    else snprintf(out,n,"%.1f Kio",kib);
}
static void pd_dashboard_geometry(struct prodock_debug_text *t,const struct prodock_display_info *s,
                         const struct prodock_display_info *before,const struct pd_sd_stats *sd,
                         const struct pd_sd_stats *old_sd,double dt,const struct prodock_display_geometry *geometry)
{
    unsigned budget=geometry && geometry->line_budget?geometry->line_budget:2556;
    int neo=geometry && geometry->board==PRODOCK_BOARD_NEO;
    for(unsigned i=0;i<1500;++i)t->cells[i]=0x0720;
    int measured=dt>0 && dt<3600;
    double fps=measured?(uint32_t)(s->game_presents-before->game_presents)/dt:0;
    double hz=measured?(uint32_t)(s->frames-before->frames)/dt:0;
    uint64_t sent=(uint64_t)s->sent_hi<<32|s->sent_lo;
    uint64_t old=(uint64_t)before->sent_hi<<32|before->sent_lo;
    int commands_known=measured && sent>=old;
    double commands=commands_known?(sent-old)/dt:0;
    double line=100.*s->line_cycles/(double)budget;
    int gpu_bad=s->errors || s->faulted || s->underflows || s->invalid_layers || s->invalid_sprites ||
                s->line_cycles>=budget || (measured && hz<1);
    int gpu_warn=!measured || line>=80 || (fps>0 && hz>0 && fps<hz*.8);
    unsigned gpu_colour=gpu_bad?PD_RED:gpu_warn?PD_AMBER:fps>0?PD_GREEN:PD_DIM;
    int usb_known=s->usb_status!=0xffffffffU;
    int usb_bad=usb_known && ((s->usb_status&0x480) ||
                 ((s->usb_status&32) && !(s->usb_status&64)));
    int usb_warn=!usb_known || !(s->usb_status&32) || (s->usb_status&12);
    unsigned usb_colour=usb_bad?PD_RED:usb_warn?PD_AMBER:PD_GREEN;
    unsigned sd_colour=sd->present && sd->counters_valid?PD_GREEN:PD_AMBER;
    unsigned overall=gpu_bad||usb_bad?PD_RED:gpu_warn||usb_warn||sd_colour==PD_AMBER?PD_AMBER:PD_GREEN;
    pd_label(t,2,0,60,PD_CYAN,0,neo?"TANG NEO  /  TABLEAU DE BORD":"PRO DOCK  /  TABLEAU DE BORD");
    pd_light(t,79,0,overall,19,overall==PD_RED?"ALERTE":overall==PD_AMBER?"VIGILANCE":"SYSTEME OK");
    pd_label(t,2,1,65,PD_GREY,0,"LINUX + GPU   |   MESURES EN DIRECT   |   ACTUALISATION 1 s");
    pd_label(t,79,1,19,PD_GREY,0,"MODE %s",s->mode==0?"PARTAGE":s->mode==1?"JEU":"CONSOLE");
    pd_panel(t,1,42,"GPU / AFFICHAGE");pd_panel(t,44,27,"USB / CONSOLE");pd_panel(t,72,27,"SD / STOCKAGE");
    pd_light(t,3,3,gpu_colour,38,gpu_bad?"DEFAUT DETECTE":gpu_warn?"A SURVEILLER":fps>0?"RENDU ACTIF":"GPU AU REPOS");
    if(measured)pd_label(t,3,4,38,PD_WHITE,0,"Jeu %5.1f FPS     LCD %5.1f Hz",fps,hz);
    else pd_label(t,3,4,38,PD_GREY,0,"Jeu    -- FPS     LCD    -- Hz");
    if(measured && hz>0)pd_label(t,3,5,38,PD_GREY,0,"Fluidite   %3.0f %% du LCD",100.*fps/hz);
    else pd_label(t,3,5,38,PD_GREY,0,"Fluidite    -- %% du LCD");
    pd_bar(t,3,6,37,fps,hz,gpu_colour,measured);
    if(commands_known)pd_label(t,3,7,38,PD_WHITE,0,"Commandes %10.0f /s",commands);
    else pd_label(t,3,7,38,PD_GREY,0,"Commandes         -- /s");
    pd_label(t,3,8,38,PD_GREY,0,"Ligne max %4u/%4u cycles  %3.0f %%",s->line_cycles,budget,line);
    pd_bar(t,3,9,37,s->line_cycles,budget,line>=90?PD_RED:line>=80?PD_AMBER:PD_GREEN,1);
    pd_label(t,3,10,38,s->errors||s->faulted?PD_RED:PD_GREY,0,"Defauts GPU %08x   Faute %u",s->errors,s->faulted);
    pd_label(t,3,11,38,s->underflows||s->invalid_layers||s->invalid_sprites?PD_RED:PD_GREY,0,
             "Sous-alim %u  Inv. C/S %u/%u",s->underflows,s->invalid_layers,s->invalid_sprites);
    pd_label(t,3,12,38,PD_GREY,0,"Total commandes %llu",(unsigned long long)sent);
    const char *usb_state=!usb_known?"ETAT INCONNU":usb_bad?"DEFAUT USB":!(s->usb_status&32)?"DECONNECTE":usb_warn?"RESET MEMORISE":"HS CONNECTE";
    pd_light(t,46,3,usb_colour,23,usb_state);
    pd_label(t,46,4,23,PD_WHITE,0,"Lien      %s",!usb_known?"--":!(s->usb_status&32)?"--":s->usb_status&64?"480 Mbit/s":"12 Mbit/s");
    pd_label(t,46,5,23,PD_GREY,0,"Console   CDC / UART2");
    pd_label(t,46,6,23,PD_GREY,0,neo?"Debug BL616 2 Mbauds":"Serie     115200 bauds");
    const char *names[]={"FIFO MSC","Reset USB","Reset MSC"};
    const unsigned bits[]={128,4,8};
    for(unsigned i=0;i<3;++i) {
        unsigned c=!usb_known?PD_AMBER:s->usb_status&bits[i]?(i?PD_AMBER:PD_RED):PD_GREEN;
        pd_label(t,46,7+i,11,PD_GREY,0,"%s",names[i]);
        pd_light(t,57,7+i,c,12,!usb_known?"INCONNU":s->usb_status&bits[i]?(i?"VU":"PERTE"):"OK");
    }
    pd_label(t,46,10,23,PD_GREY,0,"Disque USB %s",!usb_known?"INCONNU":s->usb_status&512?"SERVI":"INACTIF");
    if(usb_known)pd_label(t,46,11,23,PD_GREY,0,"Etat      0x%08x",s->usb_status);
    else pd_label(t,46,11,23,PD_AMBER,0,"Etat      non disponible");
    pd_label(t,46,12,23,PD_GREY,0,"HS = vitesse negociee");
    pd_light(t,74,3,sd_colour,23,!sd->present?"CARTE ABSENTE":!sd->counters_valid?"MESURES INDISPO.":"CARTE DETECTEE");
    if(sd->present) {
        pd_label(t,74,4,23,PD_WHITE,0,"Capacite %9.1f Gio",sd->sectors/2097152.);
        pd_label(t,74,5,23,PD_GREY,0,"Secteurs %13llu",(unsigned long long)sd->sectors);
    } else {
        pd_label(t,74,4,23,PD_GREY,0,"Capacite           --");
        pd_label(t,74,5,23,PD_GREY,0,"Secteurs           --");
    }
    int io_known=measured && sd->present && sd->counters_valid && old_sd->present && old_sd->counters_valid &&
                 sd->sectors==old_sd->sectors && sd->read_sectors>=old_sd->read_sectors && sd->written_sectors>=old_sd->written_sectors;
    double read_kib=io_known?(sd->read_sectors-old_sd->read_sectors)*.5/dt:0;
    double write_kib=io_known?(sd->written_sectors-old_sd->written_sectors)*.5/dt:0;
    if(io_known) {
        pd_label(t,74,6,23,PD_WHITE,0,"Lecture %9.0f Kio/s",read_kib);
        pd_label(t,74,8,23,PD_WHITE,0,"Ecriture%9.0f Kio/s",write_kib);
    } else {
        pd_label(t,74,6,23,PD_GREY,0,"Lecture        -- Kio/s");
        pd_label(t,74,8,23,PD_GREY,0,"Ecriture       -- Kio/s");
    }
    pd_bar(t,74,7,23,read_kib,1024,PD_CYAN,io_known);
    pd_bar(t,74,9,23,write_kib,1024,PD_GREEN,io_known);
    pd_label(t,74,10,23,PD_GREY,0,"Barres : max. 1 Mio/s");
    if(sd->present && sd->counters_valid) {
        char amount[32];pd_quantity(amount,sizeof(amount),sd->read_sectors);
        pd_label(t,74,11,23,PD_GREY,0,"Lu       %13s",amount);
        pd_quantity(amount,sizeof(amount),sd->written_sectors);
        pd_label(t,74,12,23,PD_GREY,0,"Ecrit    %13s",amount);
    } else {
        pd_label(t,74,11,23,PD_GREY,0,"Lu                 --");
        pd_label(t,74,12,23,PD_GREY,0,"Ecrit              --");
    }
    pd_label(t,2,14,96,PD_GREY,0,"AFFICHAGE  prodockctl layout split | game | console      JEU  A/D ou fleches  /  Q quitter");
}
static inline void pd_dashboard(struct prodock_debug_text *t,const struct prodock_display_info *s,
                         const struct prodock_display_info *before,const struct pd_sd_stats *sd,
                         const struct pd_sd_stats *old_sd,double dt)
{ pd_dashboard_geometry(t,s,before,sd,old_sd,dt,NULL); }
#endif
