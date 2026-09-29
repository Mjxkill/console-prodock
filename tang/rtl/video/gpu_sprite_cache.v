// G4: 64 indexed sprites, up to 32x32, fixed 32-byte source pitch.
// The complete texture cache is refreshed during vertical blanking. Lists
// preserve descriptor order within each of the sixteen layer priorities.
`default_nettype none
module gpu_sprite_cache (
    input wire clk,resetn,start,config_bank,
    input wire clear_maxima,
    output wire busy,
    output reg done,
    output wire [8:0] config_address,
    input wire [31:0] config_data,
    output wire fetch_valid,
    output reg [28:0] fetch_addr,
    input wire fetch_ready,
    input wire [255:0] fetch_data,
    input wire fetch_data_valid,
    input wire [3:0] head_layer,
    output wire [6:0] head_index,
    input wire [5:0] meta_index,
    output reg [63:0] meta_data,
    input wire [10:0] row_address,
    output reg [255:0] row_data,
    output reg [31:0] invalid_sprites,max_cycles,loads
);
    localparam IDLE=0,CLEAR=1,DESC=2,CHECK=3,FETCH=4,DRAIN=5,NEXT=6,FINISH=7;
    reg [2:0] state=IDLE;
    reg bank;
    reg [3:0] clear_index;
    reg [5:0] sprite;
    reg [2:0] word_index;
    reg [31:0] image_base,position,properties;
    reg [6:0] heads[0:15];
    reg [63:0] metadata[0:63];
    reg [255:0] textures[0:2047];
    wire [7:0] width=properties[7:0],height=properties[15:8];
    wire enabled=properties[16],flip_x=properties[17];
    wire [3:0] priority_layer=properties[23:20];
    wire valid_descriptor=width!=0 && width<=32 && height!=0 && height<=32
        && image_base[31:30]==0 && image_base[4:0]==0
        && {1'b0,image_base}+{20'b0,height,5'b0}<=33'h040000000;
    assign config_address={bank,sprite,word_index[1:0]};
    assign head_index=heads[head_layer];
    assign busy=state!=IDLE;
    always @(posedge clk) begin
        meta_data<=metadata[meta_index];
        row_data<=textures[row_address];
        if(state==CHECK && enabled && valid_descriptor)
            metadata[sprite]<={11'd0,heads[priority_layer],properties[18],flip_x,height[5:0],width[5:0],position};
    end
    reg request_valid=0,more_requests;
    reg [5:0] issued,received;
    reg [4:0] outstanding,flip_shift;
    assign fetch_valid=request_valid;
    wire accept=fetch_valid && fetch_ready;
    wire [4:0] next_outstanding=outstanding+{4'b0,accept}-{4'b0,fetch_data_valid};
    reg [31:0] elapsed;
    wire [255:0] reversed;
    genvar p;
    generate for(p=0;p<32;p=p+1) begin:reverse_pixels
        assign reversed[p*8+:8]=fetch_data[(31-p)*8+:8];
    end endgenerate
    reg [255:0] row1,row2;
    reg [10:0] address1,address2;
    reg valid1=0,valid2=0;
    // These wide data paths deliberately have no reset/enable tree.
    always @(posedge clk) begin
        row1<=flip_x ? reversed : fetch_data;
        row2<=row1>>(flip_shift*8);
        address1<={sprite,received[4:0]};address2<=address1;
        valid1<=resetn && state==FETCH && fetch_data_valid;
        valid2<=resetn && valid1;
        if(valid2) textures[address2]<=row2;
    end
    always @(posedge clk) begin
        if(!resetn) begin
            state<=IDLE;bank<=0;clear_index<=0;sprite<=0;word_index<=0;
            image_base<=0;position<=0;properties<=0;request_valid<=0;more_requests<=0;
            issued<=0;received<=0;outstanding<=0;fetch_addr<=0;flip_shift<=0;
            elapsed<=0;invalid_sprites<=0;max_cycles<=0;loads<=0;done<=0;
        end else begin
            done<=0;
            if(busy) elapsed<=elapsed+1'b1;
            case(state)
                IDLE: if(start) begin bank<=config_bank;clear_index<=0;elapsed<=0;state<=CLEAR;end
                CLEAR: begin
                    heads[clear_index]<=7'd64;
                    if(clear_index==15) begin sprite<=63;word_index<=0;state<=DESC;end
                    else clear_index<=clear_index+1'b1;
                end
                DESC: begin
                    case(word_index)
                        1:image_base<=config_data;
                        2:position<=config_data;
                        3:properties<=config_data;
                        default:begin end
                    endcase
                    if(word_index==3) state<=CHECK;else word_index<=word_index+1'b1;
                end
                CHECK: begin
                    if(!enabled) state<=NEXT;
                    else if(!valid_descriptor) begin invalid_sprites<=invalid_sprites+1'b1;state<=NEXT;end
                    else begin
                        heads[priority_layer]<={1'b0,sprite};
                        fetch_addr<=image_base[30:2];issued<=0;received<=0;outstanding<=0;
                        flip_shift<=flip_x ? 5'd0-width[4:0] : 5'd0;
                        more_requests<=1;request_valid<=1;state<=FETCH;
                    end
                end
                FETCH: begin
                    outstanding<=next_outstanding;
                    request_valid<=more_requests && !next_outstanding[4];
                    if(accept) begin
                        issued<=issued+1'b1;fetch_addr<=fetch_addr+29'd8;
                        if(issued+6'd1==height[5:0]) begin more_requests<=0;request_valid<=0;end
                    end
                    if(fetch_data_valid) begin
                        received<=received+1'b1;
                        if(received+6'd1==height[5:0]) state<=DRAIN;
                    end
                end
                DRAIN: if(!valid1 && !valid2) state<=NEXT;
                NEXT: if(sprite==0) state<=FINISH;
                      else begin sprite<=sprite-1'b1;word_index<=0;state<=DESC;end
                FINISH: begin done<=1;loads<=loads+1'b1;state<=IDLE;if(elapsed>max_cycles) max_cycles<=elapsed;end
                default:state<=IDLE;
            endcase
            if(clear_maxima) max_cycles<=0;
        end
    end
endmodule
`default_nettype wire
