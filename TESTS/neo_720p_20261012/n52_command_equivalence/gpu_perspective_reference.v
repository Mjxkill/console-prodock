// Exact floor(UQ/Q), floor(VQ/Q), signed 49-bit inputs. Q must be positive.
// Two quotient bits/cycle with parallel radix-four subtraction; the common |coordinate|<256 case skips the
// known-zero high quotient bits. Repeated coordinates below 4096 use twelve
// quotient bits rather than the full fifty-bit path. All results remain exact.
`default_nettype none
module gpu_perspective_reference (
    input wire clk,rst,start,
    input wire signed [48:0] uq,vq,q,
    output reg done,valid,
    output reg signed [48:0] tu,tv
);
    localparam IDLE=0,SETUP=1,DIVIDE=2,SIGN=3,ABS=4,SELECT=5;
    reg [2:0] state;
    reg signed [48:0] raw_u,raw_v;
    reg [48:0] au,av,qu,qv;
    reg [49:0] nu,nv;
    reg [47:0] den,ru,rv;
    // Each remainder datapath owns local denominator registers. A shared
    // bank placed beside U forced up to 6.8 ns of routing to V on the Neo.
    // ABS already separates operand capture from SETUP, so local copies
    // do not add a divider cycle. Preserve them against register merging.
    reg [47:0] den_u /* synthesis syn_preserve=1 */;
    reg [47:0] den_v /* synthesis syn_preserve=1 */;
    reg [49:0] den3_u /* synthesis syn_preserve=1 */;
    reg [49:0] den3_v /* synthesis syn_preserve=1 */;
    reg neg_u,neg_v,positive;
    reg [5:0] bits_left;
    reg quick8_u,quick8_v,quick12_u,quick12_v;
    wire fast=quick8_u && quick8_v;
    wire fast12=quick12_u && quick12_v;
    // A leading zero makes the full-width path exactly 25 radix-four steps.
    // No separate odd final bit or extra remainder multiplexer is needed.
    wire [49:0] up={ru,nu[49:48]},vp={rv,nv[49:48]};
    wire [50:0] ud1={1'b0,up}-{3'b0,den_u},vd1={1'b0,vp}-{3'b0,den_v};
    wire [50:0] ud2={1'b0,up}-{2'b0,den_u,1'b0},vd2={1'b0,vp}-{2'b0,den_v,1'b0};
    wire [50:0] ud3={1'b0,up}-{1'b0,den3_u},vd3={1'b0,vp}-{1'b0,den3_v};
    wire [3:0] choose_u={!ud3[50],!ud2[50] && ud3[50],!ud1[50] && ud2[50],ud1[50]};
    wire [3:0] choose_v={!vd3[50],!vd2[50] && vd3[50],!vd1[50] && vd2[50],vd1[50]};
    wire [1:0] digit_u={choose_u[3]|choose_u[2],choose_u[3]|choose_u[1]};
    wire [1:0] digit_v={choose_v[3]|choose_v[2],choose_v[3]|choose_v[1]};
    // The borrow thresholds are monotonic: these selects are one-hot.
    wire [47:0] ur2=(up[47:0]&{48{choose_u[0]}})|(ud1[47:0]&{48{choose_u[1]}})|
        (ud2[47:0]&{48{choose_u[2]}})|(ud3[47:0]&{48{choose_u[3]}});
    wire [47:0] vr2=(vp[47:0]&{48{choose_v[0]}})|(vd1[47:0]&{48{choose_v[1]}})|
        (vd2[47:0]&{48{choose_v[2]}})|(vd3[47:0]&{48{choose_v[3]}});
    always @(posedge clk) begin
        if(rst)begin
            raw_u<=0;raw_v<=0;state<=IDLE;done<=0;valid<=0;tu<=0;tv<=0;
            den_u<=0;den_v<=0;den3_u<=0;den3_v<=0;
            quick8_u<=0;quick8_v<=0;quick12_u<=0;quick12_v<=0;
            au<=0;av<=0;den<=0;ru<=0;rv<=0;nu<=0;nv<=0;qu<=0;qv<=0;
            neg_u<=0;neg_v<=0;positive<=0;bits_left<=0;
        end else begin
            done<=0;
            case(state)
            IDLE:begin
                raw_u<=uq;raw_v<=vq;den<=q[47:0];
                // The caller may form Q with a 49-bit add immediately before
                // START. Capture its sign now, then test the registered
                // denominator for zero in ABS; SETUP observes the same Q>0
                // predicate without appending a wide reduction to that add.
                neg_u<=uq<0;neg_v<=vq<0;positive<=!q[48];
                // Private operands may track while idle; START only advances
                // the sequencer, not the enables of all 150 operand bits.
                if(start)state<=ABS;
            end
            ABS:begin
                au<=raw_u<0 ? -raw_u:raw_u;av<=raw_v<0 ? -raw_v:raw_v;
                den_u<=den;den_v<=den;
                positive<=positive && den!=0;state<=SELECT;
            end
            SELECT:begin
                // Range comparisons finish before the wide numerator muxes.
                // This adds one setup cycle; radix-four iterations and exact
                // signed floor semantics are unchanged.
                quick8_u<=(au>>8)<den_u;quick8_v<=(av>>8)<den_v;
                quick12_u<=(au>>12)<den_u;quick12_v<=(av>>12)<den_v;
                state<=SETUP;
            end
            SETUP:begin
                qu<=0;qv<=0;valid<=positive;
                den3_u<={2'b0,den_u}+{1'b0,den_u,1'b0};
                den3_v<={2'b0,den_v}+{1'b0,den_v,1'b0};
                ru<=fast ? au>>8:fast12 ? au>>12:49'd0;rv<=fast ? av>>8:fast12 ? av>>12:49'd0;
                nu<=fast ? {au[7:0],42'd0}:fast12 ? {au[11:0],38'd0}:{1'b0,au};
                nv<=fast ? {av[7:0],42'd0}:fast12 ? {av[11:0],38'd0}:{1'b0,av};
                bits_left<=fast ? 6'd8:fast12 ? 6'd12:6'd50;state<=positive ? DIVIDE:SIGN;
            end
            DIVIDE:begin
                ru<=ur2;rv<=vr2;
                qu<={qu[46:0],digit_u};qv<={qv[46:0],digit_v};
                nu<={nu[47:0],2'b0};nv<={nv[47:0],2'b0};
                bits_left<=bits_left-6'd2;
                if(bits_left==2)state<=SIGN;
            end
            SIGN:begin
                tu<=neg_u ? ~qu+(ru==0):qu;tv<=neg_v ? ~qv+(rv==0):qv;
                done<=1;state<=IDLE;
            end
            endcase
        end
    end
endmodule
`default_nettype wire
