/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Included by prodock-gpu.c. fbcon callbacks never sleep or touch MMIO:
 * console_lock -> text_lock; worker/display ioctls -> GPU lock -> text_lock.
 * There is no path from GPU lock back to console_lock. */
static void text_changed(struct prodock_gpu *p)
{
    p->text_dirty = true; /* caller holds text_lock */
    schedule_delayed_work(&p->text_work, max(1, HZ / 30));
}
static bool text_rect(u32 x, u32 y, u32 w, u32 h)
{
    return x < 100 && y < 30 && w <= 100 - x && h <= 30 - y;
}
static void text_font(struct fb_info *info, struct fb_tilemap *map)
{
    struct prodock_gpu *p = info->par;
    unsigned long flags;
    if (map->width != 8 || map->height != 16 || map->depth != 1 || map->length > 256) return;
    spin_lock_irqsave(&p->text_lock, flags);
    if (memcmp(p->font, map->data, map->length * 16)) {
        memset(p->font, 0, sizeof(p->font));
        memcpy(p->font, map->data, map->length * 16);
        p->font_dirty = true; text_changed(p);
    }
    spin_unlock_irqrestore(&p->text_lock, flags);
}
static void text_copy(struct fb_info *info, struct fb_tilearea *a)
{
    struct prodock_gpu *p = info->par;
    unsigned long flags;
    unsigned i, row;
    if (!text_rect(a->sx,a->sy,a->width,a->height) || !text_rect(a->dx,a->dy,a->width,a->height)) return;
    spin_lock_irqsave(&p->text_lock, flags);
    for (i = 0; i < a->height; ++i) {
        row = a->dy > a->sy ? a->height - 1 - i : i;
        memmove(p->cells + (a->dy + row) * 100 + a->dx,
                p->cells + (a->sy + row) * 100 + a->sx, a->width * sizeof(u16));
    }
    text_changed(p); spin_unlock_irqrestore(&p->text_lock, flags);
}
static void text_fill(struct fb_info *info, struct fb_tilerect *r)
{
    struct prodock_gpu *p = info->par;
    unsigned long flags;
    unsigned x,y;
    u16 cell = (r->index & 255) | (r->fg & 15) << 8 | (r->bg & 15) << 12;
    if (!text_rect(r->sx,r->sy,r->width,r->height)) return;
    spin_lock_irqsave(&p->text_lock, flags);
    for (y = 0; y < r->height; ++y) for (x = 0; x < r->width; ++x)
        p->cells[(r->sy + y) * 100 + r->sx + x] = cell;
    text_changed(p); spin_unlock_irqrestore(&p->text_lock, flags);
}
static void text_blit(struct fb_info *info, struct fb_tileblit *b)
{
    struct prodock_gpu *p = info->par;
    unsigned long flags;
    unsigned x,y,i=0;
    u16 colour = (b->fg & 15) << 8 | (b->bg & 15) << 12;
    if (!text_rect(b->sx,b->sy,b->width,b->height)) return;
    spin_lock_irqsave(&p->text_lock, flags);
    for (y = 0; y < b->height && i < b->length; ++y)
        for (x = 0; x < b->width && i < b->length; ++x)
            p->cells[(b->sy + y) * 100 + b->sx + x] = colour | (b->indices[i++] & 255);
    text_changed(p); spin_unlock_irqrestore(&p->text_lock, flags);
}
static void text_cursor(struct fb_info *info, struct fb_tilecursor *c)
{
    struct prodock_gpu *p = info->par;
    unsigned long flags;
    spin_lock_irqsave(&p->text_lock, flags);
    p->cursor_x = c->sx; p->cursor_y = c->sy;
    p->cursor_on = c->mode && c->shape != FB_TILE_CURSOR_NONE && c->sx < 100 && c->sy < 30;
    text_changed(p); spin_unlock_irqrestore(&p->text_lock, flags);
}
static int text_max(struct fb_info *info) { return 256; }
static const struct fb_tile_ops prodock_tile_ops = {
    .fb_settile = text_font, .fb_tilecopy = text_copy, .fb_tilefill = text_fill,
    .fb_tileblit = text_blit, .fb_tilecursor = text_cursor, .fb_get_tilemax = text_max,
};
/* GPU lock held. Fill only inactive maps/atlas; commit acknowledges that the
 * reader has stopped using the old descriptor bank before it can be reused. */
static int text_present(struct prodock_gpu *p)
{
    struct prodock_scene s = p->scene;
    unsigned long flags;
    unsigned i, bank = p->map_bank, atlas = p->atlas_bank;
    unsigned cols = p->layout == PRODOCK_TERMINAL ? 100 : 50;
    unsigned rows = p->layout == PRODOCK_TERMINAL ? 30 : 15;
    int ret, cursor;
    bool dirty, font_dirty;
    u32 palette[16];
    u64 stamp = ktime_get_ns();
    if (p->faulted) return -EIO;
    ret = display_wait(p);
    if (ret) return ret;
    spin_lock_irqsave(&p->text_lock, flags);
    dirty = p->text_dirty; font_dirty = p->font_dirty;
    if (dirty) {
        memcpy(p->snapshot, p->cells, sizeof(p->cells));
        memcpy(p->snapshot + 3000, p->debug_cells, sizeof(p->debug_cells));
        if (font_dirty) memcpy(p->font_snapshot, p->font, sizeof(p->font));
        memcpy(palette, p->text_palette, sizeof(palette));
        p->text_dirty = false; p->font_dirty = false;
    }
    cursor = p->cursor_on ? p->cursor_y * 100 + p->cursor_x : -1;
    spin_unlock_irqrestore(&p->text_lock, flags);
    if (dirty) {
        bank ^= 1;
        if (font_dirty) {
            atlas ^= 1;
            pd_text_atlas(p->atlas, p->font_snapshot);
            memcpy_toio(p->text_io + atlas * PD_ATLAS_BYTES, p->atlas, PD_ATLAS_BYTES);
        }
        {
            unsigned part,x,y,half;
            bool full = !p->map_valid[bank] || p->map_columns[bank] != cols || p->map_rows[bank] != rows;
            u16 *old = p->cell_shadow + bank * 4500;
            void __iomem *dst = p->text_io + PD_MAP_OFFSET + bank * PD_MAP_BANK_BYTES;
            if (full) {
                pd_text_map(p->maps, p->maps + PD_MAP_BYTES / 2, p->snapshot, cols, rows, cursor);
                pd_text_map(p->maps + PD_MAP_BYTES, p->maps + PD_MAP_BYTES * 3 / 2,
                            p->snapshot + 3000, 100, 15, -1);
                memcpy_toio(dst, p->maps, PD_MAP_BANK_BYTES);
            }
            /* Compare character pairs, not entire 64 KiB tile maps. Each
             * bank keeps its OWN effective cells (including the cursor).
             * A changed pair needs four aligned DDR writes, no readback. */
            for (part = 0; part < 2; ++part) {
                unsigned base = part ? 3000 : 0;
                unsigned width = part ? 100 : cols, height = part ? 15 : rows;
                for (y = 0; y < height; ++y) for (x = 0; x < width; x += 2) {
                    unsigned index = base + y * 100 + x;
                    u16 a = pd_text_cell(p->snapshot[index], !part && cursor == (int)(y * 100 + x));
                    u16 b = pd_text_cell(p->snapshot[index + 1], !part && cursor == (int)(y * 100 + x + 1));
                    if (!full && old[index] == a && old[index + 1] == b) continue;
                    if (!full) for (half = 0; half < 2; ++half) {
                        unsigned off = part * 2 * PD_MAP_BYTES + ((y * 2 + half) * 128 + x) * 2;
                        writel_relaxed(pd_text_pair(a,b,half,0), dst + off);
                        writel_relaxed(pd_text_pair(a,b,half,1), dst + off + PD_MAP_BYTES);
                    }
                    old[index] = a; old[index + 1] = b;
                }
            }
            p->map_valid[bank] = true;
            p->map_columns[bank] = cols; p->map_rows[bank] = rows;
            /* present_raw publishes the data with cache sync + wmb. */
        }
        for (i = 0; i < 16; ++i) writel(palette[i], p->display + 0x400 + (240 + i) * 4);
    }
    if (!s.layers_enabled) memset(s.layers, 0, sizeof(s.layers));
    if (!s.sprites_enabled) memset(s.sprites, 0, sizeof(s.sprites));
    memset(s.layers + 12, 0, 4 * sizeof(s.layers[0]));
    if (p->layout != PRODOCK_GAME) {
        if (s.format == 7) s.format = 3;
        pd_text_layer(s.layers[12], bank, 0, atlas, p->layout == PRODOCK_SPLIT ? 400 : 0,
                       0, cols * 8, rows * 16);
        pd_text_layer(s.layers[13], bank, 1, atlas, p->layout == PRODOCK_SPLIT ? 400 : 0,
                       0, cols * 8, rows * 16);
        if (p->layout == PRODOCK_SPLIT) {
            pd_text_layer(s.layers[14], bank, 2, atlas, 0, 240, 800, 240);
            pd_text_layer(s.layers[15], bank, 3, atlas, 0, 240, 800, 240);
        }
    }
    s.layers_enabled = 1;
    p->text_ns += ktime_get_ns() - stamp;
    ret = present_raw(p, &s);
    if (!ret) {
        p->map_bank = bank; p->atlas_bank = atlas;
        if (dirty) ++p->text_updates;
    }
    return ret;
}
static void text_flush(struct work_struct *work)
{
    struct prodock_gpu *p = container_of(to_delayed_work(work), struct prodock_gpu, text_work);
    mutex_lock(&p->lock);
    /* A game PRESENT may already have consumed this dirty snapshot. */
    if (p->text_ready && !p->faulted && READ_ONCE(p->text_dirty)) {
        /* A running game will publish these cells in its next PRESENT.
         * Avoid inserting an extra vblank/lock wait between SUBMIT/PRESENT.
         * If it stops presenting, the terminal still refreshes within 50 ms
         * plus its next vblank (instead of waiting for the application). */
        if (p->opened && time_before(jiffies, p->last_game_present + max(1, HZ / 20)))
            schedule_delayed_work(&p->text_work, max(1, HZ / 20));
        else text_present(p);
    }
    mutex_unlock(&p->lock);
}
static int desktop_open(struct inode *inode, struct file *file)
{
    struct miscdevice *m = file->private_data;
    if (!capable(CAP_SYS_ADMIN)) return -EPERM;
    file->private_data = container_of(m, struct prodock_gpu, desktop);
    return 0;
}
static long desktop_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
    struct prodock_gpu *p = file->private_data;
    void __user *user = (void __user *)arg;
    unsigned long flags;
    int ret = 0;
    if (cmd == PRODOCK_DISPLAY_INFO) {
        struct prodock_display_info s;
        mutex_lock(&p->lock);
        s = (struct prodock_display_info){ .mode = p->layout,
            .columns = p->layout == PRODOCK_TERMINAL ? 100 : 50,
            .rows = p->layout == PRODOCK_TERMINAL ? 30 : 15,
            .text_updates = p->text_updates, .game_presents = p->game_presents,
            .sent_lo = (u32)p->sent, .sent_hi = p->sent >> 32,
            .frames = readl(p->display + 24), .done = readl(p->accel + 8),
            .errors = gpu_errors(p), .underflows = readl(p->display + 28),
            .line_cycles = readl(p->display + 0x64), .invalid_layers = readl(p->display + 0x38),
            .invalid_sprites = readl(p->display + 0x48),
            .usb_status = p->usb ? readl(p->usb + 4) : 0xffffffffU, .faulted = p->faulted,
            .checksum = readl(p->display + 0x60),
            .feed_us = div_u64(p->feed_ns, 1000), .wait_us = div_u64(p->wait_ns, 1000),
            .cache_us = div_u64(p->cache_ns, 1000), .present_us = div_u64(p->present_ns, 1000),
            .text_us = div_u64(p->text_ns, 1000) };
        mutex_unlock(&p->lock);
        return copy_to_user(user, &s, sizeof(s)) ? -EFAULT : 0;
    }
    if (cmd == PRODOCK_DEBUG_TEXT) {
        struct prodock_debug_text *s = memdup_user(user, sizeof(*s));
        if (IS_ERR(s)) return PTR_ERR(s);
        spin_lock_irqsave(&p->text_lock, flags);
        memcpy(p->debug_cells, s->cells, sizeof(p->debug_cells)); text_changed(p);
        spin_unlock_irqrestore(&p->text_lock, flags);
        kfree(s); return 0;
    }
    if (cmd == PRODOCK_LAYOUT) {
        struct prodock_layout s;
        struct fb_var_screeninfo v;
        if (copy_from_user(&s, user, sizeof(s))) return -EFAULT;
        if (s.mode > PRODOCK_TERMINAL || s.reserved[0] || s.reserved[1] || s.reserved[2]) return -EINVAL;
        mutex_lock(&p->layout_lock);
        console_lock();
        lock_fb_info(p->fb);
        v = p->fb->var;
        v.xres = v.xres_virtual = s.mode == PRODOCK_TERMINAL ? 800 : 400;
        v.yres = v.yres_virtual = s.mode == PRODOCK_TERMINAL ? 480 : 240;
        v.activate = FB_ACTIVATE_NOW | FB_ACTIVATE_ALL;
        ret = fbcon_modechange_possible(p->fb, &v);
        if (!ret) ret = fb_set_var(p->fb, &v);
        if (!ret) fbcon_update_vcs(p->fb, true);
        unlock_fb_info(p->fb);
        console_unlock();
        if (!ret) {
            mutex_lock(&p->lock);
            if (p->faulted) ret = -EIO;
            else {
                p->layout = s.mode;
                spin_lock_irqsave(&p->text_lock, flags); p->text_dirty = true;
                spin_unlock_irqrestore(&p->text_lock, flags);
                ret = text_present(p);
            }
            mutex_unlock(&p->lock);
        }
        mutex_unlock(&p->layout_lock);
        return ret;
    }
    return -ENOTTY;
}
static const struct file_operations desktop_fops = {
    .owner = THIS_MODULE, .open = desktop_open, .unlocked_ioctl = desktop_ioctl,
};
static int text_init(struct prodock_gpu *p, struct platform_device *pdev)
{
    const struct font_desc *f = find_font("VGA8x16");
    unsigned i;
    static const u32 colours[16] = {0x000000,0xaa0000,0x00aa00,0xaa5500,
        0x0000aa,0xaa00aa,0x00aaaa,0xaaaaaa,0x555555,0xff5555,0x55ff55,0xffff55,
        0x5555ff,0xff55ff,0x55ffff,0xffffff};
    if (!f || f->width != 8 || f->height != 16) return -ENODEV;
    p->text_io = devm_ioremap(&pdev->dev, PD_TEXT_BASE, 0x200000);
    p->usb = devm_platform_ioremap_resource(pdev, 2);
    if (IS_ERR(p->usb)) return PTR_ERR(p->usb);
    if (readl(p->usb) != 0x554d5343) return -ENODEV;
    p->atlas = vzalloc(PD_ATLAS_BYTES); p->maps = vzalloc(PD_MAP_BANK_BYTES);
    p->cell_shadow = vzalloc(2 * 4500 * sizeof(u16));
    if (!p->text_io || !p->atlas || !p->maps || !p->cell_shadow) return -ENOMEM;
    memcpy(p->font, f->data, sizeof(p->font));
    for (i = 0; i < 3000; ++i) p->cells[i] = 0x0720;
    for (i = 0; i < 1500; ++i) p->debug_cells[i] = 0x0720;
    for (i = 0; i < 16; ++i) {
        u32 c = colours[i];
        p->text_palette[i] = ((c >> 18) << 12) | (((c >> 10) & 63) << 6) | ((c >> 2) & 63);
    }
    p->text_dirty = p->font_dirty = p->text_ready = true;
    return 0;
}
