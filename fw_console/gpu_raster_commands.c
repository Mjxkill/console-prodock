// Legacy raster command encoding, shared by firmware and host render tests.
// Packet layout and invalid-field markers are part of the existing GPU ABI.
// Configuration, submission and hardware error reporting belong to callers.
#include "gpu.h"

gpu_command gpu_make_raster_state(unsigned page,unsigned zpage,unsigned flags,
                                  unsigned alpha,unsigned color)
{
    gpu_command c={{GPU_RASTER_STATE<<24,page|(zpage<<4),flags,alpha,color,0,0,0}};
    if(page>15 || zpage>15)c.words[1]=~0U;
    return c;
}

gpu_command gpu_make_texture(unsigned page,unsigned x,unsigned y,unsigned width,
                             unsigned height,unsigned mode_u,unsigned mode_v)
{
    gpu_command c={{GPU_TEXTURE<<24,page,(x<<16)|y,(width<<16)|height,mode_u|(mode_v<<2),0,0,0}};
    if(x>65535 || y>65535 || width>65535 || height>65535 || mode_u>2 || mode_v>2)c.words[4]=~0U;
    return c;
}

gpu_command gpu_make_plane(unsigned op,const gpu_raster_plane *p)
{
    gpu_command c={{op<<24,(uint32_t)p->origin,(uint32_t)p->dx,(uint32_t)p->dy,
        0x10000U|((uint32_t)((uint64_t)p->origin>>32)&65535),0,0,0}};
    if(p->origin<-(1LL<<47) || p->origin>=(1LL<<47))c.words[4]=~0U;
    return c;
}

gpu_command gpu_make_raster_clear(unsigned flags,unsigned color,unsigned depth)
{
    gpu_command c={{GPU_RASTER_CLEAR<<24,flags,color,depth,0,0,0,0}};
    return c;
}
