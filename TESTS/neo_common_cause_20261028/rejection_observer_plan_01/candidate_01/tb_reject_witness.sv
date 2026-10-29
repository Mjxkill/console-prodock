`timescale 1ns/1ps
module tb;
`ifdef MAPPED
    GSR GSR(.GSRI(1'b1));
`endif
    reg clk=0; always #5 clk=~clk;
    reg reset=1, arm_ack_toggle=0, snapshot_request=0;
    reg parent_reset=0, child_reset=0;
    reg parent_capture=0, copy_capture=0, check_ce=0;
    reg [255:0] parent_packet=0, copy_packet=0;
    reg [57:0] parent_state=1;
    reg [4:0] child_state=0;
    reg parent_bad_d=0, parent_bad_q=0, child_bad_d=0, child_bad_q=0, child_done=0;
    reg bad_header=0, target_valid=1;
    reg [2:0] descriptor_d=0, descriptor_q=0;
    reg [31:0] target_base=32'h12000020;
    reg [15:0] target_stride=32,target_width=16,target_height=1;
    reg [32:0] src_end=33'h12000020,dst_end=33'h12000040;
    reg [11:0] live=0;
    wire [639:0] record;
    reg [639:0] held=0, saved;
    reg corrupt_descriptor_q=0, suppress_parent_q=0;
    integer passed=0;
    neo_reject_witness dut(.*);

    // Stand-ins for the actual decision registers, with NBA scheduling.
    // Tests drive combinational D independently from the observer's code.
    always @(posedge clk) begin
        if (reset || parent_reset) parent_bad_q<=0;
        else parent_bad_q<=suppress_parent_q ? 0 : parent_bad_d;
        if (reset || child_reset) begin child_bad_q<=0;descriptor_q<=0;end
        else begin
            child_bad_q<=child_bad_d;
            if(check_ce)descriptor_q<=corrupt_descriptor_q ? ~descriptor_d : descriptor_d;
        end
        if(snapshot_request)held<=record;
    end
    task tick; begin @(posedge clk);#1;@(negedge clk);end endtask
    task expect_true(input reg value,input [255:0] message);
        if(!value)begin $display("FAIL %0s case=%0d record=%h",message,passed,record);$fatal;end
    endtask
    task setup;
        begin
            reset=1;arm_ack_toggle=0;snapshot_request=0;
            parent_reset=0;child_reset=0;parent_capture=0;copy_capture=0;check_ce=0;
            parent_packet=256'h00000000_00000000_00000000_00000000_00000020_00100001_12000000_1d000000;
            copy_packet=parent_packet;parent_state=1;child_state=0;
            parent_bad_d=0;child_bad_d=0;child_done=0;bad_header=0;target_valid=1;
            descriptor_d=0;target_base='h12000020;target_stride=32;target_width=16;target_height=1;
            src_end='h12000020;dst_end='h12000040;live=0;
            corrupt_descriptor_q=0;suppress_parent_q=0;
            tick();reset=0;tick();arm_ack_toggle=1;tick();
        end
    endtask
    task command;
        begin parent_capture=1;tick();parent_capture=0;end
    endtask
    task capture_copy;
        begin
            parent_state=58'd1<<41;copy_capture=1;tick();copy_capture=0;
            parent_state=58'd1<<42;child_state=1;check_ce=1;tick();check_ce=0;
            child_state=17;tick();
        end
    endtask
    task child_reject(input [4:0] state_value);
        begin child_state=state_value;child_bad_d=1;tick();child_done=1;end
    endtask
    task parent_reject;
        begin
            parent_bad_d=1;tick();
            expect_true(!record[580],"publication must await Q");
            parent_state=2;tick();
            expect_true(record[580],"record ready");
            expect_true(record[256+:32]==record[320+:32],"same bank tags");
            expect_true(record[256+:16]!=0 && record[272+:16]==16'h4a31,"tag identity");
        end
    endtask
    task ok(input [255:0] label);
        begin passed=passed+1;$display("PASS %0d %0s",passed,label);end
    endtask

    initial begin
        // A snapshot while idle must not consume the one-shot capture.
        setup();snapshot_request=1;tick();snapshot_request=0;
        expect_true(!record[580] && !dut.frozen,"BEFORE idle not frozen");
        command();parent_state=58'd1<<45;target_valid=0;
        copy_packet=~parent_packet;parent_reject();
        expect_true(record[593+:3]==2 && !record[582],"TARGET provenance parent");
        expect_true(record[255:0]==parent_packet,"no stale child packet");
        expect_true(record[596+:16]==1 && record[612+:16]==0,"no old CHECK generation");
        ok("idle prime and target reject");

        setup();command();parent_state=58'd1<<45;bad_header=1;target_valid=0;
        parent_reject();expect_true(record[593+:3]==1,"header priority");ok("header before target");

        setup();command();descriptor_d=3'b100;copy_packet[84]=0;
        capture_copy();child_reject(17);parent_reject();
        expect_true(record[593+:3]==3 && record[582] && record[583],"associated child validation");
        expect_true(record[255:0]==copy_packet && record[288+:32]==parent_packet[31:0],"real child plus parent header");
        expect_true(record[572+:8]==8'b00000100,"word2 differs");
        expect_true(record[566+:3]==4 && record[569+:3]==4,"D and next Q");
        expect_true(record[596+:16]==record[612+:16],"CHECK belongs to command");
        expect_true(record[432+:33]=='h12000020 && record[465+:33]=='h12000040,"CHECK ends");
        saved=record;parent_packet=0;copy_packet=0;src_end=0;dst_end=0;
        parent_reset=1;child_reset=1;snapshot_request=1;repeat(3)tick();
        expect_true(record==saved,"frozen even after app reset and new snapshot");
        ok("child validation preserves operands");

        setup();command();capture_copy();child_reject(23);parent_reject();
        expect_true(record[593+:3]==4 && record[561+:5]==23,"child default raw state");
        ok("child invalid FSM");

        setup();command();capture_copy();child_reject(17);parent_reject();
        expect_true(record[593+:3]==4,"zero descriptor flags cannot claim validation");
        ok("inconsistent child bad is not validation");

        setup();command();descriptor_d=1;corrupt_descriptor_q=1;
        capture_copy();child_reject(17);parent_reject();
        expect_true(record[593+:3]==6 && record[592],"D/Q disagreement");
        expect_true(record[566+:3]==1 && record[569+:3]==6,"raw D/Q retained");
        ok("descriptor D/Q fault");

        setup();command();descriptor_d=1;capture_copy();
        parent_state=1;command();parent_packet[63:32]='h13000000;
        parent_state=58'd1<<45;target_valid=0;parent_reject();
        expect_true(record[593+:3]==2 && !record[583],"old CHECK refused");
        expect_true(record[255:0]==parent_packet,"new parent packet");
        ok("stale CHECK across commands");

        setup();command();parent_state=58'd1<<45;target_valid=0;suppress_parent_q=1;
        parent_reject();expect_true(record[593+:3]==6 && record[592],"parent BAD D/Q refused");
        ok("parent D/Q fault");

        setup();command();parent_state=(58'd1<<45)|(58'd1<<42);target_valid=0;
        parent_reject();expect_true(record[593+:3]==6,"non onehot kept ambiguous");
        expect_true(record[498+:58]==((58'd1<<45)|(58'd1<<42)),"raw parent state retained");
        ok("multi-hot parent");

        setup();command();parent_state=58'd1<<45;child_reset=1;tick();child_reset=0;
        target_valid=0;parent_reject();expect_true(record[593+:3]==6 && record[588],"reset history");
        ok("reset before rejection");

        setup();command();parent_state=58'd1<<45;target_valid=0;
        child_reset=1;parent_bad_d=1;tick();child_reset=0;parent_state=2;tick();
        expect_true(record[580] && record[588] && record[593+:3]==6,"reset exactly at decision");
        ok("reset on decision edge");

        setup();command();parent_state=58'd1<<45;target_valid=0;
        parent_bad_d=1;tick();parent_state=2;child_reset=1;tick();
        expect_true(record[580] && record[588] && record[593+:3]==6,"reset exactly at confirmation");
        ok("reset on confirmation edge");

        setup();command();parent_state=58'd1<<5;live=12'b001100101101;
        snapshot_request=1;tick();snapshot_request=0;
        expect_true(record[580] && !record[581] && record[593+:3]==0,"manual has no rejection reason");
        expect_true(!held[580],"first simultaneous capture stale");
        expect_true(record[638] && record[628+:10]==live[9:0],"manual liveness");
        snapshot_request=1;tick();snapshot_request=0;
        expect_true(held==record,"second capture is frozen record");
        saved=record;parent_bad_d=1;tick();
        expect_true(record==saved,"manual freeze cannot be overwritten");
        ok("manual prime discarded");

        setup();command();parent_state=58'd1<<45;target_valid=0;snapshot_request=1;
        parent_reject();snapshot_request=0;
        expect_true(record[581] && record[593+:3]==2,"rejection beats manual capture");
        ok("simultaneous rejection and prime");

        setup();command();parent_state=58'd1<<45;target_valid=0;parent_reject();
        parent_state=1;parent_bad_d=0;tick();arm_ack_toggle=0;tick();
        expect_true(!record[580] && record[256+:16]==2,"explicit rearm advances tag");
        command();parent_state=58'd1<<45;bad_header=1;parent_reject();
        expect_true(record[593+:3]==1 && record[256+:16]==2,"second armed event");
        ok("rearm without FPGA load");

`ifndef MAPPED
        setup();dut.epoch=16'hffff;arm_ack_toggle=0;tick();
        expect_true(!dut.armed && record[590] && !record[580],"epoch overflow refused");
        ok("no wrapped event identity");

        setup();dut.generation=16'hffff;command();parent_state=58'd1<<45;target_valid=0;
        parent_reject();expect_true(record[593+:3]==6,"command overflow ambiguity");
        ok("command generation overflow");
`endif
        $display("RESULT PASS cases=%0d",passed);$finish;
    end
    initial begin #20000;$fatal(1,"watchdog");end
endmodule
