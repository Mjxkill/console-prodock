// SPDX-License-Identifier: GPL-2.0-only
// Two FPGA low-speed USB hosts, restricted to HID 081f:e401.
#include <linux/input.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>

struct neo_pad {
    void __iomem *regs;
    bool armed;
};

static const unsigned short neo_keys[] = {
    BTN_SOUTH, BTN_EAST, BTN_WEST, BTN_NORTH, BTN_TL, BTN_TR,
    BTN_TL2, BTN_TR2, BTN_SELECT, BTN_START,
};

static int neo_pad_open(struct input_dev *input)
{
    struct neo_pad *pad = input_get_drvdata(input);

    /* Polling stops while no application has the device open. A disconnect
     * or a held button in that gap must not become a fresh game action. The
     * input core calls open before restarting the poller under its mutex. */
    pad->armed = false;
    return 0;
}

static void neo_pad_poll(struct input_dev *input)
{
    struct neo_pad *pad = input_get_drvdata(input);
    u32 status, id, lo, hi, keys = 0;
    int x = 0, y = 0, i;

    /* STATUS atomically snapshots the ID and complete report in the FPGA. */
    status = readl(pad->regs);
    id = readl(pad->regs + 4);
    lo = readl(pad->regs + 12);
    hi = readl(pad->regs + 16);
    if ((status & 9) == 9 && id == 0xe401081f) {
        unsigned raw_x = lo & 255, raw_y = (lo >> 8) & 255;
        keys = (hi >> 12) & 0x3ff;
        x = raw_x < 64 ? -1 : raw_x >= 192 ? 1 : 0;
        y = raw_y < 64 ? -1 : raw_y >= 192 ? 1 : 0;
        /* An insertion with held buttons must not trigger a game action. */
        if (!keys && !x && !y) pad->armed = true;
        if (!pad->armed) { keys = 0; x = 0; y = 0; }
    } else {
        pad->armed = false;
    }
    input_report_abs(input, ABS_X, x);
    input_report_abs(input, ABS_Y, y);
    for (i = 0; i < ARRAY_SIZE(neo_keys); ++i)
        input_report_key(input, neo_keys[i], !!(keys & BIT(i)));
    input_sync(input);
}

static int neo_gamepads_probe(struct platform_device *pdev)
{
    void __iomem *regs = devm_platform_ioremap_resource(pdev, 0);
    int port, ret;

    if (IS_ERR(regs)) return PTR_ERR(regs);
    if (readl(regs) != 0x4e504144 || readl(regs + 4) != 0x00010002)
        return -ENODEV;
    for (port = 0; port < 2; ++port) {
        struct neo_pad *pad = devm_kzalloc(&pdev->dev, sizeof(*pad), GFP_KERNEL);
        struct input_dev *input = devm_input_allocate_device(&pdev->dev);
        int i;
        if (!pad || !input) return -ENOMEM;
        pad->regs = regs + 32 * (port + 1);
        input->name = port ? "Tang Neo gamepad 2" : "Tang Neo gamepad 1";
        input->phys = port ? "neo-usb/input1" : "neo-usb/input0";
        input->id.bustype = BUS_USB;
        input->id.vendor = 0x081f;
        input->id.product = 0xe401;
        input->open = neo_pad_open;
        input_set_drvdata(input, pad);
        input_set_abs_params(input, ABS_X, -1, 1, 0, 0);
        input_set_abs_params(input, ABS_Y, -1, 1, 0, 0);
        for (i = 0; i < ARRAY_SIZE(neo_keys); ++i)
            input_set_capability(input, EV_KEY, neo_keys[i]);
        ret = input_setup_polling(input, neo_pad_poll);
        if (ret) return ret;
        input_set_poll_interval(input, 10);
        ret = input_register_device(input);
        if (ret) return ret;
    }
    dev_info(&pdev->dev, "two USB gamepad ports, HID 081f:e401\n");
    return 0;
}

static const struct of_device_id neo_gamepads_match[] = {
    { .compatible = "mjx,neo-gamepads" }, {}
};
MODULE_DEVICE_TABLE(of, neo_gamepads_match);
static struct platform_driver neo_gamepads_driver = {
    .probe = neo_gamepads_probe,
    .driver = { .name = "neo-gamepads", .of_match_table = neo_gamepads_match },
};
module_platform_driver(neo_gamepads_driver);
MODULE_LICENSE("GPL");
