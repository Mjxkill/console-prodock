// Preuve exhaustive : l'état « file pleine » suivant, forme d'origine contre forme à sélection tardive.
module ddr_tag_queue_equiv;
    localparam TAG_LOG2=4, DEPTH=1<<TAG_LOG2;
    reg [TAG_LOG2:0] tq_w,tq_r; reg push,pop;
    wire [TAG_LOG2:0] tq_w_n = tq_w + {{TAG_LOG2{1'b0}}, push};
    wire [TAG_LOG2:0] tq_r_n = tq_r + {{TAG_LOG2{1'b0}}, pop};
    wire original = (tq_w_n[TAG_LOG2] != tq_r_n[TAG_LOG2]) && (tq_w_n[TAG_LOG2-1:0] == tq_r_n[TAG_LOG2-1:0]);
    wire [TAG_LOG2:0] tq_count = tq_w - tq_r;
    wire restructured = (push && !pop) ? tq_count == DEPTH-1 : (!push && pop) ? tq_count == DEPTH+1 : tq_count == DEPTH;
    integer cases=0;
    initial begin
        for(integer w=0;w<2*DEPTH;w++) for(integer r=0;r<2*DEPTH;r++) for(integer p=0;p<4;p++) begin
            tq_w=w[TAG_LOG2:0];tq_r=r[TAG_LOG2:0];{push,pop}=p[1:0];#1;
            if(original!==restructured) $fatal(1,"w=%0d r=%0d push=%b pop=%b: %b vs %b",w,r,push,pop,original,restructured);
            cases++;
        end
        $display("PASS: %0d cas, toutes les valeurs des pointeurs et de push/pop, formes identiques",cases);
        $finish;
    end
endmodule
