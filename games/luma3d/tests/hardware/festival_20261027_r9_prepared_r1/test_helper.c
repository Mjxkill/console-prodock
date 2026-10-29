#define main inspector_main
#include "runtime_inspect.c"
#undef main
#include <assert.h>
int main(void){
 assert(rect_valid(0,1600,800,480,768000));assert(rect_valid(1u<<20,1600,800,480,768000));
 assert(rect_valid(0,1600,400,240,192000));assert(rect_valid(48*1600+144*2,1600,512,400,409600));
 assert(!rect_valid(0,1600,801,480,768960));assert(!rect_valid(0,1600,800,481,769600));
 assert(!rect_valid(2u<<20,1600,1,1,2));assert(!rect_valid(0,1598,800,480,768000));
 assert(!rect_valid(0,1600,UINT32_MAX,480,1));assert(!rect_valid(0,1600,800,UINT32_MAX,1));
 assert(!rect_valid(0,1600,800,480,768004));assert(!rect_valid(3,1600,400,240,192000));
 assert(!rect_valid(400,1600,800,480,768000));assert(!rect_valid(479*1600,1600,400,2,1600));
 assert(!memory_region_valid(14u<<20,4));assert(!memory_region_valid(15u<<20,4));
 assert(memory_region_valid(22u<<20,384000));assert(!memory_region_valid((32u<<20)-4,8));
 puts("HELPER_RECT_PASS valid_native_scaled_roi=1 overflow_alignment_console_rejected=1 no_device_access=1");return 0;
}
