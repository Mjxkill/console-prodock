// MODIFIÉ (logic_analyser_wifi, 2026-09-19) : ports DDR3 DQ/DQS/DM ramenés de 32 à 16 bits, voir PROVENANCE.md.
//********************************************************************
//
//      Copyright ©2014-2023 Gowin Semiconductor Corporation.
//                      All rights reserved.
//
// <File>     : gw_ahb_ddr3.v
// <Author>   : EMB
// <Function> : Gowin AHB interface of DDR3 memory controller
// <Version>  : 1.0
// <Date>     : 2023
//
//********************************************************************

// gw_ahb_ddr3_top supprimé (LA16, 2026-09-20) : l'IP DDR3 est instanciée dans rtl/board/ddr_subsys.v, à côté
// du pont, pour pouvoir partager son interface utilisateur avec un arbitre (ARCHI_V3 § 9).










//-------------------------------------- gw_ahb_ddr3 --------------------------------//
module gw_ahb_ddr3
#(
    parameter   LANE_NUM         =  3 ,
    parameter   BRUST_MODE       =  16, //32,//64,//16
    parameter   ADDR_WIDTH       =  32,
    parameter   DATA_WIDTH       =  32,
    parameter   BRUST_COUNT      =  20
)
(
    input                       rst_n,
    // AHB bus I/F
    input                       HCLK,
    input                       HRESETN,
    input                       HREADY,
    input                       HSEL,
    input             [31 : 0]  HADDR,
    input              [2 : 0]  HSIZE,
    input                       HWRITE,
    input              [1 : 0]  HTRANS,
    input              [2 : 0]  HBURST,
    input             [63 : 0]  HWDATA,
    output                      HREADY_O,
    output             [1 : 0]  HRESP,
    output            [15 : 0]  HSPLIT,
    output            [63 : 0]  HRDATA,
    output            [15 : 0]  DBG,      // diag E1 (LA16), voir assign DBG
    // Interface utilisateur de l'IP DDR3 (LA16, 2026-09-20 : l'instance de l'IP est sortie du module,
    // voir rtl/board/ddr_subsys.v ; ui_* = ports de DDR3_Memory_Interface_Top, mêmes noms)
    input                       ddr_clk,             // clk_out de l'IP : horloge du domaine lpddr
    input                       init_calib_complete,
    input                       ui_cmd_ready,
    output             [2 : 0]  ui_cmd,
    output                      ui_cmd_en,
    output            [28 : 0]  ui_addr,
    input                       ui_wr_data_rdy,
    output           [127 : 0]  ui_wr_data,
    output                      ui_wr_data_en,
    output                      ui_wr_data_end,
    output            [15 : 0]  ui_wr_data_mask,
    input            [127 : 0]  ui_rd_data,
    input                       ui_rd_data_valid,
    input                       ui_rd_data_end
);


/////////////////////////////////////////////////////
// Parameter definitions
localparam [4: 0]  IDLE               = 4'd0;
localparam [4: 0]  SELECT_LANE        = 4'd1;
localparam [4: 0]  SELECT_LANE_WAIT_1 = 4'd2;
localparam [4: 0]  SELECT_LANE_WAIT_2 = 4'd3;
localparam [4: 0]  SELECT_LANE_CHK    = 4'd4;
localparam [4: 0]  LPDDR_WRITING_1    = 4'd5;
localparam [4: 0]  LPDDR_WRITING_2    = 4'd6;
localparam [4: 0]  LPDDR_READING      = 4'd7;
localparam [4: 0]  LPDDR_WR_END       = 4'd8;
localparam [4: 0]  LPDDR_RD_END       = 4'd9;
localparam [4: 0]  LPDDR_AHB          = 4'd10;


/////////////////////////////////////////////////////
// Register definitions
reg                 [3 : 0] c_status;
reg                 [3 : 0] n_status;

reg                         wr_req;
reg                         rd_req;
reg                         ahb_req;
reg                         wr_data_end;
reg                         rd_data_end;
reg                         ahb_end;

// DDR Signals
reg                [31 : 0] cmd_addr;
reg               [127 : 0] wr_data;
wire              [127 : 0] lpddr_rd_data;
wire                        lpddr_rd_valid;
wire                        lpddr_rd_end;
reg                [15 : 0] lpddr_wdata_mask;

reg                         lpddr_cmd_en;
reg                         lpddr_cmd;
wire                        lpddr_cmd_ready;
wire                        lpddr_data_ready;
reg                         lpddr_wdata_en;
reg                         lpddr_wdata_end;

// DDR work signals
reg                         lpddr_ready;
reg                 [7 : 0] lpddr_ready_cnt;
reg                 [7 : 0] lpddr_data_end_cnt;

// AHB bus signals
wire                        lpddr_ahb_end;
wire                        lpddr_ahb_req;
wire               [31 : 0] lpddr_addr_ahb;
wire                        lpddr_cmd_en_ahb;
wire                        lpddr_cmd_ahb;
wire                        lpddr_wdata_en_ahb;
wire                        lpddr_wdata_end_ahb;
wire              [127 : 0] lpddr_wr_data_ahb;
reg               [127 : 0] rd_data_lpddr_ahb;
reg                         rd_valid_p_ahb;
wire               [15 : 0] lpddr_wdata_mask_ahb;


//////////////////////////////////////////////////////////
//================= Need User Define ===================//
// LANE 0 WRITE Signal
reg                         rst_n_d1;
reg                         rst_n_d2;
reg                         lpddr_rst_n;

always @ (posedge ddr_clk or negedge rst_n) begin
    if(!rst_n) begin
        rst_n_d1    <= 1'b0;
        rst_n_d2    <= 1'b0;
        lpddr_rst_n <= 1'b0;
    end 
    else  begin
        rst_n_d1    <= 1'b1;
        rst_n_d2    <= rst_n_d1;
        lpddr_rst_n <= rst_n_d2;
    end
end

always @ (posedge ddr_clk or negedge lpddr_rst_n) begin
    if(!lpddr_rst_n)
        lpddr_ready <= 1'b0;
    else if(init_calib_complete)
        lpddr_ready <= 1'b1;
    else
        lpddr_ready <= 1'b0;
end

always @ (posedge ddr_clk or negedge lpddr_rst_n) begin
    if(!lpddr_rst_n)
        c_status <= IDLE;
    else
        c_status <= n_status;
end

always @ (*) begin
    case (c_status)
        IDLE: begin
            if ( lpddr_ready == 1'b1 )
                n_status = SELECT_LANE;
            else n_status = IDLE;
        end

        SELECT_LANE: begin
            n_status = SELECT_LANE_CHK;
        end

        SELECT_LANE_CHK: begin
            if( lpddr_cmd_ready && lpddr_data_ready && ahb_req )
                n_status = LPDDR_AHB;
            else if(ahb_req == 1'b0)
                n_status = IDLE;
            else 
                n_status = SELECT_LANE;
        end

        LPDDR_AHB: begin
            if (ahb_end)
                n_status = SELECT_LANE;
            else 
                n_status = LPDDR_AHB;
        end

        default: begin
            n_status = IDLE;
        end

    endcase
end

// Calculate Lane Number & ADDR & Burst Count
always @(posedge ddr_clk or negedge lpddr_rst_n) begin
    if(!lpddr_rst_n) begin
        ahb_end               <= 1'b0;
        ahb_req               <= 1'b0;
    end
    else begin
        ahb_end               <= lpddr_ahb_end;
        ahb_req               <= lpddr_ahb_req;
    end
end


// DDR ADDR & Write Data
always @ (posedge ddr_clk or negedge lpddr_rst_n) begin
    if(!lpddr_rst_n) begin
        cmd_addr               <= {32{1'b0}};
        wr_data                <= 'h0000_0000_0000_0000;
        lpddr_cmd_en           <= 1'b0;
        lpddr_cmd              <= 1'b0;
        lpddr_wdata_en         <= 1'b0;
        lpddr_wdata_end        <= 1'b0;
    end
    else begin
        cmd_addr               <= lpddr_addr_ahb;
        wr_data                <= lpddr_wr_data_ahb;
        lpddr_cmd_en           <= lpddr_cmd_en_ahb;
        lpddr_cmd              <= lpddr_cmd_ahb;
        lpddr_wdata_en         <= lpddr_wdata_en_ahb;
        lpddr_wdata_end        <= lpddr_wdata_end_ahb;
    end
end

always @ (posedge ddr_clk or negedge lpddr_rst_n) begin
    if(!lpddr_rst_n)
        lpddr_wdata_mask        <= 8'h00;
    else 
        lpddr_wdata_mask        <= lpddr_wdata_mask_ahb;
end

// Read Valid & Read Data from DDR
always @ (posedge ddr_clk or negedge lpddr_rst_n) begin
    if(!lpddr_rst_n) begin
        rd_valid_p_ahb         <= 1'b0;
    end
    else begin
        rd_valid_p_ahb          <= lpddr_rd_valid;
    end
end


// LA16 : l'IP DDR3 est instanciée dans ddr_subsys.v ; ici seulement le câblage vers son interface utilisateur.
assign ui_cmd          = {2'b00, lpddr_cmd};
assign ui_cmd_en       = lpddr_cmd_en;
assign ui_addr         = cmd_addr[29:1];      // 29 bits = 512 Mo (16 bits DQ) ; Sipeed : [25:1] = 64 Mo repliés
assign ui_wr_data      = wr_data;
assign ui_wr_data_en   = lpddr_wdata_en;
assign ui_wr_data_end  = lpddr_wdata_en;      // comme chez Sipeed : end = en (une seule donnée par commande)
assign ui_wr_data_mask = lpddr_wdata_mask;
assign lpddr_rd_data   = ui_rd_data;
assign lpddr_rd_valid  = ui_rd_data_valid;
assign lpddr_rd_end    = ui_rd_data_end;
assign lpddr_cmd_ready = ui_cmd_ready;
assign lpddr_data_ready= ui_wr_data_rdy;


// Diag E1 (LA16) : les lectures du cœur rendent 0 ; ces signaux départagent IP / pont / AHB.
wire [7:0] dbg_ahb;   // état interne du module AHB (reset, battement d'horloge HCLK, hready...)
assign DBG = {1'b0, dbg_ahb, lpddr_rd_data[0], init_calib_complete, lpddr_rd_valid, lpddr_wdata_en, lpddr_cmd_en,
              HWRITE, HTRANS[1]};

// ddr3_memory_and_ahb_bus instantiation
ddr3_memory_and_ahb_bus u_ddr3_memory_and_ahb_bus
(
    .lpddr_clk         (ddr_clk),
    .rst_n             (rst_n&init_calib_complete & HRESETN),
    .c_status          (c_status),
    .n_status          (n_status),
    .lpddr_rdata       (lpddr_rd_data),
    .rd_valid_p        (rd_valid_p_ahb),
    .lpddr_wr_data     (lpddr_wr_data_ahb),
    .lpddr_addr        (lpddr_addr_ahb),
    .lpddr_cmd         (lpddr_cmd_ahb),
    .lpddr_cmd_en      (lpddr_cmd_en_ahb),
    .lpddr_cmd_ready   (lpddr_cmd_ready),
    .lpddr_data_ready  (lpddr_data_ready),
    .lpddr_wdata_en    (lpddr_wdata_en_ahb),
    .lpddr_wdata_end   (lpddr_wdata_end_ahb),
    .lpddr_wdata_mask  (lpddr_wdata_mask_ahb),
    .ahb_end           (lpddr_ahb_end),
    .ahb_req           (lpddr_ahb_req),
    .HCLK              (HCLK),
    .HRESETN           (HRESETN),
    .HSEL              (HSEL),
    .HREADY            (HREADY),
    .HADDR             (HADDR),
    .HSIZE             (HSIZE),
    .HWRITE            (HWRITE),
    .HTRANS            (HTRANS),
    .HBURST            (HBURST),
    .HWDATA            (HWDATA),
    .HREADY_O          (HREADY_O),
    .HRESP             (HRESP),
    .HRDATA            (HRDATA),
    .HSPLIT            (HSPLIT),
    .dbg               (dbg_ahb)
);

endmodule










//--------------------------------------- ddr3_memory_and_ahb_bus -----------------------------------//
module ddr3_memory_and_ahb_bus
(
    lpddr_clk,
    rst_n,
    c_status,
    n_status,
    lpddr_wr_data,
    lpddr_addr, 
    lpddr_cmd,
    lpddr_cmd_en,
    lpddr_cmd_ready,
    lpddr_data_ready,
    lpddr_wdata_en,
    lpddr_wdata_end,
    lpddr_wdata_mask,
    lpddr_rdata,
    rd_valid_p,
    ahb_end,
    ahb_req,
    HCLK,
    HRESETN,
    HSEL,
    HREADY,
    HADDR,
    HSIZE,
    HWRITE,
    HTRANS,
    HBURST,
    HWDATA,
    HREADY_O,
    HRESP,
    HRDATA,
    HSPLIT,
    dbg
);


input                              lpddr_clk;
input                              rst_n;
input                      [3 : 0] c_status;
input                      [3 : 0] n_status;
input                    [127 : 0] lpddr_rdata;
output                   [127 : 0] lpddr_wr_data;
output                    [31 : 0] lpddr_addr;
input                              rd_valid_p;
output                             lpddr_cmd;
output                             lpddr_cmd_en;
input                              lpddr_cmd_ready;
input                              lpddr_data_ready;
output  reg                        lpddr_wdata_en;
output  reg                        lpddr_wdata_end;
output                    [15 : 0] lpddr_wdata_mask;
output  reg                        ahb_end;
output  reg                        ahb_req;
input                              HCLK;
input                              HRESETN;
input                              HREADY;
input                              HSEL;
input                     [31 : 0] HADDR;
input                      [2 : 0] HSIZE;
input                              HWRITE;
input                      [1 : 0] HTRANS;
input                      [2 : 0] HBURST;
input                     [63 : 0] HWDATA;
output                             HREADY_O;
output                     [1 : 0] HRESP;
output                    [15 : 0] HSPLIT;
output                    [63 : 0] HRDATA;
output                     [7 : 0] dbg;      // diag E1 (LA16)
 

localparam [4 : 0]  IDLE               = 4'd0;
localparam [4 : 0]  SELECT_LANE        = 4'd1;
localparam [4 : 0]  SELECT_LANE_WAIT_1 = 4'd2;
localparam [4 : 0]  SELECT_LANE_WAIT_2 = 4'd3;
localparam [4 : 0]  SELECT_LANE_CHK    = 4'd4;
localparam [4 : 0]  LPDDR_WRITING_1    = 4'd5;
localparam [4 : 0]  LPDDR_WRITING_2    = 4'd6;
localparam [4 : 0]  LPDDR_READING      = 4'd7;
localparam [4 : 0]  LPDDR_WR_END       = 4'd8;
localparam [4 : 0]  LPDDR_RD_END       = 4'd9;
localparam [4 : 0]  LPDDR_AHB          = 4'd10;

// AHB ops
// HBURST
localparam [2 : 0]  SINGLE = 0; 
localparam [2 : 0]  INCR   = 1;
localparam [2 : 0]  WRAP4  = 2;
localparam [2 : 0]  INCR4  = 3;
localparam [2 : 0]  WRAP8  = 4;
localparam [2 : 0]  INCR8  = 5;
localparam [2 : 0]  WRAP16 = 6;
localparam [2 : 0]  INCR16 = 7;
// HTRANS
localparam [1 : 0]  BUSY   = 1;
localparam [1 : 0]  NONSEQ = 2;
localparam [1 : 0]  SEQ    = 3;
localparam [3 : 0]  S_VLD_CNT = 1;
localparam [3 : 0]	WR_DLY = 4;

// Registers
reg              hready;
wire             hsel;
reg              hsel_r;

reg      [1 : 0] hwrite_d;
reg              hwrite_r;
reg     [31 : 0] haddr_r;
reg     [31 : 0] haddr_wr;
reg      [2 : 0] hsize_r /*syntheis preserve=1*/;
reg      [1 : 0] htrans_r;
reg      [2 : 0] hburst_r;

reg              fifo_wr;
wire             Almost_Full;

reg    [167 : 0] fifo_wdata;

reg              fifo_rd;
wire   [167 : 0] Q;

reg     [31 : 0] app_addr;
reg              app_cmd;
reg              app_cmd_en;
reg    [127 : 0] app_wdata;
reg      [7 : 0] app_mask;
reg              app_wdf_en;
reg              app_wdf_end;
wire   [127 : 0] ddr_rd_data;

reg      [4 : 0] ddr_pstate;
reg      [4 : 0] ddr_nstate;


wire             ddr_rst;
wire             lpddr_clk;
wire             rdfifo_empty;
wire    [63 : 0] ahb_rd_o;
reg    [127 : 0] hrdata_reg;
wire             cmd_ready;
wire             wr_data_rdy;

reg              ahbr_flag,ahbw_flag;
reg              ahbr_start,ahbw_start;
reg              ahbr_end_flag;
wire             ahbw_end_flag;
reg              ahbr_cmd_flag;

reg              ahbw_single;
reg              ahbw_incr16;
reg      [6 : 0] ahbw_incr16_cnt;
reg              ahbr_single;
reg              ahbr_incr16;
reg      [6 : 0] ahbr_cnt;
reg              ahbr_op;
reg              data_valid_dly;
reg              data_valid;
wire     [4 : 0] addr_wrap;
wire    [15 : 0] ahb_mask_d0;
wire    [15 : 0] ahb_mask_d1;

reg      [1 : 0] ahb_mask_2word;
reg      [7 : 0] ahb_mask_word;
reg      [7 : 0] ahb_mask_byte;
reg      [7 : 0] ahb_mask_halfword;

reg      [2 : 0] valid_cnd;
reg     [63 : 0] adata_datal0;
reg      [4 : 0] ddr_burstrd_cnt;

reg              wr_end;
reg              rd_end;
reg     [63 : 0] lpddr_rdata_d;
wire   [127 : 0] lpddr_rdata_buf;

reg	     [3 : 0] beat_cnt;
reg              hwr_en;
reg              hrd_en;

// wr fifo
reg      [3 : 0] wr_cnt;
wire             fifo_ahb_wr_wren;
wire             fifo_ahb_wr_rden;
wire   [127 : 0] fifo_ahb_wr_data;
wire   [127 : 0] fifo_ahb_rd_data;
wire             fifo_wr_empty;
wire             fifo_wr_full;
wire    [63 : 0] ahb_wr_data_q;
wire    [31 : 0] ahb_wr_addr_q;
wire    [15 : 0] ahb_wr_mask_q;

wire             hwrite_buf_wren;
reg	             hwrite_buf_rden;
wire             hwrite_buf_afull;
wire             hwrite_buf_empty;
wire             hwrite_buf_full;
wire   [127 : 0] hwrite_buf_data_in;
wire   [127 : 0] hwrite_buf_data_out;
wire    [31 : 0] haddr_q;
wire    [63 : 0] hwdata_q;
wire    [ 2 : 0] hsize_q /*syntheis preserve=1*/;

// rd fifo
wire             fifo_rd_empty;
wire             fifo_rd_full;
reg              fifo_ahb_rd_rden;
reg      [3 : 0] fifo_ahb_rd_cnt;

// AHB logics
wire             hwrite_s,hread_s;
wire             hwrite_neg;
  
assign hsel       = HREADY & HSEL & HTRANS[1];
assign hwrite_s   =  HWRITE & hsel;
assign hread_s    = !HWRITE & hsel;
assign hwrite_neg = !hwrite_d[0] & hwrite_d[1];

always @(posedge HCLK or negedge HRESETN) begin
    if(!HRESETN)
        hwrite_d <= 'b0;
    else 
        hwrite_d <= {hwrite_d[0],hwrite_s};
end

always @(posedge HCLK or negedge HRESETN) begin
    if(!HRESETN)
        haddr_r  <= 'b0;
    else if(hread_s && !ahbr_start && !ahbr_flag)
        haddr_r  <= HADDR ;
    else
        haddr_r  <= haddr_r;
end

always @(posedge HCLK or negedge HRESETN) begin
    if(!HRESETN)
        haddr_wr  <= 'b0;
    else if(hwrite_s)
        haddr_wr  <= HADDR ;
    else
        haddr_wr  <= haddr_wr;
end

always @(posedge HCLK or negedge HRESETN) begin
    if(!HRESETN)
        ahbr_flag <= 1'b0;
    else if(ahb_req && !ahbw_single)
        ahbr_flag <= 1'b0;
    else if(HREADY & HSEL & !HWRITE & (HTRANS[1] == 1'b1))
        ahbr_flag <= 1'b1;
end

always @(posedge HCLK or negedge HRESETN) begin
    if(!HRESETN)
        ahbr_start <= 1'b0;
    else if(ahbr_cmd_flag)
        ahbr_start <= 1'b0;
    else if(ahbr_single & ahbr_flag)
        ahbr_start <= 1'b1;
end

always @(posedge HCLK or negedge HRESETN) begin
    if(!HRESETN)
        hsize_r <= 1'b0;
    else if(hsel) 
        hsize_r <= HSIZE ;
    else  
        hsize_r <= hsize_r;
end
  
always @(posedge HCLK or negedge HRESETN) begin
    if(!HRESETN)
        ahbw_single <= 1'b0;
    else if(ahb_end)
        ahbw_single <= 1'b0;
    else if(!ahbw_single & !fifo_wr_empty & !ahbr_flag & !ahbr_single)  //only 1 op allowed
        ahbw_single <= 1'b1;
end

always @(posedge HCLK or negedge HRESETN) begin
    if(!HRESETN)
        ahbr_single <= 1'b0;
    else if(ahbr_single & data_valid & (fifo_ahb_rd_cnt > S_VLD_CNT))
        ahbr_single <= 1'b0;
    else if(!ahbw_single  & !ahbr_single & ahbr_flag)
        ahbr_single <= 1'b1;
end

always @(posedge HCLK or negedge HRESETN) begin
    if (!HRESETN)
        hready <= 1'b1;
    else if(HREADY & HSEL & !HWRITE & (HTRANS[1] == 1'b1))  // single read
        hready <= 1'b0;//!Almost_Full;
    else if(ahbr_flag)
        hready <= 1'b0;
    else if(ahbr_single && data_valid)
        hready <= (fifo_ahb_rd_cnt==S_VLD_CNT+1);
    else if(ahb_end & ahbw_single)
        hready <= !Almost_Full && !hwrite_buf_afull;
    else if(HREADY & HSEL & HWRITE & (HTRANS[1] == 1'b1))   // single write
        hready <= 1'b0;
end


// to ddr ui
reg        app_cmd_a;
reg        app_cmd_c;
reg [2:0]  app_cmd_d;
wire       lpddr_cmd_en_c;
wire       lpddr_cmd_en_d;

// DDR CMD 
always @ (posedge lpddr_clk or negedge rst_n) begin
    if(!rst_n)
        app_cmd  <= 1'b0;
    else if(ahb_end)
        app_cmd <= 1'b0;
    else if(ahbw_single)
        app_cmd <= 1'b0;
    else if(ahbr_single)
        app_cmd <= 1'b1;
end

assign lpddr_cmd = app_cmd;

always @ (posedge lpddr_clk or negedge rst_n) begin
    if(!rst_n)
        ahb_req <= 1'b0;
    else if(ahb_end && !ahbr_single && !ahbw_single)
        ahb_req <= 1'b0;
    else if(!ahb_end &&  !fifo_wr_empty)
        ahb_req <= 1'b1;
    else if(ahbr_single && !ahb_end)
        ahb_req <= 1'b1;
end

always @ (posedge lpddr_clk or negedge rst_n) begin
    if(!rst_n)
        app_cmd_a <= 1'b0;
    else if(ahb_end)
        app_cmd_a <= 1'b0 ;
    else if(ahb_req && (c_status == LPDDR_AHB))
        app_cmd_a <= 1'b1;
end

// LA16 (2026-09-20) : une seule commande par transaction. app_cmd_c est à niveau (ready && engagé) et
// app_cmd_a reste à 1 jusqu'à ahb_end : si cmd_ready/wr_data_rdy retombent un cycle (arbitre ddr_arb, tampon
// plein), app_cmd_c retombe puis remonte → nouveau front → commande répétée en boucle (mesuré : cmd_en et
// rd_data_valid en rafale, HREADY figé). cmd_issued mémorise que la commande est partie, jusqu'à ahb_end.
reg        cmd_issued;
always @ (posedge lpddr_clk or negedge rst_n) begin
    if(!rst_n)
       cmd_issued <= 1'b0;
    else if(ahb_end)
       cmd_issued <= 1'b0;
    else if(lpddr_cmd_en_c)
       cmd_issued <= 1'b1;
end
always @ (posedge lpddr_clk or negedge rst_n) begin
    if(!rst_n)
       app_cmd_c  <= 1'b0;
    else if(app_cmd_a && lpddr_cmd_ready && lpddr_data_ready && c_status == LPDDR_AHB && !cmd_issued)
       app_cmd_c  <= 1'b1 ;
    else
       app_cmd_c  <= 1'b0;
end

always @ (posedge lpddr_clk or negedge rst_n) begin
    if(!rst_n)
       app_cmd_d  <= 2'b0;
    else 
       app_cmd_d[2:0]  <= {app_cmd_d[1:0] ,app_cmd_c};
end

assign lpddr_cmd_en_c = app_cmd_c & (~app_cmd_d[0]);
assign lpddr_cmd_en_d = app_cmd_d[0] & (~app_cmd_d[1]);
assign lpddr_cmd_en   = app_cmd_d[1] & (~app_cmd_d[2]);

// DDR ADDR
wire [31:0] ahb_cmd_addr0;  //0010_0000[ROM] 2010_0000[RAM] 8000_0000[USER RAM]
wire [31:0] ahb_cmd_addr1;  //0010_0000[ROM] 2010_0000[RAM] 8000_0000[USER RAM]
assign ahb_cmd_addr0 = haddr_r;
assign ahb_cmd_addr1 = ahb_wr_addr_q;

always @ (posedge lpddr_clk or negedge rst_n) begin
    if(!rst_n)
        app_addr <= 'b0;
    else if(ahbw_single & lpddr_cmd_en_d)
        app_addr <= {ahb_cmd_addr1[31:4],4'h0} ;
    else if(ahbr_single & lpddr_cmd_en_d)	
        app_addr <= {ahb_cmd_addr0[31:4],ahb_cmd_addr0[3],3'b0};// ddr x1
    else 
        app_addr <= app_addr;
end
assign lpddr_addr = app_addr;

// DDR Write DATA
always @(posedge HCLK or negedge HRESETN) begin
    if (!HRESETN)
        adata_datal0  <= 'b0;
    else if(hwrite_d[0])
        adata_datal0  <= HWDATA;
end  
  
always @(posedge HCLK or negedge HRESETN) begin
    if (!HRESETN)
        hwrite_buf_rden  <= 'b0;
    else if(!hwrite_buf_empty && !ahbw_flag && !Almost_Full)
        hwrite_buf_rden  <= 1'b1;
    else
        hwrite_buf_rden  <= 'b0;
end

always @(posedge HCLK or negedge HRESETN) begin
    if (!HRESETN) 
        ahbw_flag <= 1'b0;
    else if(hwrite_buf_rden)
        ahbw_flag <= 1'b1;
    else if(ahbw_start)
        ahbw_flag <= 1'b0;
end

always @(posedge HCLK or negedge HRESETN) begin
    if (!HRESETN)
        ahbw_start <= 1'b0;
    else if(wr_cnt == WR_DLY)
        ahbw_start <= 1'b1;
    else
        ahbw_start <= 1'b0;
end

assign hwrite_buf_data_in         = {29'h0,hsize_r,haddr_wr,adata_datal0};//3 32 64
assign hwrite_buf_wren            = hwrite_d[1];
assign {hsize_q,haddr_q,hwdata_q} = hwrite_buf_data_out[3+32+64-1:0];

ddr3_memory_wrfifo u_hwrite_buf
(
    .RdClk        (HCLK),
    .WrClk        (HCLK),
    .WrEn         (hwrite_buf_wren),
    .RdEn         (hwrite_buf_rden),
    .Reset        (!HRESETN),
    .Data         (hwrite_buf_data_in),
    .Empty        (hwrite_buf_empty),
    .Full         (hwrite_buf_full),
    .Almost_Full  (hwrite_buf_afull),
    .Almost_Empty (),
    .Q            (hwrite_buf_data_out)
);

always @(posedge HCLK or negedge HRESETN) begin
    if (!HRESETN)
        wr_cnt  <= 'b0;
    else if(ahbw_start)
        wr_cnt  <= 0;
    else if(ahbw_flag)
        wr_cnt  <= (wr_cnt == WR_DLY) ? wr_cnt : wr_cnt+1;
end

assign fifo_ahb_wr_wren = (wr_cnt == WR_DLY-1);
assign fifo_ahb_wr_data = (wr_cnt == WR_DLY-1) ? {16'h0,ahb_mask_d0,haddr_q,hwdata_q}:128'h0;

assign fifo_ahb_wr_rden = (lpddr_cmd_en_c);
assign lpddr_wr_data    = {2{ahb_wr_data_q}};
assign ahb_wr_data_q    = fifo_ahb_rd_data[63:0];
assign ahb_wr_addr_q    = fifo_ahb_rd_data[95:64];
assign ahb_wr_mask_q    = fifo_ahb_rd_data[111:96];
assign lpddr_wdata_mask =  ahb_wr_mask_q;

ddr3_memory_wrfifo u_fifo_wr
(
    .RdClk        (lpddr_clk),
    .WrClk        (HCLK),
    .WrEn         (fifo_ahb_wr_wren),
    .RdEn         (fifo_ahb_wr_rden),
    .Reset        (!HRESETN),
    .Data         (fifo_ahb_wr_data),
    .Empty        (fifo_wr_empty),
    .Full         (fifo_wr_full),
    .Almost_Full  (Almost_Full),
    .Almost_Empty (),
    .Q            (fifo_ahb_rd_data)
);

always@(posedge HCLK or negedge HRESETN) begin
    if (!HRESETN) begin
        ahb_mask_2word <= 'b0;
        ahb_mask_word <= 'b0;
        ahb_mask_byte <= 'b0;
        ahb_mask_halfword <= 'b0;
    end
    else begin
        ahb_mask_2word <= (haddr_q[3] == 1'b0) ? 2'b10 :
                          (haddr_q[3] == 1'b1) ? 2'b01 :2'b0;

        ahb_mask_byte <= (hsize_q[2:0] == 3'b000 &&haddr_q [2:0] == 3'b000) ? 8'b1111_1110 :
                         (hsize_q[2:0] == 3'b000 &&haddr_q [2:0] == 3'b001) ? 8'b1111_1101 :
                         (hsize_q[2:0] == 3'b000 &&haddr_q [2:0] == 3'b010) ? 8'b1111_1011 :
                         (hsize_q[2:0] == 3'b000 &&haddr_q [2:0] == 3'b011) ? 8'b1111_0111 :
                         (hsize_q[2:0] == 3'b000 &&haddr_q [2:0] == 3'b100) ? 8'b1110_1111 :
                         (hsize_q[2:0] == 3'b000 &&haddr_q [2:0] == 3'b101) ? 8'b1101_1111 :
                         (hsize_q[2:0] == 3'b000 &&haddr_q [2:0] == 3'b110) ? 8'b1011_1111 :
                         (hsize_q[2:0] == 3'b000 &&haddr_q [2:0] == 3'b111) ? 8'b0111_1111 : 8'b0;

        ahb_mask_halfword <= (hsize_q[2:0] == 3'b001 && haddr_q[2:1] == 2'b00) ? 8'b1111_1100 :
                        (hsize_q[2:0] == 3'b001 && haddr_q[2:1] == 2'b01) ? 8'b1111_0011 :
                        (hsize_q[2:0] == 3'b001 && haddr_q[2:1] == 2'b10) ? 8'b1100_1111 :
                        (hsize_q[2:0] == 3'b001 && haddr_q[2:1] == 2'b11) ? 8'b0011_1111 :8'b0;

        ahb_mask_word <= (hsize_q[2:0] == 3'b010 && haddr_q[2] == 1'b0) ? 8'b1111_0000 :
                        (hsize_q[2:0] == 3'b010 && haddr_q[2] == 1'b1) ? 8'b0000_1111 :8'b0;
    end
end

assign ahb_mask_d0 = (hsize_q[2:0] == 3'b000 && !ahb_mask_2word[0])	?	{8'hFF,ahb_mask_byte}       :
                     (hsize_q[2:0] == 3'b000 && !ahb_mask_2word[1])	?	{ahb_mask_byte,8'hFF}       :
                     (hsize_q[2:0] == 3'b001 && !ahb_mask_2word[0])	?	{8'hFF,ahb_mask_halfword}   :
                     (hsize_q[2:0] == 3'b001 && !ahb_mask_2word[1])	?	{ahb_mask_halfword,8'hFF}   :
                     (hsize_q[2:0] == 3'b010 && !ahb_mask_2word[0])	?	{8'hFF,ahb_mask_word}       :
                     (hsize_q[2:0] == 3'b010 && !ahb_mask_2word[1])	?	{ahb_mask_word,8'hFF}       :
                     {{8{ahb_mask_2word[1]}},{8{ahb_mask_2word[0]}}};

// DDR DATA EN
always @ (posedge lpddr_clk or negedge rst_n) begin
    if(!rst_n)
       lpddr_wdata_en <= 1'b0;
    else if((lpddr_cmd_en_d) && ahbw_single)
       lpddr_wdata_en <= 1'b1;
    else
       lpddr_wdata_en <= 1'b0;
end

always @ (posedge lpddr_clk or negedge rst_n) begin
    if(!rst_n)
        lpddr_wdata_end <= 1'b0;
    else if(lpddr_cmd_en_d  && ahbw_single)
        lpddr_wdata_end <= 1'b1;
    else
        lpddr_wdata_end <= 1'b0;
end

// Current Lane start LPDDR write end (One time of whole LPDDR write)
// Change to next Lane
always @ (posedge lpddr_clk or negedge rst_n) begin
    if(!rst_n)
        ahb_end <= 1'b0;
    else if(ahbw_single && lpddr_cmd_en && c_status == LPDDR_AHB)
        ahb_end <= 1'b1;
    else if(ahbr_single && data_valid && c_status == LPDDR_AHB)
        ahb_end <= 1'b1;
    else if(ahb_end && !ahbr_single && !ahbw_single && !ahb_req)
        ahb_end <= 1'b0 ;
end

reg [2:0]lpddr_cmd_en_flag;
always @ (posedge lpddr_clk or negedge rst_n) begin
    if(!rst_n)
        lpddr_cmd_en_flag <= 1'b0;
    else 
        lpddr_cmd_en_flag <= {lpddr_cmd_en_flag[1:0],lpddr_cmd_en};
end
 
always @ (posedge lpddr_clk or negedge rst_n) begin
    if(!rst_n)
        ahbr_cmd_flag <= 1'b0;
    else if(ahbr_single && (|lpddr_cmd_en_flag))
        ahbr_cmd_flag <= 1'b1;
    else if(ahbr_cmd_flag && !ahbr_start)
        ahbr_cmd_flag <= 1'b0;
end

always@(posedge HCLK or negedge HRESETN) begin
    if (!HRESETN) 
        fifo_ahb_rd_rden <= 1'b0;
    else
        fifo_ahb_rd_rden <= !fifo_rd_empty;
end
  
always@(posedge HCLK or negedge HRESETN) begin
    if (!HRESETN) 
        fifo_ahb_rd_cnt <= 'b0;
    else if(fifo_ahb_rd_rden)
        fifo_ahb_rd_cnt <= fifo_ahb_rd_cnt+1;
    else
        fifo_ahb_rd_cnt <= 'b0;
end

always@(posedge HCLK or negedge HRESETN) begin
    if (!HRESETN) 
        data_valid <= 1'b0;
    else
        data_valid <= fifo_ahb_rd_rden;
end

// Diag E1 (LA16) : le pont ne réagissait pas aux transferts AHB (HREADY figé à 1) ; on sort le reset,
// un battement de HCLK (bit 22 d'un compteur : 2^23 cycles, ~6 Hz à 50 MHz) et les drapeaux de la machine de lecture.
reg [22:0] dbg_hb;
always @(posedge HCLK) dbg_hb <= dbg_hb + 1'b1;
// bit 0 : ne pas exposer HRESETN ici — la synthèse renommerait le net d'après ce port et la contrainte
// CLOCK_LOC de la16.cst ne le trouverait plus (et l'espion fusionne ses bascules avec celles du reset).
assign dbg = {fifo_rd_empty, hwrite_d[0], ahbr_single, ahbr_flag, hsel, hready, dbg_hb[22], 1'b0};
assign HRESP    =  2'b0;
assign HSPLIT   = 16'b0;
assign HREADY_O = hready;
assign HRDATA   = hrdata_reg[63:0];

always@(posedge HCLK or negedge HRESETN) begin
if (!HRESETN) 
    hrdata_reg <= 128'h0000;
else if ((fifo_ahb_rd_cnt == S_VLD_CNT) && data_valid)
    hrdata_reg <= lpddr_rdata_buf;
end

reg [127:0]  rd_data_lpddr_d;
always @ (posedge lpddr_clk or negedge rst_n) begin
    if(!rst_n)
       rd_data_lpddr_d <= 128'b0;
    else 
       rd_data_lpddr_d <= lpddr_rdata;
end

// Read data fifo
ddr3_memory_rdfifo u_fifo_rd
(
    .RdClk        (HCLK),
    .WrClk        (lpddr_clk),
    .WrEn         (rd_valid_p),
    .RdEn         (fifo_ahb_rd_rden),
    .Reset        (!HRESETN),
    .Data         (rd_data_lpddr_d),
    .Empty        (fifo_rd_empty),
    .Full         (fifo_rd_full),
    .Almost_Empty (),
    .Almost_Full  (),
    .Q            (lpddr_rdata_buf)
);

endmodule