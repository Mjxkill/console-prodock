// SPDX-License-Identifier: GPL-2.0-or-later
#define _XOPEN_SOURCE 600
#define _DEFAULT_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/wait.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>
#include "prodock-uapi.h"
#include "prodock-dashboard.h"
static volatile sig_atomic_t stopping;
static void stop(int sig) { (void)sig; stopping = 1; }
static double now(void)
{
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec / 1e9;
}
static int write_all(int fd, const void *data, size_t n)
{
    const char *p = data;
    while (n) {
        ssize_t k = write(fd, p, n);
        if (k < 0 && errno == EINTR && !stopping) continue;
        if (k <= 0) return -1;
        p += k; n -= k;
    }
    return 0;
}
static struct pd_sd_stats sd_stats(void)
{
    struct pd_sd_stats s={0};
    unsigned long long sectors=0,v[7];
    FILE *f=fopen("/sys/block/mmcblk0/size","r");
    if(f) { if(fscanf(f,"%llu",&sectors)==1 && sectors) { s.present=1;s.sectors=sectors; } fclose(f); }
    f=fopen("/sys/block/mmcblk0/stat","r");
    if(f) {
        if(fscanf(f,"%llu %llu %llu %llu %llu %llu %llu",&v[0],&v[1],&v[2],&v[3],&v[4],&v[5],&v[6])==7) {
            s.counters_valid=1;s.read_sectors=v[2];s.written_sectors=v[6];
        }
        fclose(f);
    }
    return s;
}
static int debug_update(int display,struct prodock_display_info *previous,struct pd_sd_stats *old_sd,double dt)
{
    struct prodock_display_info s;
    struct prodock_debug_text text;
    struct pd_sd_stats sd=sd_stats();
    if(ioctl(display,PRODOCK_DISPLAY_INFO,&s))return -1;
    pd_dashboard(&text,&s,previous,&sd,old_sd,dt);
    if(ioctl(display,PRODOCK_DEBUG_TEXT,&text))return -1;
    *previous=s;*old_sd=sd;
    return 0;
}
int main(void)
{
    int display = open("/dev/prodock-display", O_RDWR | O_CLOEXEC);
    int lcd = open("/dev/tty1", O_WRONLY | O_NOCTTY | O_CLOEXEC);
    if (display < 0 || lcd < 0) { perror("hardware terminal"); return 1; }
    int master = posix_openpt(O_RDWR | O_NOCTTY | O_CLOEXEC);
    if (master < 0 || grantpt(master) || unlockpt(master)) { perror("PTY"); return 1; }
    char slave_name[128];
    if (!ptsname(master)) return 1;
    snprintf(slave_name,sizeof(slave_name),"%s",ptsname(master));
    struct termios saved, raw;
    if (tcgetattr(STDIN_FILENO,&saved)) { perror("serial terminal"); return 1; }
    struct winsize ws = {.ws_row=15,.ws_col=50};
    if (ioctl(lcd,TIOCGWINSZ,&ws) || !ws.ws_col || !ws.ws_row) return 1;
    if (ioctl(master,TIOCSWINSZ,&ws)) return 1;
    pid_t child=fork();
    if(child<0) return 1;
    if(!child) {
        close(master); close(lcd); close(display);
        if(setsid()<0) _exit(126);
        int slave=open(slave_name,O_RDWR);
        if(slave<0 || ioctl(slave,TIOCSCTTY,0)) _exit(126);
        for(int i=0;i<3;++i) if(dup2(slave,i)<0) _exit(126);
        if(slave>2) close(slave);
        setenv("TERM","linux",1); setenv("PS1","prodock# ",1);
        execl("/bin/sh","sh",(char *)0); _exit(127);
    }
    signal(SIGTERM,stop); signal(SIGHUP,stop); signal(SIGINT,stop); signal(SIGPIPE,stop);
    raw=saved; cfmakeraw(&raw);
    if(tcsetattr(STDIN_FILENO,TCSANOW,&raw)) { kill(child,SIGHUP); return 1; }
    struct prodock_display_info previous={0};
    if(ioctl(display,PRODOCK_DISPLAY_INFO,&previous)) stopping=1;
    struct pd_sd_stats previous_sd=sd_stats();
    double last=now(); int status=0, failed=0;
    while(!stopping) {
        struct pollfd fds[2]={{STDIN_FILENO,POLLIN,0},{master,POLLIN,0}};
        int n=poll(fds,2,100);
        if(n<0 && errno!=EINTR) { failed=1;break; }
        char buf[2048]; ssize_t k;
        if(fds[0].revents&POLLIN) {
            k=read(STDIN_FILENO,buf,sizeof(buf));
            if(k<=0 || write_all(master,buf,(size_t)k)) { failed=1;break; }
        }
        if(fds[1].revents&POLLIN) {
            k=read(master,buf,sizeof(buf));
            if(k<=0) break;
            if(write_all(lcd,buf,(size_t)k) || write_all(STDOUT_FILENO,buf,(size_t)k)) { failed=1;break; }
        }
        if(fds[0].revents&(POLLERR|POLLHUP|POLLNVAL)) break;
        if((fds[1].revents&(POLLERR|POLLHUP|POLLNVAL)) && !(fds[1].revents&POLLIN)) break;
        struct winsize next;
        if(!ioctl(lcd,TIOCGWINSZ,&next) && (next.ws_col!=ws.ws_col || next.ws_row!=ws.ws_row)) {
            if(ioctl(master,TIOCSWINSZ,&next)) { failed=1;break; }
            ws=next; /* kernel sends SIGWINCH to the PTY foreground process */
        }
        double t=now();
        if(t-last>=1.) {
            if(debug_update(display,&previous,&previous_sd,t-last)) { failed=1;break; }
            last=t;
        }
        if(waitpid(child,&status,WNOHANG)==child) { child=-1;break; }
    }
    tcsetattr(STDIN_FILENO,TCSANOW,&saved);
    close(master); close(lcd); close(display);
    if(child>0) { kill(child,SIGHUP); while(waitpid(child,&status,0)<0 && errno==EINTR) {} }
    return failed || !WIFEXITED(status) ? 1 : WEXITSTATUS(status);
}
