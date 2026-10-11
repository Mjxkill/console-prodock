// SPDX-License-Identifier: MIT
/* Exercise musl locks, scheduling, address spaces and page-table updates. */
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static unsigned counter;
static void *worker(void *unused)
{
    (void)unused;
    for (unsigned i=0; i<10000; ++i) {
        if (pthread_mutex_lock(&lock)) abort();
        ++counter;
        if (pthread_mutex_unlock(&lock)) abort();
    }
    return NULL;
}
int main(void)
{
    pthread_t a,b;
    if(pthread_create(&a,NULL,worker,NULL) || pthread_create(&b,NULL,worker,NULL)) return 1;
    if(pthread_join(a,NULL) || pthread_join(b,NULL) || counter!=20000) return 2;
    for(unsigned i=0;i<32;++i) {
        unsigned char *p=mmap(NULL,131072,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
        if(p==MAP_FAILED)return 3;
        memset(p,i,131072);
        if(mprotect(p,131072,PROT_READ))return 4;
        pid_t child=fork();
        if(child<0)return 5;
        if(!child) {
            for(unsigned j=0;j<131072;++j)if(p[j]!=i)_exit(10);
            if(mprotect(p,131072,PROT_READ|PROT_WRITE))_exit(11);
            p[0]=255; _exit(0);
        }
        int status;
        if(waitpid(child,&status,0)!=child || !WIFEXITED(status) || WEXITSTATUS(status) || p[0]!=i)return 6;
        if(munmap(p,131072))return 7;
    }
    puts("PRODOCK_RUNTIME_OK threads=2 increments=20000 fork_mmap_mprotect=32");
    return 0;
}
