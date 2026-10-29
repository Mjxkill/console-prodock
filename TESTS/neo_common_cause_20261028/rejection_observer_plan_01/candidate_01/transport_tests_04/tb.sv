
`timescale 1ns/1ps
module tb;
 GSR GSR(.GSRI(1'b1));
 reg hclk=0,gclk=0,reset=1,gpu_run=1;
 real hp=6.25,gp=6.6665;
 always #(hp) hclk=~hclk;
 always #(gp) if(gpu_run)gclk=~gclk;
 reg [31:0] addr=0;
 reg wr=0,trans=0,data_bit=0;
 reg [639:0] payload=0,next_payload=0;
 reg manual_pending=0;
 wire [31:0] gpu_data,scan_data;
 wire gpu_wait,scan_wait,prime_request;
 integer checks=0,trial,i;
 reg [31:0] got,seq0,seq1;
 // Reproduce the exact same-edge NBA hazard of manual freeze vs held capture.
 always @(posedge gclk) if(manual_pending && prime_request)begin
   payload<=next_payload;manual_pending<=0;
 end
 wire n438_11,n445_11,n452_8,n460_9,n467_8,n475_9,n47_5,n483_8,n492_9,n499_7,n507_8,n515_8,n524_9,n532_8,n541_9,n550_7,n560_8,n571_5,n579_5,n587_5,n596_6,n613_6,n622_6,n632_7,n640_5,n649_6,n658_6,n668_7,n677_6,n687_7,n697_7,n708_8,n716_5;
wire [9:8] observe_meta_s1;
wire observe_meta_s2_6,observe_meta_s2_9;
wire bus_haddr_5=addr[5];
wire bus_haddr_7=addr[7];
wire bus_haddr_6=addr[6];
wire gpu_trace_arm_req;
wire gpu_trace_snap_req;
wire gpu_n3052_12;
 LUT3 decode_n571_s0(.F(n571_5),.I0(n438_11),.I1(bus_haddr_6),.I2(bus_haddr_7));
defparam decode_n571_s0.INIT=8'h02;
LUT3 decode_n579_s1(.F(n579_5),.I0(bus_haddr_6),.I1(bus_haddr_7),.I2(n445_11));
defparam decode_n579_s1.INIT=8'h10;
LUT3 decode_n587_s1(.F(n587_5),.I0(bus_haddr_6),.I1(bus_haddr_7),.I2(n452_8));
defparam decode_n587_s1.INIT=8'h10;
LUT3 decode_n596_s2(.F(n596_6),.I0(bus_haddr_6),.I1(bus_haddr_7),.I2(n460_9));
defparam decode_n596_s2.INIT=8'h10;
LUT3 decode_n47_s1(.F(n47_5),.I0(bus_haddr_6),.I1(bus_haddr_7),.I2(n467_8));
defparam decode_n47_s1.INIT=8'h10;
LUT3 decode_n613_s2(.F(n613_6),.I0(bus_haddr_6),.I1(bus_haddr_7),.I2(n475_9));
defparam decode_n613_s2.INIT=8'h10;
LUT3 decode_n622_s2(.F(n622_6),.I0(bus_haddr_6),.I1(bus_haddr_7),.I2(n483_8));
defparam decode_n622_s2.INIT=8'h10;
LUT3 decode_n632_s3(.F(n632_7),.I0(bus_haddr_6),.I1(bus_haddr_7),.I2(n492_9));
defparam decode_n632_s3.INIT=8'h10;
LUT3 decode_n640_s1(.F(n640_5),.I0(bus_haddr_6),.I1(bus_haddr_7),.I2(n499_7));
defparam decode_n640_s1.INIT=8'h10;
LUT3 decode_n649_s2(.F(n649_6),.I0(bus_haddr_6),.I1(bus_haddr_7),.I2(n507_8));
defparam decode_n649_s2.INIT=8'h10;
LUT3 decode_n658_s2(.F(n658_6),.I0(bus_haddr_6),.I1(bus_haddr_7),.I2(n515_8));
defparam decode_n658_s2.INIT=8'h10;
LUT3 decode_n668_s3(.F(n668_7),.I0(bus_haddr_6),.I1(bus_haddr_7),.I2(n524_9));
defparam decode_n668_s3.INIT=8'h10;
LUT3 decode_n677_s2(.F(n677_6),.I0(bus_haddr_6),.I1(bus_haddr_7),.I2(n532_8));
defparam decode_n677_s2.INIT=8'h10;
LUT3 decode_n687_s3(.F(n687_7),.I0(bus_haddr_6),.I1(bus_haddr_7),.I2(n541_9));
defparam decode_n687_s3.INIT=8'h10;
LUT4 decode_n697_s3(.F(n697_7),.I0(bus_haddr_5),.I1(bus_haddr_6),.I2(bus_haddr_7),.I3(n550_7));
defparam decode_n697_s3.INIT=16'h0200;
LUT4 decode_n708_s4(.F(n708_8),.I0(bus_haddr_5),.I1(bus_haddr_6),.I2(bus_haddr_7),.I3(n560_8));
defparam decode_n708_s4.INIT=16'h0200;
LUT3 decode_n716_s1(.F(n716_5),.I0(n438_11),.I1(bus_haddr_7),.I2(bus_haddr_6));
defparam decode_n716_s1.INIT=8'h20;
neo_gpu_debug_0 gpu(.rjc_snapshot_request(prime_request),.rjc_payload(payload[319:0]),.trace_arm_req(gpu_trace_arm_req),.trace_snap_req(gpu_trace_snap_req),.trace_arm_ack('0),.trace_snap_ack('0),.trace_ready(1'b1),.trace_heartbeat('0),.trace_held('0),.vid_hclk(hclk),.n6_6(reset),.n571_5(n571_5),.n579_5(n579_5),.n587_5(n587_5),.n596_6(n596_6),.n47_5(n47_5),.n613_6(n613_6),.n622_6(n622_6),.n632_7(n632_7),.n640_5(n640_5),.n649_6(n649_6),.n658_6(n658_6),.n668_7(n668_7),.n677_6(n677_6),.n687_7(n687_7),.n697_7(n697_7),.n708_8(n708_8),.n716_5(n716_5),.gpu_clk(gclk),.n237_5(reset),.\g_inferred_storage.mem_10 (1'b1),.bus_hwrite(wr),.vid_hrstn(!reset),.queue_full('0),.bus_command('0),.gpu_observe_packet_words('0),.gpu_observe_packet_words_34('0),.gpu_debug_state_0('0),.gpu_debug_state_1('0),.gpu_debug_state_2('0),.gpu_debug_state_3('0),.gpu_debug_state_4('0),.gpu_debug_state_5('0),.gpu_debug_state_6('0),.gpu_debug_state_7('0),.gpu_debug_state_8('0),.gpu_debug_state_9('0),.gpu_debug_state_10('0),.gpu_debug_state_11('0),.gpu_debug_state_12('0),.gpu_debug_state_13('0),.gpu_debug_state_14('0),.gpu_debug_state_15('0),.gpu_debug_state_64('0),.gpu_debug_state_65('0),.gpu_debug_state_66('0),.gpu_debug_state_67('0),.gpu_debug_state_68('0),.gpu_debug_state_69('0),.gpu_debug_state_70('0),.gpu_debug_state_71('0),.gpu_debug_state_72('0),.gpu_debug_state_73('0),.gpu_debug_state_74('0),.gpu_debug_state_75('0),.gpu_debug_state_76('0),.gpu_debug_state_77('0),.gpu_debug_state_78('0),.gpu_debug_state_79('0),.gpu_debug_state_80('0),.gpu_debug_state_81('0),.gpu_debug_state_82('0),.gpu_debug_state_83('0),.gpu_debug_state_84('0),.gpu_debug_state_85('0),.gpu_debug_state_86('0),.gpu_debug_state_87('0),.gpu_debug_state_88('0),.gpu_debug_state_89('0),.gpu_debug_state_90('0),.gpu_debug_state_91('0),.gpu_debug_state_92('0),.gpu_debug_state_93('0),.gpu_debug_state_94('0),.gpu_debug_state_95('0),.gpu_debug_state_96('0),.gpu_debug_state_98('0),.gpu_debug_state_99('0),.gpu_debug_state_100('0),.gpu_debug_state_101('0),.gpu_debug_state_104('0),.gpu_debug_state_105('0),.gpu_debug_state_106('0),.gpu_debug_state_107('0),.gpu_debug_state_108('0),.gpu_debug_state_109('0),.gpu_debug_state_110('0),.gpu_debug_state_111('0),.gpu_debug_state_112('0),.gpu_debug_state_113('0),.gpu_debug_state_114('0),.gpu_debug_state_115('0),.gpu_debug_state_116('0),.gpu_debug_state_117('0),.gpu_debug_state_118('0),.gpu_debug_state_119('0),.gpu_debug_state_120('0),.gpu_debug_state_121('0),.gpu_debug_state_122('0),.gpu_debug_state_123('0),.gpu_debug_state_124('0),.gpu_debug_state_125('0),.gpu_debug_state_126('0),.gpu_debug_state_127('0),.gpu_debug_state_128('0),.gpu_debug_state_129('0),.gpu_debug_state_130('0),.gpu_debug_state_131('0),.gpu_debug_state_132('0),.gpu_debug_state_133('0),.gpu_debug_state_134('0),.gpu_debug_state_135('0),.gpu_debug_state_136('0),.gpu_debug_state_137('0),.gpu_debug_state_138('0),.gpu_debug_state_139('0),.gpu_debug_state_140('0),.gpu_debug_state_141('0),.gpu_debug_state_142('0),.gpu_debug_state_143('0),.gpu_debug_state_144('0),.gpu_debug_state_145('0),.gpu_debug_state_146('0),.gpu_debug_state_147('0),.gpu_debug_state_148('0),.gpu_debug_state_149('0),.gpu_debug_state_150('0),.gpu_debug_state_151('0),.gpu_debug_state_152('0),.gpu_debug_state_153('0),.gpu_debug_state_154('0),.gpu_debug_state_155('0),.gpu_debug_state_156('0),.gpu_debug_state_157('0),.gpu_debug_state_158('0),.gpu_debug_state_159('0),.gpu_debug_state_160('0),.gpu_debug_state_161('0),.gpu_debug_state_162('0),.gpu_debug_state_163('0),.gpu_debug_state_164('0),.gpu_debug_state_165('0),.gpu_debug_state_166('0),.gpu_debug_state_167('0),.gpu_debug_state_168('0),.gpu_debug_state_169('0),.gpu_debug_state_170('0),.gpu_debug_state_171('0),.gpu_debug_state_172('0),.gpu_debug_state_173('0),.gpu_debug_state_174('0),.gpu_debug_state_175('0),.gpu_debug_state_176('0),.gpu_debug_state_177('0),.gpu_debug_state_178('0),.gpu_debug_state_179('0),.gpu_debug_state_180('0),.gpu_debug_state_181('0),.gpu_debug_state_182('0),.gpu_debug_state_183('0),.gpu_debug_state_184('0),.gpu_debug_state_185('0),.gpu_debug_state_186('0),.gpu_debug_state_187('0),.gpu_debug_state_188('0),.gpu_debug_state_189('0),.gpu_debug_state_190('0),.gpu_debug_state_191('0),.gpu_debug_state_224('0),.gpu_debug_state_225('0),.gpu_debug_state_226('0),.gpu_debug_state_227('0),.gpu_debug_state_228('0),.gpu_debug_state_229('0),.gpu_debug_state_230('0),.gpu_debug_state_231('0),.gpu_debug_state_232('0),.gpu_debug_state_233('0),.gpu_debug_state_234('0),.gpu_debug_state_235('0),.gpu_debug_state_236('0),.gpu_debug_state_237('0),.gpu_debug_state_238('0),.gpu_debug_state_239('0),.gpu_debug_state_240('0),.gpu_debug_state_241('0),.gpu_debug_state_242('0),.gpu_debug_state_243('0),.gpu_debug_state_244('0),.gpu_debug_state_245('0),.gpu_debug_state_246('0),.gpu_debug_state_247('0),.gpu_debug_state_38('0),.gpu_debug_state_192('0),.gpu_debug_state_193('0),.gpu_debug_state_194('0),.gpu_debug_state_195('0),.gpu_debug_state_196('0),.gpu_debug_state_197('0),.gpu_debug_state_198('0),.gpu_debug_state_199('0),.gpu_debug_state_200('0),.gpu_debug_state_201('0),.gpu_debug_state_202('0),.gpu_debug_state_203('0),.gpu_debug_state_204('0),.gpu_debug_state_205('0),.gpu_debug_state_206('0),.gpu_debug_state_207('0),.gpu_debug_state_208('0),.gpu_debug_state_209('0),.gpu_debug_state_210('0),.gpu_debug_state_211('0),.gpu_debug_state_212('0),.gpu_debug_state_213('0),.gpu_debug_state_214('0),.gpu_debug_state_215('0),.gpu_debug_state_216('0),.gpu_debug_state_217('0),.gpu_debug_state_218('0),.gpu_debug_state_219('0),.gpu_debug_state_220('0),.gpu_debug_state_221('0),.gpu_debug_state_222('0),.gpu_debug_state_223('0),.gpu_debug_state_37('0),.gpu_debug_state_39('0),.gpu_debug_state_40('0),.gpu_debug_state_41('0),.gpu_debug_state_42('0),.gpu_debug_state_43('0),.gpu_debug_state_44('0),.gpu_debug_state_45('0),.gpu_debug_state_46('0),.gpu_debug_state_47('0),.gpu_debug_state_48('0),.gpu_debug_state_49('0),.gpu_debug_state_50('0),.gpu_debug_state_51('0),.gpu_debug_state_52('0),.gpu_debug_state_53('0),.gpu_debug_state_54('0),.gpu_debug_state_55('0),.gpu_debug_state_97('0),.gpu_debug_state_102('0),.bus_haddr_0(addr[0]),.bus_haddr_1(addr[1]),.bus_haddr_2(addr[2]),.bus_haddr_3(addr[3]),.bus_haddr_4(addr[4]),.bus_haddr_5(addr[5]),.bus_haddr_6(addr[6]),.bus_haddr_7(addr[7]),.bus_haddr_12(addr[12]),.bus_haddr_13(addr[13]),.bus_haddr_14(addr[14]),.observe_meta_s1(observe_meta_s1),.observe_meta_s2_6(observe_meta_s2_6),.observe_meta_s2_9(observe_meta_s2_9),.bus_hwdata(data_bit),.bus_htrans(trans),.read_wait(gpu_wait),.n3052_12(gpu_n3052_12),.debug_hrdata(gpu_data));
neo_gpu_debug scan(.rjc_payload(payload[639:320]),.vid_hrstn(!reset),.vid_hclk(hclk),.n6_6(reset),.n571_5(n571_5),.n579_5(n579_5),.n587_5(n587_5),.n596_6(n596_6),.n47_5(n47_5),.n613_6(n613_6),.n622_6(n622_6),.n632_7(n632_7),.n640_5(n640_5),.n649_6(n649_6),.n658_6(n658_6),.n668_7(n668_7),.n677_6(n677_6),.n687_7(n687_7),.n697_7(n697_7),.n708_8(n708_8),.n716_5(n716_5),.gpu_clk(gclk),.n237_5(reset),.bus_hwrite(wr),.scan_debug_live_96('0),.scan_debug_live_97('0),.scan_debug_live_98('0),.scan_debug_live_99('0),.scan_debug_live_100('0),.scan_debug_live_101('0),.scan_debug_live_102('0),.scan_debug_live_103('0),.scan_debug_live_104('0),.scan_debug_live_105('0),.scan_debug_live_106('0),.scan_debug_live_107('0),.scan_debug_live_108('0),.scan_debug_live_109('0),.scan_debug_live_110('0),.scan_debug_live_111('0),.scan_debug_live_112('0),.scan_debug_live_113('0),.scan_debug_live_114('0),.scan_debug_live_115('0),.scan_debug_live_116('0),.scan_debug_live_117('0),.scan_debug_live_118('0),.scan_debug_live_119('0),.scan_debug_live_120('0),.scan_debug_live_121('0),.scan_debug_live_122('0),.scan_debug_live_123('0),.scan_debug_live_124('0),.scan_debug_live_125('0),.scan_debug_live_126('0),.scan_debug_live_127('0),.scan_debug_live_128('0),.scan_debug_live_129('0),.scan_debug_live_130('0),.scan_debug_live_131('0),.scan_debug_live_132('0),.scan_debug_live_133('0),.scan_debug_live_134('0),.scan_debug_live_135('0),.scan_debug_live_136('0),.scan_debug_live_137('0),.scan_debug_live_138('0),.scan_debug_live_139('0),.scan_debug_live_140('0),.scan_debug_live_141('0),.scan_debug_live_142('0),.scan_debug_live_143('0),.scan_debug_live_144('0),.scan_debug_live_145('0),.scan_debug_live_146('0),.scan_debug_live_147('0),.scan_debug_live_148('0),.scan_debug_live_149('0),.scan_debug_live_150('0),.scan_debug_live_151('0),.scan_debug_live_152('0),.scan_debug_live_153('0),.scan_debug_live_154('0),.scan_debug_live_155('0),.scan_debug_live_156('0),.scan_debug_live_157('0),.scan_debug_live_158('0),.scan_debug_live_159('0),.scan_debug_live_160('0),.scan_debug_live_161('0),.scan_debug_live_162('0),.scan_debug_live_163('0),.scan_debug_live_164('0),.scan_debug_live_165('0),.scan_debug_live_166('0),.scan_debug_live_167('0),.scan_debug_live_168('0),.scan_debug_live_169('0),.scan_debug_live_170('0),.scan_debug_live_171('0),.scan_debug_live_172('0),.scan_debug_live_173('0),.scan_debug_live_174('0),.scan_debug_live_175('0),.scan_debug_live_176('0),.scan_debug_live_177('0),.scan_debug_live_178('0),.scan_debug_live_179('0),.scan_debug_live_180('0),.scan_debug_live_181('0),.scan_debug_live_182('0),.scan_debug_live_183('0),.scan_debug_live_184('0),.scan_debug_live_185('0),.scan_debug_live_186('0),.scan_debug_live_187('0),.scan_debug_live_188('0),.scan_debug_live_189('0),.scan_debug_live_190('0),.scan_debug_live_191('0),.scan_debug_live_192('0),.scan_debug_live_193('0),.scan_debug_live_194('0),.scan_debug_live_195('0),.scan_debug_live_196('0),.scan_debug_live_197('0),.scan_debug_live_198('0),.scan_debug_live_199('0),.scan_debug_live_200('0),.scan_debug_live_201('0),.scan_debug_live_202('0),.scan_debug_live_203('0),.scan_debug_live_204('0),.scan_debug_live_205('0),.scan_debug_live_206('0),.scan_debug_live_207('0),.scan_debug_live_208('0),.scan_debug_live_209('0),.scan_debug_live_210('0),.scan_debug_live_211('0),.scan_debug_live_212('0),.scan_debug_live_213('0),.scan_debug_live_214('0),.scan_debug_live_215('0),.scan_debug_live_216('0),.scan_debug_live_217('0),.scan_debug_live_218('0),.scan_debug_live_219('0),.scan_debug_live_220('0),.scan_debug_live_224(!reset),.up(1'b1),.scan_debug_live_0('0),.scan_debug_live_1('0),.scan_debug_live_2('0),.scan_debug_live_3('0),.scan_debug_live_5_6('0),.scan_debug_live_6('0),.scan_debug_live_7('0),.scan_debug_live_8('0),.scan_debug_live_9('0),.scan_debug_live_11('0),.scan_debug_live_13('0),.scan_debug_live_15('0),.scan_debug_live_16('0),.scan_debug_live_17('0),.scan_debug_live_18('0),.scan_debug_live_19('0),.scan_debug_live_20('0),.scan_debug_live_21('0),.scan_debug_live_22('0),.scan_debug_live_23('0),.scan_debug_live_24('0),.scan_debug_live_25('0),.scan_debug_live_26('0),.scan_debug_live_27('0),.scan_debug_live_28('0),.scan_debug_live_29('0),.scan_debug_live_30('0),.scan_debug_live_31('0),.scan_debug_live_37('0),.scan_debug_live_38('0),.scan_debug_live_39('0),.scan_debug_live_40('0),.scan_debug_live_41('0),.scan_debug_live_42('0),.scan_debug_live_43('0),.scan_debug_live_44('0),.scan_debug_live_45('0),.scan_debug_live_46('0),.scan_debug_live_47('0),.scan_debug_live_48('0),.scan_debug_live_49('0),.scan_debug_live_50('0),.scan_debug_live_51('0),.scan_debug_live_52('0),.scan_debug_live_53('0),.scan_debug_live_54('0),.scan_debug_live_55('0),.scan_debug_live_56('0),.scan_debug_live_57('0),.scan_debug_live_58('0),.scan_debug_live_59('0),.scan_debug_live_60('0),.scan_debug_live_61('0),.scan_debug_live_62('0),.scan_debug_live_63('0),.scan_debug_live_10('0),.scan_debug_live_12('0),.scan_debug_live_10_15('0),.scan_debug_live_69('0),.scan_debug_live_70('0),.scan_debug_live_71('0),.scan_debug_live_72('0),.scan_debug_live_73('0),.scan_debug_live_74('0),.scan_debug_live_75('0),.scan_debug_live_76('0),.scan_debug_live_77('0),.scan_debug_live_78('0),.scan_debug_live_79('0),.scan_debug_live_80('0),.scan_debug_live_81('0),.scan_debug_live_82('0),.scan_debug_live_83('0),.scan_debug_live_84('0),.scan_debug_live_85('0),.scan_debug_live_86('0),.scan_debug_live_87('0),.scan_debug_live_32('0),.scan_debug_live_33('0),.bus_haddr_0(addr[0]),.bus_haddr_1(addr[1]),.bus_haddr_2(addr[2]),.bus_haddr_3(addr[3]),.bus_haddr_4(addr[4]),.bus_haddr_5(addr[5]),.bus_haddr_6(addr[6]),.bus_haddr_7(addr[7]),.bus_haddr_12(addr[12]),.bus_haddr_13(addr[13]),.bus_haddr_14(addr[14]),.bus_hwdata(data_bit),.bus_htrans(trans),.read_wait(scan_wait),.n550_7(n550_7),.n560_8(n560_8),.n499_7(n499_7),.n438_11(n438_11),.n507_8(n507_8),.n445_11(n445_11),.n515_8(n515_8),.n452_8(n452_8),.n524_9(n524_9),.n460_9(n460_9),.n532_8(n532_8),.n467_8(n467_8),.n541_9(n541_9),.n475_9(n475_9),.n483_8(n483_8),.n492_9(n492_9),.observe_meta_s1(observe_meta_s1),.observe_meta_s2_6(observe_meta_s2_6),.observe_meta_s2_9(observe_meta_s2_9),.scan_debug_hrdata(scan_data));
 task write_reg(input integer page,input integer offset);
 begin
  @(negedge hclk);addr=(page<<12)|offset;wr=1;trans=1;data_bit=1;
  @(negedge hclk);wr=0;trans=0;
  repeat(2)@(negedge hclk);data_bit=0;
 end endtask
 task read_reg(input integer page,input integer offset,output reg[31:0] value);
 begin
  @(negedge hclk);addr=(page<<12)|offset;wr=0;trans=1;
  repeat(3)@(posedge hclk);#1;value=page==5?gpu_data:scan_data;
  @(negedge hclk);trans=0;repeat(2)@(negedge hclk);
 end endtask
 task snapshot(input integer page);
 integer tries;reg[31:0] before_count,after_count;
 begin
  read_reg(page,12,before_count);write_reg(page,4);
  after_count=before_count;tries=0;
  while(after_count==before_count && tries<100)begin read_reg(page,12,after_count);tries=tries+1;end
  if(after_count!=before_count+1)$fatal(1,"snapshot count page%0d got%h before%h",page,after_count,before_count);
  read_reg(page,4,after_count);
  if(after_count[1:0]!=2)$fatal(1,"snapshot not ready page%0d status%h",page,after_count);
 end endtask
 task verify_page(input integer page,input [319:0] expected);
 integer word_index,offset;reg[31:0] value;
 begin
  for(word_index=0;word_index<10;word_index=word_index+1)begin
   offset=word_index<8 ? 32+4*word_index:16+4*(word_index-8);
   read_reg(page,offset,value);
   if(value!==expected[word_index*32+:32])
    $fatal(1,"payload page%0d word%0d got%h expected%h",page,word_index,value,expected[word_index*32+:32]);
   checks=checks+1;
  end
 end endtask
 initial begin
  repeat(5)@(negedge hclk);reset=0;repeat(12)@(negedge hclk);
  read_reg(5,0,got);if(got!==32'h4e474442)$fatal(1,"GPU ID %h",got);
  read_reg(6,0,got);if(got!==32'h4e474442)$fatal(1,"SCAN ID %h",got);
  for(trial=0;trial<6;trial=trial+1)begin
   for(i=0;i<20;i=i+1)next_payload[i*32+:32]=$random;
   if(trial==3)begin hp=7.1;gp=4.9;end
   // Prime captures old payload, and only then publishes the frozen new one.
   manual_pending=1;snapshot(5);
   if(manual_pending)$fatal(1,"prime not observed in GPU domain");
   snapshot(5);snapshot(6);
   verify_page(5,payload[319:0]);verify_page(6,payload[639:320]);
   verify_page(6,payload[639:320]);verify_page(5,payload[319:0]);
  end
  // GPU stopped: AHB must not invent a fresh acknowledgement or capture.
  @(negedge gclk);gpu_run=0;
  read_reg(5,12,seq0);write_reg(5,4);repeat(15)@(negedge hclk);
  read_reg(5,12,seq1);if(seq1!==seq0)$fatal(1,"ACK while GPU stopped");
  read_reg(5,4,got);if(!got[0])$fatal(1,"missing busy while GPU stopped");
  gpu_run=1;repeat(20)@(negedge hclk);
  read_reg(5,12,seq1);if(seq1!==seq0+1)$fatal(1,"resume count");
  verify_page(5,payload[319:0]);
  // Reset while a request is pending clears both transport-valid flags.
  @(negedge gclk);gpu_run=0;write_reg(6,4);reset=1;
  repeat(4)@(negedge hclk);gpu_run=1;repeat(5)@(negedge hclk);reset=0;
  repeat(12)@(negedge hclk);
  read_reg(5,4,got);if(got[1:0]!=0)$fatal(1,"GPU stale valid after reset");
  read_reg(6,4,got);if(got[1:0]!=0)$fatal(1,"SCAN stale valid after reset");
  snapshot(5);snapshot(6);verify_page(5,payload[319:0]);verify_page(6,payload[639:320]);
  $display("RESULT PASS checks=%0d nominal80_75=1 drift=1 stopped=1 reset_pending=1",checks);$finish;
 end
 initial begin #2000000;$fatal(1,"transport watchdog");end
endmodule
