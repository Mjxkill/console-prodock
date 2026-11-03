#!/usr/bin/env python3
"""Actual Linux adapter linked separately to mocked kernel/engine APIs.

Checks adapter contracts, not hardware or the common pump (tested separately).
No generated header contains implementation. Temporary files are removed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HEADER = r'''
#ifndef SPI_LINUX_TEST_H
#define SPI_LINUX_TEST_H
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
typedef uint32_t u32;
#define __iomem
#define __force
#define MODULE_LICENSE(x)
#define builtin_platform_driver(x) struct platform_driver *test_driver = &(x)
#define SPI_CS_HIGH 4
#define SPI_BPW_MASK(x) (1U << ((x)-1))
#define DIV_ROUND_UP(a,b) (((a)+(b)-1)/(b))
struct device { void *of_node; };
struct platform_device { struct device dev; };
struct spi_controller;
struct spi_device { struct spi_controller *controller; unsigned max_speed_hz; };
struct spi_message { int status; };
struct spi_transfer {
 const void *tx_buf; void *rx_buf;
 unsigned len, bits_per_word, speed_hz, effective_speed_hz;
};
struct spi_controller {
 struct device dev; void *data;
 unsigned num_chipselect, mode_bits, bits_per_word_mask, min_speed_hz, max_speed_hz;
 int (*setup)(struct spi_device *);
 void (*set_cs)(struct spi_device *,bool);
 int (*transfer_one)(struct spi_controller *,struct spi_device *,struct spi_transfer *);
 void (*handle_err)(struct spi_controller *,struct spi_message *);
};
struct of_device_id { const char *compatible; };
struct platform_driver {
 int (*probe)(struct platform_device *);
 struct { const char *name; const struct of_device_id *of_match_table;
          bool suppress_bind_attrs; } driver;
};
extern struct platform_driver *test_driver;
struct spi_controller *devm_spi_alloc_host(struct device *,size_t);
void *spi_controller_get_devdata(struct spi_controller *);
void *devm_platform_ioremap_resource(struct platform_device *,unsigned);
int device_property_read_u32(struct device *,const char *,u32 *);
int devm_spi_register_controller(struct device *,struct spi_controller *);
bool IS_ERR(const void *);
int PTR_ERR(const void *);
u32 readl(const void *);
void writel(u32,void *);
void dev_err(struct device *,const char *,...);
#endif
'''
MODEL = r'''
#include "kernel.h"
#include "prodock-spi-pio.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static struct spi_controller ctlr;
static struct platform_device platform;
static unsigned regs[32],gpio[32],clock_hz=80000000;
static int init_error,speed_error,exchange_error,recovery_error,property_error;
static unsigned inits,speeds,exchanges,recoveries,logs,registrations,last_hz,last_n;
static const unsigned char *last_tx;
static unsigned char *last_rx;
static void check(int ok,const char *message)
{ if(!ok){fprintf(stderr,"FAIL: %s\n",message);exit(1);} }
struct spi_controller *devm_spi_alloc_host(struct device *d,size_t n)
{ (void)d;free(ctlr.data);memset(&ctlr,0,sizeof(ctlr));ctlr.data=calloc(1,n);return &ctlr; }
void *spi_controller_get_devdata(struct spi_controller *c){return c->data;}
void *devm_platform_ioremap_resource(struct platform_device *d,unsigned n)
{(void)d;return n ? gpio:regs;}
int device_property_read_u32(struct device *d,const char *name,u32 *value)
{(void)d;check(!strcmp(name,"clock-frequency"),"clock property");*value=clock_hz;return property_error;}
int devm_spi_register_controller(struct device *d,struct spi_controller *c)
{(void)d;check(c==&ctlr,"registered controller");++registrations;return 0;}
bool IS_ERR(const void *p){(void)p;return false;}
int PTR_ERR(const void *p){(void)p;return -EIO;}
u32 readl(const void *p){return *(const u32 *)p;}
void writel(u32 value,void *p){*(u32 *)p=value;}
void dev_err(struct device *d,const char *format,...){(void)d;(void)format;++logs;}
int atcspi200_init(struct atcspi200 *s,void *base,unsigned hz,unsigned requested)
{
 ++inits;check(base==regs && hz==80000000 && requested==400000,"init parameters");
 check(gpio[0x30/4]==1 && (gpio[0x28/4]&1),"CS high output before init");
 s->ready=!init_error;s->actual_hz=400000;return init_error;
}
int atcspi200_set_speed(struct atcspi200 *s,unsigned hz)
{++speeds;last_hz=hz;if (!speed_error) s->actual_hz=hz==20000000 ? 19000000 : hz;return speed_error;}
int SPI_Master_send_receive(struct atcspi200 *s,const unsigned char *tx,
 unsigned char *rx,unsigned count)
{if(!s->ready)return -EIO;++exchanges;last_tx=tx;last_rx=rx;last_n=count;return exchange_error;}
int atcspi200_recover(struct atcspi200 *s)
{++recoveries;check(gpio[0x30/4]==1,"CS high before recovery");s->ready=!recovery_error;return recovery_error;}
unsigned atcspi200_milliseconds(void){return 0;}
int main(void)
{
 struct spi_device dev={.controller=&ctlr,.max_speed_hz=400000};
 unsigned char tx[3]={1,2,3},rx[3];
 struct spi_transfer x={.tx_buf=tx,.rx_buf=rx,.len=3,.bits_per_word=8,.speed_hz=20000000};
 clock_hz=40000000;
 check(test_driver->probe(&platform)==-EINVAL && !inits,"reject wrong source clock");
 clock_hz=80000000;property_error=-ENOENT;
 check(test_driver->probe(&platform)==-EINVAL && !inits,"missing clock property");
 property_error=0;init_error=-ETIMEDOUT;
 check(test_driver->probe(&platform)==-ETIMEDOUT && !registrations,"failed init not registered");
 init_error=0;check(!test_driver->probe(&platform) && registrations==1,"probe registration");
 check(ctlr.num_chipselect==1 && ctlr.bits_per_word_mask==128 && ctlr.max_speed_hz==20000000,"capabilities");
 check(ctlr.setup!=NULL,"SD clock configuration callback is required");
 check(!ctlr.setup(&dev) && !speeds,"400k already configured by probe");
 x.speed_hz=400000;
 check(!ctlr.transfer_one(&ctlr,&dev,&x) && !speeds,"identification exchange never sets speed");
 check(x.effective_speed_hz==400000,"report identification speed");
 dev.max_speed_hz=20000000;
 check(!ctlr.setup(&dev) && speeds==1 && last_hz==20000000,"configure operating clock once");
 /* mmc_spi reuses status transfers: stale metadata must not restore 400k. */
 unsigned before=exchanges, ratecalls=speeds;
 for (unsigned i=0;i<10;++i) {
  x.speed_hz=i&1 ? 20000000 : 400000;
  check(!ctlr.transfer_one(&ctlr,&dev,&x),"transfer success");
  check(!ctlr.setup(&dev),"CS-release setup success");
 }
 check(speeds==ratecalls && exchanges==before+10,"data/CS-release perform no speed calls");
 check(last_n==3 && last_tx==tx && last_rx==rx,"forward buffers and length");
 check(x.effective_speed_hz==19000000,"report actual engine speed, not stale metadata");
 before=exchanges;ratecalls=speeds;
 x.bits_per_word=16;
 check(ctlr.transfer_one(&ctlr,&dev,&x)==-EINVAL && exchanges==before && speeds==ratecalls,"reject word size before engine");
 x.bits_per_word=8;speed_error=-ERANGE;dev.max_speed_hz=1000;
 check(ctlr.setup(&dev)==-ERANGE,"configuration error reported");
 ratecalls=speeds;
 check(ctlr.transfer_one(&ctlr,&dev,&x)==-ERANGE && exchanges==before && speeds==ratecalls,
       "failed setup prevents exchange without retrying configuration");
 speed_error=0;dev.max_speed_hz=20000000;
 check(!ctlr.setup(&dev) && speeds==ratecalls+1,"valid setup clears prior error");
 dev.max_speed_hz=400000;
 check(!ctlr.setup(&dev) && last_hz==400000,"SD reinitialization clock");
 check(!ctlr.transfer_one(&ctlr,&dev,&x) && x.effective_speed_hz==400000,"reinitialized rate");
 dev.max_speed_hz=20000000;check(!ctlr.setup(&dev),"return to operating clock");
 exchange_error=-ETIMEDOUT;
 check(ctlr.transfer_one(&ctlr,&dev,&x)==-ETIMEDOUT,"transfer error propagated");
 struct spi_message msg={.status=-ETIMEDOUT};
 gpio[0x30/4]=0;ctlr.handle_err(&ctlr,&msg);
 check(recoveries==1 && msg.status==-ETIMEDOUT && !logs,"recovery preserves message error");
 recovery_error=-EIO;gpio[0x30/4]=0;ctlr.handle_err(&ctlr,&msg);
 check(recoveries==2 && logs==1 && msg.status==-ETIMEDOUT,"failed recovery logged, first error retained");
 before=exchanges;
 check(!ctlr.setup(&dev) && ctlr.transfer_one(&ctlr,&dev,&x)==-EIO && exchanges==before,
       "unchanged clock cannot revive a controller whose recovery failed");
 gpio[0x2c/4]=gpio[0x30/4]=0;ctlr.set_cs(&dev,false);ctlr.set_cs(&dev,true);
 check(gpio[0x2c/4]==1 && gpio[0x30/4]==1,"physical CS polarity");
 free(ctlr.data);puts("PASS: Linux SD adapter setup, fixed-rate exchanges, reinitialization and errors");return 0;
}
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver',type=Path,default=ROOT/'linux/drivers/prodock-spi.c')
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    driver=args.driver.resolve()
    header = ROOT/'linux/drivers/prodock-spi-pio.h'
    report = {'passed':False,'hardware':False,'scope':'Linux adapter with mocked kernel and engine',
              'inputs':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),driver,header)},'steps':[]}
    with tempfile.TemporaryDirectory(prefix='console-spi-linux-') as tempdir:
        temp=Path(tempdir)
        (temp/'kernel.h').write_text(HEADER)
        (temp/'model.c').write_text(MODEL)
        for name in ('io','module','platform_device','property','spi/spi'):
            p=temp/('linux/'+name+'.h');p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text('#include "kernel.h"\n')
        flags=['gcc','-std=gnu11','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
               '-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(temp),'-I'+str(header.parent)]
        commands=[flags+['-c',str(driver),'-o',str(temp/'driver.o')],
                  flags+['-c',str(temp/'model.c'),'-o',str(temp/'model.o')],
                  flags+[str(temp/'driver.o'),str(temp/'model.o'),'-o',str(temp/'test')],[str(temp/'test')]]
        for command in commands:
            p=subprocess.run(command,text=True,capture_output=True,timeout=30)
            report['steps'].append({'command':command,'rc':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:break
        report['passed']=len(report['steps'])==4 and all(s['rc']==0 for s in report['steps'])
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['steps'][-1]));return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
