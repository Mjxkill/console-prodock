//
//Written by GowinSynthesis
//Tool Version "V1.9.12.03"
//Mon Oct 26 08:29:06 2026

//Source file index table:
//file0 "\/home/michael/console/tang/impl/console_neo_n56r18_local_capture/source/tang/boards/neo/neo_capture_local.v"
`timescale 100 ps/100 ps
module neo_capture_local (
  clk,
  resetn,
  sample,
  arm_req,
  snap_req,
  arm_ack,
  snap_ack,
  ready,
  heartbeat,
  held
)
;
input clk;
input resetn;
input [23:0] sample;
input arm_req;
input snap_req;
output arm_ack;
output snap_ack;
output ready;
output heartbeat;
output [63:0] held;
wire complete_7;
wire valid_0_8;
wire n293_9;
wire n411_6;
wire n410_6;
wire n409_6;
wire n408_6;
wire n407_6;
wire n406_6;
wire n405_6;
wire n404_6;
wire n403_6;
wire n402_6;
wire n401_6;
wire n400_6;
wire n399_6;
wire n398_6;
wire n397_6;
wire n396_6;
wire n395_6;
wire n394_6;
wire n393_6;
wire n392_6;
wire n391_6;
wire n390_6;
wire n389_6;
wire n388_6;
wire n387_6;
wire n386_6;
wire n385_6;
wire n384_6;
wire n383_6;
wire n382_6;
wire n381_6;
wire n380_6;
wire n379_6;
wire n378_6;
wire n377_6;
wire n376_6;
wire n375_6;
wire n374_6;
wire n373_6;
wire n372_6;
wire n371_6;
wire n370_6;
wire n369_6;
wire n368_6;
wire n367_6;
wire n366_6;
wire n365_6;
wire n364_6;
wire n363_6;
wire n362_6;
wire n360_6;
wire n359_6;
wire n358_6;
wire n357_6;
wire n491_6;
wire n490_6;
wire n489_6;
wire n488_6;
wire n487_6;
wire n486_6;
wire n485_6;
wire n484_6;
wire n483_6;
wire n416_6;
wire n415_6;
wire n414_6;
wire n413_6;
wire n493_7;
wire n495_7;
wire n496_7;
wire n201_7;
wire n488_7;
wire n487_7;
wire n485_7;
wire n484_7;
wire n483_7;
wire n202_9;
wire n203_9;
wire n204_9;
wire n205_9;
wire n206_9;
wire n207_9;
wire n208_9;
wire n209_9;
wire n210_9;
wire n211_9;
wire n212_9;
wire n213_9;
wire n214_9;
wire n215_9;
wire n216_9;
wire n217_9;
wire n218_9;
wire n219_9;
wire n220_9;
wire n221_9;
wire n222_9;
wire n223_9;
wire n224_9;
wire n225_9;
wire n292_11;
wire n412_9;
wire snap_ack_10;
wire pending;
wire seen_reset;
wire seen_ce;
wire armed;
wire complete;
wire n77_7;
wire [0:0] up;
wire [1:0] arm_sync;
wire [1:0] snap_sync;
wire [7:0] beat;
wire [0:0] valid;
wire [23:0] at_event;
wire [23:0] after_event;
wire VCC;
wire GND;
  LUT3 armed_s3 (
    .F(complete_7),
    .I0(pending),
    .I1(armed),
    .I2(n201_7) 
);
defparam armed_s3.INIT=8'h8F;
  LUT4 valid_0_s3 (
    .F(valid_0_8),
    .I0(pending),
    .I1(sample[18]),
    .I2(armed),
    .I3(n201_7) 
);
defparam valid_0_s3.INIT=16'h40FF;
  LUT3 n293_s4 (
    .F(n293_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready) 
);
defparam n293_s4.INIT=8'h60;
  LUT2 n411_s1 (
    .F(n411_6),
    .I0(ready),
    .I1(at_event[0]) 
);
defparam n411_s1.INIT=4'h8;
  LUT2 n410_s1 (
    .F(n410_6),
    .I0(ready),
    .I1(at_event[1]) 
);
defparam n410_s1.INIT=4'h8;
  LUT2 n409_s1 (
    .F(n409_6),
    .I0(ready),
    .I1(at_event[2]) 
);
defparam n409_s1.INIT=4'h8;
  LUT2 n408_s1 (
    .F(n408_6),
    .I0(ready),
    .I1(at_event[3]) 
);
defparam n408_s1.INIT=4'h8;
  LUT2 n407_s1 (
    .F(n407_6),
    .I0(ready),
    .I1(at_event[4]) 
);
defparam n407_s1.INIT=4'h8;
  LUT2 n406_s1 (
    .F(n406_6),
    .I0(ready),
    .I1(at_event[5]) 
);
defparam n406_s1.INIT=4'h8;
  LUT2 n405_s1 (
    .F(n405_6),
    .I0(ready),
    .I1(at_event[6]) 
);
defparam n405_s1.INIT=4'h8;
  LUT2 n404_s1 (
    .F(n404_6),
    .I0(ready),
    .I1(at_event[7]) 
);
defparam n404_s1.INIT=4'h8;
  LUT2 n403_s1 (
    .F(n403_6),
    .I0(ready),
    .I1(at_event[8]) 
);
defparam n403_s1.INIT=4'h8;
  LUT2 n402_s1 (
    .F(n402_6),
    .I0(ready),
    .I1(at_event[9]) 
);
defparam n402_s1.INIT=4'h8;
  LUT2 n401_s1 (
    .F(n401_6),
    .I0(ready),
    .I1(at_event[10]) 
);
defparam n401_s1.INIT=4'h8;
  LUT2 n400_s1 (
    .F(n400_6),
    .I0(ready),
    .I1(at_event[11]) 
);
defparam n400_s1.INIT=4'h8;
  LUT2 n399_s1 (
    .F(n399_6),
    .I0(ready),
    .I1(at_event[12]) 
);
defparam n399_s1.INIT=4'h8;
  LUT2 n398_s1 (
    .F(n398_6),
    .I0(ready),
    .I1(at_event[13]) 
);
defparam n398_s1.INIT=4'h8;
  LUT2 n397_s1 (
    .F(n397_6),
    .I0(ready),
    .I1(at_event[14]) 
);
defparam n397_s1.INIT=4'h8;
  LUT2 n396_s1 (
    .F(n396_6),
    .I0(ready),
    .I1(at_event[15]) 
);
defparam n396_s1.INIT=4'h8;
  LUT2 n395_s1 (
    .F(n395_6),
    .I0(ready),
    .I1(at_event[16]) 
);
defparam n395_s1.INIT=4'h8;
  LUT2 n394_s1 (
    .F(n394_6),
    .I0(ready),
    .I1(at_event[17]) 
);
defparam n394_s1.INIT=4'h8;
  LUT2 n393_s1 (
    .F(n393_6),
    .I0(ready),
    .I1(at_event[18]) 
);
defparam n393_s1.INIT=4'h8;
  LUT2 n392_s1 (
    .F(n392_6),
    .I0(ready),
    .I1(at_event[19]) 
);
defparam n392_s1.INIT=4'h8;
  LUT2 n391_s1 (
    .F(n391_6),
    .I0(ready),
    .I1(at_event[20]) 
);
defparam n391_s1.INIT=4'h8;
  LUT2 n390_s1 (
    .F(n390_6),
    .I0(ready),
    .I1(at_event[21]) 
);
defparam n390_s1.INIT=4'h8;
  LUT2 n389_s1 (
    .F(n389_6),
    .I0(ready),
    .I1(at_event[22]) 
);
defparam n389_s1.INIT=4'h8;
  LUT2 n388_s1 (
    .F(n388_6),
    .I0(ready),
    .I1(at_event[23]) 
);
defparam n388_s1.INIT=4'h8;
  LUT2 n387_s1 (
    .F(n387_6),
    .I0(ready),
    .I1(after_event[0]) 
);
defparam n387_s1.INIT=4'h8;
  LUT2 n386_s1 (
    .F(n386_6),
    .I0(ready),
    .I1(after_event[1]) 
);
defparam n386_s1.INIT=4'h8;
  LUT2 n385_s1 (
    .F(n385_6),
    .I0(ready),
    .I1(after_event[2]) 
);
defparam n385_s1.INIT=4'h8;
  LUT2 n384_s1 (
    .F(n384_6),
    .I0(ready),
    .I1(after_event[3]) 
);
defparam n384_s1.INIT=4'h8;
  LUT2 n383_s1 (
    .F(n383_6),
    .I0(ready),
    .I1(after_event[4]) 
);
defparam n383_s1.INIT=4'h8;
  LUT2 n382_s1 (
    .F(n382_6),
    .I0(ready),
    .I1(after_event[5]) 
);
defparam n382_s1.INIT=4'h8;
  LUT2 n381_s1 (
    .F(n381_6),
    .I0(ready),
    .I1(after_event[6]) 
);
defparam n381_s1.INIT=4'h8;
  LUT2 n380_s1 (
    .F(n380_6),
    .I0(ready),
    .I1(after_event[7]) 
);
defparam n380_s1.INIT=4'h8;
  LUT2 n379_s1 (
    .F(n379_6),
    .I0(ready),
    .I1(after_event[8]) 
);
defparam n379_s1.INIT=4'h8;
  LUT2 n378_s1 (
    .F(n378_6),
    .I0(ready),
    .I1(after_event[9]) 
);
defparam n378_s1.INIT=4'h8;
  LUT2 n377_s1 (
    .F(n377_6),
    .I0(ready),
    .I1(after_event[10]) 
);
defparam n377_s1.INIT=4'h8;
  LUT2 n376_s1 (
    .F(n376_6),
    .I0(ready),
    .I1(after_event[11]) 
);
defparam n376_s1.INIT=4'h8;
  LUT2 n375_s1 (
    .F(n375_6),
    .I0(ready),
    .I1(after_event[12]) 
);
defparam n375_s1.INIT=4'h8;
  LUT2 n374_s1 (
    .F(n374_6),
    .I0(ready),
    .I1(after_event[13]) 
);
defparam n374_s1.INIT=4'h8;
  LUT2 n373_s1 (
    .F(n373_6),
    .I0(ready),
    .I1(after_event[14]) 
);
defparam n373_s1.INIT=4'h8;
  LUT2 n372_s1 (
    .F(n372_6),
    .I0(ready),
    .I1(after_event[15]) 
);
defparam n372_s1.INIT=4'h8;
  LUT2 n371_s1 (
    .F(n371_6),
    .I0(ready),
    .I1(after_event[16]) 
);
defparam n371_s1.INIT=4'h8;
  LUT2 n370_s1 (
    .F(n370_6),
    .I0(ready),
    .I1(after_event[17]) 
);
defparam n370_s1.INIT=4'h8;
  LUT2 n369_s1 (
    .F(n369_6),
    .I0(ready),
    .I1(after_event[18]) 
);
defparam n369_s1.INIT=4'h8;
  LUT2 n368_s1 (
    .F(n368_6),
    .I0(ready),
    .I1(after_event[19]) 
);
defparam n368_s1.INIT=4'h8;
  LUT2 n367_s1 (
    .F(n367_6),
    .I0(ready),
    .I1(after_event[20]) 
);
defparam n367_s1.INIT=4'h8;
  LUT2 n366_s1 (
    .F(n366_6),
    .I0(ready),
    .I1(after_event[21]) 
);
defparam n366_s1.INIT=4'h8;
  LUT2 n365_s1 (
    .F(n365_6),
    .I0(ready),
    .I1(after_event[22]) 
);
defparam n365_s1.INIT=4'h8;
  LUT2 n364_s1 (
    .F(n364_6),
    .I0(ready),
    .I1(after_event[23]) 
);
defparam n364_s1.INIT=4'h8;
  LUT2 n363_s1 (
    .F(n363_6),
    .I0(ready),
    .I1(valid[0]) 
);
defparam n363_s1.INIT=4'h8;
  LUT2 n362_s1 (
    .F(n362_6),
    .I0(ready),
    .I1(complete) 
);
defparam n362_s1.INIT=4'h8;
  LUT2 n360_s1 (
    .F(n360_6),
    .I0(armed),
    .I1(ready) 
);
defparam n360_s1.INIT=4'h8;
  LUT2 n359_s1 (
    .F(n359_6),
    .I0(seen_reset),
    .I1(ready) 
);
defparam n359_s1.INIT=4'h8;
  LUT2 n358_s1 (
    .F(n358_6),
    .I0(seen_ce),
    .I1(ready) 
);
defparam n358_s1.INIT=4'h8;
  LUT2 n357_s1 (
    .F(n357_6),
    .I0(arm_ack),
    .I1(ready) 
);
defparam n357_s1.INIT=4'h8;
  LUT2 n491_s1 (
    .F(n491_6),
    .I0(beat[0]),
    .I1(ready) 
);
defparam n491_s1.INIT=4'h4;
  LUT3 n490_s1 (
    .F(n490_6),
    .I0(beat[1]),
    .I1(beat[0]),
    .I2(ready) 
);
defparam n490_s1.INIT=8'h60;
  LUT4 n489_s1 (
    .F(n489_6),
    .I0(beat[1]),
    .I1(beat[0]),
    .I2(beat[2]),
    .I3(ready) 
);
defparam n489_s1.INIT=16'h7800;
  LUT2 n488_s1 (
    .F(n488_6),
    .I0(n488_7),
    .I1(ready) 
);
defparam n488_s1.INIT=4'h8;
  LUT3 n487_s1 (
    .F(n487_6),
    .I0(n487_7),
    .I1(beat[4]),
    .I2(ready) 
);
defparam n487_s1.INIT=8'h60;
  LUT4 n486_s1 (
    .F(n486_6),
    .I0(n487_7),
    .I1(beat[4]),
    .I2(beat[5]),
    .I3(ready) 
);
defparam n486_s1.INIT=16'h7800;
  LUT4 n485_s1 (
    .F(n485_6),
    .I0(n487_7),
    .I1(n485_7),
    .I2(beat[6]),
    .I3(ready) 
);
defparam n485_s1.INIT=16'h7800;
  LUT4 n484_s1 (
    .F(n484_6),
    .I0(n487_7),
    .I1(n484_7),
    .I2(beat[7]),
    .I3(ready) 
);
defparam n484_s1.INIT=16'h7800;
  LUT4 n483_s1 (
    .F(n483_6),
    .I0(n487_7),
    .I1(n483_7),
    .I2(heartbeat),
    .I3(ready) 
);
defparam n483_s1.INIT=16'h7800;
  LUT2 n416_s1 (
    .F(n416_6),
    .I0(ready),
    .I1(snap_req) 
);
defparam n416_s1.INIT=4'h8;
  LUT2 n415_s1 (
    .F(n415_6),
    .I0(ready),
    .I1(snap_sync[0]) 
);
defparam n415_s1.INIT=4'h8;
  LUT2 n414_s1 (
    .F(n414_6),
    .I0(ready),
    .I1(arm_req) 
);
defparam n414_s1.INIT=4'h8;
  LUT2 n413_s1 (
    .F(n413_6),
    .I0(ready),
    .I1(arm_sync[0]) 
);
defparam n413_s1.INIT=4'h8;
  LUT4 n493_s2 (
    .F(n493_7),
    .I0(sample[18]),
    .I1(pending),
    .I2(armed),
    .I3(n201_7) 
);
defparam n493_s2.INIT=16'h2C00;
  LUT4 n495_s2 (
    .F(n495_7),
    .I0(sample[17]),
    .I1(armed),
    .I2(seen_reset),
    .I3(n201_7) 
);
defparam n495_s2.INIT=16'hF800;
  LUT4 n496_s2 (
    .F(n496_7),
    .I0(sample[16]),
    .I1(armed),
    .I2(seen_ce),
    .I3(n201_7) 
);
defparam n496_s2.INIT=16'hF800;
  LUT3 n201_s2 (
    .F(n201_7),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready) 
);
defparam n201_s2.INIT=8'h90;
  LUT4 n488_s2 (
    .F(n488_7),
    .I0(beat[1]),
    .I1(beat[0]),
    .I2(beat[2]),
    .I3(beat[3]) 
);
defparam n488_s2.INIT=16'h7F80;
  LUT4 n487_s2 (
    .F(n487_7),
    .I0(beat[1]),
    .I1(beat[0]),
    .I2(beat[2]),
    .I3(beat[3]) 
);
defparam n487_s2.INIT=16'h8000;
  LUT2 n485_s2 (
    .F(n485_7),
    .I0(beat[4]),
    .I1(beat[5]) 
);
defparam n485_s2.INIT=4'h8;
  LUT3 n484_s2 (
    .F(n484_7),
    .I0(beat[4]),
    .I1(beat[5]),
    .I2(beat[6]) 
);
defparam n484_s2.INIT=8'h80;
  LUT4 n483_s2 (
    .F(n483_7),
    .I0(beat[4]),
    .I1(beat[5]),
    .I2(beat[6]),
    .I3(beat[7]) 
);
defparam n483_s2.INIT=16'h8000;
  LUT4 n202_s3 (
    .F(n202_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[23]) 
);
defparam n202_s3.INIT=16'h9000;
  LUT4 n203_s3 (
    .F(n203_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[22]) 
);
defparam n203_s3.INIT=16'h9000;
  LUT4 n204_s3 (
    .F(n204_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[21]) 
);
defparam n204_s3.INIT=16'h9000;
  LUT4 n205_s3 (
    .F(n205_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[20]) 
);
defparam n205_s3.INIT=16'h9000;
  LUT4 n206_s3 (
    .F(n206_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[19]) 
);
defparam n206_s3.INIT=16'h9000;
  LUT4 n207_s3 (
    .F(n207_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[18]) 
);
defparam n207_s3.INIT=16'h9000;
  LUT4 n208_s3 (
    .F(n208_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[17]) 
);
defparam n208_s3.INIT=16'h9000;
  LUT4 n209_s3 (
    .F(n209_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[16]) 
);
defparam n209_s3.INIT=16'h9000;
  LUT4 n210_s3 (
    .F(n210_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[15]) 
);
defparam n210_s3.INIT=16'h9000;
  LUT4 n211_s3 (
    .F(n211_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[14]) 
);
defparam n211_s3.INIT=16'h9000;
  LUT4 n212_s3 (
    .F(n212_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[13]) 
);
defparam n212_s3.INIT=16'h9000;
  LUT4 n213_s3 (
    .F(n213_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[12]) 
);
defparam n213_s3.INIT=16'h9000;
  LUT4 n214_s3 (
    .F(n214_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[11]) 
);
defparam n214_s3.INIT=16'h9000;
  LUT4 n215_s3 (
    .F(n215_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[10]) 
);
defparam n215_s3.INIT=16'h9000;
  LUT4 n216_s3 (
    .F(n216_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[9]) 
);
defparam n216_s3.INIT=16'h9000;
  LUT4 n217_s3 (
    .F(n217_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[8]) 
);
defparam n217_s3.INIT=16'h9000;
  LUT4 n218_s3 (
    .F(n218_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[7]) 
);
defparam n218_s3.INIT=16'h9000;
  LUT4 n219_s3 (
    .F(n219_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[6]) 
);
defparam n219_s3.INIT=16'h9000;
  LUT4 n220_s3 (
    .F(n220_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[5]) 
);
defparam n220_s3.INIT=16'h9000;
  LUT4 n221_s3 (
    .F(n221_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[4]) 
);
defparam n221_s3.INIT=16'h9000;
  LUT4 n222_s3 (
    .F(n222_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[3]) 
);
defparam n222_s3.INIT=16'h9000;
  LUT4 n223_s3 (
    .F(n223_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[2]) 
);
defparam n223_s3.INIT=16'h9000;
  LUT4 n224_s3 (
    .F(n224_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[1]) 
);
defparam n224_s3.INIT=16'h9000;
  LUT4 n225_s3 (
    .F(n225_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[0]) 
);
defparam n225_s3.INIT=16'h9000;
  LUT2 n292_s3 (
    .F(n292_11),
    .I0(arm_sync[1]),
    .I1(ready) 
);
defparam n292_s3.INIT=4'h8;
  LUT4 n412_s3 (
    .F(n412_9),
    .I0(ready),
    .I1(snap_sync[1]),
    .I2(snap_ack),
    .I3(n293_9) 
);
defparam n412_s3.INIT=16'hF088;
  LUT4 snap_ack_s7 (
    .F(snap_ack_10),
    .I0(ready),
    .I1(snap_ack),
    .I2(snap_sync[1]),
    .I3(n293_9) 
);
defparam snap_ack_s7.INIT=16'h007D;
  DFFCE up_0_s0 (
    .Q(up[0]),
    .D(VCC),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam up_0_s0.INIT=1'b0;
  DFFCE arm_sync_1_s0 (
    .Q(arm_sync[1]),
    .D(n413_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam arm_sync_1_s0.INIT=1'b0;
  DFFCE arm_sync_0_s0 (
    .Q(arm_sync[0]),
    .D(n414_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam arm_sync_0_s0.INIT=1'b0;
  DFFCE snap_sync_1_s0 (
    .Q(snap_sync[1]),
    .D(n415_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam snap_sync_1_s0.INIT=1'b0;
  DFFCE snap_sync_0_s0 (
    .Q(snap_sync[0]),
    .D(n416_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam snap_sync_0_s0.INIT=1'b0;
  DFFCE beat_8_s0 (
    .Q(heartbeat),
    .D(n483_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam beat_8_s0.INIT=1'b0;
  DFFCE beat_7_s0 (
    .Q(beat[7]),
    .D(n484_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam beat_7_s0.INIT=1'b0;
  DFFCE beat_6_s0 (
    .Q(beat[6]),
    .D(n485_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam beat_6_s0.INIT=1'b0;
  DFFCE beat_5_s0 (
    .Q(beat[5]),
    .D(n486_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam beat_5_s0.INIT=1'b0;
  DFFCE beat_4_s0 (
    .Q(beat[4]),
    .D(n487_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam beat_4_s0.INIT=1'b0;
  DFFCE beat_3_s0 (
    .Q(beat[3]),
    .D(n488_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam beat_3_s0.INIT=1'b0;
  DFFCE beat_2_s0 (
    .Q(beat[2]),
    .D(n489_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam beat_2_s0.INIT=1'b0;
  DFFCE beat_1_s0 (
    .Q(beat[1]),
    .D(n490_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam beat_1_s0.INIT=1'b0;
  DFFCE beat_0_s0 (
    .Q(beat[0]),
    .D(n491_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam beat_0_s0.INIT=1'b0;
  DFFCE pending_s0 (
    .Q(pending),
    .D(n493_7),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam pending_s0.INIT=1'b0;
  DFFCE seen_reset_s0 (
    .Q(seen_reset),
    .D(n495_7),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam seen_reset_s0.INIT=1'b0;
  DFFCE seen_ce_s0 (
    .Q(seen_ce),
    .D(n496_7),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam seen_ce_s0.INIT=1'b0;
  DFFCE up_1_s0 (
    .Q(ready),
    .D(up[0]),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam up_1_s0.INIT=1'b0;
  DFFCE held_63_s3 (
    .Q(held[56]),
    .D(ready),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_63_s3.INIT=1'b0;
  DFFCE held_54_s2 (
    .Q(held[54]),
    .D(n357_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_54_s2.INIT=1'b0;
  DFFCE held_53_s2 (
    .Q(held[53]),
    .D(n358_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_53_s2.INIT=1'b0;
  DFFCE held_52_s2 (
    .Q(held[52]),
    .D(n359_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_52_s2.INIT=1'b0;
  DFFCE held_51_s2 (
    .Q(held[51]),
    .D(n360_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_51_s2.INIT=1'b0;
  DFFCE held_50_s2 (
    .Q(held[49]),
    .D(n362_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_50_s2.INIT=1'b0;
  DFFCE held_48_s2 (
    .Q(held[48]),
    .D(n363_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_48_s2.INIT=1'b0;
  DFFCE held_47_s2 (
    .Q(held[47]),
    .D(n364_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_47_s2.INIT=1'b0;
  DFFCE held_46_s2 (
    .Q(held[46]),
    .D(n365_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_46_s2.INIT=1'b0;
  DFFCE held_45_s2 (
    .Q(held[45]),
    .D(n366_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_45_s2.INIT=1'b0;
  DFFCE held_44_s2 (
    .Q(held[44]),
    .D(n367_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_44_s2.INIT=1'b0;
  DFFCE held_43_s2 (
    .Q(held[43]),
    .D(n368_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_43_s2.INIT=1'b0;
  DFFCE held_42_s2 (
    .Q(held[42]),
    .D(n369_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_42_s2.INIT=1'b0;
  DFFCE held_41_s2 (
    .Q(held[41]),
    .D(n370_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_41_s2.INIT=1'b0;
  DFFCE held_40_s2 (
    .Q(held[40]),
    .D(n371_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_40_s2.INIT=1'b0;
  DFFCE held_39_s2 (
    .Q(held[39]),
    .D(n372_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_39_s2.INIT=1'b0;
  DFFCE held_38_s2 (
    .Q(held[38]),
    .D(n373_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_38_s2.INIT=1'b0;
  DFFCE held_37_s2 (
    .Q(held[37]),
    .D(n374_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_37_s2.INIT=1'b0;
  DFFCE held_36_s2 (
    .Q(held[36]),
    .D(n375_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_36_s2.INIT=1'b0;
  DFFCE held_35_s2 (
    .Q(held[35]),
    .D(n376_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_35_s2.INIT=1'b0;
  DFFCE held_34_s2 (
    .Q(held[34]),
    .D(n377_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_34_s2.INIT=1'b0;
  DFFCE held_33_s2 (
    .Q(held[33]),
    .D(n378_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_33_s2.INIT=1'b0;
  DFFCE held_32_s2 (
    .Q(held[32]),
    .D(n379_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_32_s2.INIT=1'b0;
  DFFCE held_31_s2 (
    .Q(held[31]),
    .D(n380_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_31_s2.INIT=1'b0;
  DFFCE held_30_s2 (
    .Q(held[30]),
    .D(n381_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_30_s2.INIT=1'b0;
  DFFCE held_29_s2 (
    .Q(held[29]),
    .D(n382_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_29_s2.INIT=1'b0;
  DFFCE held_28_s2 (
    .Q(held[28]),
    .D(n383_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_28_s2.INIT=1'b0;
  DFFCE held_27_s2 (
    .Q(held[27]),
    .D(n384_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_27_s2.INIT=1'b0;
  DFFCE held_26_s2 (
    .Q(held[26]),
    .D(n385_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_26_s2.INIT=1'b0;
  DFFCE held_25_s2 (
    .Q(held[25]),
    .D(n386_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_25_s2.INIT=1'b0;
  DFFCE held_24_s2 (
    .Q(held[24]),
    .D(n387_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_24_s2.INIT=1'b0;
  DFFCE held_23_s2 (
    .Q(held[23]),
    .D(n388_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_23_s2.INIT=1'b0;
  DFFCE held_22_s2 (
    .Q(held[22]),
    .D(n389_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_22_s2.INIT=1'b0;
  DFFCE held_21_s2 (
    .Q(held[21]),
    .D(n390_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_21_s2.INIT=1'b0;
  DFFCE held_20_s2 (
    .Q(held[20]),
    .D(n391_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_20_s2.INIT=1'b0;
  DFFCE held_19_s2 (
    .Q(held[19]),
    .D(n392_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_19_s2.INIT=1'b0;
  DFFCE held_18_s2 (
    .Q(held[18]),
    .D(n393_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_18_s2.INIT=1'b0;
  DFFCE held_17_s2 (
    .Q(held[17]),
    .D(n394_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_17_s2.INIT=1'b0;
  DFFCE held_16_s2 (
    .Q(held[16]),
    .D(n395_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_16_s2.INIT=1'b0;
  DFFCE held_15_s2 (
    .Q(held[15]),
    .D(n396_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_15_s2.INIT=1'b0;
  DFFCE held_14_s2 (
    .Q(held[14]),
    .D(n397_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_14_s2.INIT=1'b0;
  DFFCE held_13_s2 (
    .Q(held[13]),
    .D(n398_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_13_s2.INIT=1'b0;
  DFFCE held_12_s2 (
    .Q(held[12]),
    .D(n399_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_12_s2.INIT=1'b0;
  DFFCE held_11_s2 (
    .Q(held[11]),
    .D(n400_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_11_s2.INIT=1'b0;
  DFFCE held_10_s2 (
    .Q(held[10]),
    .D(n401_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_10_s2.INIT=1'b0;
  DFFCE held_9_s2 (
    .Q(held[9]),
    .D(n402_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_9_s2.INIT=1'b0;
  DFFCE held_8_s2 (
    .Q(held[8]),
    .D(n403_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_8_s2.INIT=1'b0;
  DFFCE held_7_s2 (
    .Q(held[7]),
    .D(n404_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_7_s2.INIT=1'b0;
  DFFCE held_6_s2 (
    .Q(held[6]),
    .D(n405_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_6_s2.INIT=1'b0;
  DFFCE held_5_s2 (
    .Q(held[5]),
    .D(n406_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_5_s2.INIT=1'b0;
  DFFCE held_4_s2 (
    .Q(held[4]),
    .D(n407_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_4_s2.INIT=1'b0;
  DFFCE held_3_s2 (
    .Q(held[3]),
    .D(n408_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_3_s2.INIT=1'b0;
  DFFCE held_2_s2 (
    .Q(held[2]),
    .D(n409_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_2_s2.INIT=1'b0;
  DFFCE held_1_s2 (
    .Q(held[1]),
    .D(n410_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_1_s2.INIT=1'b0;
  DFFCE held_0_s2 (
    .Q(held[0]),
    .D(n411_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_0_s2.INIT=1'b0;
  DFFCE armed_s1 (
    .Q(armed),
    .D(n293_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam armed_s1.INIT=1'b0;
  DFFCE complete_s1 (
    .Q(complete),
    .D(n201_7),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam complete_s1.INIT=1'b0;
  DFFCE valid_0_s1 (
    .Q(valid[0]),
    .D(n201_7),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam valid_0_s1.INIT=1'b0;
  DFFCE at_event_23_s1 (
    .Q(at_event[23]),
    .D(n202_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_23_s1.INIT=1'b0;
  DFFCE at_event_22_s1 (
    .Q(at_event[22]),
    .D(n203_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_22_s1.INIT=1'b0;
  DFFCE at_event_21_s1 (
    .Q(at_event[21]),
    .D(n204_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_21_s1.INIT=1'b0;
  DFFCE at_event_20_s1 (
    .Q(at_event[20]),
    .D(n205_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_20_s1.INIT=1'b0;
  DFFCE at_event_19_s1 (
    .Q(at_event[19]),
    .D(n206_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_19_s1.INIT=1'b0;
  DFFCE at_event_18_s1 (
    .Q(at_event[18]),
    .D(n207_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_18_s1.INIT=1'b0;
  DFFCE at_event_17_s1 (
    .Q(at_event[17]),
    .D(n208_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_17_s1.INIT=1'b0;
  DFFCE at_event_16_s1 (
    .Q(at_event[16]),
    .D(n209_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_16_s1.INIT=1'b0;
  DFFCE at_event_15_s1 (
    .Q(at_event[15]),
    .D(n210_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_15_s1.INIT=1'b0;
  DFFCE at_event_14_s1 (
    .Q(at_event[14]),
    .D(n211_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_14_s1.INIT=1'b0;
  DFFCE at_event_13_s1 (
    .Q(at_event[13]),
    .D(n212_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_13_s1.INIT=1'b0;
  DFFCE at_event_12_s1 (
    .Q(at_event[12]),
    .D(n213_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_12_s1.INIT=1'b0;
  DFFCE at_event_11_s1 (
    .Q(at_event[11]),
    .D(n214_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_11_s1.INIT=1'b0;
  DFFCE at_event_10_s1 (
    .Q(at_event[10]),
    .D(n215_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_10_s1.INIT=1'b0;
  DFFCE at_event_9_s1 (
    .Q(at_event[9]),
    .D(n216_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_9_s1.INIT=1'b0;
  DFFCE at_event_8_s1 (
    .Q(at_event[8]),
    .D(n217_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_8_s1.INIT=1'b0;
  DFFCE at_event_7_s1 (
    .Q(at_event[7]),
    .D(n218_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_7_s1.INIT=1'b0;
  DFFCE at_event_6_s1 (
    .Q(at_event[6]),
    .D(n219_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_6_s1.INIT=1'b0;
  DFFCE at_event_5_s1 (
    .Q(at_event[5]),
    .D(n220_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_5_s1.INIT=1'b0;
  DFFCE at_event_4_s1 (
    .Q(at_event[4]),
    .D(n221_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_4_s1.INIT=1'b0;
  DFFCE at_event_3_s1 (
    .Q(at_event[3]),
    .D(n222_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_3_s1.INIT=1'b0;
  DFFCE at_event_2_s1 (
    .Q(at_event[2]),
    .D(n223_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_2_s1.INIT=1'b0;
  DFFCE at_event_1_s1 (
    .Q(at_event[1]),
    .D(n224_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_1_s1.INIT=1'b0;
  DFFCE at_event_0_s1 (
    .Q(at_event[0]),
    .D(n225_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_0_s1.INIT=1'b0;
  DFFCE after_event_23_s1 (
    .Q(after_event[23]),
    .D(n202_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_23_s1.INIT=1'b0;
  DFFCE after_event_22_s1 (
    .Q(after_event[22]),
    .D(n203_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_22_s1.INIT=1'b0;
  DFFCE after_event_21_s1 (
    .Q(after_event[21]),
    .D(n204_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_21_s1.INIT=1'b0;
  DFFCE after_event_20_s1 (
    .Q(after_event[20]),
    .D(n205_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_20_s1.INIT=1'b0;
  DFFCE after_event_19_s1 (
    .Q(after_event[19]),
    .D(n206_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_19_s1.INIT=1'b0;
  DFFCE after_event_18_s1 (
    .Q(after_event[18]),
    .D(n207_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_18_s1.INIT=1'b0;
  DFFCE after_event_17_s1 (
    .Q(after_event[17]),
    .D(n208_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_17_s1.INIT=1'b0;
  DFFCE after_event_16_s1 (
    .Q(after_event[16]),
    .D(n209_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_16_s1.INIT=1'b0;
  DFFCE after_event_15_s1 (
    .Q(after_event[15]),
    .D(n210_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_15_s1.INIT=1'b0;
  DFFCE after_event_14_s1 (
    .Q(after_event[14]),
    .D(n211_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_14_s1.INIT=1'b0;
  DFFCE after_event_13_s1 (
    .Q(after_event[13]),
    .D(n212_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_13_s1.INIT=1'b0;
  DFFCE after_event_12_s1 (
    .Q(after_event[12]),
    .D(n213_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_12_s1.INIT=1'b0;
  DFFCE after_event_11_s1 (
    .Q(after_event[11]),
    .D(n214_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_11_s1.INIT=1'b0;
  DFFCE after_event_10_s1 (
    .Q(after_event[10]),
    .D(n215_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_10_s1.INIT=1'b0;
  DFFCE after_event_9_s1 (
    .Q(after_event[9]),
    .D(n216_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_9_s1.INIT=1'b0;
  DFFCE after_event_8_s1 (
    .Q(after_event[8]),
    .D(n217_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_8_s1.INIT=1'b0;
  DFFCE after_event_7_s1 (
    .Q(after_event[7]),
    .D(n218_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_7_s1.INIT=1'b0;
  DFFCE after_event_6_s1 (
    .Q(after_event[6]),
    .D(n219_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_6_s1.INIT=1'b0;
  DFFCE after_event_5_s1 (
    .Q(after_event[5]),
    .D(n220_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_5_s1.INIT=1'b0;
  DFFCE after_event_4_s1 (
    .Q(after_event[4]),
    .D(n221_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_4_s1.INIT=1'b0;
  DFFCE after_event_3_s1 (
    .Q(after_event[3]),
    .D(n222_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_3_s1.INIT=1'b0;
  DFFCE after_event_2_s1 (
    .Q(after_event[2]),
    .D(n223_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_2_s1.INIT=1'b0;
  DFFCE after_event_1_s1 (
    .Q(after_event[1]),
    .D(n224_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_1_s1.INIT=1'b0;
  DFFCE after_event_0_s1 (
    .Q(after_event[0]),
    .D(n225_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_0_s1.INIT=1'b0;
  DFFCE arm_ack_s7 (
    .Q(arm_ack),
    .D(n292_11),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam arm_ack_s7.INIT=1'b0;
  DFFCE snap_ack_s6 (
    .Q(snap_ack),
    .D(n412_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam snap_ack_s6.INIT=1'b0;
  INV n77_s2 (
    .O(n77_7),
    .I(resetn) 
);
  VCC VCC_cZ (
    .V(VCC)
);
  GND GND_cZ (
    .G(GND)
);

assign held[50] = held[49];
assign held[55] = GND;
assign held[57] = GND;
assign held[58] = GND;
assign held[59] = GND;
assign held[60] = GND;
assign held[61] = GND;
assign held[62] = held[56];
assign held[63] = held[56];
endmodule /* neo_capture_local */

//
//Written by GowinSynthesis
//Tool Version "V1.9.12.03"
//Mon Oct 26 08:29:07 2026

//Source file index table:
//file0 "\/home/michael/console/tang/impl/console_neo_n56r18_local_capture/source/tang/boards/neo/neo_capture_bus.v"
`timescale 100 ps/100 ps
module neo_capture_bus (
  clk,
  resetn,
  legacy_wait,
  write_pending,
  write_bit,
  write_addr,
  read_addr,
  legacy_data,
  hrdata,
  arm_req,
  snap_req,
  arm_ack,
  snap_ack,
  ready,
  heartbeat,
  held
)
;
input clk;
input resetn;
input legacy_wait;
input write_pending;
input write_bit;
input [7:0] write_addr;
input [7:0] read_addr;
input [31:0] legacy_data;
output [31:0] hrdata;
output arm_req;
output snap_req;
input arm_ack;
input snap_ack;
input ready;
input heartbeat;
input [63:0] held;
wire arm_busy_8;
wire snap_busy_8;
wire settle_1_8;
wire shadow_63_8;
wire n525_8;
wire n520_6;
wire n517_6;
wire n515_6;
wire n513_6;
wire n512_6;
wire n510_6;
wire n508_6;
wire n507_6;
wire n505_6;
wire n504_6;
wire n501_6;
wire n498_6;
wire n497_6;
wire n496_6;
wire n495_6;
wire n493_6;
wire n490_8;
wire n356_6;
wire n355_6;
wire n352_6;
wire n351_6;
wire n350_6;
wire n349_6;
wire n348_6;
wire n347_6;
wire n346_6;
wire n345_6;
wire n343_6;
wire n342_6;
wire n341_6;
wire n340_6;
wire n339_6;
wire n338_6;
wire n337_6;
wire n336_6;
wire n335_6;
wire n334_6;
wire n333_6;
wire n331_6;
wire n330_6;
wire n328_6;
wire n327_6;
wire n326_6;
wire n325_6;
wire n324_6;
wire n323_6;
wire n322_6;
wire n321_6;
wire n320_6;
wire n319_6;
wire n318_6;
wire n317_6;
wire n316_6;
wire n315_6;
wire n314_6;
wire n313_6;
wire n312_6;
wire n311_6;
wire n310_6;
wire n309_6;
wire n308_6;
wire n307_6;
wire n306_6;
wire n305_6;
wire n304_6;
wire n303_6;
wire n302_6;
wire n301_6;
wire n300_6;
wire n299_6;
wire n298_6;
wire n297_6;
wire n296_6;
wire n295_6;
wire n294_6;
wire n293_6;
wire n292_6;
wire n291_6;
wire n290_6;
wire n289_6;
wire n288_6;
wire n287_6;
wire n286_6;
wire n285_6;
wire n284_6;
wire n283_6;
wire n282_6;
wire n281_6;
wire n280_6;
wire n279_6;
wire n278_6;
wire n277_6;
wire n276_6;
wire n275_6;
wire n274_6;
wire n273_6;
wire n272_6;
wire n271_6;
wire n270_6;
wire n269_6;
wire n268_6;
wire n267_6;
wire n266_6;
wire n265_6;
wire n264_6;
wire n263_6;
wire n262_6;
wire n261_6;
wire n260_6;
wire n259_6;
wire n258_6;
wire n257_6;
wire n109_6;
wire n108_6;
wire n107_6;
wire n106_6;
wire n105_6;
wire n104_6;
wire n103_6;
wire n101_6;
wire n100_6;
wire n99_6;
wire n98_6;
wire n97_6;
wire n96_6;
wire n95_6;
wire n94_6;
wire n93_6;
wire n92_6;
wire n91_6;
wire n89_6;
wire n88_6;
wire n86_6;
wire n85_6;
wire n84_6;
wire n83_6;
wire n82_6;
wire n81_6;
wire n80_6;
wire n79_6;
wire n838_6;
wire n837_6;
wire n836_6;
wire n835_6;
wire n834_6;
wire n833_6;
wire n832_6;
wire n831_6;
wire n830_6;
wire n829_6;
wire n828_6;
wire n827_6;
wire n826_6;
wire n825_6;
wire n824_6;
wire n823_6;
wire n822_6;
wire n821_6;
wire n820_6;
wire n819_6;
wire n818_6;
wire n817_6;
wire n816_6;
wire n815_6;
wire n814_6;
wire n813_6;
wire n812_6;
wire n811_6;
wire n810_6;
wire n809_6;
wire n808_6;
wire n807_6;
wire n636_6;
wire n632_6;
wire n629_6;
wire n628_6;
wire n627_6;
wire n626_6;
wire n625_6;
wire n624_6;
wire n623_6;
wire n622_6;
wire n1490_4;
wire arm_busy_9;
wire settle_1_9;
wire n525_9;
wire n525_10;
wire n525_11;
wire n519_7;
wire n518_7;
wire n516_7;
wire n514_7;
wire n512_7;
wire n511_7;
wire n509_7;
wire n507_7;
wire n506_7;
wire n504_7;
wire n503_7;
wire n502_7;
wire n500_7;
wire n499_7;
wire n497_7;
wire n495_7;
wire n494_7;
wire n492_7;
wire n491_7;
wire n349_7;
wire n348_7;
wire n346_7;
wire n344_7;
wire n342_7;
wire n341_7;
wire n339_7;
wire n337_7;
wire n336_7;
wire n334_7;
wire n332_7;
wire n330_7;
wire n329_7;
wire n327_7;
wire n326_7;
wire n324_7;
wire n322_7;
wire n322_8;
wire n321_7;
wire n107_7;
wire n106_7;
wire n104_7;
wire n102_7;
wire n100_7;
wire n99_7;
wire n97_7;
wire n95_7;
wire n94_7;
wire n92_7;
wire n91_7;
wire n90_7;
wire n88_7;
wire n87_7;
wire n85_7;
wire n84_7;
wire n83_7;
wire n82_7;
wire n80_7;
wire n838_7;
wire n838_8;
wire n838_9;
wire n837_7;
wire n837_8;
wire n837_9;
wire n836_7;
wire n836_8;
wire n836_9;
wire n835_7;
wire n835_8;
wire n835_9;
wire n834_7;
wire n834_8;
wire n834_9;
wire n833_7;
wire n833_8;
wire n833_9;
wire n832_7;
wire n832_8;
wire n832_9;
wire n831_8;
wire n831_9;
wire n830_8;
wire n830_9;
wire n829_8;
wire n829_9;
wire n828_8;
wire n828_9;
wire n827_8;
wire n827_9;
wire n826_7;
wire n826_8;
wire n826_9;
wire n825_8;
wire n825_9;
wire n824_7;
wire n824_8;
wire n824_9;
wire n823_8;
wire n823_9;
wire n822_7;
wire n822_8;
wire n822_9;
wire n821_7;
wire n821_8;
wire n821_9;
wire n820_8;
wire n820_9;
wire n819_8;
wire n819_9;
wire n818_8;
wire n818_9;
wire n817_8;
wire n817_9;
wire n816_7;
wire n816_8;
wire n816_9;
wire n815_8;
wire n815_9;
wire n814_8;
wire n814_9;
wire n813_7;
wire n813_8;
wire n813_9;
wire n812_7;
wire n812_8;
wire n812_9;
wire n811_7;
wire n811_8;
wire n811_9;
wire n810_8;
wire n810_9;
wire n809_8;
wire n809_9;
wire n808_7;
wire n808_8;
wire n808_9;
wire n807_8;
wire n807_9;
wire n1490_5;
wire n1490_6;
wire n1490_7;
wire n525_12;
wire n514_8;
wire n509_8;
wire n504_8;
wire n502_8;
wire n499_8;
wire n492_8;
wire n491_8;
wire n344_8;
wire n339_8;
wire n334_8;
wire n332_8;
wire n326_8;
wire n324_8;
wire n322_9;
wire n102_8;
wire n97_8;
wire n92_8;
wire n90_8;
wire n84_9;
wire n80_8;
wire n838_10;
wire n838_11;
wire n838_12;
wire n838_13;
wire n838_14;
wire n838_15;
wire n837_10;
wire n834_10;
wire n834_11;
wire n833_10;
wire n833_11;
wire n499_9;
wire n838_16;
wire n838_17;
wire n838_18;
wire n838_19;
wire n103_9;
wire n332_10;
wire n345_9;
wire n496_9;
wire n502_10;
wire n636_11;
wire n636_13;
wire n84_11;
wire n90_10;
wire n325_9;
wire n102_10;
wire n329_9;
wire n344_10;
wire n514_10;
wire n87_9;
wire n499_11;
wire snap_busy_11;
wire arm_req_10;
wire n809_11;
wire n810_11;
wire n815_11;
wire n818_11;
wire n823_11;
wire n807_11;
wire n814_11;
wire n820_11;
wire n831_11;
wire n817_11;
wire n819_11;
wire n825_11;
wire n827_11;
wire n828_11;
wire n829_11;
wire n830_11;
wire n111_11;
wire beat_last_13;
wire n522_9;
wire arm_req_25;
wire n1490_10;
wire n491_11;
wire n492_11;
wire n494_10;
wire n500_10;
wire n503_10;
wire n506_10;
wire n509_11;
wire n511_10;
wire n516_10;
wire n518_10;
wire n519_10;
wire n521_9;
wire n110_9;
wire n529_9;
wire n530_9;
wire n531_9;
wire n532_9;
wire n533_9;
wire n534_9;
wire n535_9;
wire n536_9;
wire rejected;
wire arm_busy;
wire snap_busy;
wire beat_last;
wire snapshot_valid;
wire n43_6;
wire [1:0] up;
wire [1:0] arm_sync;
wire [1:0] snap_sync;
wire [1:0] ready_sync;
wire [1:0] beat_sync;
wire [31:0] response;
wire [1:0] settle;
wire [63:0] shadow;
wire [31:0] sequence_id;
wire [31:1] arm_count;
wire [31:0] heartbeat_count;
wire [7:0] read_latched;
wire VCC;
wire GND;
  LUT3 hrdata_d_31_s (
    .F(hrdata[31]),
    .I0(response[31]),
    .I1(legacy_data[31]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_31_s.INIT=8'hAC;
  LUT3 hrdata_d_30_s (
    .F(hrdata[30]),
    .I0(legacy_data[30]),
    .I1(response[30]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_30_s.INIT=8'hCA;
  LUT3 hrdata_d_29_s (
    .F(hrdata[29]),
    .I0(legacy_data[29]),
    .I1(response[29]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_29_s.INIT=8'hCA;
  LUT3 hrdata_d_28_s (
    .F(hrdata[28]),
    .I0(legacy_data[28]),
    .I1(response[28]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_28_s.INIT=8'hCA;
  LUT3 hrdata_d_27_s (
    .F(hrdata[27]),
    .I0(legacy_data[27]),
    .I1(response[27]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_27_s.INIT=8'hCA;
  LUT3 hrdata_d_26_s (
    .F(hrdata[26]),
    .I0(legacy_data[26]),
    .I1(response[26]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_26_s.INIT=8'hCA;
  LUT3 hrdata_d_25_s (
    .F(hrdata[25]),
    .I0(legacy_data[25]),
    .I1(response[25]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_25_s.INIT=8'hCA;
  LUT3 hrdata_d_24_s (
    .F(hrdata[24]),
    .I0(legacy_data[24]),
    .I1(response[24]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_24_s.INIT=8'hCA;
  LUT3 hrdata_d_23_s (
    .F(hrdata[23]),
    .I0(legacy_data[23]),
    .I1(response[23]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_23_s.INIT=8'hCA;
  LUT3 hrdata_d_22_s (
    .F(hrdata[22]),
    .I0(legacy_data[22]),
    .I1(response[22]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_22_s.INIT=8'hCA;
  LUT3 hrdata_d_21_s (
    .F(hrdata[21]),
    .I0(legacy_data[21]),
    .I1(response[21]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_21_s.INIT=8'hCA;
  LUT3 hrdata_d_20_s (
    .F(hrdata[20]),
    .I0(legacy_data[20]),
    .I1(response[20]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_20_s.INIT=8'hCA;
  LUT3 hrdata_d_19_s (
    .F(hrdata[19]),
    .I0(legacy_data[19]),
    .I1(response[19]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_19_s.INIT=8'hCA;
  LUT3 hrdata_d_18_s (
    .F(hrdata[18]),
    .I0(legacy_data[18]),
    .I1(response[18]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_18_s.INIT=8'hCA;
  LUT3 hrdata_d_17_s (
    .F(hrdata[17]),
    .I0(legacy_data[17]),
    .I1(response[17]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_17_s.INIT=8'hCA;
  LUT3 hrdata_d_16_s (
    .F(hrdata[16]),
    .I0(legacy_data[16]),
    .I1(response[16]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_16_s.INIT=8'hCA;
  LUT3 hrdata_d_15_s (
    .F(hrdata[15]),
    .I0(legacy_data[15]),
    .I1(response[15]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_15_s.INIT=8'hCA;
  LUT3 hrdata_d_14_s (
    .F(hrdata[14]),
    .I0(legacy_data[14]),
    .I1(response[14]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_14_s.INIT=8'hCA;
  LUT3 hrdata_d_13_s (
    .F(hrdata[13]),
    .I0(legacy_data[13]),
    .I1(response[13]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_13_s.INIT=8'hCA;
  LUT3 hrdata_d_12_s (
    .F(hrdata[12]),
    .I0(legacy_data[12]),
    .I1(response[12]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_12_s.INIT=8'hCA;
  LUT3 hrdata_d_11_s (
    .F(hrdata[11]),
    .I0(legacy_data[11]),
    .I1(response[11]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_11_s.INIT=8'hCA;
  LUT3 hrdata_d_10_s (
    .F(hrdata[10]),
    .I0(legacy_data[10]),
    .I1(response[10]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_10_s.INIT=8'hCA;
  LUT3 hrdata_d_9_s (
    .F(hrdata[9]),
    .I0(legacy_data[9]),
    .I1(response[9]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_9_s.INIT=8'hCA;
  LUT3 hrdata_d_8_s (
    .F(hrdata[8]),
    .I0(legacy_data[8]),
    .I1(response[8]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_8_s.INIT=8'hCA;
  LUT3 hrdata_d_7_s (
    .F(hrdata[7]),
    .I0(legacy_data[7]),
    .I1(response[7]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_7_s.INIT=8'hCA;
  LUT3 hrdata_d_6_s (
    .F(hrdata[6]),
    .I0(legacy_data[6]),
    .I1(response[6]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_6_s.INIT=8'hCA;
  LUT3 hrdata_d_5_s (
    .F(hrdata[5]),
    .I0(legacy_data[5]),
    .I1(response[5]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_5_s.INIT=8'hCA;
  LUT3 hrdata_d_4_s (
    .F(hrdata[4]),
    .I0(legacy_data[4]),
    .I1(response[4]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_4_s.INIT=8'hCA;
  LUT3 hrdata_d_3_s (
    .F(hrdata[3]),
    .I0(legacy_data[3]),
    .I1(response[3]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_3_s.INIT=8'hCA;
  LUT3 hrdata_d_2_s (
    .F(hrdata[2]),
    .I0(legacy_data[2]),
    .I1(response[2]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_2_s.INIT=8'hCA;
  LUT3 hrdata_d_1_s (
    .F(hrdata[1]),
    .I0(legacy_data[1]),
    .I1(response[1]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_1_s.INIT=8'hCA;
  LUT3 hrdata_d_0_s (
    .F(hrdata[0]),
    .I0(legacy_data[0]),
    .I1(response[0]),
    .I2(read_latched[7]) 
);
defparam hrdata_d_0_s.INIT=8'hCA;
  LUT2 arm_busy_s3 (
    .F(arm_busy_8),
    .I0(arm_req_10),
    .I1(arm_busy_9) 
);
defparam arm_busy_s3.INIT=4'hB;
  LUT2 snap_busy_s3 (
    .F(snap_busy_8),
    .I0(shadow_63_8),
    .I1(snap_busy_11) 
);
defparam snap_busy_s3.INIT=4'hE;
  LUT3 settle_1_s3 (
    .F(settle_1_8),
    .I0(settle_1_9),
    .I1(snap_busy_11),
    .I2(up[1]) 
);
defparam settle_1_s3.INIT=8'hEF;
  LUT4 shadow_63_s3 (
    .F(shadow_63_8),
    .I0(settle[0]),
    .I1(settle[1]),
    .I2(settle_1_9),
    .I3(up[1]) 
);
defparam shadow_63_s3.INIT=16'h40FF;
  LUT4 n525_s3 (
    .F(n525_8),
    .I0(n525_9),
    .I1(n525_10),
    .I2(write_addr[7]),
    .I3(n525_11) 
);
defparam n525_s3.INIT=16'h4000;
  LUT4 n520_s1 (
    .F(n520_6),
    .I0(arm_count[1]),
    .I1(arm_req),
    .I2(arm_count[2]),
    .I3(up[1]) 
);
defparam n520_s1.INIT=16'h7800;
  LUT4 n517_s1 (
    .F(n517_6),
    .I0(arm_count[4]),
    .I1(n518_7),
    .I2(arm_count[5]),
    .I3(up[1]) 
);
defparam n517_s1.INIT=16'h7800;
  LUT4 n515_s1 (
    .F(n515_6),
    .I0(arm_count[6]),
    .I1(n516_7),
    .I2(arm_count[7]),
    .I3(up[1]) 
);
defparam n515_s1.INIT=16'h7800;
  LUT4 n513_s1 (
    .F(n513_6),
    .I0(arm_count[8]),
    .I1(n514_7),
    .I2(arm_count[9]),
    .I3(up[1]) 
);
defparam n513_s1.INIT=16'h7800;
  LUT4 n512_s1 (
    .F(n512_6),
    .I0(n514_7),
    .I1(n512_7),
    .I2(arm_count[10]),
    .I3(up[1]) 
);
defparam n512_s1.INIT=16'h7800;
  LUT4 n510_s1 (
    .F(n510_6),
    .I0(arm_count[11]),
    .I1(n511_7),
    .I2(arm_count[12]),
    .I3(up[1]) 
);
defparam n510_s1.INIT=16'h7800;
  LUT4 n508_s1 (
    .F(n508_6),
    .I0(arm_count[13]),
    .I1(n509_7),
    .I2(arm_count[14]),
    .I3(up[1]) 
);
defparam n508_s1.INIT=16'h7800;
  LUT4 n507_s1 (
    .F(n507_6),
    .I0(n509_7),
    .I1(n507_7),
    .I2(arm_count[15]),
    .I3(up[1]) 
);
defparam n507_s1.INIT=16'h7800;
  LUT4 n505_s1 (
    .F(n505_6),
    .I0(arm_count[16]),
    .I1(n506_7),
    .I2(arm_count[17]),
    .I3(up[1]) 
);
defparam n505_s1.INIT=16'h7800;
  LUT4 n504_s1 (
    .F(n504_6),
    .I0(n509_7),
    .I1(n504_7),
    .I2(arm_count[18]),
    .I3(up[1]) 
);
defparam n504_s1.INIT=16'h7800;
  LUT4 n501_s1 (
    .F(n501_6),
    .I0(arm_count[20]),
    .I1(n502_7),
    .I2(arm_count[21]),
    .I3(up[1]) 
);
defparam n501_s1.INIT=16'h7800;
  LUT4 n498_s1 (
    .F(n498_6),
    .I0(arm_count[23]),
    .I1(n499_7),
    .I2(arm_count[24]),
    .I3(up[1]) 
);
defparam n498_s1.INIT=16'h7800;
  LUT4 n497_s1 (
    .F(n497_6),
    .I0(n499_7),
    .I1(n497_7),
    .I2(arm_count[25]),
    .I3(up[1]) 
);
defparam n497_s1.INIT=16'h7800;
  LUT4 n496_s1 (
    .F(n496_6),
    .I0(n499_7),
    .I1(n496_9),
    .I2(arm_count[26]),
    .I3(up[1]) 
);
defparam n496_s1.INIT=16'h7800;
  LUT4 n495_s1 (
    .F(n495_6),
    .I0(n499_7),
    .I1(n495_7),
    .I2(arm_count[27]),
    .I3(up[1]) 
);
defparam n495_s1.INIT=16'h7800;
  LUT4 n493_s1 (
    .F(n493_6),
    .I0(arm_count[28]),
    .I1(n494_7),
    .I2(arm_count[29]),
    .I3(up[1]) 
);
defparam n493_s1.INIT=16'h7800;
  LUT3 n490_s3 (
    .F(n490_8),
    .I0(up[1]),
    .I1(n1490_4),
    .I2(n525_9) 
);
defparam n490_s3.INIT=8'h80;
  LUT4 n356_s1 (
    .F(n356_6),
    .I0(settle[0]),
    .I1(settle[1]),
    .I2(snap_busy_11),
    .I3(up[1]) 
);
defparam n356_s1.INIT=16'h0100;
  LUT4 n355_s1 (
    .F(n355_6),
    .I0(settle[1]),
    .I1(snap_busy_11),
    .I2(up[1]),
    .I3(settle[0]) 
);
defparam n355_s1.INIT=16'h1000;
  LUT2 n352_s1 (
    .F(n352_6),
    .I0(sequence_id[0]),
    .I1(up[1]) 
);
defparam n352_s1.INIT=4'h4;
  LUT3 n351_s1 (
    .F(n351_6),
    .I0(sequence_id[1]),
    .I1(sequence_id[0]),
    .I2(up[1]) 
);
defparam n351_s1.INIT=8'h60;
  LUT4 n350_s1 (
    .F(n350_6),
    .I0(sequence_id[1]),
    .I1(sequence_id[0]),
    .I2(sequence_id[2]),
    .I3(up[1]) 
);
defparam n350_s1.INIT=16'h7800;
  LUT2 n349_s1 (
    .F(n349_6),
    .I0(n349_7),
    .I1(up[1]) 
);
defparam n349_s1.INIT=4'h8;
  LUT3 n348_s1 (
    .F(n348_6),
    .I0(sequence_id[4]),
    .I1(n348_7),
    .I2(up[1]) 
);
defparam n348_s1.INIT=8'h60;
  LUT4 n347_s1 (
    .F(n347_6),
    .I0(sequence_id[4]),
    .I1(n348_7),
    .I2(sequence_id[5]),
    .I3(up[1]) 
);
defparam n347_s1.INIT=16'h7800;
  LUT4 n346_s1 (
    .F(n346_6),
    .I0(n348_7),
    .I1(n346_7),
    .I2(sequence_id[6]),
    .I3(up[1]) 
);
defparam n346_s1.INIT=16'h7800;
  LUT4 n345_s1 (
    .F(n345_6),
    .I0(n348_7),
    .I1(n345_9),
    .I2(sequence_id[7]),
    .I3(up[1]) 
);
defparam n345_s1.INIT=16'h7800;
  LUT4 n343_s1 (
    .F(n343_6),
    .I0(sequence_id[8]),
    .I1(n344_7),
    .I2(sequence_id[9]),
    .I3(up[1]) 
);
defparam n343_s1.INIT=16'h7800;
  LUT4 n342_s1 (
    .F(n342_6),
    .I0(n344_7),
    .I1(n342_7),
    .I2(sequence_id[10]),
    .I3(up[1]) 
);
defparam n342_s1.INIT=16'h7800;
  LUT3 n341_s1 (
    .F(n341_6),
    .I0(sequence_id[11]),
    .I1(n341_7),
    .I2(up[1]) 
);
defparam n341_s1.INIT=8'h60;
  LUT4 n340_s1 (
    .F(n340_6),
    .I0(sequence_id[11]),
    .I1(n341_7),
    .I2(sequence_id[12]),
    .I3(up[1]) 
);
defparam n340_s1.INIT=16'h7800;
  LUT3 n339_s1 (
    .F(n339_6),
    .I0(sequence_id[13]),
    .I1(n339_7),
    .I2(up[1]) 
);
defparam n339_s1.INIT=8'h60;
  LUT4 n338_s1 (
    .F(n338_6),
    .I0(sequence_id[13]),
    .I1(n339_7),
    .I2(sequence_id[14]),
    .I3(up[1]) 
);
defparam n338_s1.INIT=16'h7800;
  LUT4 n337_s1 (
    .F(n337_6),
    .I0(n339_7),
    .I1(n337_7),
    .I2(sequence_id[15]),
    .I3(up[1]) 
);
defparam n337_s1.INIT=16'h7800;
  LUT3 n336_s1 (
    .F(n336_6),
    .I0(sequence_id[16]),
    .I1(n336_7),
    .I2(up[1]) 
);
defparam n336_s1.INIT=8'h60;
  LUT4 n335_s1 (
    .F(n335_6),
    .I0(sequence_id[16]),
    .I1(n336_7),
    .I2(sequence_id[17]),
    .I3(up[1]) 
);
defparam n335_s1.INIT=16'h7800;
  LUT3 n334_s1 (
    .F(n334_6),
    .I0(sequence_id[18]),
    .I1(n334_7),
    .I2(up[1]) 
);
defparam n334_s1.INIT=8'h60;
  LUT4 n333_s1 (
    .F(n333_6),
    .I0(sequence_id[18]),
    .I1(n334_7),
    .I2(sequence_id[19]),
    .I3(up[1]) 
);
defparam n333_s1.INIT=16'h7800;
  LUT4 n331_s1 (
    .F(n331_6),
    .I0(sequence_id[20]),
    .I1(n332_7),
    .I2(sequence_id[21]),
    .I3(up[1]) 
);
defparam n331_s1.INIT=16'h7800;
  LUT3 n330_s1 (
    .F(n330_6),
    .I0(sequence_id[22]),
    .I1(n330_7),
    .I2(up[1]) 
);
defparam n330_s1.INIT=8'h60;
  LUT4 n328_s1 (
    .F(n328_6),
    .I0(sequence_id[23]),
    .I1(n329_7),
    .I2(sequence_id[24]),
    .I3(up[1]) 
);
defparam n328_s1.INIT=16'h7800;
  LUT3 n327_s1 (
    .F(n327_6),
    .I0(sequence_id[25]),
    .I1(n327_7),
    .I2(up[1]) 
);
defparam n327_s1.INIT=8'h60;
  LUT2 n326_s1 (
    .F(n326_6),
    .I0(n326_7),
    .I1(up[1]) 
);
defparam n326_s1.INIT=4'h8;
  LUT4 n325_s1 (
    .F(n325_6),
    .I0(n329_7),
    .I1(n325_9),
    .I2(sequence_id[27]),
    .I3(up[1]) 
);
defparam n325_s1.INIT=16'h7800;
  LUT3 n324_s1 (
    .F(n324_6),
    .I0(sequence_id[28]),
    .I1(n324_7),
    .I2(up[1]) 
);
defparam n324_s1.INIT=8'h60;
  LUT4 n323_s1 (
    .F(n323_6),
    .I0(sequence_id[28]),
    .I1(n324_7),
    .I2(sequence_id[29]),
    .I3(up[1]) 
);
defparam n323_s1.INIT=16'h7800;
  LUT4 n322_s1 (
    .F(n322_6),
    .I0(n322_7),
    .I1(n322_8),
    .I2(sequence_id[30]),
    .I3(up[1]) 
);
defparam n322_s1.INIT=16'h7800;
  LUT4 n321_s1 (
    .F(n321_6),
    .I0(n329_7),
    .I1(n321_7),
    .I2(sequence_id[31]),
    .I3(up[1]) 
);
defparam n321_s1.INIT=16'h7800;
  LUT2 n320_s1 (
    .F(n320_6),
    .I0(up[1]),
    .I1(held[0]) 
);
defparam n320_s1.INIT=4'h8;
  LUT2 n319_s1 (
    .F(n319_6),
    .I0(up[1]),
    .I1(held[1]) 
);
defparam n319_s1.INIT=4'h8;
  LUT2 n318_s1 (
    .F(n318_6),
    .I0(up[1]),
    .I1(held[2]) 
);
defparam n318_s1.INIT=4'h8;
  LUT2 n317_s1 (
    .F(n317_6),
    .I0(up[1]),
    .I1(held[3]) 
);
defparam n317_s1.INIT=4'h8;
  LUT2 n316_s1 (
    .F(n316_6),
    .I0(up[1]),
    .I1(held[4]) 
);
defparam n316_s1.INIT=4'h8;
  LUT2 n315_s1 (
    .F(n315_6),
    .I0(up[1]),
    .I1(held[5]) 
);
defparam n315_s1.INIT=4'h8;
  LUT2 n314_s1 (
    .F(n314_6),
    .I0(up[1]),
    .I1(held[6]) 
);
defparam n314_s1.INIT=4'h8;
  LUT2 n313_s1 (
    .F(n313_6),
    .I0(up[1]),
    .I1(held[7]) 
);
defparam n313_s1.INIT=4'h8;
  LUT2 n312_s1 (
    .F(n312_6),
    .I0(up[1]),
    .I1(held[8]) 
);
defparam n312_s1.INIT=4'h8;
  LUT2 n311_s1 (
    .F(n311_6),
    .I0(up[1]),
    .I1(held[9]) 
);
defparam n311_s1.INIT=4'h8;
  LUT2 n310_s1 (
    .F(n310_6),
    .I0(up[1]),
    .I1(held[10]) 
);
defparam n310_s1.INIT=4'h8;
  LUT2 n309_s1 (
    .F(n309_6),
    .I0(up[1]),
    .I1(held[11]) 
);
defparam n309_s1.INIT=4'h8;
  LUT2 n308_s1 (
    .F(n308_6),
    .I0(up[1]),
    .I1(held[12]) 
);
defparam n308_s1.INIT=4'h8;
  LUT2 n307_s1 (
    .F(n307_6),
    .I0(up[1]),
    .I1(held[13]) 
);
defparam n307_s1.INIT=4'h8;
  LUT2 n306_s1 (
    .F(n306_6),
    .I0(up[1]),
    .I1(held[14]) 
);
defparam n306_s1.INIT=4'h8;
  LUT2 n305_s1 (
    .F(n305_6),
    .I0(up[1]),
    .I1(held[15]) 
);
defparam n305_s1.INIT=4'h8;
  LUT2 n304_s1 (
    .F(n304_6),
    .I0(up[1]),
    .I1(held[16]) 
);
defparam n304_s1.INIT=4'h8;
  LUT2 n303_s1 (
    .F(n303_6),
    .I0(up[1]),
    .I1(held[17]) 
);
defparam n303_s1.INIT=4'h8;
  LUT2 n302_s1 (
    .F(n302_6),
    .I0(up[1]),
    .I1(held[18]) 
);
defparam n302_s1.INIT=4'h8;
  LUT2 n301_s1 (
    .F(n301_6),
    .I0(up[1]),
    .I1(held[19]) 
);
defparam n301_s1.INIT=4'h8;
  LUT2 n300_s1 (
    .F(n300_6),
    .I0(up[1]),
    .I1(held[20]) 
);
defparam n300_s1.INIT=4'h8;
  LUT2 n299_s1 (
    .F(n299_6),
    .I0(up[1]),
    .I1(held[21]) 
);
defparam n299_s1.INIT=4'h8;
  LUT2 n298_s1 (
    .F(n298_6),
    .I0(up[1]),
    .I1(held[22]) 
);
defparam n298_s1.INIT=4'h8;
  LUT2 n297_s1 (
    .F(n297_6),
    .I0(up[1]),
    .I1(held[23]) 
);
defparam n297_s1.INIT=4'h8;
  LUT2 n296_s1 (
    .F(n296_6),
    .I0(up[1]),
    .I1(held[24]) 
);
defparam n296_s1.INIT=4'h8;
  LUT2 n295_s1 (
    .F(n295_6),
    .I0(up[1]),
    .I1(held[25]) 
);
defparam n295_s1.INIT=4'h8;
  LUT2 n294_s1 (
    .F(n294_6),
    .I0(up[1]),
    .I1(held[26]) 
);
defparam n294_s1.INIT=4'h8;
  LUT2 n293_s1 (
    .F(n293_6),
    .I0(up[1]),
    .I1(held[27]) 
);
defparam n293_s1.INIT=4'h8;
  LUT2 n292_s1 (
    .F(n292_6),
    .I0(up[1]),
    .I1(held[28]) 
);
defparam n292_s1.INIT=4'h8;
  LUT2 n291_s1 (
    .F(n291_6),
    .I0(up[1]),
    .I1(held[29]) 
);
defparam n291_s1.INIT=4'h8;
  LUT2 n290_s1 (
    .F(n290_6),
    .I0(up[1]),
    .I1(held[30]) 
);
defparam n290_s1.INIT=4'h8;
  LUT2 n289_s1 (
    .F(n289_6),
    .I0(up[1]),
    .I1(held[31]) 
);
defparam n289_s1.INIT=4'h8;
  LUT2 n288_s1 (
    .F(n288_6),
    .I0(up[1]),
    .I1(held[32]) 
);
defparam n288_s1.INIT=4'h8;
  LUT2 n287_s1 (
    .F(n287_6),
    .I0(up[1]),
    .I1(held[33]) 
);
defparam n287_s1.INIT=4'h8;
  LUT2 n286_s1 (
    .F(n286_6),
    .I0(up[1]),
    .I1(held[34]) 
);
defparam n286_s1.INIT=4'h8;
  LUT2 n285_s1 (
    .F(n285_6),
    .I0(up[1]),
    .I1(held[35]) 
);
defparam n285_s1.INIT=4'h8;
  LUT2 n284_s1 (
    .F(n284_6),
    .I0(up[1]),
    .I1(held[36]) 
);
defparam n284_s1.INIT=4'h8;
  LUT2 n283_s1 (
    .F(n283_6),
    .I0(up[1]),
    .I1(held[37]) 
);
defparam n283_s1.INIT=4'h8;
  LUT2 n282_s1 (
    .F(n282_6),
    .I0(up[1]),
    .I1(held[38]) 
);
defparam n282_s1.INIT=4'h8;
  LUT2 n281_s1 (
    .F(n281_6),
    .I0(up[1]),
    .I1(held[39]) 
);
defparam n281_s1.INIT=4'h8;
  LUT2 n280_s1 (
    .F(n280_6),
    .I0(up[1]),
    .I1(held[40]) 
);
defparam n280_s1.INIT=4'h8;
  LUT2 n279_s1 (
    .F(n279_6),
    .I0(up[1]),
    .I1(held[41]) 
);
defparam n279_s1.INIT=4'h8;
  LUT2 n278_s1 (
    .F(n278_6),
    .I0(up[1]),
    .I1(held[42]) 
);
defparam n278_s1.INIT=4'h8;
  LUT2 n277_s1 (
    .F(n277_6),
    .I0(up[1]),
    .I1(held[43]) 
);
defparam n277_s1.INIT=4'h8;
  LUT2 n276_s1 (
    .F(n276_6),
    .I0(up[1]),
    .I1(held[44]) 
);
defparam n276_s1.INIT=4'h8;
  LUT2 n275_s1 (
    .F(n275_6),
    .I0(up[1]),
    .I1(held[45]) 
);
defparam n275_s1.INIT=4'h8;
  LUT2 n274_s1 (
    .F(n274_6),
    .I0(up[1]),
    .I1(held[46]) 
);
defparam n274_s1.INIT=4'h8;
  LUT2 n273_s1 (
    .F(n273_6),
    .I0(up[1]),
    .I1(held[47]) 
);
defparam n273_s1.INIT=4'h8;
  LUT2 n272_s1 (
    .F(n272_6),
    .I0(up[1]),
    .I1(held[48]) 
);
defparam n272_s1.INIT=4'h8;
  LUT2 n271_s1 (
    .F(n271_6),
    .I0(up[1]),
    .I1(held[49]) 
);
defparam n271_s1.INIT=4'h8;
  LUT2 n270_s1 (
    .F(n270_6),
    .I0(up[1]),
    .I1(held[50]) 
);
defparam n270_s1.INIT=4'h8;
  LUT2 n269_s1 (
    .F(n269_6),
    .I0(up[1]),
    .I1(held[51]) 
);
defparam n269_s1.INIT=4'h8;
  LUT2 n268_s1 (
    .F(n268_6),
    .I0(up[1]),
    .I1(held[52]) 
);
defparam n268_s1.INIT=4'h8;
  LUT2 n267_s1 (
    .F(n267_6),
    .I0(up[1]),
    .I1(held[53]) 
);
defparam n267_s1.INIT=4'h8;
  LUT2 n266_s1 (
    .F(n266_6),
    .I0(up[1]),
    .I1(held[54]) 
);
defparam n266_s1.INIT=4'h8;
  LUT2 n265_s1 (
    .F(n265_6),
    .I0(up[1]),
    .I1(held[55]) 
);
defparam n265_s1.INIT=4'h8;
  LUT2 n264_s1 (
    .F(n264_6),
    .I0(up[1]),
    .I1(held[56]) 
);
defparam n264_s1.INIT=4'h8;
  LUT2 n263_s1 (
    .F(n263_6),
    .I0(up[1]),
    .I1(held[57]) 
);
defparam n263_s1.INIT=4'h8;
  LUT2 n262_s1 (
    .F(n262_6),
    .I0(up[1]),
    .I1(held[58]) 
);
defparam n262_s1.INIT=4'h8;
  LUT2 n261_s1 (
    .F(n261_6),
    .I0(up[1]),
    .I1(held[59]) 
);
defparam n261_s1.INIT=4'h8;
  LUT2 n260_s1 (
    .F(n260_6),
    .I0(up[1]),
    .I1(held[60]) 
);
defparam n260_s1.INIT=4'h8;
  LUT2 n259_s1 (
    .F(n259_6),
    .I0(up[1]),
    .I1(held[61]) 
);
defparam n259_s1.INIT=4'h8;
  LUT2 n258_s1 (
    .F(n258_6),
    .I0(up[1]),
    .I1(held[62]) 
);
defparam n258_s1.INIT=4'h8;
  LUT2 n257_s1 (
    .F(n257_6),
    .I0(up[1]),
    .I1(held[63]) 
);
defparam n257_s1.INIT=4'h8;
  LUT3 n109_s1 (
    .F(n109_6),
    .I0(heartbeat_count[1]),
    .I1(heartbeat_count[0]),
    .I2(up[1]) 
);
defparam n109_s1.INIT=8'h60;
  LUT4 n108_s1 (
    .F(n108_6),
    .I0(heartbeat_count[1]),
    .I1(heartbeat_count[0]),
    .I2(heartbeat_count[2]),
    .I3(up[1]) 
);
defparam n108_s1.INIT=16'h7800;
  LUT2 n107_s1 (
    .F(n107_6),
    .I0(n107_7),
    .I1(up[1]) 
);
defparam n107_s1.INIT=4'h8;
  LUT3 n106_s1 (
    .F(n106_6),
    .I0(heartbeat_count[4]),
    .I1(n106_7),
    .I2(up[1]) 
);
defparam n106_s1.INIT=8'h60;
  LUT4 n105_s1 (
    .F(n105_6),
    .I0(heartbeat_count[4]),
    .I1(n106_7),
    .I2(heartbeat_count[5]),
    .I3(up[1]) 
);
defparam n105_s1.INIT=16'h7800;
  LUT4 n104_s1 (
    .F(n104_6),
    .I0(n106_7),
    .I1(n104_7),
    .I2(heartbeat_count[6]),
    .I3(up[1]) 
);
defparam n104_s1.INIT=16'h7800;
  LUT4 n103_s1 (
    .F(n103_6),
    .I0(n106_7),
    .I1(n103_9),
    .I2(heartbeat_count[7]),
    .I3(up[1]) 
);
defparam n103_s1.INIT=16'h7800;
  LUT4 n101_s1 (
    .F(n101_6),
    .I0(heartbeat_count[8]),
    .I1(n102_7),
    .I2(heartbeat_count[9]),
    .I3(up[1]) 
);
defparam n101_s1.INIT=16'h7800;
  LUT4 n100_s1 (
    .F(n100_6),
    .I0(n102_7),
    .I1(n100_7),
    .I2(heartbeat_count[10]),
    .I3(up[1]) 
);
defparam n100_s1.INIT=16'h7800;
  LUT3 n99_s1 (
    .F(n99_6),
    .I0(heartbeat_count[11]),
    .I1(n99_7),
    .I2(up[1]) 
);
defparam n99_s1.INIT=8'h60;
  LUT4 n98_s1 (
    .F(n98_6),
    .I0(heartbeat_count[11]),
    .I1(n99_7),
    .I2(heartbeat_count[12]),
    .I3(up[1]) 
);
defparam n98_s1.INIT=16'h7800;
  LUT3 n97_s1 (
    .F(n97_6),
    .I0(heartbeat_count[13]),
    .I1(n97_7),
    .I2(up[1]) 
);
defparam n97_s1.INIT=8'h60;
  LUT4 n96_s1 (
    .F(n96_6),
    .I0(heartbeat_count[13]),
    .I1(n97_7),
    .I2(heartbeat_count[14]),
    .I3(up[1]) 
);
defparam n96_s1.INIT=16'h7800;
  LUT4 n95_s1 (
    .F(n95_6),
    .I0(n97_7),
    .I1(n95_7),
    .I2(heartbeat_count[15]),
    .I3(up[1]) 
);
defparam n95_s1.INIT=16'h7800;
  LUT3 n94_s1 (
    .F(n94_6),
    .I0(heartbeat_count[16]),
    .I1(n94_7),
    .I2(up[1]) 
);
defparam n94_s1.INIT=8'h60;
  LUT4 n93_s1 (
    .F(n93_6),
    .I0(heartbeat_count[16]),
    .I1(n94_7),
    .I2(heartbeat_count[17]),
    .I3(up[1]) 
);
defparam n93_s1.INIT=16'h7800;
  LUT4 n92_s1 (
    .F(n92_6),
    .I0(n97_7),
    .I1(n92_7),
    .I2(heartbeat_count[18]),
    .I3(up[1]) 
);
defparam n92_s1.INIT=16'h7800;
  LUT2 n91_s1 (
    .F(n91_6),
    .I0(n91_7),
    .I1(up[1]) 
);
defparam n91_s1.INIT=4'h8;
  LUT4 n89_s1 (
    .F(n89_6),
    .I0(heartbeat_count[20]),
    .I1(n90_7),
    .I2(heartbeat_count[21]),
    .I3(up[1]) 
);
defparam n89_s1.INIT=16'h7800;
  LUT3 n88_s1 (
    .F(n88_6),
    .I0(heartbeat_count[22]),
    .I1(n88_7),
    .I2(up[1]) 
);
defparam n88_s1.INIT=8'h60;
  LUT4 n86_s1 (
    .F(n86_6),
    .I0(heartbeat_count[23]),
    .I1(n87_7),
    .I2(heartbeat_count[24]),
    .I3(up[1]) 
);
defparam n86_s1.INIT=16'h7800;
  LUT4 n85_s1 (
    .F(n85_6),
    .I0(n87_7),
    .I1(n85_7),
    .I2(heartbeat_count[25]),
    .I3(up[1]) 
);
defparam n85_s1.INIT=16'h7800;
  LUT4 n84_s1 (
    .F(n84_6),
    .I0(n84_7),
    .I1(n84_11),
    .I2(heartbeat_count[26]),
    .I3(up[1]) 
);
defparam n84_s1.INIT=16'h7800;
  LUT4 n83_s1 (
    .F(n83_6),
    .I0(n87_7),
    .I1(n83_7),
    .I2(heartbeat_count[27]),
    .I3(up[1]) 
);
defparam n83_s1.INIT=16'h7800;
  LUT3 n82_s1 (
    .F(n82_6),
    .I0(heartbeat_count[28]),
    .I1(n82_7),
    .I2(up[1]) 
);
defparam n82_s1.INIT=8'h60;
  LUT4 n81_s1 (
    .F(n81_6),
    .I0(heartbeat_count[28]),
    .I1(n82_7),
    .I2(heartbeat_count[29]),
    .I3(up[1]) 
);
defparam n81_s1.INIT=16'h7800;
  LUT3 n80_s1 (
    .F(n80_6),
    .I0(heartbeat_count[30]),
    .I1(n80_7),
    .I2(up[1]) 
);
defparam n80_s1.INIT=8'h60;
  LUT4 n79_s1 (
    .F(n79_6),
    .I0(heartbeat_count[30]),
    .I1(n80_7),
    .I2(heartbeat_count[31]),
    .I3(up[1]) 
);
defparam n79_s1.INIT=16'h7800;
  LUT4 n838_s1 (
    .F(n838_6),
    .I0(n838_7),
    .I1(n838_8),
    .I2(n838_9),
    .I3(up[1]) 
);
defparam n838_s1.INIT=16'h7F00;
  LUT4 n837_s1 (
    .F(n837_6),
    .I0(n837_7),
    .I1(n837_8),
    .I2(n837_9),
    .I3(up[1]) 
);
defparam n837_s1.INIT=16'h7F00;
  LUT4 n836_s1 (
    .F(n836_6),
    .I0(n836_7),
    .I1(n836_8),
    .I2(n836_9),
    .I3(up[1]) 
);
defparam n836_s1.INIT=16'h7F00;
  LUT4 n835_s1 (
    .F(n835_6),
    .I0(n835_7),
    .I1(n835_8),
    .I2(n835_9),
    .I3(up[1]) 
);
defparam n835_s1.INIT=16'h7F00;
  LUT4 n834_s1 (
    .F(n834_6),
    .I0(n834_7),
    .I1(n834_8),
    .I2(n834_9),
    .I3(up[1]) 
);
defparam n834_s1.INIT=16'h7F00;
  LUT4 n833_s1 (
    .F(n833_6),
    .I0(n833_7),
    .I1(n833_8),
    .I2(n833_9),
    .I3(up[1]) 
);
defparam n833_s1.INIT=16'h7F00;
  LUT4 n832_s1 (
    .F(n832_6),
    .I0(n832_7),
    .I1(n832_8),
    .I2(n832_9),
    .I3(up[1]) 
);
defparam n832_s1.INIT=16'h7F00;
  LUT4 n831_s1 (
    .F(n831_6),
    .I0(n831_11),
    .I1(n831_8),
    .I2(n831_9),
    .I3(up[1]) 
);
defparam n831_s1.INIT=16'hBF00;
  LUT4 n830_s1 (
    .F(n830_6),
    .I0(n830_11),
    .I1(n830_8),
    .I2(n830_9),
    .I3(up[1]) 
);
defparam n830_s1.INIT=16'hBF00;
  LUT4 n829_s1 (
    .F(n829_6),
    .I0(n829_11),
    .I1(n829_8),
    .I2(n829_9),
    .I3(up[1]) 
);
defparam n829_s1.INIT=16'hBF00;
  LUT4 n828_s1 (
    .F(n828_6),
    .I0(n828_11),
    .I1(n828_8),
    .I2(n828_9),
    .I3(up[1]) 
);
defparam n828_s1.INIT=16'hBF00;
  LUT4 n827_s1 (
    .F(n827_6),
    .I0(n827_11),
    .I1(n827_8),
    .I2(n827_9),
    .I3(up[1]) 
);
defparam n827_s1.INIT=16'hBF00;
  LUT4 n826_s1 (
    .F(n826_6),
    .I0(n826_7),
    .I1(n826_8),
    .I2(n826_9),
    .I3(up[1]) 
);
defparam n826_s1.INIT=16'h7F00;
  LUT4 n825_s1 (
    .F(n825_6),
    .I0(n825_11),
    .I1(n825_8),
    .I2(n825_9),
    .I3(up[1]) 
);
defparam n825_s1.INIT=16'hBF00;
  LUT4 n824_s1 (
    .F(n824_6),
    .I0(n824_7),
    .I1(n824_8),
    .I2(n824_9),
    .I3(up[1]) 
);
defparam n824_s1.INIT=16'h7F00;
  LUT4 n823_s1 (
    .F(n823_6),
    .I0(n823_11),
    .I1(n823_8),
    .I2(n823_9),
    .I3(up[1]) 
);
defparam n823_s1.INIT=16'hBF00;
  LUT4 n822_s1 (
    .F(n822_6),
    .I0(n822_7),
    .I1(n822_8),
    .I2(n822_9),
    .I3(up[1]) 
);
defparam n822_s1.INIT=16'h7F00;
  LUT4 n821_s1 (
    .F(n821_6),
    .I0(n821_7),
    .I1(n821_8),
    .I2(n821_9),
    .I3(up[1]) 
);
defparam n821_s1.INIT=16'h7F00;
  LUT4 n820_s1 (
    .F(n820_6),
    .I0(n820_11),
    .I1(n820_8),
    .I2(n820_9),
    .I3(up[1]) 
);
defparam n820_s1.INIT=16'hBF00;
  LUT4 n819_s1 (
    .F(n819_6),
    .I0(n819_11),
    .I1(n819_8),
    .I2(n819_9),
    .I3(up[1]) 
);
defparam n819_s1.INIT=16'hBF00;
  LUT4 n818_s1 (
    .F(n818_6),
    .I0(n818_11),
    .I1(n818_8),
    .I2(n818_9),
    .I3(up[1]) 
);
defparam n818_s1.INIT=16'hBF00;
  LUT4 n817_s1 (
    .F(n817_6),
    .I0(n817_11),
    .I1(n817_8),
    .I2(n817_9),
    .I3(up[1]) 
);
defparam n817_s1.INIT=16'hBF00;
  LUT4 n816_s1 (
    .F(n816_6),
    .I0(n816_7),
    .I1(n816_8),
    .I2(n816_9),
    .I3(up[1]) 
);
defparam n816_s1.INIT=16'h7F00;
  LUT4 n815_s1 (
    .F(n815_6),
    .I0(n815_11),
    .I1(n815_8),
    .I2(n815_9),
    .I3(up[1]) 
);
defparam n815_s1.INIT=16'hBF00;
  LUT4 n814_s1 (
    .F(n814_6),
    .I0(n814_11),
    .I1(n814_8),
    .I2(n814_9),
    .I3(up[1]) 
);
defparam n814_s1.INIT=16'hBF00;
  LUT4 n813_s1 (
    .F(n813_6),
    .I0(n813_7),
    .I1(n813_8),
    .I2(n813_9),
    .I3(up[1]) 
);
defparam n813_s1.INIT=16'h7F00;
  LUT4 n812_s1 (
    .F(n812_6),
    .I0(n812_7),
    .I1(n812_8),
    .I2(n812_9),
    .I3(up[1]) 
);
defparam n812_s1.INIT=16'h7F00;
  LUT4 n811_s1 (
    .F(n811_6),
    .I0(n811_7),
    .I1(n811_8),
    .I2(n811_9),
    .I3(up[1]) 
);
defparam n811_s1.INIT=16'h7F00;
  LUT4 n810_s1 (
    .F(n810_6),
    .I0(n810_11),
    .I1(n810_8),
    .I2(n810_9),
    .I3(up[1]) 
);
defparam n810_s1.INIT=16'hBF00;
  LUT4 n809_s1 (
    .F(n809_6),
    .I0(n809_11),
    .I1(n809_8),
    .I2(n809_9),
    .I3(up[1]) 
);
defparam n809_s1.INIT=16'hBF00;
  LUT4 n808_s1 (
    .F(n808_6),
    .I0(n808_7),
    .I1(n808_8),
    .I2(n808_9),
    .I3(up[1]) 
);
defparam n808_s1.INIT=16'h7F00;
  LUT4 n807_s1 (
    .F(n807_6),
    .I0(n807_11),
    .I1(n807_8),
    .I2(n807_9),
    .I3(up[1]) 
);
defparam n807_s1.INIT=16'hBF00;
  LUT3 n636_s1 (
    .F(n636_6),
    .I0(n636_13),
    .I1(n636_11),
    .I2(up[1]) 
);
defparam n636_s1.INIT=8'hE0;
  LUT3 n632_s1 (
    .F(n632_6),
    .I0(snap_req),
    .I1(snap_busy_11),
    .I2(up[1]) 
);
defparam n632_s1.INIT=8'h60;
  LUT2 n629_s1 (
    .F(n629_6),
    .I0(up[1]),
    .I1(heartbeat) 
);
defparam n629_s1.INIT=4'h8;
  LUT2 n628_s1 (
    .F(n628_6),
    .I0(up[1]),
    .I1(beat_sync[0]) 
);
defparam n628_s1.INIT=4'h8;
  LUT2 n627_s1 (
    .F(n627_6),
    .I0(up[1]),
    .I1(ready) 
);
defparam n627_s1.INIT=4'h8;
  LUT2 n626_s1 (
    .F(n626_6),
    .I0(up[1]),
    .I1(ready_sync[0]) 
);
defparam n626_s1.INIT=4'h8;
  LUT2 n625_s1 (
    .F(n625_6),
    .I0(up[1]),
    .I1(snap_ack) 
);
defparam n625_s1.INIT=4'h8;
  LUT2 n624_s1 (
    .F(n624_6),
    .I0(up[1]),
    .I1(snap_sync[0]) 
);
defparam n624_s1.INIT=4'h8;
  LUT2 n623_s1 (
    .F(n623_6),
    .I0(up[1]),
    .I1(arm_ack) 
);
defparam n623_s1.INIT=4'h8;
  LUT2 n622_s1 (
    .F(n622_6),
    .I0(up[1]),
    .I1(arm_sync[0]) 
);
defparam n622_s1.INIT=4'h8;
  LUT4 n1490_s1 (
    .F(n1490_4),
    .I0(n1490_5),
    .I1(n525_10),
    .I2(n1490_6),
    .I3(n1490_7) 
);
defparam n1490_s1.INIT=16'h8000;
  LUT4 arm_busy_s4 (
    .F(arm_busy_9),
    .I0(arm_busy),
    .I1(arm_sync[1]),
    .I2(arm_req),
    .I3(up[1]) 
);
defparam arm_busy_s4.INIT=16'h7D00;
  LUT3 settle_1_s4 (
    .F(settle_1_9),
    .I0(snap_sync[1]),
    .I1(snap_req),
    .I2(snap_busy) 
);
defparam settle_1_s4.INIT=8'h90;
  LUT3 n525_s4 (
    .F(n525_9),
    .I0(write_addr[3]),
    .I1(write_addr[4]),
    .I2(write_addr[2]) 
);
defparam n525_s4.INIT=8'h10;
  LUT4 n525_s5 (
    .F(n525_10),
    .I0(write_addr[0]),
    .I1(write_addr[1]),
    .I2(write_addr[5]),
    .I3(write_addr[6]) 
);
defparam n525_s5.INIT=16'h0001;
  LUT3 n525_s6 (
    .F(n525_11),
    .I0(n1490_5),
    .I1(n1490_7),
    .I2(n525_12) 
);
defparam n525_s6.INIT=8'h80;
  LUT4 n519_s2 (
    .F(n519_7),
    .I0(arm_count[2]),
    .I1(arm_count[1]),
    .I2(arm_req),
    .I3(arm_count[3]) 
);
defparam n519_s2.INIT=16'h7F80;
  LUT4 n518_s2 (
    .F(n518_7),
    .I0(arm_count[3]),
    .I1(arm_count[2]),
    .I2(arm_count[1]),
    .I3(arm_req) 
);
defparam n518_s2.INIT=16'h8000;
  LUT3 n516_s2 (
    .F(n516_7),
    .I0(arm_count[5]),
    .I1(arm_count[4]),
    .I2(n518_7) 
);
defparam n516_s2.INIT=8'h80;
  LUT2 n514_s2 (
    .F(n514_7),
    .I0(n518_7),
    .I1(n514_8) 
);
defparam n514_s2.INIT=4'h8;
  LUT2 n512_s2 (
    .F(n512_7),
    .I0(arm_count[9]),
    .I1(arm_count[8]) 
);
defparam n512_s2.INIT=4'h8;
  LUT4 n511_s2 (
    .F(n511_7),
    .I0(arm_count[10]),
    .I1(arm_count[9]),
    .I2(arm_count[8]),
    .I3(n514_7) 
);
defparam n511_s2.INIT=16'h8000;
  LUT4 n509_s2 (
    .F(n509_7),
    .I0(arm_count[11]),
    .I1(n518_7),
    .I2(n514_8),
    .I3(n509_8) 
);
defparam n509_s2.INIT=16'h8000;
  LUT2 n507_s2 (
    .F(n507_7),
    .I0(arm_count[14]),
    .I1(arm_count[13]) 
);
defparam n507_s2.INIT=4'h8;
  LUT4 n506_s2 (
    .F(n506_7),
    .I0(arm_count[15]),
    .I1(arm_count[14]),
    .I2(arm_count[13]),
    .I3(n509_7) 
);
defparam n506_s2.INIT=16'h8000;
  LUT2 n504_s2 (
    .F(n504_7),
    .I0(arm_count[17]),
    .I1(n504_8) 
);
defparam n504_s2.INIT=4'h8;
  LUT4 n503_s2 (
    .F(n503_7),
    .I0(arm_count[18]),
    .I1(n509_7),
    .I2(n504_7),
    .I3(arm_count[19]) 
);
defparam n503_s2.INIT=16'h7F80;
  LUT2 n502_s2 (
    .F(n502_7),
    .I0(n509_7),
    .I1(n502_8) 
);
defparam n502_s2.INIT=4'h8;
  LUT4 n500_s2 (
    .F(n500_7),
    .I0(arm_count[21]),
    .I1(arm_count[20]),
    .I2(n509_7),
    .I3(n502_8) 
);
defparam n500_s2.INIT=16'h8000;
  LUT2 n499_s2 (
    .F(n499_7),
    .I0(n509_7),
    .I1(n499_8) 
);
defparam n499_s2.INIT=4'h8;
  LUT2 n497_s2 (
    .F(n497_7),
    .I0(arm_count[24]),
    .I1(arm_count[23]) 
);
defparam n497_s2.INIT=4'h8;
  LUT4 n495_s2 (
    .F(n495_7),
    .I0(arm_count[26]),
    .I1(arm_count[25]),
    .I2(arm_count[24]),
    .I3(arm_count[23]) 
);
defparam n495_s2.INIT=16'h8000;
  LUT4 n494_s2 (
    .F(n494_7),
    .I0(arm_count[27]),
    .I1(n509_7),
    .I2(n499_8),
    .I3(n495_7) 
);
defparam n494_s2.INIT=16'h8000;
  LUT4 n492_s2 (
    .F(n492_7),
    .I0(n509_7),
    .I1(n499_8),
    .I2(n492_8),
    .I3(arm_count[30]) 
);
defparam n492_s2.INIT=16'h7F80;
  LUT4 n491_s2 (
    .F(n491_7),
    .I0(n509_7),
    .I1(n499_8),
    .I2(n495_7),
    .I3(n491_8) 
);
defparam n491_s2.INIT=16'h8000;
  LUT4 n349_s2 (
    .F(n349_7),
    .I0(sequence_id[2]),
    .I1(sequence_id[1]),
    .I2(sequence_id[0]),
    .I3(sequence_id[3]) 
);
defparam n349_s2.INIT=16'h7F80;
  LUT4 n348_s2 (
    .F(n348_7),
    .I0(sequence_id[3]),
    .I1(sequence_id[2]),
    .I2(sequence_id[1]),
    .I3(sequence_id[0]) 
);
defparam n348_s2.INIT=16'h8000;
  LUT2 n346_s2 (
    .F(n346_7),
    .I0(sequence_id[5]),
    .I1(sequence_id[4]) 
);
defparam n346_s2.INIT=4'h8;
  LUT2 n344_s2 (
    .F(n344_7),
    .I0(n348_7),
    .I1(n344_8) 
);
defparam n344_s2.INIT=4'h8;
  LUT2 n342_s2 (
    .F(n342_7),
    .I0(sequence_id[9]),
    .I1(sequence_id[8]) 
);
defparam n342_s2.INIT=4'h8;
  LUT4 n341_s2 (
    .F(n341_7),
    .I0(sequence_id[10]),
    .I1(sequence_id[9]),
    .I2(sequence_id[8]),
    .I3(n344_7) 
);
defparam n341_s2.INIT=16'h8000;
  LUT4 n339_s2 (
    .F(n339_7),
    .I0(sequence_id[11]),
    .I1(n348_7),
    .I2(n344_8),
    .I3(n339_8) 
);
defparam n339_s2.INIT=16'h8000;
  LUT2 n337_s2 (
    .F(n337_7),
    .I0(sequence_id[14]),
    .I1(sequence_id[13]) 
);
defparam n337_s2.INIT=4'h8;
  LUT4 n336_s2 (
    .F(n336_7),
    .I0(sequence_id[15]),
    .I1(sequence_id[14]),
    .I2(sequence_id[13]),
    .I3(n339_7) 
);
defparam n336_s2.INIT=16'h8000;
  LUT3 n334_s2 (
    .F(n334_7),
    .I0(sequence_id[17]),
    .I1(n339_7),
    .I2(n334_8) 
);
defparam n334_s2.INIT=8'h80;
  LUT2 n332_s2 (
    .F(n332_7),
    .I0(n339_7),
    .I1(n332_8) 
);
defparam n332_s2.INIT=4'h8;
  LUT4 n330_s2 (
    .F(n330_7),
    .I0(sequence_id[21]),
    .I1(sequence_id[20]),
    .I2(n339_7),
    .I3(n332_8) 
);
defparam n330_s2.INIT=16'h8000;
  LUT2 n329_s2 (
    .F(n329_7),
    .I0(n339_7),
    .I1(n322_7) 
);
defparam n329_s2.INIT=4'h8;
  LUT4 n327_s2 (
    .F(n327_7),
    .I0(sequence_id[24]),
    .I1(sequence_id[23]),
    .I2(n339_7),
    .I3(n322_7) 
);
defparam n327_s2.INIT=16'h8000;
  LUT4 n326_s2 (
    .F(n326_7),
    .I0(n339_7),
    .I1(n322_7),
    .I2(n326_8),
    .I3(sequence_id[26]) 
);
defparam n326_s2.INIT=16'h7F80;
  LUT3 n324_s2 (
    .F(n324_7),
    .I0(n339_7),
    .I1(n322_7),
    .I2(n324_8) 
);
defparam n324_s2.INIT=8'h80;
  LUT4 n322_s2 (
    .F(n322_7),
    .I0(sequence_id[22]),
    .I1(sequence_id[17]),
    .I2(n334_8),
    .I3(n322_9) 
);
defparam n322_s2.INIT=16'h8000;
  LUT4 n322_s3 (
    .F(n322_8),
    .I0(sequence_id[29]),
    .I1(sequence_id[28]),
    .I2(n339_7),
    .I3(n324_8) 
);
defparam n322_s3.INIT=16'h8000;
  LUT4 n321_s2 (
    .F(n321_7),
    .I0(sequence_id[30]),
    .I1(sequence_id[29]),
    .I2(sequence_id[28]),
    .I3(n324_8) 
);
defparam n321_s2.INIT=16'h8000;
  LUT4 n107_s2 (
    .F(n107_7),
    .I0(heartbeat_count[2]),
    .I1(heartbeat_count[1]),
    .I2(heartbeat_count[0]),
    .I3(heartbeat_count[3]) 
);
defparam n107_s2.INIT=16'h7F80;
  LUT4 n106_s2 (
    .F(n106_7),
    .I0(heartbeat_count[3]),
    .I1(heartbeat_count[2]),
    .I2(heartbeat_count[1]),
    .I3(heartbeat_count[0]) 
);
defparam n106_s2.INIT=16'h8000;
  LUT2 n104_s2 (
    .F(n104_7),
    .I0(heartbeat_count[5]),
    .I1(heartbeat_count[4]) 
);
defparam n104_s2.INIT=4'h8;
  LUT2 n102_s2 (
    .F(n102_7),
    .I0(n106_7),
    .I1(n102_8) 
);
defparam n102_s2.INIT=4'h8;
  LUT2 n100_s2 (
    .F(n100_7),
    .I0(heartbeat_count[9]),
    .I1(heartbeat_count[8]) 
);
defparam n100_s2.INIT=4'h8;
  LUT4 n99_s2 (
    .F(n99_7),
    .I0(heartbeat_count[10]),
    .I1(heartbeat_count[9]),
    .I2(heartbeat_count[8]),
    .I3(n102_7) 
);
defparam n99_s2.INIT=16'h8000;
  LUT4 n97_s2 (
    .F(n97_7),
    .I0(heartbeat_count[11]),
    .I1(n106_7),
    .I2(n102_8),
    .I3(n97_8) 
);
defparam n97_s2.INIT=16'h8000;
  LUT2 n95_s2 (
    .F(n95_7),
    .I0(heartbeat_count[14]),
    .I1(heartbeat_count[13]) 
);
defparam n95_s2.INIT=4'h8;
  LUT4 n94_s2 (
    .F(n94_7),
    .I0(heartbeat_count[15]),
    .I1(heartbeat_count[14]),
    .I2(heartbeat_count[13]),
    .I3(n97_7) 
);
defparam n94_s2.INIT=16'h8000;
  LUT2 n92_s2 (
    .F(n92_7),
    .I0(heartbeat_count[17]),
    .I1(n92_8) 
);
defparam n92_s2.INIT=4'h8;
  LUT4 n91_s2 (
    .F(n91_7),
    .I0(heartbeat_count[18]),
    .I1(n97_7),
    .I2(n92_7),
    .I3(heartbeat_count[19]) 
);
defparam n91_s2.INIT=16'h7F80;
  LUT2 n90_s2 (
    .F(n90_7),
    .I0(n97_7),
    .I1(n90_8) 
);
defparam n90_s2.INIT=4'h8;
  LUT4 n88_s2 (
    .F(n88_7),
    .I0(heartbeat_count[21]),
    .I1(heartbeat_count[20]),
    .I2(n97_7),
    .I3(n90_8) 
);
defparam n88_s2.INIT=16'h8000;
  LUT2 n87_s2 (
    .F(n87_7),
    .I0(n97_7),
    .I1(n84_7) 
);
defparam n87_s2.INIT=4'h8;
  LUT2 n85_s2 (
    .F(n85_7),
    .I0(heartbeat_count[24]),
    .I1(heartbeat_count[23]) 
);
defparam n85_s2.INIT=4'h8;
  LUT4 n84_s2 (
    .F(n84_7),
    .I0(heartbeat_count[22]),
    .I1(heartbeat_count[17]),
    .I2(n92_8),
    .I3(n84_9) 
);
defparam n84_s2.INIT=16'h8000;
  LUT4 n83_s2 (
    .F(n83_7),
    .I0(heartbeat_count[26]),
    .I1(heartbeat_count[25]),
    .I2(heartbeat_count[24]),
    .I3(heartbeat_count[23]) 
);
defparam n83_s2.INIT=16'h8000;
  LUT4 n82_s2 (
    .F(n82_7),
    .I0(heartbeat_count[27]),
    .I1(n97_7),
    .I2(n84_7),
    .I3(n83_7) 
);
defparam n82_s2.INIT=16'h8000;
  LUT3 n80_s2 (
    .F(n80_7),
    .I0(n97_7),
    .I1(n84_7),
    .I2(n80_8) 
);
defparam n80_s2.INIT=8'h80;
  LUT4 n838_s2 (
    .F(n838_7),
    .I0(n838_10),
    .I1(sequence_id[0]),
    .I2(arm_busy),
    .I3(n838_11) 
);
defparam n838_s2.INIT=16'h0777;
  LUT4 n838_s3 (
    .F(n838_8),
    .I0(n838_12),
    .I1(shadow[0]),
    .I2(heartbeat_count[0]),
    .I3(n838_13) 
);
defparam n838_s3.INIT=16'h0777;
  LUT3 n838_s4 (
    .F(n838_9),
    .I0(n838_14),
    .I1(shadow[32]),
    .I2(n838_15) 
);
defparam n838_s4.INIT=8'h07;
  LUT4 n837_s2 (
    .F(n837_7),
    .I0(shadow[1]),
    .I1(n838_12),
    .I2(snap_busy),
    .I3(n838_11) 
);
defparam n837_s2.INIT=16'h0777;
  LUT4 n837_s3 (
    .F(n837_8),
    .I0(shadow[33]),
    .I1(n838_14),
    .I2(heartbeat_count[1]),
    .I3(n838_13) 
);
defparam n837_s3.INIT=16'h0777;
  LUT4 n837_s4 (
    .F(n837_9),
    .I0(arm_count[1]),
    .I1(n837_10),
    .I2(sequence_id[1]),
    .I3(n838_10) 
);
defparam n837_s4.INIT=16'h0777;
  LUT4 n836_s2 (
    .F(n836_7),
    .I0(shadow[34]),
    .I1(n838_14),
    .I2(ready_sync[1]),
    .I3(n838_11) 
);
defparam n836_s2.INIT=16'h0777;
  LUT4 n836_s3 (
    .F(n836_8),
    .I0(n838_10),
    .I1(sequence_id[2]),
    .I2(heartbeat_count[2]),
    .I3(n838_13) 
);
defparam n836_s3.INIT=16'h0777;
  LUT4 n836_s4 (
    .F(n836_9),
    .I0(arm_count[2]),
    .I1(n837_10),
    .I2(shadow[2]),
    .I3(n838_12) 
);
defparam n836_s4.INIT=16'h0777;
  LUT4 n835_s2 (
    .F(n835_7),
    .I0(n838_11),
    .I1(snapshot_valid),
    .I2(shadow[35]),
    .I3(n838_14) 
);
defparam n835_s2.INIT=16'h0777;
  LUT4 n835_s3 (
    .F(n835_8),
    .I0(n838_10),
    .I1(sequence_id[3]),
    .I2(heartbeat_count[3]),
    .I3(n838_13) 
);
defparam n835_s3.INIT=16'h0777;
  LUT4 n835_s4 (
    .F(n835_9),
    .I0(arm_count[3]),
    .I1(n837_10),
    .I2(shadow[3]),
    .I3(n838_12) 
);
defparam n835_s4.INIT=16'h0777;
  LUT4 n834_s2 (
    .F(n834_7),
    .I0(n838_12),
    .I1(shadow[4]),
    .I2(n834_10),
    .I3(n834_11) 
);
defparam n834_s2.INIT=16'h0007;
  LUT4 n834_s3 (
    .F(n834_8),
    .I0(n838_10),
    .I1(sequence_id[4]),
    .I2(shadow[36]),
    .I3(n838_14) 
);
defparam n834_s3.INIT=16'h0777;
  LUT4 n834_s4 (
    .F(n834_9),
    .I0(arm_count[4]),
    .I1(n837_10),
    .I2(heartbeat_count[4]),
    .I3(n838_13) 
);
defparam n834_s4.INIT=16'h0777;
  LUT2 n833_s2 (
    .F(n833_7),
    .I0(n833_10),
    .I1(n833_11) 
);
defparam n833_s2.INIT=4'h1;
  LUT4 n833_s3 (
    .F(n833_8),
    .I0(n838_12),
    .I1(shadow[5]),
    .I2(heartbeat_count[5]),
    .I3(n838_13) 
);
defparam n833_s3.INIT=16'h0777;
  LUT4 n833_s4 (
    .F(n833_9),
    .I0(n838_10),
    .I1(sequence_id[5]),
    .I2(shadow[37]),
    .I3(n838_14) 
);
defparam n833_s4.INIT=16'h0777;
  LUT4 n832_s2 (
    .F(n832_7),
    .I0(n838_12),
    .I1(shadow[6]),
    .I2(heartbeat_count[6]),
    .I3(n838_13) 
);
defparam n832_s2.INIT=16'h0777;
  LUT4 n832_s3 (
    .F(n832_8),
    .I0(shadow[38]),
    .I1(n838_14),
    .I2(rejected),
    .I3(n838_11) 
);
defparam n832_s3.INIT=16'h0777;
  LUT4 n832_s4 (
    .F(n832_9),
    .I0(arm_count[6]),
    .I1(n837_10),
    .I2(sequence_id[6]),
    .I3(n838_10) 
);
defparam n832_s4.INIT=16'h0777;
  LUT4 n831_s3 (
    .F(n831_8),
    .I0(n838_12),
    .I1(shadow[7]),
    .I2(shadow[39]),
    .I3(n838_14) 
);
defparam n831_s3.INIT=16'h0777;
  LUT4 n831_s4 (
    .F(n831_9),
    .I0(arm_count[7]),
    .I1(n837_10),
    .I2(sequence_id[7]),
    .I3(n838_10) 
);
defparam n831_s4.INIT=16'h0777;
  LUT4 n830_s3 (
    .F(n830_8),
    .I0(arm_count[8]),
    .I1(n837_10),
    .I2(sequence_id[8]),
    .I3(n838_10) 
);
defparam n830_s3.INIT=16'h0777;
  LUT4 n830_s4 (
    .F(n830_9),
    .I0(n838_12),
    .I1(shadow[8]),
    .I2(heartbeat_count[8]),
    .I3(n838_13) 
);
defparam n830_s4.INIT=16'h0777;
  LUT4 n829_s3 (
    .F(n829_8),
    .I0(arm_count[9]),
    .I1(n837_10),
    .I2(sequence_id[9]),
    .I3(n838_10) 
);
defparam n829_s3.INIT=16'h0777;
  LUT4 n829_s4 (
    .F(n829_9),
    .I0(n838_12),
    .I1(shadow[9]),
    .I2(heartbeat_count[9]),
    .I3(n838_13) 
);
defparam n829_s4.INIT=16'h0777;
  LUT4 n828_s3 (
    .F(n828_8),
    .I0(arm_count[10]),
    .I1(n837_10),
    .I2(sequence_id[10]),
    .I3(n838_10) 
);
defparam n828_s3.INIT=16'h0777;
  LUT4 n828_s4 (
    .F(n828_9),
    .I0(n838_12),
    .I1(shadow[10]),
    .I2(heartbeat_count[10]),
    .I3(n838_13) 
);
defparam n828_s4.INIT=16'h0777;
  LUT4 n827_s3 (
    .F(n827_8),
    .I0(arm_count[11]),
    .I1(n837_10),
    .I2(sequence_id[11]),
    .I3(n838_10) 
);
defparam n827_s3.INIT=16'h0777;
  LUT4 n827_s4 (
    .F(n827_9),
    .I0(n838_12),
    .I1(shadow[11]),
    .I2(heartbeat_count[11]),
    .I3(n838_13) 
);
defparam n827_s4.INIT=16'h0777;
  LUT4 n826_s2 (
    .F(n826_7),
    .I0(n838_12),
    .I1(shadow[12]),
    .I2(heartbeat_count[12]),
    .I3(n838_13) 
);
defparam n826_s2.INIT=16'h0777;
  LUT4 n826_s3 (
    .F(n826_8),
    .I0(arm_count[12]),
    .I1(n837_10),
    .I2(sequence_id[12]),
    .I3(n838_10) 
);
defparam n826_s3.INIT=16'h0777;
  LUT3 n826_s4 (
    .F(n826_9),
    .I0(n838_14),
    .I1(shadow[44]),
    .I2(n834_10) 
);
defparam n826_s4.INIT=8'h07;
  LUT4 n825_s3 (
    .F(n825_8),
    .I0(arm_count[13]),
    .I1(n837_10),
    .I2(sequence_id[13]),
    .I3(n838_10) 
);
defparam n825_s3.INIT=16'h0777;
  LUT4 n825_s4 (
    .F(n825_9),
    .I0(n838_12),
    .I1(shadow[13]),
    .I2(heartbeat_count[13]),
    .I3(n838_13) 
);
defparam n825_s4.INIT=16'h0777;
  LUT4 n824_s2 (
    .F(n824_7),
    .I0(arm_count[14]),
    .I1(n837_10),
    .I2(sequence_id[14]),
    .I3(n838_10) 
);
defparam n824_s2.INIT=16'h0777;
  LUT4 n824_s3 (
    .F(n824_8),
    .I0(shadow[46]),
    .I1(n838_14),
    .I2(heartbeat_count[14]),
    .I3(n838_13) 
);
defparam n824_s3.INIT=16'h0777;
  LUT3 n824_s4 (
    .F(n824_9),
    .I0(n838_12),
    .I1(shadow[14]),
    .I2(n834_10) 
);
defparam n824_s4.INIT=8'h07;
  LUT4 n823_s3 (
    .F(n823_8),
    .I0(n838_12),
    .I1(shadow[15]),
    .I2(heartbeat_count[15]),
    .I3(n838_13) 
);
defparam n823_s3.INIT=16'h0777;
  LUT4 n823_s4 (
    .F(n823_9),
    .I0(n838_10),
    .I1(sequence_id[15]),
    .I2(shadow[47]),
    .I3(n838_14) 
);
defparam n823_s4.INIT=16'h0777;
  LUT4 n822_s2 (
    .F(n822_7),
    .I0(n838_12),
    .I1(shadow[16]),
    .I2(heartbeat_count[16]),
    .I3(n838_13) 
);
defparam n822_s2.INIT=16'h0777;
  LUT4 n822_s3 (
    .F(n822_8),
    .I0(arm_count[16]),
    .I1(n837_10),
    .I2(sequence_id[16]),
    .I3(n838_10) 
);
defparam n822_s3.INIT=16'h0777;
  LUT3 n822_s4 (
    .F(n822_9),
    .I0(n838_14),
    .I1(shadow[48]),
    .I2(n834_10) 
);
defparam n822_s4.INIT=8'h07;
  LUT4 n821_s2 (
    .F(n821_7),
    .I0(n838_12),
    .I1(shadow[17]),
    .I2(heartbeat_count[17]),
    .I3(n838_13) 
);
defparam n821_s2.INIT=16'h0777;
  LUT4 n821_s3 (
    .F(n821_8),
    .I0(arm_count[17]),
    .I1(n837_10),
    .I2(sequence_id[17]),
    .I3(n838_10) 
);
defparam n821_s3.INIT=16'h0777;
  LUT3 n821_s4 (
    .F(n821_9),
    .I0(n838_14),
    .I1(shadow[49]),
    .I2(n834_10) 
);
defparam n821_s4.INIT=8'h07;
  LUT4 n820_s3 (
    .F(n820_8),
    .I0(arm_count[18]),
    .I1(n837_10),
    .I2(sequence_id[18]),
    .I3(n838_10) 
);
defparam n820_s3.INIT=16'h0777;
  LUT4 n820_s4 (
    .F(n820_9),
    .I0(n838_12),
    .I1(shadow[18]),
    .I2(shadow[50]),
    .I3(n838_14) 
);
defparam n820_s4.INIT=16'h0777;
  LUT4 n819_s3 (
    .F(n819_8),
    .I0(arm_count[19]),
    .I1(n837_10),
    .I2(sequence_id[19]),
    .I3(n838_10) 
);
defparam n819_s3.INIT=16'h0777;
  LUT4 n819_s4 (
    .F(n819_9),
    .I0(n838_12),
    .I1(shadow[19]),
    .I2(heartbeat_count[19]),
    .I3(n838_13) 
);
defparam n819_s4.INIT=16'h0777;
  LUT4 n818_s3 (
    .F(n818_8),
    .I0(n838_12),
    .I1(shadow[20]),
    .I2(heartbeat_count[20]),
    .I3(n838_13) 
);
defparam n818_s3.INIT=16'h0777;
  LUT4 n818_s4 (
    .F(n818_9),
    .I0(n838_10),
    .I1(sequence_id[20]),
    .I2(shadow[52]),
    .I3(n838_14) 
);
defparam n818_s4.INIT=16'h0777;
  LUT4 n817_s3 (
    .F(n817_8),
    .I0(arm_count[21]),
    .I1(n837_10),
    .I2(sequence_id[21]),
    .I3(n838_10) 
);
defparam n817_s3.INIT=16'h0777;
  LUT4 n817_s4 (
    .F(n817_9),
    .I0(n838_12),
    .I1(shadow[21]),
    .I2(heartbeat_count[21]),
    .I3(n838_13) 
);
defparam n817_s4.INIT=16'h0777;
  LUT4 n816_s2 (
    .F(n816_7),
    .I0(n838_12),
    .I1(shadow[22]),
    .I2(heartbeat_count[22]),
    .I3(n838_13) 
);
defparam n816_s2.INIT=16'h0777;
  LUT4 n816_s3 (
    .F(n816_8),
    .I0(arm_count[22]),
    .I1(n837_10),
    .I2(sequence_id[22]),
    .I3(n838_10) 
);
defparam n816_s3.INIT=16'h0777;
  LUT3 n816_s4 (
    .F(n816_9),
    .I0(n838_14),
    .I1(shadow[54]),
    .I2(n834_10) 
);
defparam n816_s4.INIT=8'h07;
  LUT4 n815_s3 (
    .F(n815_8),
    .I0(n838_12),
    .I1(shadow[23]),
    .I2(heartbeat_count[23]),
    .I3(n838_13) 
);
defparam n815_s3.INIT=16'h0777;
  LUT4 n815_s4 (
    .F(n815_9),
    .I0(n838_10),
    .I1(sequence_id[23]),
    .I2(shadow[55]),
    .I3(n838_14) 
);
defparam n815_s4.INIT=16'h0777;
  LUT4 n814_s3 (
    .F(n814_8),
    .I0(arm_count[24]),
    .I1(n837_10),
    .I2(sequence_id[24]),
    .I3(n838_10) 
);
defparam n814_s3.INIT=16'h0777;
  LUT4 n814_s4 (
    .F(n814_9),
    .I0(n838_12),
    .I1(shadow[24]),
    .I2(shadow[56]),
    .I3(n838_14) 
);
defparam n814_s4.INIT=16'h0777;
  LUT3 n813_s2 (
    .F(n813_7),
    .I0(n838_12),
    .I1(shadow[25]),
    .I2(n834_10) 
);
defparam n813_s2.INIT=8'h07;
  LUT4 n813_s3 (
    .F(n813_8),
    .I0(shadow[57]),
    .I1(n838_14),
    .I2(heartbeat_count[25]),
    .I3(n838_13) 
);
defparam n813_s3.INIT=16'h0777;
  LUT4 n813_s4 (
    .F(n813_9),
    .I0(arm_count[25]),
    .I1(n837_10),
    .I2(sequence_id[25]),
    .I3(n838_10) 
);
defparam n813_s4.INIT=16'h0777;
  LUT4 n812_s2 (
    .F(n812_7),
    .I0(n838_12),
    .I1(shadow[26]),
    .I2(heartbeat_count[26]),
    .I3(n838_13) 
);
defparam n812_s2.INIT=16'h0777;
  LUT4 n812_s3 (
    .F(n812_8),
    .I0(arm_count[26]),
    .I1(n837_10),
    .I2(sequence_id[26]),
    .I3(n838_10) 
);
defparam n812_s3.INIT=16'h0777;
  LUT3 n812_s4 (
    .F(n812_9),
    .I0(n838_14),
    .I1(shadow[58]),
    .I2(n834_10) 
);
defparam n812_s4.INIT=8'h07;
  LUT3 n811_s2 (
    .F(n811_7),
    .I0(n838_14),
    .I1(shadow[59]),
    .I2(n834_10) 
);
defparam n811_s2.INIT=8'h07;
  LUT4 n811_s3 (
    .F(n811_8),
    .I0(arm_count[27]),
    .I1(n837_10),
    .I2(shadow[27]),
    .I3(n838_12) 
);
defparam n811_s3.INIT=16'h0777;
  LUT4 n811_s4 (
    .F(n811_9),
    .I0(n838_10),
    .I1(sequence_id[27]),
    .I2(heartbeat_count[27]),
    .I3(n838_13) 
);
defparam n811_s4.INIT=16'h0777;
  LUT4 n810_s3 (
    .F(n810_8),
    .I0(n838_12),
    .I1(shadow[28]),
    .I2(heartbeat_count[28]),
    .I3(n838_13) 
);
defparam n810_s3.INIT=16'h0777;
  LUT4 n810_s4 (
    .F(n810_9),
    .I0(n838_10),
    .I1(sequence_id[28]),
    .I2(shadow[60]),
    .I3(n838_14) 
);
defparam n810_s4.INIT=16'h0777;
  LUT4 n809_s3 (
    .F(n809_8),
    .I0(n838_12),
    .I1(shadow[29]),
    .I2(heartbeat_count[29]),
    .I3(n838_13) 
);
defparam n809_s3.INIT=16'h0777;
  LUT4 n809_s4 (
    .F(n809_9),
    .I0(n838_10),
    .I1(sequence_id[29]),
    .I2(shadow[61]),
    .I3(n838_14) 
);
defparam n809_s4.INIT=16'h0777;
  LUT4 n808_s2 (
    .F(n808_7),
    .I0(arm_count[30]),
    .I1(n837_10),
    .I2(sequence_id[30]),
    .I3(n838_10) 
);
defparam n808_s2.INIT=16'h0777;
  LUT4 n808_s3 (
    .F(n808_8),
    .I0(n838_12),
    .I1(shadow[30]),
    .I2(heartbeat_count[30]),
    .I3(n838_13) 
);
defparam n808_s3.INIT=16'h0777;
  LUT3 n808_s4 (
    .F(n808_9),
    .I0(n838_14),
    .I1(shadow[62]),
    .I2(n834_10) 
);
defparam n808_s4.INIT=8'h07;
  LUT4 n807_s3 (
    .F(n807_8),
    .I0(arm_count[31]),
    .I1(n837_10),
    .I2(sequence_id[31]),
    .I3(n838_10) 
);
defparam n807_s3.INIT=16'h0777;
  LUT4 n807_s4 (
    .F(n807_9),
    .I0(n838_12),
    .I1(shadow[31]),
    .I2(shadow[63]),
    .I3(n838_14) 
);
defparam n807_s4.INIT=16'h0777;
  LUT3 n1490_s2 (
    .F(n1490_5),
    .I0(arm_busy),
    .I1(snap_busy),
    .I2(ready_sync[1]) 
);
defparam n1490_s2.INIT=8'h10;
  LUT4 n1490_s3 (
    .F(n1490_6),
    .I0(legacy_wait),
    .I1(write_pending),
    .I2(write_bit),
    .I3(write_addr[7]) 
);
defparam n1490_s3.INIT=16'h4000;
  LUT3 n1490_s4 (
    .F(n1490_7),
    .I0(write_addr[4]),
    .I1(write_addr[2]),
    .I2(write_addr[3]) 
);
defparam n1490_s4.INIT=8'h14;
  LUT4 n525_s7 (
    .F(n525_12),
    .I0(legacy_wait),
    .I1(write_pending),
    .I2(write_bit),
    .I3(up[1]) 
);
defparam n525_s7.INIT=16'h4000;
  LUT4 n514_s3 (
    .F(n514_8),
    .I0(arm_count[7]),
    .I1(arm_count[6]),
    .I2(arm_count[5]),
    .I3(arm_count[4]) 
);
defparam n514_s3.INIT=16'h8000;
  LUT4 n509_s3 (
    .F(n509_8),
    .I0(arm_count[12]),
    .I1(arm_count[10]),
    .I2(arm_count[9]),
    .I3(arm_count[8]) 
);
defparam n509_s3.INIT=16'h8000;
  LUT4 n504_s3 (
    .F(n504_8),
    .I0(arm_count[16]),
    .I1(arm_count[15]),
    .I2(arm_count[14]),
    .I3(arm_count[13]) 
);
defparam n504_s3.INIT=16'h8000;
  LUT4 n502_s3 (
    .F(n502_8),
    .I0(arm_count[19]),
    .I1(arm_count[18]),
    .I2(arm_count[17]),
    .I3(n504_8) 
);
defparam n502_s3.INIT=16'h8000;
  LUT4 n499_s3 (
    .F(n499_8),
    .I0(arm_count[22]),
    .I1(arm_count[17]),
    .I2(n504_8),
    .I3(n499_9) 
);
defparam n499_s3.INIT=16'h8000;
  LUT4 n492_s3 (
    .F(n492_8),
    .I0(arm_count[29]),
    .I1(arm_count[28]),
    .I2(arm_count[27]),
    .I3(n495_7) 
);
defparam n492_s3.INIT=16'h8000;
  LUT4 n491_s3 (
    .F(n491_8),
    .I0(arm_count[30]),
    .I1(arm_count[29]),
    .I2(arm_count[28]),
    .I3(arm_count[27]) 
);
defparam n491_s3.INIT=16'h8000;
  LUT4 n344_s3 (
    .F(n344_8),
    .I0(sequence_id[7]),
    .I1(sequence_id[6]),
    .I2(sequence_id[5]),
    .I3(sequence_id[4]) 
);
defparam n344_s3.INIT=16'h8000;
  LUT4 n339_s3 (
    .F(n339_8),
    .I0(sequence_id[12]),
    .I1(sequence_id[10]),
    .I2(sequence_id[9]),
    .I3(sequence_id[8]) 
);
defparam n339_s3.INIT=16'h8000;
  LUT4 n334_s3 (
    .F(n334_8),
    .I0(sequence_id[16]),
    .I1(sequence_id[15]),
    .I2(sequence_id[14]),
    .I3(sequence_id[13]) 
);
defparam n334_s3.INIT=16'h8000;
  LUT4 n332_s3 (
    .F(n332_8),
    .I0(sequence_id[19]),
    .I1(sequence_id[18]),
    .I2(sequence_id[17]),
    .I3(n334_8) 
);
defparam n332_s3.INIT=16'h8000;
  LUT3 n326_s3 (
    .F(n326_8),
    .I0(sequence_id[25]),
    .I1(sequence_id[24]),
    .I2(sequence_id[23]) 
);
defparam n326_s3.INIT=8'h80;
  LUT3 n324_s3 (
    .F(n324_8),
    .I0(sequence_id[27]),
    .I1(sequence_id[26]),
    .I2(n326_8) 
);
defparam n324_s3.INIT=8'h80;
  LUT4 n322_s4 (
    .F(n322_9),
    .I0(sequence_id[21]),
    .I1(sequence_id[20]),
    .I2(sequence_id[19]),
    .I3(sequence_id[18]) 
);
defparam n322_s4.INIT=16'h8000;
  LUT4 n102_s3 (
    .F(n102_8),
    .I0(heartbeat_count[7]),
    .I1(heartbeat_count[6]),
    .I2(heartbeat_count[5]),
    .I3(heartbeat_count[4]) 
);
defparam n102_s3.INIT=16'h8000;
  LUT4 n97_s3 (
    .F(n97_8),
    .I0(heartbeat_count[12]),
    .I1(heartbeat_count[10]),
    .I2(heartbeat_count[9]),
    .I3(heartbeat_count[8]) 
);
defparam n97_s3.INIT=16'h8000;
  LUT4 n92_s3 (
    .F(n92_8),
    .I0(heartbeat_count[16]),
    .I1(heartbeat_count[15]),
    .I2(heartbeat_count[14]),
    .I3(heartbeat_count[13]) 
);
defparam n92_s3.INIT=16'h8000;
  LUT4 n90_s3 (
    .F(n90_8),
    .I0(heartbeat_count[19]),
    .I1(heartbeat_count[18]),
    .I2(heartbeat_count[17]),
    .I3(n92_8) 
);
defparam n90_s3.INIT=16'h8000;
  LUT4 n84_s4 (
    .F(n84_9),
    .I0(heartbeat_count[21]),
    .I1(heartbeat_count[20]),
    .I2(heartbeat_count[19]),
    .I3(heartbeat_count[18]) 
);
defparam n84_s4.INIT=16'h8000;
  LUT4 n80_s3 (
    .F(n80_8),
    .I0(heartbeat_count[29]),
    .I1(heartbeat_count[28]),
    .I2(heartbeat_count[27]),
    .I3(n83_7) 
);
defparam n80_s3.INIT=16'h8000;
  LUT3 n838_s5 (
    .F(n838_10),
    .I0(read_latched[3]),
    .I1(n838_16),
    .I2(n838_17) 
);
defparam n838_s5.INIT=8'h80;
  LUT3 n838_s6 (
    .F(n838_11),
    .I0(read_latched[3]),
    .I1(n838_16),
    .I2(n838_17) 
);
defparam n838_s6.INIT=8'h40;
  LUT3 n838_s7 (
    .F(n838_12),
    .I0(read_latched[3]),
    .I1(n838_18),
    .I2(n838_19) 
);
defparam n838_s7.INIT=8'h40;
  LUT3 n838_s8 (
    .F(n838_13),
    .I0(read_latched[3]),
    .I1(n838_18),
    .I2(n838_19) 
);
defparam n838_s8.INIT=8'h80;
  LUT3 n838_s9 (
    .F(n838_14),
    .I0(read_latched[3]),
    .I1(n838_17),
    .I2(n838_19) 
);
defparam n838_s9.INIT=8'h40;
  LUT4 n838_s10 (
    .F(n838_15),
    .I0(arm_req),
    .I1(read_latched[3]),
    .I2(n838_16),
    .I3(n838_18) 
);
defparam n838_s10.INIT=16'hB000;
  LUT3 n837_s5 (
    .F(n837_10),
    .I0(read_latched[3]),
    .I1(n838_16),
    .I2(n838_18) 
);
defparam n837_s5.INIT=8'h80;
  LUT3 n834_s5 (
    .F(n834_10),
    .I0(read_latched[3]),
    .I1(n838_16),
    .I2(n838_18) 
);
defparam n834_s5.INIT=8'h40;
  LUT4 n834_s6 (
    .F(n834_11),
    .I0(read_latched[3]),
    .I1(snap_req),
    .I2(n838_16),
    .I3(n838_17) 
);
defparam n834_s6.INIT=16'h4000;
  LUT4 n833_s5 (
    .F(n833_10),
    .I0(read_latched[3]),
    .I1(arm_req),
    .I2(n838_16),
    .I3(n838_17) 
);
defparam n833_s5.INIT=16'h4000;
  LUT4 n833_s6 (
    .F(n833_11),
    .I0(arm_count[5]),
    .I1(read_latched[3]),
    .I2(n838_16),
    .I3(n838_18) 
);
defparam n833_s6.INIT=16'hB000;
  LUT4 n499_s4 (
    .F(n499_9),
    .I0(arm_count[21]),
    .I1(arm_count[20]),
    .I2(arm_count[19]),
    .I3(arm_count[18]) 
);
defparam n499_s4.INIT=16'h8000;
  LUT4 n838_s11 (
    .F(n838_16),
    .I0(read_latched[4]),
    .I1(read_latched[5]),
    .I2(read_latched[6]),
    .I3(read_latched[7]) 
);
defparam n838_s11.INIT=16'h0100;
  LUT3 n838_s12 (
    .F(n838_17),
    .I0(read_latched[0]),
    .I1(read_latched[1]),
    .I2(read_latched[2]) 
);
defparam n838_s12.INIT=8'h10;
  LUT3 n838_s13 (
    .F(n838_18),
    .I0(read_latched[0]),
    .I1(read_latched[1]),
    .I2(read_latched[2]) 
);
defparam n838_s13.INIT=8'h01;
  LUT4 n838_s14 (
    .F(n838_19),
    .I0(read_latched[5]),
    .I1(read_latched[6]),
    .I2(read_latched[7]),
    .I3(read_latched[4]) 
);
defparam n838_s14.INIT=16'h1000;
  LUT3 n103_s3 (
    .F(n103_9),
    .I0(heartbeat_count[6]),
    .I1(heartbeat_count[5]),
    .I2(heartbeat_count[4]) 
);
defparam n103_s3.INIT=8'h80;
  LUT4 n332_s4 (
    .F(n332_10),
    .I0(sequence_id[20]),
    .I1(n339_7),
    .I2(n332_8),
    .I3(up[1]) 
);
defparam n332_s4.INIT=16'h6A00;
  LUT3 n345_s3 (
    .F(n345_9),
    .I0(sequence_id[6]),
    .I1(sequence_id[5]),
    .I2(sequence_id[4]) 
);
defparam n345_s3.INIT=8'h80;
  LUT3 n496_s3 (
    .F(n496_9),
    .I0(arm_count[25]),
    .I1(arm_count[24]),
    .I2(arm_count[23]) 
);
defparam n496_s3.INIT=8'h80;
  LUT4 n502_s4 (
    .F(n502_10),
    .I0(arm_count[20]),
    .I1(n509_7),
    .I2(n502_8),
    .I3(up[1]) 
);
defparam n502_s4.INIT=16'h6A00;
  LUT4 n636_s5 (
    .F(n636_11),
    .I0(n1490_5),
    .I1(n525_10),
    .I2(n1490_6),
    .I3(n1490_7) 
);
defparam n636_s5.INIT=16'h4000;
  LUT4 n636_s6 (
    .F(n636_13),
    .I0(n525_9),
    .I1(n525_10),
    .I2(n1490_6),
    .I3(rejected) 
);
defparam n636_s6.INIT=16'h7F00;
  LUT4 n84_s5 (
    .F(n84_11),
    .I0(heartbeat_count[25]),
    .I1(n97_7),
    .I2(heartbeat_count[24]),
    .I3(heartbeat_count[23]) 
);
defparam n84_s5.INIT=16'h8000;
  LUT4 n90_s4 (
    .F(n90_10),
    .I0(heartbeat_count[20]),
    .I1(n97_7),
    .I2(n90_8),
    .I3(up[1]) 
);
defparam n90_s4.INIT=16'h6A00;
  LUT4 n325_s3 (
    .F(n325_9),
    .I0(sequence_id[26]),
    .I1(sequence_id[25]),
    .I2(sequence_id[24]),
    .I3(sequence_id[23]) 
);
defparam n325_s3.INIT=16'h8000;
  LUT4 n102_s4 (
    .F(n102_10),
    .I0(heartbeat_count[8]),
    .I1(n106_7),
    .I2(n102_8),
    .I3(up[1]) 
);
defparam n102_s4.INIT=16'h6A00;
  LUT4 n329_s3 (
    .F(n329_9),
    .I0(sequence_id[23]),
    .I1(n339_7),
    .I2(n322_7),
    .I3(up[1]) 
);
defparam n329_s3.INIT=16'h6A00;
  LUT4 n344_s4 (
    .F(n344_10),
    .I0(sequence_id[8]),
    .I1(n348_7),
    .I2(n344_8),
    .I3(up[1]) 
);
defparam n344_s4.INIT=16'h6A00;
  LUT4 n514_s4 (
    .F(n514_10),
    .I0(arm_count[8]),
    .I1(n518_7),
    .I2(n514_8),
    .I3(up[1]) 
);
defparam n514_s4.INIT=16'h6A00;
  LUT4 n87_s3 (
    .F(n87_9),
    .I0(heartbeat_count[23]),
    .I1(n97_7),
    .I2(n84_7),
    .I3(up[1]) 
);
defparam n87_s3.INIT=16'h6A00;
  LUT4 n499_s5 (
    .F(n499_11),
    .I0(arm_count[23]),
    .I1(n509_7),
    .I2(n499_8),
    .I3(up[1]) 
);
defparam n499_s5.INIT=16'h6A00;
  LUT4 snap_busy_s5 (
    .F(snap_busy_11),
    .I0(write_addr[3]),
    .I1(write_addr[4]),
    .I2(write_addr[2]),
    .I3(n1490_4) 
);
defparam snap_busy_s5.INIT=16'hEF00;
  LUT4 arm_req_s7 (
    .F(arm_req_10),
    .I0(n1490_4),
    .I1(write_addr[3]),
    .I2(write_addr[4]),
    .I3(write_addr[2]) 
);
defparam arm_req_s7.INIT=16'h0200;
  LUT4 n809_s5 (
    .F(n809_11),
    .I0(arm_count[29]),
    .I1(read_latched[3]),
    .I2(n838_16),
    .I3(n838_18) 
);
defparam n809_s5.INIT=16'h8000;
  LUT4 n810_s5 (
    .F(n810_11),
    .I0(arm_count[28]),
    .I1(read_latched[3]),
    .I2(n838_16),
    .I3(n838_18) 
);
defparam n810_s5.INIT=16'h8000;
  LUT4 n815_s5 (
    .F(n815_11),
    .I0(arm_count[23]),
    .I1(read_latched[3]),
    .I2(n838_16),
    .I3(n838_18) 
);
defparam n815_s5.INIT=16'h8000;
  LUT4 n818_s5 (
    .F(n818_11),
    .I0(arm_count[20]),
    .I1(read_latched[3]),
    .I2(n838_16),
    .I3(n838_18) 
);
defparam n818_s5.INIT=16'h8000;
  LUT4 n823_s5 (
    .F(n823_11),
    .I0(arm_count[15]),
    .I1(read_latched[3]),
    .I2(n838_16),
    .I3(n838_18) 
);
defparam n823_s5.INIT=16'h8000;
  LUT4 n807_s5 (
    .F(n807_11),
    .I0(heartbeat_count[31]),
    .I1(read_latched[3]),
    .I2(n838_18),
    .I3(n838_19) 
);
defparam n807_s5.INIT=16'h8000;
  LUT4 n814_s5 (
    .F(n814_11),
    .I0(heartbeat_count[24]),
    .I1(read_latched[3]),
    .I2(n838_18),
    .I3(n838_19) 
);
defparam n814_s5.INIT=16'h8000;
  LUT4 n820_s5 (
    .F(n820_11),
    .I0(heartbeat_count[18]),
    .I1(read_latched[3]),
    .I2(n838_18),
    .I3(n838_19) 
);
defparam n820_s5.INIT=16'h8000;
  LUT4 n831_s5 (
    .F(n831_11),
    .I0(heartbeat_count[7]),
    .I1(read_latched[3]),
    .I2(n838_18),
    .I3(n838_19) 
);
defparam n831_s5.INIT=16'h8000;
  LUT4 n817_s5 (
    .F(n817_11),
    .I0(shadow[53]),
    .I1(read_latched[3]),
    .I2(n838_17),
    .I3(n838_19) 
);
defparam n817_s5.INIT=16'h2000;
  LUT4 n819_s5 (
    .F(n819_11),
    .I0(shadow[51]),
    .I1(read_latched[3]),
    .I2(n838_17),
    .I3(n838_19) 
);
defparam n819_s5.INIT=16'h2000;
  LUT4 n825_s5 (
    .F(n825_11),
    .I0(shadow[45]),
    .I1(read_latched[3]),
    .I2(n838_17),
    .I3(n838_19) 
);
defparam n825_s5.INIT=16'h2000;
  LUT4 n827_s5 (
    .F(n827_11),
    .I0(shadow[43]),
    .I1(read_latched[3]),
    .I2(n838_17),
    .I3(n838_19) 
);
defparam n827_s5.INIT=16'h2000;
  LUT4 n828_s5 (
    .F(n828_11),
    .I0(shadow[42]),
    .I1(read_latched[3]),
    .I2(n838_17),
    .I3(n838_19) 
);
defparam n828_s5.INIT=16'h2000;
  LUT4 n829_s5 (
    .F(n829_11),
    .I0(shadow[41]),
    .I1(read_latched[3]),
    .I2(n838_17),
    .I3(n838_19) 
);
defparam n829_s5.INIT=16'h2000;
  LUT4 n830_s5 (
    .F(n830_11),
    .I0(shadow[40]),
    .I1(read_latched[3]),
    .I2(n838_17),
    .I3(n838_19) 
);
defparam n830_s5.INIT=16'h2000;
  LUT2 n111_s3 (
    .F(n111_11),
    .I0(beat_sync[1]),
    .I1(up[1]) 
);
defparam n111_s3.INIT=4'h8;
  LUT3 beat_last_s5 (
    .F(beat_last_13),
    .I0(beat_last),
    .I1(beat_sync[1]),
    .I2(up[1]) 
);
defparam beat_last_s5.INIT=8'h6F;
  LUT3 n522_s3 (
    .F(n522_9),
    .I0(arm_req),
    .I1(arm_req_10),
    .I2(up[1]) 
);
defparam n522_s3.INIT=8'h60;
  LUT2 arm_req_s9 (
    .F(arm_req_25),
    .I0(arm_req_10),
    .I1(up[1]) 
);
defparam arm_req_s9.INIT=4'hB;
  LUT4 n1490_s6 (
    .F(n1490_10),
    .I0(snapshot_valid),
    .I1(up[1]),
    .I2(n1490_4),
    .I3(shadow_63_8) 
);
defparam n1490_s6.INIT=16'h0C0A;
  LUT4 n491_s5 (
    .F(n491_11),
    .I0(arm_req_10),
    .I1(n491_7),
    .I2(arm_count[31]),
    .I3(up[1]) 
);
defparam n491_s5.INIT=16'h7800;
  LUT4 n492_s5 (
    .F(n492_11),
    .I0(arm_count[30]),
    .I1(n492_7),
    .I2(arm_req_10),
    .I3(up[1]) 
);
defparam n492_s5.INIT=16'hCA00;
  LUT4 n494_s4 (
    .F(n494_10),
    .I0(arm_req_10),
    .I1(n494_7),
    .I2(arm_count[28]),
    .I3(up[1]) 
);
defparam n494_s4.INIT=16'h7800;
  LUT4 n500_s4 (
    .F(n500_10),
    .I0(arm_req_10),
    .I1(n500_7),
    .I2(arm_count[22]),
    .I3(up[1]) 
);
defparam n500_s4.INIT=16'h7800;
  LUT4 n503_s4 (
    .F(n503_10),
    .I0(arm_count[19]),
    .I1(n503_7),
    .I2(arm_req_10),
    .I3(up[1]) 
);
defparam n503_s4.INIT=16'hCA00;
  LUT4 n506_s4 (
    .F(n506_10),
    .I0(arm_req_10),
    .I1(n506_7),
    .I2(arm_count[16]),
    .I3(up[1]) 
);
defparam n506_s4.INIT=16'h7800;
  LUT4 n509_s5 (
    .F(n509_11),
    .I0(arm_req_10),
    .I1(n509_7),
    .I2(arm_count[13]),
    .I3(up[1]) 
);
defparam n509_s5.INIT=16'h7800;
  LUT4 n511_s4 (
    .F(n511_10),
    .I0(arm_req_10),
    .I1(n511_7),
    .I2(arm_count[11]),
    .I3(up[1]) 
);
defparam n511_s4.INIT=16'h7800;
  LUT4 n516_s4 (
    .F(n516_10),
    .I0(arm_req_10),
    .I1(n516_7),
    .I2(arm_count[6]),
    .I3(up[1]) 
);
defparam n516_s4.INIT=16'h7800;
  LUT4 n518_s4 (
    .F(n518_10),
    .I0(arm_req_10),
    .I1(n518_7),
    .I2(arm_count[4]),
    .I3(up[1]) 
);
defparam n518_s4.INIT=16'h7800;
  LUT4 n519_s4 (
    .F(n519_10),
    .I0(arm_count[3]),
    .I1(n519_7),
    .I2(arm_req_10),
    .I3(up[1]) 
);
defparam n519_s4.INIT=16'hCA00;
  LUT4 n521_s3 (
    .F(n521_9),
    .I0(arm_req),
    .I1(arm_req_10),
    .I2(arm_count[1]),
    .I3(up[1]) 
);
defparam n521_s3.INIT=16'h7800;
  LUT4 n110_s3 (
    .F(n110_9),
    .I0(beat_last),
    .I1(beat_sync[1]),
    .I2(heartbeat_count[0]),
    .I3(up[1]) 
);
defparam n110_s3.INIT=16'h9600;
  LUT4 n529_s3 (
    .F(n529_9),
    .I0(read_addr[7]),
    .I1(read_latched[7]),
    .I2(legacy_wait),
    .I3(up[1]) 
);
defparam n529_s3.INIT=16'hCA00;
  LUT4 n530_s3 (
    .F(n530_9),
    .I0(read_addr[6]),
    .I1(read_latched[6]),
    .I2(legacy_wait),
    .I3(up[1]) 
);
defparam n530_s3.INIT=16'hCA00;
  LUT4 n531_s3 (
    .F(n531_9),
    .I0(read_addr[5]),
    .I1(read_latched[5]),
    .I2(legacy_wait),
    .I3(up[1]) 
);
defparam n531_s3.INIT=16'hCA00;
  LUT4 n532_s3 (
    .F(n532_9),
    .I0(read_addr[4]),
    .I1(read_latched[4]),
    .I2(legacy_wait),
    .I3(up[1]) 
);
defparam n532_s3.INIT=16'hCA00;
  LUT4 n533_s3 (
    .F(n533_9),
    .I0(read_addr[3]),
    .I1(read_latched[3]),
    .I2(legacy_wait),
    .I3(up[1]) 
);
defparam n533_s3.INIT=16'hCA00;
  LUT4 n534_s3 (
    .F(n534_9),
    .I0(read_addr[2]),
    .I1(read_latched[2]),
    .I2(legacy_wait),
    .I3(up[1]) 
);
defparam n534_s3.INIT=16'hCA00;
  LUT4 n535_s3 (
    .F(n535_9),
    .I0(read_addr[1]),
    .I1(read_latched[1]),
    .I2(legacy_wait),
    .I3(up[1]) 
);
defparam n535_s3.INIT=16'hCA00;
  LUT4 n536_s3 (
    .F(n536_9),
    .I0(read_addr[0]),
    .I1(read_latched[0]),
    .I2(legacy_wait),
    .I3(up[1]) 
);
defparam n536_s3.INIT=16'hCA00;
  DFFCE up_0_s0 (
    .Q(up[0]),
    .D(VCC),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam up_0_s0.INIT=1'b0;
  DFFCE arm_sync_1_s0 (
    .Q(arm_sync[1]),
    .D(n622_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam arm_sync_1_s0.INIT=1'b0;
  DFFCE arm_sync_0_s0 (
    .Q(arm_sync[0]),
    .D(n623_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam arm_sync_0_s0.INIT=1'b0;
  DFFCE snap_sync_1_s0 (
    .Q(snap_sync[1]),
    .D(n624_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam snap_sync_1_s0.INIT=1'b0;
  DFFCE snap_sync_0_s0 (
    .Q(snap_sync[0]),
    .D(n625_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam snap_sync_0_s0.INIT=1'b0;
  DFFCE ready_sync_1_s0 (
    .Q(ready_sync[1]),
    .D(n626_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam ready_sync_1_s0.INIT=1'b0;
  DFFCE ready_sync_0_s0 (
    .Q(ready_sync[0]),
    .D(n627_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam ready_sync_0_s0.INIT=1'b0;
  DFFCE beat_sync_1_s0 (
    .Q(beat_sync[1]),
    .D(n628_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam beat_sync_1_s0.INIT=1'b0;
  DFFCE beat_sync_0_s0 (
    .Q(beat_sync[0]),
    .D(n629_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam beat_sync_0_s0.INIT=1'b0;
  DFFCE snap_req_s2 (
    .Q(snap_req),
    .D(n632_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam snap_req_s2.INIT=1'b0;
  DFFCE rejected_s0 (
    .Q(rejected),
    .D(n636_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam rejected_s0.INIT=1'b0;
  DFFCE response_31_s0 (
    .Q(response[31]),
    .D(n807_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_31_s0.INIT=1'b0;
  DFFCE response_30_s0 (
    .Q(response[30]),
    .D(n808_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_30_s0.INIT=1'b0;
  DFFCE response_29_s0 (
    .Q(response[29]),
    .D(n809_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_29_s0.INIT=1'b0;
  DFFCE response_28_s0 (
    .Q(response[28]),
    .D(n810_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_28_s0.INIT=1'b0;
  DFFCE response_27_s0 (
    .Q(response[27]),
    .D(n811_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_27_s0.INIT=1'b0;
  DFFCE response_26_s0 (
    .Q(response[26]),
    .D(n812_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_26_s0.INIT=1'b0;
  DFFCE response_25_s0 (
    .Q(response[25]),
    .D(n813_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_25_s0.INIT=1'b0;
  DFFCE response_24_s0 (
    .Q(response[24]),
    .D(n814_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_24_s0.INIT=1'b0;
  DFFCE response_23_s0 (
    .Q(response[23]),
    .D(n815_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_23_s0.INIT=1'b0;
  DFFCE response_22_s0 (
    .Q(response[22]),
    .D(n816_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_22_s0.INIT=1'b0;
  DFFCE response_21_s0 (
    .Q(response[21]),
    .D(n817_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_21_s0.INIT=1'b0;
  DFFCE response_20_s0 (
    .Q(response[20]),
    .D(n818_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_20_s0.INIT=1'b0;
  DFFCE response_19_s0 (
    .Q(response[19]),
    .D(n819_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_19_s0.INIT=1'b0;
  DFFCE response_18_s0 (
    .Q(response[18]),
    .D(n820_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_18_s0.INIT=1'b0;
  DFFCE response_17_s0 (
    .Q(response[17]),
    .D(n821_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_17_s0.INIT=1'b0;
  DFFCE response_16_s0 (
    .Q(response[16]),
    .D(n822_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_16_s0.INIT=1'b0;
  DFFCE response_15_s0 (
    .Q(response[15]),
    .D(n823_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_15_s0.INIT=1'b0;
  DFFCE response_14_s0 (
    .Q(response[14]),
    .D(n824_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_14_s0.INIT=1'b0;
  DFFCE response_13_s0 (
    .Q(response[13]),
    .D(n825_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_13_s0.INIT=1'b0;
  DFFCE response_12_s0 (
    .Q(response[12]),
    .D(n826_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_12_s0.INIT=1'b0;
  DFFCE response_11_s0 (
    .Q(response[11]),
    .D(n827_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_11_s0.INIT=1'b0;
  DFFCE response_10_s0 (
    .Q(response[10]),
    .D(n828_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_10_s0.INIT=1'b0;
  DFFCE response_9_s0 (
    .Q(response[9]),
    .D(n829_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_9_s0.INIT=1'b0;
  DFFCE response_8_s0 (
    .Q(response[8]),
    .D(n830_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_8_s0.INIT=1'b0;
  DFFCE response_7_s0 (
    .Q(response[7]),
    .D(n831_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_7_s0.INIT=1'b0;
  DFFCE response_6_s0 (
    .Q(response[6]),
    .D(n832_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_6_s0.INIT=1'b0;
  DFFCE response_5_s0 (
    .Q(response[5]),
    .D(n833_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_5_s0.INIT=1'b0;
  DFFCE response_4_s0 (
    .Q(response[4]),
    .D(n834_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_4_s0.INIT=1'b0;
  DFFCE response_3_s0 (
    .Q(response[3]),
    .D(n835_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_3_s0.INIT=1'b0;
  DFFCE response_2_s0 (
    .Q(response[2]),
    .D(n836_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_2_s0.INIT=1'b0;
  DFFCE response_1_s0 (
    .Q(response[1]),
    .D(n837_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_1_s0.INIT=1'b0;
  DFFCE response_0_s0 (
    .Q(response[0]),
    .D(n838_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam response_0_s0.INIT=1'b0;
  DFFCE up_1_s0 (
    .Q(up[1]),
    .D(up[0]),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam up_1_s0.INIT=1'b0;
  DFFCE arm_busy_s1 (
    .Q(arm_busy),
    .D(n490_8),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_busy_8) 
);
defparam arm_busy_s1.INIT=1'b0;
  DFFCE snap_busy_s1 (
    .Q(snap_busy),
    .D(n525_8),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(snap_busy_8) 
);
defparam snap_busy_s1.INIT=1'b0;
  DFFCE settle_1_s1 (
    .Q(settle[1]),
    .D(n355_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(settle_1_8) 
);
defparam settle_1_s1.INIT=1'b0;
  DFFCE settle_0_s1 (
    .Q(settle[0]),
    .D(n356_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(settle_1_8) 
);
defparam settle_0_s1.INIT=1'b0;
  DFFCE shadow_63_s1 (
    .Q(shadow[63]),
    .D(n257_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_63_s1.INIT=1'b0;
  DFFCE shadow_62_s1 (
    .Q(shadow[62]),
    .D(n258_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_62_s1.INIT=1'b0;
  DFFCE shadow_61_s1 (
    .Q(shadow[61]),
    .D(n259_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_61_s1.INIT=1'b0;
  DFFCE shadow_60_s1 (
    .Q(shadow[60]),
    .D(n260_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_60_s1.INIT=1'b0;
  DFFCE shadow_59_s1 (
    .Q(shadow[59]),
    .D(n261_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_59_s1.INIT=1'b0;
  DFFCE shadow_58_s1 (
    .Q(shadow[58]),
    .D(n262_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_58_s1.INIT=1'b0;
  DFFCE shadow_57_s1 (
    .Q(shadow[57]),
    .D(n263_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_57_s1.INIT=1'b0;
  DFFCE shadow_56_s1 (
    .Q(shadow[56]),
    .D(n264_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_56_s1.INIT=1'b0;
  DFFCE shadow_55_s1 (
    .Q(shadow[55]),
    .D(n265_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_55_s1.INIT=1'b0;
  DFFCE shadow_54_s1 (
    .Q(shadow[54]),
    .D(n266_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_54_s1.INIT=1'b0;
  DFFCE shadow_53_s1 (
    .Q(shadow[53]),
    .D(n267_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_53_s1.INIT=1'b0;
  DFFCE shadow_52_s1 (
    .Q(shadow[52]),
    .D(n268_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_52_s1.INIT=1'b0;
  DFFCE shadow_51_s1 (
    .Q(shadow[51]),
    .D(n269_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_51_s1.INIT=1'b0;
  DFFCE shadow_50_s1 (
    .Q(shadow[50]),
    .D(n270_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_50_s1.INIT=1'b0;
  DFFCE shadow_49_s1 (
    .Q(shadow[49]),
    .D(n271_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_49_s1.INIT=1'b0;
  DFFCE shadow_48_s1 (
    .Q(shadow[48]),
    .D(n272_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_48_s1.INIT=1'b0;
  DFFCE shadow_47_s1 (
    .Q(shadow[47]),
    .D(n273_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_47_s1.INIT=1'b0;
  DFFCE shadow_46_s1 (
    .Q(shadow[46]),
    .D(n274_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_46_s1.INIT=1'b0;
  DFFCE shadow_45_s1 (
    .Q(shadow[45]),
    .D(n275_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_45_s1.INIT=1'b0;
  DFFCE shadow_44_s1 (
    .Q(shadow[44]),
    .D(n276_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_44_s1.INIT=1'b0;
  DFFCE shadow_43_s1 (
    .Q(shadow[43]),
    .D(n277_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_43_s1.INIT=1'b0;
  DFFCE shadow_42_s1 (
    .Q(shadow[42]),
    .D(n278_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_42_s1.INIT=1'b0;
  DFFCE shadow_41_s1 (
    .Q(shadow[41]),
    .D(n279_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_41_s1.INIT=1'b0;
  DFFCE shadow_40_s1 (
    .Q(shadow[40]),
    .D(n280_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_40_s1.INIT=1'b0;
  DFFCE shadow_39_s1 (
    .Q(shadow[39]),
    .D(n281_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_39_s1.INIT=1'b0;
  DFFCE shadow_38_s1 (
    .Q(shadow[38]),
    .D(n282_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_38_s1.INIT=1'b0;
  DFFCE shadow_37_s1 (
    .Q(shadow[37]),
    .D(n283_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_37_s1.INIT=1'b0;
  DFFCE shadow_36_s1 (
    .Q(shadow[36]),
    .D(n284_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_36_s1.INIT=1'b0;
  DFFCE shadow_35_s1 (
    .Q(shadow[35]),
    .D(n285_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_35_s1.INIT=1'b0;
  DFFCE shadow_34_s1 (
    .Q(shadow[34]),
    .D(n286_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_34_s1.INIT=1'b0;
  DFFCE shadow_33_s1 (
    .Q(shadow[33]),
    .D(n287_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_33_s1.INIT=1'b0;
  DFFCE shadow_32_s1 (
    .Q(shadow[32]),
    .D(n288_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_32_s1.INIT=1'b0;
  DFFCE shadow_31_s1 (
    .Q(shadow[31]),
    .D(n289_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_31_s1.INIT=1'b0;
  DFFCE shadow_30_s1 (
    .Q(shadow[30]),
    .D(n290_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_30_s1.INIT=1'b0;
  DFFCE shadow_29_s1 (
    .Q(shadow[29]),
    .D(n291_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_29_s1.INIT=1'b0;
  DFFCE shadow_28_s1 (
    .Q(shadow[28]),
    .D(n292_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_28_s1.INIT=1'b0;
  DFFCE shadow_27_s1 (
    .Q(shadow[27]),
    .D(n293_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_27_s1.INIT=1'b0;
  DFFCE shadow_26_s1 (
    .Q(shadow[26]),
    .D(n294_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_26_s1.INIT=1'b0;
  DFFCE shadow_25_s1 (
    .Q(shadow[25]),
    .D(n295_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_25_s1.INIT=1'b0;
  DFFCE shadow_24_s1 (
    .Q(shadow[24]),
    .D(n296_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_24_s1.INIT=1'b0;
  DFFCE shadow_23_s1 (
    .Q(shadow[23]),
    .D(n297_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_23_s1.INIT=1'b0;
  DFFCE shadow_22_s1 (
    .Q(shadow[22]),
    .D(n298_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_22_s1.INIT=1'b0;
  DFFCE shadow_21_s1 (
    .Q(shadow[21]),
    .D(n299_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_21_s1.INIT=1'b0;
  DFFCE shadow_20_s1 (
    .Q(shadow[20]),
    .D(n300_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_20_s1.INIT=1'b0;
  DFFCE shadow_19_s1 (
    .Q(shadow[19]),
    .D(n301_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_19_s1.INIT=1'b0;
  DFFCE shadow_18_s1 (
    .Q(shadow[18]),
    .D(n302_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_18_s1.INIT=1'b0;
  DFFCE shadow_17_s1 (
    .Q(shadow[17]),
    .D(n303_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_17_s1.INIT=1'b0;
  DFFCE shadow_16_s1 (
    .Q(shadow[16]),
    .D(n304_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_16_s1.INIT=1'b0;
  DFFCE shadow_15_s1 (
    .Q(shadow[15]),
    .D(n305_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_15_s1.INIT=1'b0;
  DFFCE shadow_14_s1 (
    .Q(shadow[14]),
    .D(n306_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_14_s1.INIT=1'b0;
  DFFCE shadow_13_s1 (
    .Q(shadow[13]),
    .D(n307_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_13_s1.INIT=1'b0;
  DFFCE shadow_12_s1 (
    .Q(shadow[12]),
    .D(n308_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_12_s1.INIT=1'b0;
  DFFCE shadow_11_s1 (
    .Q(shadow[11]),
    .D(n309_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_11_s1.INIT=1'b0;
  DFFCE shadow_10_s1 (
    .Q(shadow[10]),
    .D(n310_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_10_s1.INIT=1'b0;
  DFFCE shadow_9_s1 (
    .Q(shadow[9]),
    .D(n311_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_9_s1.INIT=1'b0;
  DFFCE shadow_8_s1 (
    .Q(shadow[8]),
    .D(n312_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_8_s1.INIT=1'b0;
  DFFCE shadow_7_s1 (
    .Q(shadow[7]),
    .D(n313_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_7_s1.INIT=1'b0;
  DFFCE shadow_6_s1 (
    .Q(shadow[6]),
    .D(n314_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_6_s1.INIT=1'b0;
  DFFCE shadow_5_s1 (
    .Q(shadow[5]),
    .D(n315_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_5_s1.INIT=1'b0;
  DFFCE shadow_4_s1 (
    .Q(shadow[4]),
    .D(n316_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_4_s1.INIT=1'b0;
  DFFCE shadow_3_s1 (
    .Q(shadow[3]),
    .D(n317_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_3_s1.INIT=1'b0;
  DFFCE shadow_2_s1 (
    .Q(shadow[2]),
    .D(n318_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_2_s1.INIT=1'b0;
  DFFCE shadow_1_s1 (
    .Q(shadow[1]),
    .D(n319_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_1_s1.INIT=1'b0;
  DFFCE shadow_0_s1 (
    .Q(shadow[0]),
    .D(n320_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam shadow_0_s1.INIT=1'b0;
  DFFCE sequence_id_31_s1 (
    .Q(sequence_id[31]),
    .D(n321_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_31_s1.INIT=1'b0;
  DFFCE sequence_id_30_s1 (
    .Q(sequence_id[30]),
    .D(n322_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_30_s1.INIT=1'b0;
  DFFCE sequence_id_29_s1 (
    .Q(sequence_id[29]),
    .D(n323_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_29_s1.INIT=1'b0;
  DFFCE sequence_id_28_s1 (
    .Q(sequence_id[28]),
    .D(n324_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_28_s1.INIT=1'b0;
  DFFCE sequence_id_27_s1 (
    .Q(sequence_id[27]),
    .D(n325_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_27_s1.INIT=1'b0;
  DFFCE sequence_id_26_s1 (
    .Q(sequence_id[26]),
    .D(n326_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_26_s1.INIT=1'b0;
  DFFCE sequence_id_25_s1 (
    .Q(sequence_id[25]),
    .D(n327_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_25_s1.INIT=1'b0;
  DFFCE sequence_id_24_s1 (
    .Q(sequence_id[24]),
    .D(n328_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_24_s1.INIT=1'b0;
  DFFCE sequence_id_23_s1 (
    .Q(sequence_id[23]),
    .D(n329_9),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_23_s1.INIT=1'b0;
  DFFCE sequence_id_22_s1 (
    .Q(sequence_id[22]),
    .D(n330_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_22_s1.INIT=1'b0;
  DFFCE sequence_id_21_s1 (
    .Q(sequence_id[21]),
    .D(n331_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_21_s1.INIT=1'b0;
  DFFCE sequence_id_20_s1 (
    .Q(sequence_id[20]),
    .D(n332_10),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_20_s1.INIT=1'b0;
  DFFCE sequence_id_19_s1 (
    .Q(sequence_id[19]),
    .D(n333_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_19_s1.INIT=1'b0;
  DFFCE sequence_id_18_s1 (
    .Q(sequence_id[18]),
    .D(n334_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_18_s1.INIT=1'b0;
  DFFCE sequence_id_17_s1 (
    .Q(sequence_id[17]),
    .D(n335_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_17_s1.INIT=1'b0;
  DFFCE sequence_id_16_s1 (
    .Q(sequence_id[16]),
    .D(n336_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_16_s1.INIT=1'b0;
  DFFCE sequence_id_15_s1 (
    .Q(sequence_id[15]),
    .D(n337_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_15_s1.INIT=1'b0;
  DFFCE sequence_id_14_s1 (
    .Q(sequence_id[14]),
    .D(n338_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_14_s1.INIT=1'b0;
  DFFCE sequence_id_13_s1 (
    .Q(sequence_id[13]),
    .D(n339_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_13_s1.INIT=1'b0;
  DFFCE sequence_id_12_s1 (
    .Q(sequence_id[12]),
    .D(n340_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_12_s1.INIT=1'b0;
  DFFCE sequence_id_11_s1 (
    .Q(sequence_id[11]),
    .D(n341_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_11_s1.INIT=1'b0;
  DFFCE sequence_id_10_s1 (
    .Q(sequence_id[10]),
    .D(n342_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_10_s1.INIT=1'b0;
  DFFCE sequence_id_9_s1 (
    .Q(sequence_id[9]),
    .D(n343_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_9_s1.INIT=1'b0;
  DFFCE sequence_id_8_s1 (
    .Q(sequence_id[8]),
    .D(n344_10),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_8_s1.INIT=1'b0;
  DFFCE sequence_id_7_s1 (
    .Q(sequence_id[7]),
    .D(n345_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_7_s1.INIT=1'b0;
  DFFCE sequence_id_6_s1 (
    .Q(sequence_id[6]),
    .D(n346_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_6_s1.INIT=1'b0;
  DFFCE sequence_id_5_s1 (
    .Q(sequence_id[5]),
    .D(n347_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_5_s1.INIT=1'b0;
  DFFCE sequence_id_4_s1 (
    .Q(sequence_id[4]),
    .D(n348_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_4_s1.INIT=1'b0;
  DFFCE sequence_id_3_s1 (
    .Q(sequence_id[3]),
    .D(n349_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_3_s1.INIT=1'b0;
  DFFCE sequence_id_2_s1 (
    .Q(sequence_id[2]),
    .D(n350_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_2_s1.INIT=1'b0;
  DFFCE sequence_id_1_s1 (
    .Q(sequence_id[1]),
    .D(n351_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_1_s1.INIT=1'b0;
  DFFCE sequence_id_0_s1 (
    .Q(sequence_id[0]),
    .D(n352_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(shadow_63_8) 
);
defparam sequence_id_0_s1.INIT=1'b0;
  DFFCE arm_count_29_s1 (
    .Q(arm_count[29]),
    .D(n493_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_req_25) 
);
defparam arm_count_29_s1.INIT=1'b0;
  DFFCE arm_count_27_s1 (
    .Q(arm_count[27]),
    .D(n495_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_req_25) 
);
defparam arm_count_27_s1.INIT=1'b0;
  DFFCE arm_count_26_s1 (
    .Q(arm_count[26]),
    .D(n496_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_req_25) 
);
defparam arm_count_26_s1.INIT=1'b0;
  DFFCE arm_count_25_s1 (
    .Q(arm_count[25]),
    .D(n497_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_req_25) 
);
defparam arm_count_25_s1.INIT=1'b0;
  DFFCE arm_count_24_s1 (
    .Q(arm_count[24]),
    .D(n498_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_req_25) 
);
defparam arm_count_24_s1.INIT=1'b0;
  DFFCE arm_count_23_s1 (
    .Q(arm_count[23]),
    .D(n499_11),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_req_25) 
);
defparam arm_count_23_s1.INIT=1'b0;
  DFFCE arm_count_21_s1 (
    .Q(arm_count[21]),
    .D(n501_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_req_25) 
);
defparam arm_count_21_s1.INIT=1'b0;
  DFFCE arm_count_20_s1 (
    .Q(arm_count[20]),
    .D(n502_10),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_req_25) 
);
defparam arm_count_20_s1.INIT=1'b0;
  DFFCE arm_count_18_s1 (
    .Q(arm_count[18]),
    .D(n504_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_req_25) 
);
defparam arm_count_18_s1.INIT=1'b0;
  DFFCE arm_count_17_s1 (
    .Q(arm_count[17]),
    .D(n505_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_req_25) 
);
defparam arm_count_17_s1.INIT=1'b0;
  DFFCE arm_count_15_s1 (
    .Q(arm_count[15]),
    .D(n507_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_req_25) 
);
defparam arm_count_15_s1.INIT=1'b0;
  DFFCE arm_count_14_s1 (
    .Q(arm_count[14]),
    .D(n508_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_req_25) 
);
defparam arm_count_14_s1.INIT=1'b0;
  DFFCE arm_count_12_s1 (
    .Q(arm_count[12]),
    .D(n510_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_req_25) 
);
defparam arm_count_12_s1.INIT=1'b0;
  DFFCE arm_count_10_s1 (
    .Q(arm_count[10]),
    .D(n512_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_req_25) 
);
defparam arm_count_10_s1.INIT=1'b0;
  DFFCE arm_count_9_s1 (
    .Q(arm_count[9]),
    .D(n513_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_req_25) 
);
defparam arm_count_9_s1.INIT=1'b0;
  DFFCE arm_count_8_s1 (
    .Q(arm_count[8]),
    .D(n514_10),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_req_25) 
);
defparam arm_count_8_s1.INIT=1'b0;
  DFFCE arm_count_7_s1 (
    .Q(arm_count[7]),
    .D(n515_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_req_25) 
);
defparam arm_count_7_s1.INIT=1'b0;
  DFFCE arm_count_5_s1 (
    .Q(arm_count[5]),
    .D(n517_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_req_25) 
);
defparam arm_count_5_s1.INIT=1'b0;
  DFFCE arm_count_2_s1 (
    .Q(arm_count[2]),
    .D(n520_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(arm_req_25) 
);
defparam arm_count_2_s1.INIT=1'b0;
  DFFCE heartbeat_count_31_s1 (
    .Q(heartbeat_count[31]),
    .D(n79_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_31_s1.INIT=1'b0;
  DFFCE heartbeat_count_30_s1 (
    .Q(heartbeat_count[30]),
    .D(n80_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_30_s1.INIT=1'b0;
  DFFCE heartbeat_count_29_s1 (
    .Q(heartbeat_count[29]),
    .D(n81_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_29_s1.INIT=1'b0;
  DFFCE heartbeat_count_28_s1 (
    .Q(heartbeat_count[28]),
    .D(n82_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_28_s1.INIT=1'b0;
  DFFCE heartbeat_count_27_s1 (
    .Q(heartbeat_count[27]),
    .D(n83_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_27_s1.INIT=1'b0;
  DFFCE heartbeat_count_26_s1 (
    .Q(heartbeat_count[26]),
    .D(n84_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_26_s1.INIT=1'b0;
  DFFCE heartbeat_count_25_s1 (
    .Q(heartbeat_count[25]),
    .D(n85_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_25_s1.INIT=1'b0;
  DFFCE heartbeat_count_24_s1 (
    .Q(heartbeat_count[24]),
    .D(n86_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_24_s1.INIT=1'b0;
  DFFCE heartbeat_count_23_s1 (
    .Q(heartbeat_count[23]),
    .D(n87_9),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_23_s1.INIT=1'b0;
  DFFCE heartbeat_count_22_s1 (
    .Q(heartbeat_count[22]),
    .D(n88_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_22_s1.INIT=1'b0;
  DFFCE heartbeat_count_21_s1 (
    .Q(heartbeat_count[21]),
    .D(n89_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_21_s1.INIT=1'b0;
  DFFCE heartbeat_count_20_s1 (
    .Q(heartbeat_count[20]),
    .D(n90_10),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_20_s1.INIT=1'b0;
  DFFCE heartbeat_count_19_s1 (
    .Q(heartbeat_count[19]),
    .D(n91_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_19_s1.INIT=1'b0;
  DFFCE heartbeat_count_18_s1 (
    .Q(heartbeat_count[18]),
    .D(n92_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_18_s1.INIT=1'b0;
  DFFCE heartbeat_count_17_s1 (
    .Q(heartbeat_count[17]),
    .D(n93_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_17_s1.INIT=1'b0;
  DFFCE heartbeat_count_16_s1 (
    .Q(heartbeat_count[16]),
    .D(n94_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_16_s1.INIT=1'b0;
  DFFCE heartbeat_count_15_s1 (
    .Q(heartbeat_count[15]),
    .D(n95_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_15_s1.INIT=1'b0;
  DFFCE heartbeat_count_14_s1 (
    .Q(heartbeat_count[14]),
    .D(n96_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_14_s1.INIT=1'b0;
  DFFCE heartbeat_count_13_s1 (
    .Q(heartbeat_count[13]),
    .D(n97_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_13_s1.INIT=1'b0;
  DFFCE heartbeat_count_12_s1 (
    .Q(heartbeat_count[12]),
    .D(n98_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_12_s1.INIT=1'b0;
  DFFCE heartbeat_count_11_s1 (
    .Q(heartbeat_count[11]),
    .D(n99_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_11_s1.INIT=1'b0;
  DFFCE heartbeat_count_10_s1 (
    .Q(heartbeat_count[10]),
    .D(n100_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_10_s1.INIT=1'b0;
  DFFCE heartbeat_count_9_s1 (
    .Q(heartbeat_count[9]),
    .D(n101_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_9_s1.INIT=1'b0;
  DFFCE heartbeat_count_8_s1 (
    .Q(heartbeat_count[8]),
    .D(n102_10),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_8_s1.INIT=1'b0;
  DFFCE heartbeat_count_7_s1 (
    .Q(heartbeat_count[7]),
    .D(n103_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_7_s1.INIT=1'b0;
  DFFCE heartbeat_count_6_s1 (
    .Q(heartbeat_count[6]),
    .D(n104_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_6_s1.INIT=1'b0;
  DFFCE heartbeat_count_5_s1 (
    .Q(heartbeat_count[5]),
    .D(n105_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_5_s1.INIT=1'b0;
  DFFCE heartbeat_count_4_s1 (
    .Q(heartbeat_count[4]),
    .D(n106_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_4_s1.INIT=1'b0;
  DFFCE heartbeat_count_3_s1 (
    .Q(heartbeat_count[3]),
    .D(n107_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_3_s1.INIT=1'b0;
  DFFCE heartbeat_count_2_s1 (
    .Q(heartbeat_count[2]),
    .D(n108_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_2_s1.INIT=1'b0;
  DFFCE heartbeat_count_1_s1 (
    .Q(heartbeat_count[1]),
    .D(n109_6),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(beat_last_13) 
);
defparam heartbeat_count_1_s1.INIT=1'b0;
  DFFCE beat_last_s4 (
    .Q(beat_last),
    .D(n111_11),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam beat_last_s4.INIT=1'b0;
  DFFCE arm_req_s8 (
    .Q(arm_req),
    .D(n522_9),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam arm_req_s8.INIT=1'b0;
  DFFCE snapshot_valid_s4 (
    .Q(snapshot_valid),
    .D(n1490_10),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam snapshot_valid_s4.INIT=1'b0;
  DFFCE arm_count_31_s3 (
    .Q(arm_count[31]),
    .D(n491_11),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam arm_count_31_s3.INIT=1'b0;
  DFFCE arm_count_30_s3 (
    .Q(arm_count[30]),
    .D(n492_11),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam arm_count_30_s3.INIT=1'b0;
  DFFCE arm_count_28_s3 (
    .Q(arm_count[28]),
    .D(n494_10),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam arm_count_28_s3.INIT=1'b0;
  DFFCE arm_count_22_s3 (
    .Q(arm_count[22]),
    .D(n500_10),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam arm_count_22_s3.INIT=1'b0;
  DFFCE arm_count_19_s3 (
    .Q(arm_count[19]),
    .D(n503_10),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam arm_count_19_s3.INIT=1'b0;
  DFFCE arm_count_16_s3 (
    .Q(arm_count[16]),
    .D(n506_10),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam arm_count_16_s3.INIT=1'b0;
  DFFCE arm_count_13_s3 (
    .Q(arm_count[13]),
    .D(n509_11),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam arm_count_13_s3.INIT=1'b0;
  DFFCE arm_count_11_s3 (
    .Q(arm_count[11]),
    .D(n511_10),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam arm_count_11_s3.INIT=1'b0;
  DFFCE arm_count_6_s3 (
    .Q(arm_count[6]),
    .D(n516_10),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam arm_count_6_s3.INIT=1'b0;
  DFFCE arm_count_4_s3 (
    .Q(arm_count[4]),
    .D(n518_10),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam arm_count_4_s3.INIT=1'b0;
  DFFCE arm_count_3_s3 (
    .Q(arm_count[3]),
    .D(n519_10),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam arm_count_3_s3.INIT=1'b0;
  DFFCE arm_count_1_s3 (
    .Q(arm_count[1]),
    .D(n521_9),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam arm_count_1_s3.INIT=1'b0;
  DFFCE heartbeat_count_0_s3 (
    .Q(heartbeat_count[0]),
    .D(n110_9),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam heartbeat_count_0_s3.INIT=1'b0;
  DFFCE read_latched_7_s4 (
    .Q(read_latched[7]),
    .D(n529_9),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam read_latched_7_s4.INIT=1'b0;
  DFFCE read_latched_6_s3 (
    .Q(read_latched[6]),
    .D(n530_9),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam read_latched_6_s3.INIT=1'b0;
  DFFCE read_latched_5_s3 (
    .Q(read_latched[5]),
    .D(n531_9),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam read_latched_5_s3.INIT=1'b0;
  DFFCE read_latched_4_s3 (
    .Q(read_latched[4]),
    .D(n532_9),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam read_latched_4_s3.INIT=1'b0;
  DFFCE read_latched_3_s3 (
    .Q(read_latched[3]),
    .D(n533_9),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam read_latched_3_s3.INIT=1'b0;
  DFFCE read_latched_2_s3 (
    .Q(read_latched[2]),
    .D(n534_9),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam read_latched_2_s3.INIT=1'b0;
  DFFCE read_latched_1_s3 (
    .Q(read_latched[1]),
    .D(n535_9),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam read_latched_1_s3.INIT=1'b0;
  DFFCE read_latched_0_s3 (
    .Q(read_latched[0]),
    .D(n536_9),
    .CLK(clk),
    .CLEAR(n43_6),
    .CE(VCC) 
);
defparam read_latched_0_s3.INIT=1'b0;
  INV n43_s2 (
    .O(n43_6),
    .I(resetn) 
);
  VCC VCC_cZ (
    .V(VCC)
);
  GND GND_cZ (
    .G(GND)
);

endmodule /* neo_capture_bus */
