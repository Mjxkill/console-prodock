/* Generated test witnesses; never linked into the game. */
typedef struct {unsigned world;const char *action,*target;float x,y,dx,dy;unsigned count;} PuzzleStep;
static const PuzzleStep puzzle_steps[]={
{26,"rotate","beam_mirror_a",432,432,0,0,1},
{26,"exit","post_exit",0,0,0,0,1},
{35,"rotate","beam_mirror_a",272,240,0,0,1},
{35,"rotate","beam_mirror_c",560,368,0,0,1},
{35,"rotate","beam_mirror_d",560,560,0,0,1},
{35,"rotate","beam_mirror_f",720,432,0,0,1},
{35,"rotate","beam_mirror_i",720,560,0,0,1},
{35,"push","shade_crate_a",464,688,1,0,3},
{35,"push","shade_crate_b",176,688,1,0,3},
{35,"interact","post_answers",0,0,0,0,1},
{35,"exit","post_exit",0,0,0,0,1},
};
typedef struct {unsigned first,last,begin,end;} PuzzleGroup;
static const PuzzleGroup puzzle_groups[]={
{26,26,0,2},
{35,35,2,11},
};
