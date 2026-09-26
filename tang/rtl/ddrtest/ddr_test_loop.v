// ddr_test_loop.v — E1 : test DDR3 Sipeed pro_ddr_test, émission en boucle sur ttyUSB2 (if01).
//
// Différence avec le top Sipeed : la séquence d'émission (W, R, num_ok) rejoue indéfiniment
// (pause 1 s entre rafales) pour être capturable à tout moment. Le critère reste
// "57 52 FF FF FF" (W + R + num_ok = 0xFFFFFF : les 16 777 215 mots de 256 bits tous corrects).
// Le reste est strictement le design Sipeed : ddr3_test, FIFO, BAUDGEN/UART_TX, netlist DDR3.
`default_nettype none
module top (
    input  wire        sys_clk,   // 50 MHz P16
    output wire        uart_tx,   // P15 → BL616 → ttyUSB2 (115200)
    input  wire        rst_n,     // K16 USR_KEY.0 (actif haut au repos)
    output wire [5:0]  led,
    output wire [14:0] ddr_addr,
    output wire [2:0]  ddr_bank,
    output wire        ddr_cs,
    output wire        ddr_ras,
    output wire        ddr_cas,
    output wire        ddr_we,
    output wire        ddr_ck,
    output wire        ddr_ck_n,
    output wire        ddr_cke,
    output wire        ddr_odt,
    output wire        ddr_reset_n,
    output wire [3:0]  ddr_dm,
    inout  wire [31:0] ddr_dq,
    inout  wire [3:0]  ddr_dqs,
    inout  wire [3:0]  ddr_dqs_n
);
    wire clk100M;

    reg         uart_wr;
    wire        tx_done;
    reg  [7:0]  uart_wdata;
    wire        tx_empty;
    wire        tx_full;
    wire [7:0]  tx_data;
    wire        b_tick;

    FIFO #(.DWIDTH(8), .AWIDTH(13)) uFIFO_TX (
        .clk    (clk100M),
        .resetn (rst_n),
        .rd     (tx_done),
        .wr     (uart_wr),
        .w_data (uart_wdata),
        .empty  (tx_empty),
        .full   (tx_full),
        .r_data (tx_data)
    );

    BAUDGEN uBAUDGEN (.clk(clk100M), .resetn(rst_n), .baudtick(b_tick));

    UART_TX uUART_TX (
        .clk     (clk100M),
        .resetn  (rst_n),
        .tx_start(~tx_empty),
        .b_tick  (b_tick),
        .d_in    (tx_data),
        .tx_done (tx_done),
        .tx      (uart_tx)
    );

    wire pll_lock;
    wire memory_clk;
    wire pll_stop;

    Gowin_PLL upll (
        .lock   (pll_lock),
        .clkout0(),
        .clkout1(clk100M),
        .clkout2(memory_clk),
        .clkin  (sys_clk),
        .reset  (~rst_n),
        .enclk0 (1'b1),
        .enclk1 (1'b1),
        .enclk2 (pll_stop)
    );

    wire init_calib_complete;
    wire app_rdy;
    wire app_wdf_rdy;
    wire clk_x1;
    wire [2:0]   app_cmd;
    wire         app_en;
    wire [28:0]  app_addr;
    wire [255:0] app_wdf_data;
    wire         app_wdf_wren;
    wire         app_wdf_end;
    wire [255:0] app_rd_data;
    wire         app_rd_data_valid;
    wire         app_burst;
    wire [31:0]  app_wdf_mask;

    DDR3_Memory_Interface_Top u_ddr3 (
        .memory_clk         (memory_clk),
        .pll_stop           (pll_stop),
        .clk                (clk100M),
        .rst_n              (rst_n),
        .cmd_ready          (app_rdy),
        .cmd                (app_cmd),
        .cmd_en             (app_en),
        .addr               (app_addr),
        .wr_data_rdy        (app_wdf_rdy),
        .wr_data            (app_wdf_data),
        .wr_data_en         (app_wdf_wren),
        .wr_data_end        (app_wdf_end),
        .wr_data_mask       (32'd0),
        .rd_data            (app_rd_data),
        .rd_data_valid      (app_rd_data_valid),
        .rd_data_end        (),
        .sr_req             (1'b0),
        .ref_req            (1'b0),
        .sr_ack             (),
        .ref_ack            (),
        .init_calib_complete(init_calib_complete),
        .clk_out            (clk_x1),
        .pll_lock           (pll_lock),
        .burst              (app_burst),
        .ddr_rst            (),
        .O_ddr_addr         (ddr_addr),
        .O_ddr_ba           (ddr_bank),
        .O_ddr_cs_n         (ddr_cs),
        .O_ddr_ras_n        (ddr_ras),
        .O_ddr_cas_n        (ddr_cas),
        .O_ddr_we_n         (ddr_we),
        .O_ddr_clk          (ddr_ck),
        .O_ddr_clk_n        (ddr_ck_n),
        .O_ddr_cke          (ddr_cke),
        .O_ddr_odt          (ddr_odt),
        .O_ddr_reset_n      (ddr_reset_n),
        .O_ddr_dqm          (ddr_dm),
        .IO_ddr_dq          (ddr_dq),
        .IO_ddr_dqs         (ddr_dqs),
        .IO_ddr_dqs_n       (ddr_dqs_n)
    );

    // lissage du rd_data_valid (fix timing Sipeed, 2024/04/14)
    reg         read_av;
    reg [255:0] read_data;
    always @(posedge clk_x1) begin
        read_av   <= app_rd_data_valid;
        read_data <= app_rd_data;
    end

    wire        wdone, rdone;
    wire [23:0] num_ok;
    wire [2:0]  test_state;

    ddr3_test u_ddr_test (
        .clk                (clk_x1),
        .rst_n              (rst_n),
        .app_rdy            (app_rdy),
        .app_cmd            (app_cmd),
        .app_en             (app_en),
        .app_addr           (app_addr),
        .wr_data_rdy        (app_wdf_rdy),
        .app_wdf_data       (app_wdf_data),
        .app_wdf_wren       (app_wdf_wren),
        .app_wdf_end        (app_wdf_end),
        .app_wdf_mask       (app_wdf_mask),
        .app_burst          (app_burst),
        .app_rd_data_valid  (read_av),
        .app_rd_data        (read_data),
        .init_calib_complete(init_calib_complete),
        .wdone              (wdone),
        .rdone              (rdone),
        .num_ok             (num_ok),
        .test_state         (test_state)
    );

    // LED = état du test (mêmes motifs que le top Sipeed)
    wire [5:0] led_state =
        (test_state == 3'd0) ? 6'b111110 :
        (test_state == 3'd1) ? 6'b111101 :
        (test_state == 3'd2) ? 6'b111011 :
        (test_state == 3'd3) ? 6'b110111 :
        (test_state == 3'd4) ? 6'b101111 :
        (test_state == 3'd5) ? 6'b011111 : 6'b111111;
    assign led = led_state;

    // ==================== émission en boucle ====================
    // Test 1 : 'C' toutes les 100 ms dès le boot (valide le lien UART indépendamment du DDR3).
    // Ensuite la machine de rafale (W, R, num_ok) prendra la main quand wdone&rdone seront vrais.
    reg [23:0] c_cnt;
    reg [27:0] burst_pause;
    reg [2:0]  seq_state;   // 0..5 : pause, W, R, b1, b2, b3
    reg [2:0]  seq_cnt;

    always @(posedge clk100M or negedge rst_n) begin
        if (!rst_n) begin
            uart_wr    <= 1'b0;
            uart_wdata <= 8'd0;
            c_cnt      <= 24'd0;
            burst_pause<= 28'd0;
            seq_state  <= 3'd0;
        end
        else begin
            uart_wr <= 1'b0;
            if (seq_state == 3'd0) begin
                if (c_cnt >= 24'd9_999_999) begin        // 'C' toutes les 100 ms
                    uart_wr    <= 1'b1;
                    uart_wdata <= "C";
                    c_cnt      <= 24'd0;
                    if (wdone & rdone) begin             // test DDR3 fini → passer en mode rafale
                        seq_state <= 3'd1;
                    end
                end
                else c_cnt <= c_cnt + 1'b1;
            end
            else if (seq_state == 3'd1) begin            // rafale W puis R puis 3 octets, toutes les 1 s
                if (burst_pause >= 27'd19_999_999) begin // 200 ms
                    burst_pause <= 28'd0;
                    uart_wr     <= 1'b1;
                    case (seq_cnt)
                        3'd0: uart_wdata <= "W";
                        3'd1: uart_wdata <= "R";
                        3'd2: uart_wdata <= num_ok[23:16];
                        3'd3: uart_wdata <= num_ok[15:8];
                        default: uart_wdata <= num_ok[7:0];
                    endcase
                    seq_cnt <= (seq_cnt == 3'd4) ? 3'd0 : seq_cnt + 3'd1;
                end
                else burst_pause <= burst_pause + 1'b1;
            end
        end
    end

endmodule
`default_nettype wire