`timescale 1ns/1ps
module tb;
    reg [31:0] legacy;
    reg [67:0] select;
    reg [319:0] snapshot;
    wire [31:0] merged;
    integer address,trial,lane,word_index,count=0;
    reg [31:0] expected;
    neo_rjc_readback dut(.*);
    initial begin
        for(trial=0;trial<16;trial=trial+1)begin
            for(word_index=0;word_index<10;word_index=word_index+1)
                snapshot[word_index*32+:32]=$random;
            for(address=0;address<256;address=address+1)begin
                legacy=$random;select=0;
                for(lane=0;lane<4;lane=lane+1)
                    for(word_index=0;word_index<17;word_index=word_index+1)
                        select[lane*17+word_index]=(address==word_index*4);
                expected=legacy;
                if(address==16)expected=snapshot[256+:32];
                else if(address==20)expected=snapshot[288+:32];
                else if(address>=32 && address<=60 && address%4==0)
                    expected=snapshot[(address-32)*8+:32];
                #1;
                if(merged!==expected)$fatal(1,"address=%h actual=%h expected=%h",address,merged,expected);
                count=count+1;
            end
        end
        $display("RESULT PASS reads=%0d",count);$finish;
    end
endmodule
