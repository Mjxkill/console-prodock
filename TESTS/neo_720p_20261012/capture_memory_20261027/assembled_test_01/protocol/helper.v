//
//Written by GowinSynthesis
//Tool Version "V1.9.12.03"
//Tue Oct 27 00:43:42 2026

//Source file index table:
//file0 "\/home/michael/console/tang/impl/console_neo_n56r21_capture_memory/source/tang/boards/neo/neo_capture_local.v"
`timescale 100 ps/100 ps
module neo_capture_local (
  clk,
  resetn,
  sample,
  mem_events,
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
input [3:0] mem_events;
input arm_req;
input snap_req;
output arm_ack;
output snap_ack;
output ready;
output heartbeat;
output [63:0] held;
wire complete_7;
wire valid_0_8;
wire n297_9;
wire n419_6;
wire n418_6;
wire n417_6;
wire n416_6;
wire n415_6;
wire n414_6;
wire n413_6;
wire n412_6;
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
wire n368_6;
wire n367_6;
wire n366_6;
wire n365_6;
wire n363_6;
wire n362_6;
wire n361_6;
wire n360_6;
wire n499_6;
wire n498_6;
wire n497_6;
wire n496_6;
wire n495_6;
wire n494_6;
wire n493_6;
wire n492_6;
wire n491_6;
wire n424_6;
wire n423_6;
wire n422_6;
wire n421_6;
wire n501_7;
wire n503_7;
wire n504_7;
wire n555_7;
wire n556_7;
wire n557_7;
wire n558_7;
wire n205_7;
wire n496_7;
wire n495_7;
wire n493_7;
wire n492_7;
wire n491_7;
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
wire n226_9;
wire n227_9;
wire n228_9;
wire n229_9;
wire n296_11;
wire n420_9;
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
wire [3:0] mem_seen;
wire [0:0] valid;
wire [23:0] at_event;
wire [23:0] after_event;
wire VCC;
wire GND;
  LUT3 armed_s3 (
    .F(complete_7),
    .I0(pending),
    .I1(armed),
    .I2(n205_7) 
);
defparam armed_s3.INIT=8'h8F;
  LUT4 valid_0_s3 (
    .F(valid_0_8),
    .I0(pending),
    .I1(sample[18]),
    .I2(armed),
    .I3(n205_7) 
);
defparam valid_0_s3.INIT=16'h40FF;
  LUT3 n297_s4 (
    .F(n297_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready) 
);
defparam n297_s4.INIT=8'h60;
  LUT2 n419_s1 (
    .F(n419_6),
    .I0(ready),
    .I1(at_event[0]) 
);
defparam n419_s1.INIT=4'h8;
  LUT2 n418_s1 (
    .F(n418_6),
    .I0(ready),
    .I1(at_event[1]) 
);
defparam n418_s1.INIT=4'h8;
  LUT2 n417_s1 (
    .F(n417_6),
    .I0(ready),
    .I1(at_event[2]) 
);
defparam n417_s1.INIT=4'h8;
  LUT2 n416_s1 (
    .F(n416_6),
    .I0(ready),
    .I1(at_event[3]) 
);
defparam n416_s1.INIT=4'h8;
  LUT2 n415_s1 (
    .F(n415_6),
    .I0(ready),
    .I1(at_event[4]) 
);
defparam n415_s1.INIT=4'h8;
  LUT2 n414_s1 (
    .F(n414_6),
    .I0(ready),
    .I1(at_event[5]) 
);
defparam n414_s1.INIT=4'h8;
  LUT2 n413_s1 (
    .F(n413_6),
    .I0(ready),
    .I1(at_event[6]) 
);
defparam n413_s1.INIT=4'h8;
  LUT2 n412_s1 (
    .F(n412_6),
    .I0(ready),
    .I1(at_event[7]) 
);
defparam n412_s1.INIT=4'h8;
  LUT2 n411_s1 (
    .F(n411_6),
    .I0(ready),
    .I1(at_event[8]) 
);
defparam n411_s1.INIT=4'h8;
  LUT2 n410_s1 (
    .F(n410_6),
    .I0(ready),
    .I1(at_event[9]) 
);
defparam n410_s1.INIT=4'h8;
  LUT2 n409_s1 (
    .F(n409_6),
    .I0(ready),
    .I1(at_event[10]) 
);
defparam n409_s1.INIT=4'h8;
  LUT2 n408_s1 (
    .F(n408_6),
    .I0(ready),
    .I1(at_event[11]) 
);
defparam n408_s1.INIT=4'h8;
  LUT2 n407_s1 (
    .F(n407_6),
    .I0(ready),
    .I1(at_event[12]) 
);
defparam n407_s1.INIT=4'h8;
  LUT2 n406_s1 (
    .F(n406_6),
    .I0(ready),
    .I1(at_event[13]) 
);
defparam n406_s1.INIT=4'h8;
  LUT2 n405_s1 (
    .F(n405_6),
    .I0(ready),
    .I1(at_event[14]) 
);
defparam n405_s1.INIT=4'h8;
  LUT2 n404_s1 (
    .F(n404_6),
    .I0(ready),
    .I1(at_event[15]) 
);
defparam n404_s1.INIT=4'h8;
  LUT2 n403_s1 (
    .F(n403_6),
    .I0(ready),
    .I1(at_event[16]) 
);
defparam n403_s1.INIT=4'h8;
  LUT2 n402_s1 (
    .F(n402_6),
    .I0(ready),
    .I1(at_event[17]) 
);
defparam n402_s1.INIT=4'h8;
  LUT2 n401_s1 (
    .F(n401_6),
    .I0(ready),
    .I1(at_event[18]) 
);
defparam n401_s1.INIT=4'h8;
  LUT2 n400_s1 (
    .F(n400_6),
    .I0(ready),
    .I1(at_event[19]) 
);
defparam n400_s1.INIT=4'h8;
  LUT2 n399_s1 (
    .F(n399_6),
    .I0(ready),
    .I1(at_event[20]) 
);
defparam n399_s1.INIT=4'h8;
  LUT2 n398_s1 (
    .F(n398_6),
    .I0(ready),
    .I1(at_event[21]) 
);
defparam n398_s1.INIT=4'h8;
  LUT2 n397_s1 (
    .F(n397_6),
    .I0(ready),
    .I1(at_event[22]) 
);
defparam n397_s1.INIT=4'h8;
  LUT2 n396_s1 (
    .F(n396_6),
    .I0(ready),
    .I1(at_event[23]) 
);
defparam n396_s1.INIT=4'h8;
  LUT2 n395_s1 (
    .F(n395_6),
    .I0(ready),
    .I1(after_event[0]) 
);
defparam n395_s1.INIT=4'h8;
  LUT2 n394_s1 (
    .F(n394_6),
    .I0(ready),
    .I1(after_event[1]) 
);
defparam n394_s1.INIT=4'h8;
  LUT2 n393_s1 (
    .F(n393_6),
    .I0(ready),
    .I1(after_event[2]) 
);
defparam n393_s1.INIT=4'h8;
  LUT2 n392_s1 (
    .F(n392_6),
    .I0(ready),
    .I1(after_event[3]) 
);
defparam n392_s1.INIT=4'h8;
  LUT2 n391_s1 (
    .F(n391_6),
    .I0(ready),
    .I1(after_event[4]) 
);
defparam n391_s1.INIT=4'h8;
  LUT2 n390_s1 (
    .F(n390_6),
    .I0(ready),
    .I1(after_event[5]) 
);
defparam n390_s1.INIT=4'h8;
  LUT2 n389_s1 (
    .F(n389_6),
    .I0(ready),
    .I1(after_event[6]) 
);
defparam n389_s1.INIT=4'h8;
  LUT2 n388_s1 (
    .F(n388_6),
    .I0(ready),
    .I1(after_event[7]) 
);
defparam n388_s1.INIT=4'h8;
  LUT2 n387_s1 (
    .F(n387_6),
    .I0(ready),
    .I1(after_event[8]) 
);
defparam n387_s1.INIT=4'h8;
  LUT2 n386_s1 (
    .F(n386_6),
    .I0(ready),
    .I1(after_event[9]) 
);
defparam n386_s1.INIT=4'h8;
  LUT2 n385_s1 (
    .F(n385_6),
    .I0(ready),
    .I1(after_event[10]) 
);
defparam n385_s1.INIT=4'h8;
  LUT2 n384_s1 (
    .F(n384_6),
    .I0(ready),
    .I1(after_event[11]) 
);
defparam n384_s1.INIT=4'h8;
  LUT2 n383_s1 (
    .F(n383_6),
    .I0(ready),
    .I1(after_event[12]) 
);
defparam n383_s1.INIT=4'h8;
  LUT2 n382_s1 (
    .F(n382_6),
    .I0(ready),
    .I1(after_event[13]) 
);
defparam n382_s1.INIT=4'h8;
  LUT2 n381_s1 (
    .F(n381_6),
    .I0(ready),
    .I1(after_event[14]) 
);
defparam n381_s1.INIT=4'h8;
  LUT2 n380_s1 (
    .F(n380_6),
    .I0(ready),
    .I1(after_event[15]) 
);
defparam n380_s1.INIT=4'h8;
  LUT2 n379_s1 (
    .F(n379_6),
    .I0(ready),
    .I1(after_event[16]) 
);
defparam n379_s1.INIT=4'h8;
  LUT2 n378_s1 (
    .F(n378_6),
    .I0(ready),
    .I1(after_event[17]) 
);
defparam n378_s1.INIT=4'h8;
  LUT2 n377_s1 (
    .F(n377_6),
    .I0(ready),
    .I1(after_event[18]) 
);
defparam n377_s1.INIT=4'h8;
  LUT2 n376_s1 (
    .F(n376_6),
    .I0(ready),
    .I1(after_event[19]) 
);
defparam n376_s1.INIT=4'h8;
  LUT2 n375_s1 (
    .F(n375_6),
    .I0(ready),
    .I1(after_event[20]) 
);
defparam n375_s1.INIT=4'h8;
  LUT2 n374_s1 (
    .F(n374_6),
    .I0(ready),
    .I1(after_event[21]) 
);
defparam n374_s1.INIT=4'h8;
  LUT2 n373_s1 (
    .F(n373_6),
    .I0(ready),
    .I1(after_event[22]) 
);
defparam n373_s1.INIT=4'h8;
  LUT2 n372_s1 (
    .F(n372_6),
    .I0(ready),
    .I1(after_event[23]) 
);
defparam n372_s1.INIT=4'h8;
  LUT2 n371_s1 (
    .F(n371_6),
    .I0(ready),
    .I1(valid[0]) 
);
defparam n371_s1.INIT=4'h8;
  LUT2 n370_s1 (
    .F(n370_6),
    .I0(ready),
    .I1(complete) 
);
defparam n370_s1.INIT=4'h8;
  LUT2 n368_s1 (
    .F(n368_6),
    .I0(armed),
    .I1(ready) 
);
defparam n368_s1.INIT=4'h8;
  LUT2 n367_s1 (
    .F(n367_6),
    .I0(seen_reset),
    .I1(ready) 
);
defparam n367_s1.INIT=4'h8;
  LUT2 n366_s1 (
    .F(n366_6),
    .I0(seen_ce),
    .I1(ready) 
);
defparam n366_s1.INIT=4'h8;
  LUT2 n365_s1 (
    .F(n365_6),
    .I0(arm_ack),
    .I1(ready) 
);
defparam n365_s1.INIT=4'h8;
  LUT3 n363_s1 (
    .F(n363_6),
    .I0(mem_events[0]),
    .I1(mem_seen[0]),
    .I2(ready) 
);
defparam n363_s1.INIT=8'hE0;
  LUT3 n362_s1 (
    .F(n362_6),
    .I0(mem_events[1]),
    .I1(mem_seen[1]),
    .I2(ready) 
);
defparam n362_s1.INIT=8'hE0;
  LUT3 n361_s1 (
    .F(n361_6),
    .I0(mem_events[2]),
    .I1(mem_seen[2]),
    .I2(ready) 
);
defparam n361_s1.INIT=8'hE0;
  LUT3 n360_s1 (
    .F(n360_6),
    .I0(mem_events[3]),
    .I1(mem_seen[3]),
    .I2(ready) 
);
defparam n360_s1.INIT=8'hE0;
  LUT2 n499_s1 (
    .F(n499_6),
    .I0(beat[0]),
    .I1(ready) 
);
defparam n499_s1.INIT=4'h4;
  LUT3 n498_s1 (
    .F(n498_6),
    .I0(beat[1]),
    .I1(beat[0]),
    .I2(ready) 
);
defparam n498_s1.INIT=8'h60;
  LUT4 n497_s1 (
    .F(n497_6),
    .I0(beat[1]),
    .I1(beat[0]),
    .I2(beat[2]),
    .I3(ready) 
);
defparam n497_s1.INIT=16'h7800;
  LUT2 n496_s1 (
    .F(n496_6),
    .I0(n496_7),
    .I1(ready) 
);
defparam n496_s1.INIT=4'h8;
  LUT3 n495_s1 (
    .F(n495_6),
    .I0(n495_7),
    .I1(beat[4]),
    .I2(ready) 
);
defparam n495_s1.INIT=8'h60;
  LUT4 n494_s1 (
    .F(n494_6),
    .I0(n495_7),
    .I1(beat[4]),
    .I2(beat[5]),
    .I3(ready) 
);
defparam n494_s1.INIT=16'h7800;
  LUT4 n493_s1 (
    .F(n493_6),
    .I0(n495_7),
    .I1(n493_7),
    .I2(beat[6]),
    .I3(ready) 
);
defparam n493_s1.INIT=16'h7800;
  LUT4 n492_s1 (
    .F(n492_6),
    .I0(n495_7),
    .I1(n492_7),
    .I2(beat[7]),
    .I3(ready) 
);
defparam n492_s1.INIT=16'h7800;
  LUT4 n491_s1 (
    .F(n491_6),
    .I0(n495_7),
    .I1(n491_7),
    .I2(heartbeat),
    .I3(ready) 
);
defparam n491_s1.INIT=16'h7800;
  LUT2 n424_s1 (
    .F(n424_6),
    .I0(ready),
    .I1(snap_req) 
);
defparam n424_s1.INIT=4'h8;
  LUT2 n423_s1 (
    .F(n423_6),
    .I0(ready),
    .I1(snap_sync[0]) 
);
defparam n423_s1.INIT=4'h8;
  LUT2 n422_s1 (
    .F(n422_6),
    .I0(ready),
    .I1(arm_req) 
);
defparam n422_s1.INIT=4'h8;
  LUT2 n421_s1 (
    .F(n421_6),
    .I0(ready),
    .I1(arm_sync[0]) 
);
defparam n421_s1.INIT=4'h8;
  LUT4 n501_s2 (
    .F(n501_7),
    .I0(sample[18]),
    .I1(pending),
    .I2(armed),
    .I3(n205_7) 
);
defparam n501_s2.INIT=16'h2C00;
  LUT4 n503_s2 (
    .F(n503_7),
    .I0(sample[17]),
    .I1(armed),
    .I2(seen_reset),
    .I3(n205_7) 
);
defparam n503_s2.INIT=16'hF800;
  LUT4 n504_s2 (
    .F(n504_7),
    .I0(sample[16]),
    .I1(armed),
    .I2(seen_ce),
    .I3(n205_7) 
);
defparam n504_s2.INIT=16'hF800;
  LUT3 n555_s2 (
    .F(n555_7),
    .I0(mem_events[3]),
    .I1(mem_seen[3]),
    .I2(n205_7) 
);
defparam n555_s2.INIT=8'hE0;
  LUT3 n556_s2 (
    .F(n556_7),
    .I0(mem_events[2]),
    .I1(mem_seen[2]),
    .I2(n205_7) 
);
defparam n556_s2.INIT=8'hE0;
  LUT3 n557_s2 (
    .F(n557_7),
    .I0(mem_events[1]),
    .I1(mem_seen[1]),
    .I2(n205_7) 
);
defparam n557_s2.INIT=8'hE0;
  LUT3 n558_s2 (
    .F(n558_7),
    .I0(mem_events[0]),
    .I1(mem_seen[0]),
    .I2(n205_7) 
);
defparam n558_s2.INIT=8'hE0;
  LUT3 n205_s2 (
    .F(n205_7),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready) 
);
defparam n205_s2.INIT=8'h90;
  LUT4 n496_s2 (
    .F(n496_7),
    .I0(beat[1]),
    .I1(beat[0]),
    .I2(beat[2]),
    .I3(beat[3]) 
);
defparam n496_s2.INIT=16'h7F80;
  LUT4 n495_s2 (
    .F(n495_7),
    .I0(beat[1]),
    .I1(beat[0]),
    .I2(beat[2]),
    .I3(beat[3]) 
);
defparam n495_s2.INIT=16'h8000;
  LUT2 n493_s2 (
    .F(n493_7),
    .I0(beat[4]),
    .I1(beat[5]) 
);
defparam n493_s2.INIT=4'h8;
  LUT3 n492_s2 (
    .F(n492_7),
    .I0(beat[4]),
    .I1(beat[5]),
    .I2(beat[6]) 
);
defparam n492_s2.INIT=8'h80;
  LUT4 n491_s2 (
    .F(n491_7),
    .I0(beat[4]),
    .I1(beat[5]),
    .I2(beat[6]),
    .I3(beat[7]) 
);
defparam n491_s2.INIT=16'h8000;
  LUT4 n206_s3 (
    .F(n206_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[23]) 
);
defparam n206_s3.INIT=16'h9000;
  LUT4 n207_s3 (
    .F(n207_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[22]) 
);
defparam n207_s3.INIT=16'h9000;
  LUT4 n208_s3 (
    .F(n208_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[21]) 
);
defparam n208_s3.INIT=16'h9000;
  LUT4 n209_s3 (
    .F(n209_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[20]) 
);
defparam n209_s3.INIT=16'h9000;
  LUT4 n210_s3 (
    .F(n210_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[19]) 
);
defparam n210_s3.INIT=16'h9000;
  LUT4 n211_s3 (
    .F(n211_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[18]) 
);
defparam n211_s3.INIT=16'h9000;
  LUT4 n212_s3 (
    .F(n212_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[17]) 
);
defparam n212_s3.INIT=16'h9000;
  LUT4 n213_s3 (
    .F(n213_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[16]) 
);
defparam n213_s3.INIT=16'h9000;
  LUT4 n214_s3 (
    .F(n214_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[15]) 
);
defparam n214_s3.INIT=16'h9000;
  LUT4 n215_s3 (
    .F(n215_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[14]) 
);
defparam n215_s3.INIT=16'h9000;
  LUT4 n216_s3 (
    .F(n216_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[13]) 
);
defparam n216_s3.INIT=16'h9000;
  LUT4 n217_s3 (
    .F(n217_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[12]) 
);
defparam n217_s3.INIT=16'h9000;
  LUT4 n218_s3 (
    .F(n218_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[11]) 
);
defparam n218_s3.INIT=16'h9000;
  LUT4 n219_s3 (
    .F(n219_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[10]) 
);
defparam n219_s3.INIT=16'h9000;
  LUT4 n220_s3 (
    .F(n220_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[9]) 
);
defparam n220_s3.INIT=16'h9000;
  LUT4 n221_s3 (
    .F(n221_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[8]) 
);
defparam n221_s3.INIT=16'h9000;
  LUT4 n222_s3 (
    .F(n222_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[7]) 
);
defparam n222_s3.INIT=16'h9000;
  LUT4 n223_s3 (
    .F(n223_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[6]) 
);
defparam n223_s3.INIT=16'h9000;
  LUT4 n224_s3 (
    .F(n224_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[5]) 
);
defparam n224_s3.INIT=16'h9000;
  LUT4 n225_s3 (
    .F(n225_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[4]) 
);
defparam n225_s3.INIT=16'h9000;
  LUT4 n226_s3 (
    .F(n226_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[3]) 
);
defparam n226_s3.INIT=16'h9000;
  LUT4 n227_s3 (
    .F(n227_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[2]) 
);
defparam n227_s3.INIT=16'h9000;
  LUT4 n228_s3 (
    .F(n228_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[1]) 
);
defparam n228_s3.INIT=16'h9000;
  LUT4 n229_s3 (
    .F(n229_9),
    .I0(arm_sync[1]),
    .I1(arm_ack),
    .I2(ready),
    .I3(sample[0]) 
);
defparam n229_s3.INIT=16'h9000;
  LUT2 n296_s3 (
    .F(n296_11),
    .I0(arm_sync[1]),
    .I1(ready) 
);
defparam n296_s3.INIT=4'h8;
  LUT4 n420_s3 (
    .F(n420_9),
    .I0(ready),
    .I1(snap_sync[1]),
    .I2(snap_ack),
    .I3(n297_9) 
);
defparam n420_s3.INIT=16'hF088;
  LUT4 snap_ack_s7 (
    .F(snap_ack_10),
    .I0(ready),
    .I1(snap_ack),
    .I2(snap_sync[1]),
    .I3(n297_9) 
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
    .D(n421_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam arm_sync_1_s0.INIT=1'b0;
  DFFCE arm_sync_0_s0 (
    .Q(arm_sync[0]),
    .D(n422_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam arm_sync_0_s0.INIT=1'b0;
  DFFCE snap_sync_1_s0 (
    .Q(snap_sync[1]),
    .D(n423_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam snap_sync_1_s0.INIT=1'b0;
  DFFCE snap_sync_0_s0 (
    .Q(snap_sync[0]),
    .D(n424_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam snap_sync_0_s0.INIT=1'b0;
  DFFCE beat_8_s0 (
    .Q(heartbeat),
    .D(n491_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam beat_8_s0.INIT=1'b0;
  DFFCE beat_7_s0 (
    .Q(beat[7]),
    .D(n492_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam beat_7_s0.INIT=1'b0;
  DFFCE beat_6_s0 (
    .Q(beat[6]),
    .D(n493_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam beat_6_s0.INIT=1'b0;
  DFFCE beat_5_s0 (
    .Q(beat[5]),
    .D(n494_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam beat_5_s0.INIT=1'b0;
  DFFCE beat_4_s0 (
    .Q(beat[4]),
    .D(n495_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam beat_4_s0.INIT=1'b0;
  DFFCE beat_3_s0 (
    .Q(beat[3]),
    .D(n496_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam beat_3_s0.INIT=1'b0;
  DFFCE beat_2_s0 (
    .Q(beat[2]),
    .D(n497_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam beat_2_s0.INIT=1'b0;
  DFFCE beat_1_s0 (
    .Q(beat[1]),
    .D(n498_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam beat_1_s0.INIT=1'b0;
  DFFCE beat_0_s0 (
    .Q(beat[0]),
    .D(n499_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam beat_0_s0.INIT=1'b0;
  DFFCE pending_s0 (
    .Q(pending),
    .D(n501_7),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam pending_s0.INIT=1'b0;
  DFFCE seen_reset_s0 (
    .Q(seen_reset),
    .D(n503_7),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam seen_reset_s0.INIT=1'b0;
  DFFCE seen_ce_s0 (
    .Q(seen_ce),
    .D(n504_7),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam seen_ce_s0.INIT=1'b0;
  DFFCE mem_seen_3_s0 (
    .Q(mem_seen[3]),
    .D(n555_7),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam mem_seen_3_s0.INIT=1'b0;
  DFFCE mem_seen_2_s0 (
    .Q(mem_seen[2]),
    .D(n556_7),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam mem_seen_2_s0.INIT=1'b0;
  DFFCE mem_seen_1_s0 (
    .Q(mem_seen[1]),
    .D(n557_7),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam mem_seen_1_s0.INIT=1'b0;
  DFFCE mem_seen_0_s0 (
    .Q(mem_seen[0]),
    .D(n558_7),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam mem_seen_0_s0.INIT=1'b0;
  DFFCE up_1_s0 (
    .Q(ready),
    .D(up[0]),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam up_1_s0.INIT=1'b0;
  DFFCE held_63_s3 (
    .Q(held[60]),
    .D(ready),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_63_s3.INIT=1'b0;
  DFFCE held_59_s2 (
    .Q(held[59]),
    .D(n360_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_59_s2.INIT=1'b0;
  DFFCE held_58_s2 (
    .Q(held[58]),
    .D(n361_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_58_s2.INIT=1'b0;
  DFFCE held_57_s2 (
    .Q(held[57]),
    .D(n362_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_57_s2.INIT=1'b0;
  DFFCE held_56_s2 (
    .Q(held[56]),
    .D(n363_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_56_s2.INIT=1'b0;
  DFFCE held_54_s2 (
    .Q(held[54]),
    .D(n365_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_54_s2.INIT=1'b0;
  DFFCE held_53_s2 (
    .Q(held[53]),
    .D(n366_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_53_s2.INIT=1'b0;
  DFFCE held_52_s2 (
    .Q(held[52]),
    .D(n367_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_52_s2.INIT=1'b0;
  DFFCE held_51_s2 (
    .Q(held[51]),
    .D(n368_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_51_s2.INIT=1'b0;
  DFFCE held_50_s2 (
    .Q(held[49]),
    .D(n370_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_50_s2.INIT=1'b0;
  DFFCE held_48_s2 (
    .Q(held[48]),
    .D(n371_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_48_s2.INIT=1'b0;
  DFFCE held_47_s2 (
    .Q(held[47]),
    .D(n372_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_47_s2.INIT=1'b0;
  DFFCE held_46_s2 (
    .Q(held[46]),
    .D(n373_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_46_s2.INIT=1'b0;
  DFFCE held_45_s2 (
    .Q(held[45]),
    .D(n374_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_45_s2.INIT=1'b0;
  DFFCE held_44_s2 (
    .Q(held[44]),
    .D(n375_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_44_s2.INIT=1'b0;
  DFFCE held_43_s2 (
    .Q(held[43]),
    .D(n376_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_43_s2.INIT=1'b0;
  DFFCE held_42_s2 (
    .Q(held[42]),
    .D(n377_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_42_s2.INIT=1'b0;
  DFFCE held_41_s2 (
    .Q(held[41]),
    .D(n378_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_41_s2.INIT=1'b0;
  DFFCE held_40_s2 (
    .Q(held[40]),
    .D(n379_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_40_s2.INIT=1'b0;
  DFFCE held_39_s2 (
    .Q(held[39]),
    .D(n380_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_39_s2.INIT=1'b0;
  DFFCE held_38_s2 (
    .Q(held[38]),
    .D(n381_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_38_s2.INIT=1'b0;
  DFFCE held_37_s2 (
    .Q(held[37]),
    .D(n382_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_37_s2.INIT=1'b0;
  DFFCE held_36_s2 (
    .Q(held[36]),
    .D(n383_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_36_s2.INIT=1'b0;
  DFFCE held_35_s2 (
    .Q(held[35]),
    .D(n384_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_35_s2.INIT=1'b0;
  DFFCE held_34_s2 (
    .Q(held[34]),
    .D(n385_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_34_s2.INIT=1'b0;
  DFFCE held_33_s2 (
    .Q(held[33]),
    .D(n386_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_33_s2.INIT=1'b0;
  DFFCE held_32_s2 (
    .Q(held[32]),
    .D(n387_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_32_s2.INIT=1'b0;
  DFFCE held_31_s2 (
    .Q(held[31]),
    .D(n388_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_31_s2.INIT=1'b0;
  DFFCE held_30_s2 (
    .Q(held[30]),
    .D(n389_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_30_s2.INIT=1'b0;
  DFFCE held_29_s2 (
    .Q(held[29]),
    .D(n390_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_29_s2.INIT=1'b0;
  DFFCE held_28_s2 (
    .Q(held[28]),
    .D(n391_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_28_s2.INIT=1'b0;
  DFFCE held_27_s2 (
    .Q(held[27]),
    .D(n392_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_27_s2.INIT=1'b0;
  DFFCE held_26_s2 (
    .Q(held[26]),
    .D(n393_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_26_s2.INIT=1'b0;
  DFFCE held_25_s2 (
    .Q(held[25]),
    .D(n394_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_25_s2.INIT=1'b0;
  DFFCE held_24_s2 (
    .Q(held[24]),
    .D(n395_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_24_s2.INIT=1'b0;
  DFFCE held_23_s2 (
    .Q(held[23]),
    .D(n396_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_23_s2.INIT=1'b0;
  DFFCE held_22_s2 (
    .Q(held[22]),
    .D(n397_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_22_s2.INIT=1'b0;
  DFFCE held_21_s2 (
    .Q(held[21]),
    .D(n398_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_21_s2.INIT=1'b0;
  DFFCE held_20_s2 (
    .Q(held[20]),
    .D(n399_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_20_s2.INIT=1'b0;
  DFFCE held_19_s2 (
    .Q(held[19]),
    .D(n400_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_19_s2.INIT=1'b0;
  DFFCE held_18_s2 (
    .Q(held[18]),
    .D(n401_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_18_s2.INIT=1'b0;
  DFFCE held_17_s2 (
    .Q(held[17]),
    .D(n402_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_17_s2.INIT=1'b0;
  DFFCE held_16_s2 (
    .Q(held[16]),
    .D(n403_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_16_s2.INIT=1'b0;
  DFFCE held_15_s2 (
    .Q(held[15]),
    .D(n404_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_15_s2.INIT=1'b0;
  DFFCE held_14_s2 (
    .Q(held[14]),
    .D(n405_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_14_s2.INIT=1'b0;
  DFFCE held_13_s2 (
    .Q(held[13]),
    .D(n406_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_13_s2.INIT=1'b0;
  DFFCE held_12_s2 (
    .Q(held[12]),
    .D(n407_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_12_s2.INIT=1'b0;
  DFFCE held_11_s2 (
    .Q(held[11]),
    .D(n408_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_11_s2.INIT=1'b0;
  DFFCE held_10_s2 (
    .Q(held[10]),
    .D(n409_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_10_s2.INIT=1'b0;
  DFFCE held_9_s2 (
    .Q(held[9]),
    .D(n410_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_9_s2.INIT=1'b0;
  DFFCE held_8_s2 (
    .Q(held[8]),
    .D(n411_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_8_s2.INIT=1'b0;
  DFFCE held_7_s2 (
    .Q(held[7]),
    .D(n412_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_7_s2.INIT=1'b0;
  DFFCE held_6_s2 (
    .Q(held[6]),
    .D(n413_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_6_s2.INIT=1'b0;
  DFFCE held_5_s2 (
    .Q(held[5]),
    .D(n414_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_5_s2.INIT=1'b0;
  DFFCE held_4_s2 (
    .Q(held[4]),
    .D(n415_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_4_s2.INIT=1'b0;
  DFFCE held_3_s2 (
    .Q(held[3]),
    .D(n416_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_3_s2.INIT=1'b0;
  DFFCE held_2_s2 (
    .Q(held[2]),
    .D(n417_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_2_s2.INIT=1'b0;
  DFFCE held_1_s2 (
    .Q(held[1]),
    .D(n418_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_1_s2.INIT=1'b0;
  DFFCE held_0_s2 (
    .Q(held[0]),
    .D(n419_6),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(snap_ack_10) 
);
defparam held_0_s2.INIT=1'b0;
  DFFCE armed_s1 (
    .Q(armed),
    .D(n297_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam armed_s1.INIT=1'b0;
  DFFCE complete_s1 (
    .Q(complete),
    .D(n205_7),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam complete_s1.INIT=1'b0;
  DFFCE valid_0_s1 (
    .Q(valid[0]),
    .D(n205_7),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam valid_0_s1.INIT=1'b0;
  DFFCE at_event_23_s1 (
    .Q(at_event[23]),
    .D(n206_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_23_s1.INIT=1'b0;
  DFFCE at_event_22_s1 (
    .Q(at_event[22]),
    .D(n207_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_22_s1.INIT=1'b0;
  DFFCE at_event_21_s1 (
    .Q(at_event[21]),
    .D(n208_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_21_s1.INIT=1'b0;
  DFFCE at_event_20_s1 (
    .Q(at_event[20]),
    .D(n209_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_20_s1.INIT=1'b0;
  DFFCE at_event_19_s1 (
    .Q(at_event[19]),
    .D(n210_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_19_s1.INIT=1'b0;
  DFFCE at_event_18_s1 (
    .Q(at_event[18]),
    .D(n211_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_18_s1.INIT=1'b0;
  DFFCE at_event_17_s1 (
    .Q(at_event[17]),
    .D(n212_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_17_s1.INIT=1'b0;
  DFFCE at_event_16_s1 (
    .Q(at_event[16]),
    .D(n213_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_16_s1.INIT=1'b0;
  DFFCE at_event_15_s1 (
    .Q(at_event[15]),
    .D(n214_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_15_s1.INIT=1'b0;
  DFFCE at_event_14_s1 (
    .Q(at_event[14]),
    .D(n215_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_14_s1.INIT=1'b0;
  DFFCE at_event_13_s1 (
    .Q(at_event[13]),
    .D(n216_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_13_s1.INIT=1'b0;
  DFFCE at_event_12_s1 (
    .Q(at_event[12]),
    .D(n217_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_12_s1.INIT=1'b0;
  DFFCE at_event_11_s1 (
    .Q(at_event[11]),
    .D(n218_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_11_s1.INIT=1'b0;
  DFFCE at_event_10_s1 (
    .Q(at_event[10]),
    .D(n219_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_10_s1.INIT=1'b0;
  DFFCE at_event_9_s1 (
    .Q(at_event[9]),
    .D(n220_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_9_s1.INIT=1'b0;
  DFFCE at_event_8_s1 (
    .Q(at_event[8]),
    .D(n221_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_8_s1.INIT=1'b0;
  DFFCE at_event_7_s1 (
    .Q(at_event[7]),
    .D(n222_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_7_s1.INIT=1'b0;
  DFFCE at_event_6_s1 (
    .Q(at_event[6]),
    .D(n223_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_6_s1.INIT=1'b0;
  DFFCE at_event_5_s1 (
    .Q(at_event[5]),
    .D(n224_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_5_s1.INIT=1'b0;
  DFFCE at_event_4_s1 (
    .Q(at_event[4]),
    .D(n225_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_4_s1.INIT=1'b0;
  DFFCE at_event_3_s1 (
    .Q(at_event[3]),
    .D(n226_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_3_s1.INIT=1'b0;
  DFFCE at_event_2_s1 (
    .Q(at_event[2]),
    .D(n227_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_2_s1.INIT=1'b0;
  DFFCE at_event_1_s1 (
    .Q(at_event[1]),
    .D(n228_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_1_s1.INIT=1'b0;
  DFFCE at_event_0_s1 (
    .Q(at_event[0]),
    .D(n229_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(valid_0_8) 
);
defparam at_event_0_s1.INIT=1'b0;
  DFFCE after_event_23_s1 (
    .Q(after_event[23]),
    .D(n206_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_23_s1.INIT=1'b0;
  DFFCE after_event_22_s1 (
    .Q(after_event[22]),
    .D(n207_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_22_s1.INIT=1'b0;
  DFFCE after_event_21_s1 (
    .Q(after_event[21]),
    .D(n208_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_21_s1.INIT=1'b0;
  DFFCE after_event_20_s1 (
    .Q(after_event[20]),
    .D(n209_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_20_s1.INIT=1'b0;
  DFFCE after_event_19_s1 (
    .Q(after_event[19]),
    .D(n210_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_19_s1.INIT=1'b0;
  DFFCE after_event_18_s1 (
    .Q(after_event[18]),
    .D(n211_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_18_s1.INIT=1'b0;
  DFFCE after_event_17_s1 (
    .Q(after_event[17]),
    .D(n212_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_17_s1.INIT=1'b0;
  DFFCE after_event_16_s1 (
    .Q(after_event[16]),
    .D(n213_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_16_s1.INIT=1'b0;
  DFFCE after_event_15_s1 (
    .Q(after_event[15]),
    .D(n214_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_15_s1.INIT=1'b0;
  DFFCE after_event_14_s1 (
    .Q(after_event[14]),
    .D(n215_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_14_s1.INIT=1'b0;
  DFFCE after_event_13_s1 (
    .Q(after_event[13]),
    .D(n216_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_13_s1.INIT=1'b0;
  DFFCE after_event_12_s1 (
    .Q(after_event[12]),
    .D(n217_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_12_s1.INIT=1'b0;
  DFFCE after_event_11_s1 (
    .Q(after_event[11]),
    .D(n218_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_11_s1.INIT=1'b0;
  DFFCE after_event_10_s1 (
    .Q(after_event[10]),
    .D(n219_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_10_s1.INIT=1'b0;
  DFFCE after_event_9_s1 (
    .Q(after_event[9]),
    .D(n220_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_9_s1.INIT=1'b0;
  DFFCE after_event_8_s1 (
    .Q(after_event[8]),
    .D(n221_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_8_s1.INIT=1'b0;
  DFFCE after_event_7_s1 (
    .Q(after_event[7]),
    .D(n222_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_7_s1.INIT=1'b0;
  DFFCE after_event_6_s1 (
    .Q(after_event[6]),
    .D(n223_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_6_s1.INIT=1'b0;
  DFFCE after_event_5_s1 (
    .Q(after_event[5]),
    .D(n224_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_5_s1.INIT=1'b0;
  DFFCE after_event_4_s1 (
    .Q(after_event[4]),
    .D(n225_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_4_s1.INIT=1'b0;
  DFFCE after_event_3_s1 (
    .Q(after_event[3]),
    .D(n226_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_3_s1.INIT=1'b0;
  DFFCE after_event_2_s1 (
    .Q(after_event[2]),
    .D(n227_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_2_s1.INIT=1'b0;
  DFFCE after_event_1_s1 (
    .Q(after_event[1]),
    .D(n228_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_1_s1.INIT=1'b0;
  DFFCE after_event_0_s1 (
    .Q(after_event[0]),
    .D(n229_9),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(complete_7) 
);
defparam after_event_0_s1.INIT=1'b0;
  DFFCE arm_ack_s7 (
    .Q(arm_ack),
    .D(n296_11),
    .CLK(clk),
    .CLEAR(n77_7),
    .CE(VCC) 
);
defparam arm_ack_s7.INIT=1'b0;
  DFFCE snap_ack_s6 (
    .Q(snap_ack),
    .D(n420_9),
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
assign held[61] = GND;
assign held[62] = held[60];
assign held[63] = held[60];
endmodule /* neo_capture_local */
