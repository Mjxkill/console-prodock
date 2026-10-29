// UART2 AE350 <-> USB CDC EP2, 115200 bauds, 8N1.
// EP2 livre des impulsions retardées après ready : la FIFO TX réserve 4 places.
`default_nettype none
module uart2_to_ep2 #(
    parameter integer CLK_HZ = 60000000,
    parameter integer BAUD = 115200
) (
    input  wire       phy_clk,
    input  wire       reset,
    input  wire       uart2_txd,
    output wire       uart2_rxd,
    output reg        uart_rx_data_val,
    output reg [7:0]  uart_rx_data,
    input  wire       ep2_rx_dval,
    input  wire [7:0] ep2_rx_data,
    output wire       ep2_rx_rdy
);
    localparam integer BIT_CYCLES = (CLK_HZ + BAUD / 2) / BAUD;
    localparam integer COUNT_W = $clog2(BIT_CYCLES);
    localparam [COUNT_W-1:0] BIT_LAST = BIT_CYCLES - 1;
    localparam [COUNT_W-1:0] HALF_LAST = BIT_CYCLES / 2 - 1;
    localparam [2:0] IDLE=0, START=1, DATA=2, STOP=3, WAIT_HIGH=4;

    // UART asynchrone : seule la seconde bascule alimente le récepteur.
    reg [1:0] rx_sync;
    always @(posedge phy_clk or posedge reset)
        if (reset) rx_sync <= 2'b11;
        else rx_sync <= {rx_sync[0], uart2_txd};

    reg [2:0] rx_state, rx_bit;
    reg [COUNT_W-1:0] rx_count;
    reg [7:0] rx_shift;
    always @(posedge phy_clk or posedge reset) begin
        if (reset) begin
            rx_state <= IDLE;
            rx_bit <= 0;
            rx_count <= 0;
            rx_shift <= 0;
            uart_rx_data_val <= 0;
            uart_rx_data <= 0;
        end else begin
            uart_rx_data_val <= 0;
            case (rx_state)
                IDLE: if (!rx_sync[1]) begin
                    rx_count <= HALF_LAST;
                    rx_state <= START;
                end
                START: if (rx_count != 0) rx_count <= rx_count - 1'b1;
                    else if (rx_sync[1]) rx_state <= IDLE;
                    else begin
                        rx_count <= BIT_LAST;
                        rx_bit <= 0;
                        rx_state <= DATA;
                    end
                DATA: if (rx_count != 0) rx_count <= rx_count - 1'b1;
                    else begin
                        rx_shift[rx_bit] <= rx_sync[1];
                        rx_count <= BIT_LAST;
                        if (rx_bit == 7) rx_state <= STOP;
                        else rx_bit <= rx_bit + 1'b1;
                    end
                STOP: if (rx_count != 0) rx_count <= rx_count - 1'b1;
                    else if (rx_sync[1]) begin
                        uart_rx_data <= rx_shift;
                        uart_rx_data_val <= 1;
                        rx_state <= IDLE;
                    end else rx_state <= WAIT_HIGH;
                WAIT_HIGH: if (rx_sync[1]) rx_state <= IDLE;
                default: rx_state <= IDLE;
            endcase
        end
    end

    reg [7:0] tx_fifo [0:7];
    reg [2:0] wr_ptr, rd_ptr;
    reg [3:0] tx_count;
    reg [9:0] tx_shift;
    reg [3:0] tx_bit;
    reg [COUNT_W-1:0] tx_timer;
    reg tx_busy;
    wire tx_pop = !tx_busy && (tx_count != 0);
    assign ep2_rx_rdy = !reset && (tx_count < 4);
    assign uart2_rxd = tx_busy ? tx_shift[0] : 1'b1;

    always @(posedge phy_clk or posedge reset) begin
        if (reset) begin
            wr_ptr <= 0;
            rd_ptr <= 0;
            tx_count <= 0;
            tx_busy <= 0;
            tx_shift <= 10'h3ff;
            tx_bit <= 0;
            tx_timer <= 0;
        end else begin
            if (ep2_rx_dval) begin
                tx_fifo[wr_ptr] <= ep2_rx_data;
                wr_ptr <= wr_ptr + 1'b1;
            end
            case ({ep2_rx_dval, tx_pop})
                2'b10: tx_count <= tx_count + 1'b1;
                2'b01: tx_count <= tx_count - 1'b1;
                default: ;
            endcase
            if (tx_pop) begin
                tx_shift <= {1'b1, tx_fifo[rd_ptr], 1'b0};
                rd_ptr <= rd_ptr + 1'b1;
                tx_bit <= 0;
                tx_timer <= BIT_LAST;
                tx_busy <= 1;
            end else if (tx_busy) begin
                if (tx_timer != 0) tx_timer <= tx_timer - 1'b1;
                else begin
                    tx_timer <= BIT_LAST;
                    tx_shift <= {1'b1, tx_shift[9:1]};
                    if (tx_bit == 9) tx_busy <= 0;
                    else tx_bit <= tx_bit + 1'b1;
                end
            end
        end
    end
endmodule
`default_nettype wire
