// SPDX-License-Identifier: GPL-2.0-or-later
#include <linux/capability.h>
#include <linux/console.h>
#include <linux/delay.h>
#include <linux/fb.h>
#include <linux/fbcon.h>
#include <linux/font.h>
#include <linux/fs.h>
#include <linux/io.h>
#include <linux/iopoll.h>
#include <linux/ktime.h>
#include <linux/miscdevice.h>
#include <linux/mm.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of_address.h>
#include <linux/platform_device.h>
#include <linux/slab.h>
#include <linux/uaccess.h>
#include <linux/vmalloc.h>
#include <linux/workqueue.h>
#include <linux/spinlock.h>
#include "prodock-cache.h"
#include "prodock-validate.h"
#include "prodock-text-model.h"
#define FB_BASE 0x01700000U
#define PD_CELL_STRIDE 160
#define PD_CELL_ROWS 45
#define PD_CELLS (PD_CELL_STRIDE * PD_CELL_ROWS)
#define PD_DEBUG_ROWS 23
#define PD_DEBUG_CELLS (PD_CELL_STRIDE * PD_DEBUG_ROWS)
#define PD_SNAPSHOT_CELLS (PD_CELLS + PD_DEBUG_CELLS)
struct prodock_gpu {
    void __iomem *display, *accel, *memory, *text_io, *usb;
    struct mutex lock;
    struct mutex layout_lock;
    struct miscdevice misc, desktop;
    struct fb_info *fb;
    void __iomem *fb_io;
    struct fb_deferred_io defio;
    struct delayed_work flush;
    u32 pseudo_palette[16];
    bool opened, faulted;
    spinlock_t text_lock;
    struct delayed_work text_work;
    u16 cells[PD_CELLS], debug_cells[PD_DEBUG_CELLS], snapshot[PD_SNAPSHOT_CELLS];
    struct prodock_display_geometry geometry;
    unsigned width, height, pitch, fb_size, columns, rows, debug_rows;
    unsigned map_width, map_height, map_bytes, map_w_log2, map_h_log2;
    u8 font[4096], font_snapshot[4096];
    u32 text_palette[16];
    u8 *atlas;
    u16 *maps;
    u16 *cell_shadow;
    bool map_valid[2];
    unsigned map_columns[2], map_rows[2];
    unsigned layout, map_bank, atlas_bank, text_updates, game_presents;
    unsigned cursor_x, cursor_y;
    bool text_ready, text_dirty, font_dirty, cursor_on;
    u64 sent;
    u64 feed_ns, wait_ns, cache_ns, present_ns, text_ns;
    struct prodock_scene scene;
    /* Relative bank numbering: the first complete upload establishes bank 0.
     * Only present_raw commits after text_init, always with composition on. */
    struct prodock_scene descriptors[2];
    unsigned descriptor_bank;
    bool descriptor_valid[2];
    unsigned long last_game_present;
};
static int display_wait(struct prodock_gpu *p)
{
    u32 val;
    int ret = readl_poll_timeout(p->display + 12, val, !(val & 1), 100, 250000);
    if (ret) p->faulted = true;
    return ret;
}
static u32 gpu_errors(struct prodock_gpu *p)
{
    return readl(p->accel + 12) | readl(p->accel + 28) |
        readl(p->accel + 36) | readl(p->accel + 52);
}
static int present_raw(struct prodock_gpu *p, const struct prodock_scene *s);
#include "prodock-text.h"
static int fb_restore(struct prodock_gpu *p)
{
    unsigned i;
    int ret;
    if (p->text_ready) {
        p->scene = (struct prodock_scene){ .base = FB_BASE, .stride = p->pitch, .format = 3 };
        return text_present(p);
    }
    ret = display_wait(p);
    if (ret) return ret;
    /* C37 pipelines RGB fetches when composition is enabled, even with
     * empty overlay tables. The legacy direct reader misses deadlines
     * under simultaneous rendering/CPU traffic. Clear the inactive bank. */
    for (i = 0; i < 128; ++i) writel(0, p->display + 0x800 + i * 4);
    for (i = 0; i < 256; ++i) writel(0, p->display + 0xc00 + i * 4);
    writel(FB_BASE, p->display + 4);
    writel(p->pitch, p->display + 0x6c);
    writel(1, p->display + 0x30); writel(0, p->display + 0x40);
    writel(3, p->display + 8); writel(1, p->display + 12);
    return display_wait(p);
}
static int gpu_open(struct inode *inode, struct file *file)
{
    struct miscdevice *misc = file->private_data;
    struct prodock_gpu *p = container_of(misc, struct prodock_gpu, misc);
    int ret = 0;
    if (!capable(CAP_SYS_RAWIO)) return -EPERM;
    mutex_lock(&p->lock);
    if (p->opened) ret = -EBUSY;
    else if (p->faulted) ret = -EIO;
    else { p->opened = true; file->private_data = p; }
    mutex_unlock(&p->lock);
    return ret;
}
static int gpu_release(struct inode *inode, struct file *file)
{
    struct prodock_gpu *p = file->private_data;
    int ret;
    mutex_lock(&p->lock);
    if (p->layout == PRODOCK_GAME) {
        unsigned long flags;
        p->layout = PRODOCK_SPLIT;
        spin_lock_irqsave(&p->text_lock, flags); p->text_dirty = true;
        spin_unlock_irqrestore(&p->text_lock, flags);
    }
    ret = fb_restore(p);
    p->opened = false;
    mutex_unlock(&p->lock);
    schedule_delayed_work(&p->flush, 0);
    return ret;
}
static int submit(struct prodock_gpu *p, const struct prodock_batch *batch)
{
    unsigned i, j, expected;
    bool geometry = false;
    u32 val;
    int ret;
    u64 stamp;
    if (!batch->count || batch->count > PRODOCK_BATCH_MAX || batch->reserved) return -EINVAL;
    /* Validate the ENTIRE batch before touching the FIFO. */
    for (i = 0; i < batch->count; ++i) {
        ret = prodock_command(batch->commands[i]);
        if (ret) return ret;
        if ((batch->commands[i][0] >> 24) >= PRODOCK_GEOM_MATRIX) geometry = true;
    }
    /* A missing optional frontend must not reach the FIFO or fault the GPU.
     * Legacy batches do not add any MMIO/capability polling to their path. */
    if (geometry && readl(p->accel + 0x48) != PRODOCK_GEOMETRY_SIGNATURE)
        return -EOPNOTSUPP;
    if (gpu_errors(p)) return -EIO;
    expected = (readl(p->accel + 8) + batch->count) & 65535;
    stamp = ktime_get_ns();
    ret = prodock_cache_sync();
    p->cache_ns += ktime_get_ns() - stamp;
    if (ret) goto fault;
    wmb(); /* Publish CPU writes before GPU reads; no programmable PMA on A25. */
    (void)readl(p->memory);
    stamp = ktime_get_ns();
    for (i = 0; i < batch->count; ++i)
        for (j = 0; j < 8; ++j) {
            /* One writer: a free word cannot be consumed by another client. */
            /* The timer path is expensive on this RV32 core. Avoid it when
             * the FIFO already has room; a full FIFO still has a real,
             * bounded deadline. No scheduler sleep between adjacent words. */
            /* Same-peripheral relaxed IO keeps FIFO/status order. The
             * publication barrier above and completion barrier below order
             * normal DDR memory; no full fence is needed for every word. */
            if (readl_relaxed(p->accel + 4) & 2) {
                ret = read_poll_timeout(readl_relaxed, val, !(val & 2), 0, 250000,
                                        false, p->accel + 4);
                if (ret) goto fault;
            }
            writel_relaxed(batch->commands[i][j], p->accel + 16);
            if (j == 7) ++p->sent;
        }
    mb();
    p->feed_ns += ktime_get_ns() - stamp;
    stamp = ktime_get_ns();
    ret = readl_poll_timeout(p->accel + 8, val, (val & 65535) == expected, 50, 2000000);
    if (ret) goto fault;
    /* Published error counters have a separate CDC synchronizer. */
    usleep_range(10, 20);
    p->wait_ns += ktime_get_ns() - stamp;
    if (gpu_errors(p)) { ret = -EIO; goto fault; }
    stamp = ktime_get_ns();
    ret = prodock_cache_sync();
    p->cache_ns += ktime_get_ns() - stamp;
    if (ret) goto fault;
    return 0;
fault:
    p->faulted = true; /* Outcome unknown: never replay after a timeout. */
    return ret;
}
static int present_raw(struct prodock_gpu *p, const struct prodock_scene *s)
{
    unsigned i, j;
    unsigned bank = p->descriptor_bank;
    struct prodock_scene *old = &p->descriptors[bank];
    bool valid = p->descriptor_valid[bank];
    u64 stamp = ktime_get_ns();
    int ret = display_wait(p);
    if (ret) return ret;
    for (i = 0; i < 16; ++i)
        for (j = 0; j < 8; ++j)
            if (!valid || old->layers[i][j] != s->layers[i][j])
                writel(s->layers[i][j], p->display + 0x800 + i * 32 + j * 4);
    for (i = 0; i < 64; ++i)
        for (j = 0; j < 4; ++j)
            if (!valid || old->sprites[i][j] != s->sprites[i][j])
                writel(s->sprites[i][j], p->display + 0xc00 + i * 16 + j * 4);
    ret = prodock_cache_sync();
    if (ret) { p->faulted = true; return ret; }
    wmb(); (void)readl(p->memory);
    writel(s->base, p->display + 4); writel(s->stride, p->display + 0x6c);
    /* Always enable composition: this also selects C37's pipelined RGB
     * reader and atomically flips descriptor banks. Disabled layers were
     * replaced by a zero table before reaching this function. */
    writel(1, p->display + 0x30);
    writel(s->sprites_enabled, p->display + 0x40);
    writel(s->format, p->display + 8); writel(1, p->display + 12);
    ret = display_wait(p);
    if (!ret) {
        *old = *s;
        p->descriptor_valid[bank] = true;
        p->descriptor_bank ^= 1;
    }
    p->present_ns += ktime_get_ns() - stamp;
    return ret;
}
static int present(struct prodock_gpu *p, const struct prodock_scene *s)
{
    unsigned i;
    int ret = prodock_scene_valid_for(s, p->width, p->height);
    if (ret) return ret;
    /* A half-resolution desktop surface uses the same 1600-byte pitch and
     * 480-row allocation in both layouts. The split scanout reads full
     * lines; opaque terminal planes cover the unused right/bottom pixels. */
    if (s->format == 7 && (s->stride < p->pitch || !prodock_range(s->base, (__u64)s->stride * p->height)))
        return -ERANGE;
    for (i = 12; i < 16; ++i)
        if (s->layers_enabled && (s->layers[i][6] & 1)) return -EBUSY;
    /* Sprites behind layer 12 cannot obscure either system console. */
    for (i = 0; i < 64; ++i)
        if (s->sprites_enabled && (s->sprites[i][2] & (1U << 16)) &&
            ((s->sprites[i][2] >> 20) & 15) >= 12) return -EBUSY;
    p->scene = *s;
    ret = text_present(p);
    if (!ret) { ++p->game_presents; p->last_game_present = jiffies; }
    return ret;
}
static long gpu_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
    struct prodock_gpu *p = file->private_data;
    void __user *user = (void __user *)arg;
    void *data = NULL;
    size_t size;
    long ret = 0;
    unsigned i;
    if (cmd == PRODOCK_INFO) {
        struct prodock_info info;
        mutex_lock(&p->lock);
        info = (struct prodock_info){ .abi = PRODOCK_ABI, .memory_base = PRODOCK_GPU_BASE,
            .memory_bytes = PRODOCK_GPU_BYTES, .width = p->width, .height = p->height,
            .caps = readl(p->accel + 48), .done = readl(p->accel + 8),
            .errors = gpu_errors(p), .underflows = readl(p->display + 28),
            .frames = readl(p->display + 24), .checksum = readl(p->display + 0x60),
            .faulted = p->faulted };
        mutex_unlock(&p->lock);
        return copy_to_user(user, &info, sizeof(info)) ? -EFAULT : 0;
    }
    if (cmd == PRODOCK_GEOMETRY_INFO) {
        struct prodock_geometry_info info = {0};
        mutex_lock(&p->lock);
        info.signature = readl(p->accel + 0x48);
        if (info.signature != PRODOCK_GEOMETRY_SIGNATURE) {
            mutex_unlock(&p->lock);
            return -EOPNOTSUPP;
        }
        info.errors = readl(p->accel + 0x4c);
        info.vertices = readl(p->accel + 0x50);
        info.triangles = readl(p->accel + 0x54);
        info.culled = readl(p->accel + 0x58);
        info.intersections = readl(p->accel + 0x5c);
        info.slivers = readl(p->accel + 0x60);
        info.cycles = readl(p->accel + 0x64);
        mutex_unlock(&p->lock);
        return copy_to_user(user, &info, sizeof(info)) ? -EFAULT : 0;
    }
    switch (cmd) {
    case PRODOCK_SUBMIT: size = sizeof(struct prodock_batch); break;
    case PRODOCK_PRESENT: size = sizeof(struct prodock_scene); break;
    case PRODOCK_PALETTE: size = sizeof(struct prodock_palette); break;
    case PRODOCK_FONT: size = sizeof(struct prodock_font); break;
    default: return -ENOTTY;
    }
    data = memdup_user(user, size);
    if (IS_ERR(data)) return PTR_ERR(data);
    mutex_lock(&p->lock);
    if (p->faulted) { ret = -EIO; goto out; }
    if (cmd == PRODOCK_SUBMIT) ret = submit(p, data);
    else if (cmd == PRODOCK_PRESENT) {
        struct prodock_scene *s = data;
        if (!s->layers_enabled) memset(s->layers, 0, sizeof(s->layers));
        ret = present(p, s);
    } else if (cmd == PRODOCK_PALETTE) {
        const struct prodock_palette *c = data;
        for (i = 240; i < 256; ++i)
            if (c->rgb[i]) { ret = -EINVAL; goto out; }
        for (i = 0; i < 240; ++i) writel(c->rgb[i] & 0x3ffff, p->display + 0x400 + i * 4);
    } else {
        const struct prodock_font *f = data;
        writel(0, p->accel + 20);
        for (i = 0; i < 4096; ++i) writel(f->bytes[i], p->accel + 24);
    }
out:
    mutex_unlock(&p->lock); kfree(data); return ret;
}
static int gpu_mmap(struct file *file, struct vm_area_struct *vma)
{
    u64 off = (u64)vma->vm_pgoff << PAGE_SHIFT;
    unsigned long length = vma->vm_end - vma->vm_start;
    if (!(vma->vm_flags & VM_SHARED) || (vma->vm_flags & VM_EXEC) ||
        off >= PRODOCK_GPU_BYTES || length > PRODOCK_GPU_BYTES - off) return -EINVAL;
    vm_flags_clear(vma, VM_MAYEXEC);
    vm_flags_set(vma, VM_IO | VM_DONTEXPAND | VM_DONTDUMP);
    vma->vm_page_prot = pgprot_noncached(vma->vm_page_prot);
    return remap_pfn_range(vma, vma->vm_start, (PRODOCK_GPU_BASE + off) >> PAGE_SHIFT,
                           length, vma->vm_page_prot);
}
static const struct file_operations gpu_fops = {
    .owner = THIS_MODULE, .open = gpu_open, .release = gpu_release,
    .unlocked_ioctl = gpu_ioctl, .mmap = gpu_mmap,
};
static void fb_flush(struct work_struct *work)
{
    struct prodock_gpu *p = container_of(to_delayed_work(work), struct prodock_gpu, flush);
    mutex_lock(&p->lock);
    if (!p->text_ready && !p->opened && !p->faulted) {
        memcpy_toio(p->fb_io, p->fb->screen_buffer, p->fb_size);
        if (prodock_cache_sync()) p->faulted = true;
    }
    mutex_unlock(&p->lock);
}
static void fb_damage(struct fb_info *info, off_t offset, size_t length)
{
    struct prodock_gpu *p = info->par;
    if (offset >= 0 && offset < p->fb_size && length)
        schedule_delayed_work(&p->flush, max(1, HZ / 20));
}
static void fb_area(struct fb_info *info, u32 x, u32 y, u32 w, u32 h)
{
    struct prodock_gpu *p = info->par;
    if (y < p->height && w && h) fb_damage(info, y * p->pitch, min(h, p->height - y) * p->pitch);
}
static void fb_deferred(struct fb_info *info, struct list_head *pages)
{
    struct prodock_gpu *p = info->par;
    fb_damage(info, 0, p->fb_size);
}
FB_GEN_DEFAULT_DEFERRED_SYSMEM_OPS(prodock_fb, fb_damage, fb_area)
static int fb_color(unsigned n, unsigned r, unsigned g, unsigned b, unsigned a, struct fb_info *info)
{
    struct prodock_gpu *p = info->par;
    if (n >= 16) return -EINVAL;
    p->pseudo_palette[n] = (r & 0xf800) | ((g >> 5) & 0x7e0) | (b >> 11);
    /* Palette updates are rare; the worker publishes them with the maps. */
    {
        unsigned long flags;
        spin_lock_irqsave(&p->text_lock, flags);
        p->text_palette[n] = ((r >> 10) << 12) | ((g >> 10) << 6) | (b >> 10);
        p->text_dirty = true;
        spin_unlock_irqrestore(&p->text_lock, flags);
        schedule_delayed_work(&p->text_work, 0);
    }
    return 0;
}
static int fb_check(struct fb_var_screeninfo *v, struct fb_info *info)
{
    struct prodock_gpu *p = info->par;
    if (!((v->xres == p->width && v->yres == p->height) ||
          (v->xres == p->width / 2 && v->yres == p->height / 2)) ||
        v->xres_virtual != v->xres || v->yres_virtual != v->yres ||
        v->bits_per_pixel != 16 || v->xoffset || v->yoffset || v->rotate || v->nonstd) return -EINVAL;
    v->red = (struct fb_bitfield){ 11, 5, 0 }; v->green = (struct fb_bitfield){ 5, 6, 0 };
    v->blue = (struct fb_bitfield){ 0, 5, 0 }; v->transp = (struct fb_bitfield){ 0, 0, 0 };
    return 0;
}
static int fb_open(struct fb_info *info, int user)
{
    /* fb0 now backs fbcon tile operations, not a pixel surface. Refuse
     * userspace access instead of accepting invisible pixel writes or a
     * mode change bypassing the desktop manager. Games use the GPU ABI. */
    return user ? -EOPNOTSUPP : 0;
}
static const struct fb_ops prodock_fb_ops = {
    .owner = THIS_MODULE, .fb_open = fb_open, .fb_check_var = fb_check, .fb_setcolreg = fb_color,
    FB_DEFAULT_DEFERRED_OPS(prodock_fb),
};
static int prodock_gpu_probe(struct platform_device *pdev)
{
    struct prodock_gpu *p;
    struct device_node *node;
    struct resource memory;
    struct fb_info *info;
    int ret;
    info = framebuffer_alloc(sizeof(*p), &pdev->dev);
    if (!info) return -ENOMEM;
    p = info->par; p->fb = info; mutex_init(&p->lock); mutex_init(&p->layout_lock);
    spin_lock_init(&p->text_lock);
    INIT_DELAYED_WORK(&p->text_work, text_flush);
    INIT_DELAYED_WORK(&p->flush, fb_flush);
    ret = prodock_cache_probe();
    if (ret) goto fail;
    p->display = devm_platform_ioremap_resource(pdev, 0);
    if (IS_ERR(p->display)) { ret = PTR_ERR(p->display); goto fail; }
    p->accel = devm_platform_ioremap_resource(pdev, 1);
    if (IS_ERR(p->accel)) { ret = PTR_ERR(p->accel); goto fail; }
    if (readl(p->display) != 0x47505531 || readl(p->accel) != 0x424c5432 || readl(p->accel + 48) != 0x1ff) {
        ret = -ENODEV; goto fail;
    }
    /* Dimensions are explicit in new device trees and checked against the
     * FPGA. Old G22 images have no geometry registers: accept 800x480 only. */
    p->width = 800; p->height = 480;
    of_property_read_u32(pdev->dev.of_node, "width", &p->width);
    of_property_read_u32(pdev->dev.of_node, "height", &p->height);
    if (!((p->width == 800 && p->height == 480) || (p->width == 1280 && p->height == 720)) ||
        (readl(p->display + 0x70) != (p->height << 16 | p->width) &&
         (p->width != 800 || readl(p->display + 0x70) != 0))) { ret = -ENODEV; goto fail; }
    p->geometry = (struct prodock_display_geometry){ .width = p->width, .height = p->height,
        .pixel_hz = 35000000, .memory_hz = 75000000, .htotal = 1193, .vtotal = 533 };
    of_property_read_u32(pdev->dev.of_node, "pixel-clock-hz", &p->geometry.pixel_hz);
    of_property_read_u32(pdev->dev.of_node, "memory-clock-hz", &p->geometry.memory_hz);
    of_property_read_u32(pdev->dev.of_node, "horizontal-total", &p->geometry.htotal);
    of_property_read_u32(pdev->dev.of_node, "vertical-total", &p->geometry.vtotal);
    of_property_read_u32(pdev->dev.of_node, "board-id", &p->geometry.board);
    if (!p->geometry.pixel_hz || !p->geometry.memory_hz || p->geometry.htotal < p->width ||
        p->geometry.vtotal < p->height || p->geometry.htotal > 2048 || p->geometry.vtotal > 1024) {
        ret = -EINVAL; goto fail;
    }
    if (readl(p->display + 0x74) && readl(p->display + 0x74) !=
        (p->geometry.vtotal << 16 | p->geometry.htotal)) { ret = -ENODEV; goto fail; }
    p->geometry.line_budget = div_u64((u64)p->geometry.memory_hz * p->geometry.htotal, p->geometry.pixel_hz);
    p->pitch = p->width * 2; p->fb_size = p->pitch * p->height;
    p->columns = p->width / 8; p->rows = p->height / 16; p->debug_rows = DIV_ROUND_UP(p->height / 2, 16);
    p->map_w_log2 = p->width == 1280 ? 8 : 7; p->map_h_log2 = p->height == 720 ? 7 : 6;
    p->map_width = 1U << p->map_w_log2; p->map_height = 1U << p->map_h_log2;
    p->map_bytes = 2 * p->map_width * p->map_height;
    node = of_parse_phandle(pdev->dev.of_node, "memory-region", 0);
    ret = node ? of_address_to_resource(node, 0, &memory) : -EINVAL;
    of_node_put(node);
    if (ret) goto fail;
    if (memory.start != PRODOCK_GPU_BASE || resource_size(&memory) != PRODOCK_RESERVED_BYTES) { ret = -EINVAL; goto fail; }
    if (!devm_request_mem_region(&pdev->dev, memory.start, resource_size(&memory), "prodock-gpu-ddr")) {
        ret = -EBUSY; goto fail;
    }
    p->memory = devm_ioremap(&pdev->dev, memory.start, PAGE_SIZE);
    p->fb_io = devm_ioremap(&pdev->dev, FB_BASE, PAGE_ALIGN(p->fb_size));
    if (!p->memory || !p->fb_io) { ret = -ENOMEM; goto fail; }
    info->screen_buffer = vzalloc(PAGE_ALIGN(p->fb_size));
    if (!info->screen_buffer) { ret = -ENOMEM; goto fail; }
    info->screen_size = p->fb_size;
    memset_io(p->fb_io, 0, p->fb_size);
    ret = prodock_cache_sync();
    if (ret) goto pixels;
    info->fix = (struct fb_fix_screeninfo){ .id = "ProDock C37", .smem_start = 0,
        .smem_len = p->fb_size, .type = FB_TYPE_PACKED_PIXELS, .visual = FB_VISUAL_TRUECOLOR,
        .line_length = p->pitch, .accel = FB_ACCEL_NONE };
    info->var = (struct fb_var_screeninfo){ .xres = p->width / 2, .yres = p->height / 2, .xres_virtual = p->width / 2,
        .yres_virtual = p->height / 2, .bits_per_pixel = 16, .width = -1, .height = -1 };
    fb_check(&info->var, info);
    info->fbops = &prodock_fb_ops; info->pseudo_palette = p->pseudo_palette;
    info->flags = FBINFO_VIRTFB | FBINFO_MISC_TILEBLITTING;
    info->tileops = &prodock_tile_ops;
    bitmap_zero(info->pixmap.blit_x, FB_MAX_BLIT_WIDTH);
    bitmap_zero(info->pixmap.blit_y, FB_MAX_BLIT_HEIGHT);
    set_bit(7, info->pixmap.blit_x); set_bit(15, info->pixmap.blit_y);
    ret = text_init(p, pdev);
    if (ret) goto pixels;
    p->defio.delay = max(1, HZ / 20); p->defio.deferred_io = fb_deferred;
    info->fbdefio = &p->defio;
    ret = fb_deferred_io_init(info);
    if (ret) goto pixels;
    ret = fb_alloc_cmap(&info->cmap, 16, 0);
    if (ret) goto defio;
    ret = fb_restore(p);
    if (ret) goto cmap;
    ret = register_framebuffer(info);
    if (ret) goto cmap;
    p->misc = (struct miscdevice){ .minor = MISC_DYNAMIC_MINOR, .name = "prodock-gpu",
        .fops = &gpu_fops, .parent = &pdev->dev, .mode = 0600 };
    ret = misc_register(&p->misc);
    if (ret) { unregister_framebuffer(info); goto cmap; }
    p->desktop = (struct miscdevice){ .minor = MISC_DYNAMIC_MINOR, .name = "prodock-display",
        .fops = &desktop_fops, .parent = &pdev->dev, .mode = 0600 };
    ret = misc_register(&p->desktop);
    if (ret) { misc_deregister(&p->misc); unregister_framebuffer(info); goto cmap; }
    platform_set_drvdata(pdev, p);
    dev_info(&pdev->dev, "GPU V1: hardware text, split/game/terminal, 86 MiB for applications\n");
    return 0;
cmap:
    cancel_delayed_work_sync(&p->flush);
    fb_dealloc_cmap(&info->cmap);
defio:
    fb_deferred_io_cleanup(info);
pixels:
    cancel_delayed_work_sync(&p->text_work);
    vfree(p->atlas); vfree(p->maps); vfree(p->cell_shadow);
    vfree(info->screen_buffer);
fail: framebuffer_release(info); return ret;
}
static const struct of_device_id prodock_gpu_match[] = {
    { .compatible = "mjx,prodock-gpu-v1" }, { }
};
static struct platform_driver prodock_gpu_driver = {
    .probe = prodock_gpu_probe,
    .driver = { .name = "prodock-gpu", .of_match_table = prodock_gpu_match,
                .suppress_bind_attrs = true },
};
builtin_platform_driver(prodock_gpu_driver);
MODULE_LICENSE("GPL");
