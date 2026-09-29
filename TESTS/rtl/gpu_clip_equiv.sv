// Preuve : fenêtre vide, forme d'origine (left_x>right_x) contre forme préparée, couches et sprites.
module gpu_clip_equiv #(parameter WIDTH=800);
    reg signed [15:0] pos_x; reg signed [17:0] window_w; reg [5:0] sprite_w;
    wire signed [17:0] right_edge=$signed(pos_x)+window_w-18'sd1;
    wire signed [17:0] left_x=pos_x<0 ? 18'sd0 : $signed(pos_x);
    wire signed [17:0] right_x=right_edge>WIDTH-1 ? WIDTH-1 : right_edge;
    wire original=left_x>right_x;
    wire prepared=pos_x<0 ? right_edge<0 : ($signed(pos_x)>WIDTH-1 || window_w<=0);
    wire signed [17:0] sprite_x=$signed(pos_x);
    wire signed [17:0] sprite_right=$signed(pos_x)+$signed({12'b0,sprite_w})-18'sd1;
    wire signed [17:0] s_left=$signed(pos_x)<0 ? 18'sd0 : $signed(pos_x);
    wire signed [17:0] s_right=sprite_right>WIDTH-1 ? WIDTH-1 : sprite_right;
    wire s_original=s_left>s_right;
    wire s_prepared=sprite_x<0 ? sprite_right<0 : (sprite_x>WIDTH-1 || sprite_w==0);
    integer cases=0;
    initial begin
        // Toutes les positions ; largeurs de fenêtre autour de chaque valeur critique et au hasard.
        for(integer x=-32768;x<32768;x++) begin
            pos_x=x[15:0];
            for(integer k=0;k<40;k++) begin
                case(k)
                    0:window_w=-18'sd65535; 1:window_w=-18'sd1; 2:window_w=0; 3:window_w=1; 4:window_w=2;
                    5:window_w=WIDTH-1; 6:window_w=WIDTH; 7:window_w=WIDTH+1; 8:window_w=18'sd65535;
                    9:window_w=18'sd32768; 10:window_w=-x; 11:window_w=-x+1; 12:window_w=-x-1; 13:window_w=WIDTH-x;
                    default:window_w=$signed(18'($urandom_range(0,131071)))-18'sd65535;
                endcase
                if(window_w>18'sd65535) window_w=18'sd65535;
                if(window_w<-18'sd65535) window_w=-18'sd65535;
                #1;if(original!==prepared) $fatal(1,"layer x=%0d w=%0d: %b vs %b",x,window_w,original,prepared);
                cases++;
            end
            for(integer w=0;w<64;w++) begin
                sprite_w=w[5:0];#1;
                if(s_original!==s_prepared) $fatal(1,"sprite x=%0d w=%0d: %b vs %b",x,w,s_original,s_prepared);
                cases++;
            end
        end
        $display("PASS WIDTH=%0d: %0d cas, fenêtre vide identique pour les couches et les sprites",WIDTH,cases);
        $finish;
    end
endmodule
