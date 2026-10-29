LUMA — art production and import

Current reviewed integration
----------------------------
The game consumes the ComfyUI atlas and terrain. acceptance.json records the
exact reviewed source set, output hashes, exclusions and reproducible import
command. The actual integrated reference is ../build/village_r5.png: the first
village has curved paths, houses, a greenhouse, foreground trees and residents.
The engine separately verified its GPU compositor at 800x480 and 1280x720.
Those software results are distinct from the frozen hardware trial packages.

The hero has a coherent four-phase frontal walk using distinct support legs.
The opposite support was derived by a local ComfyUI masked leg transform that
preserves the upper body and lantern. This is recorded as derived artwork,
not a second independent generated pose. Back/right/left static orientations
are now present as player_n/player_e/player_w and reviewed at native size in
hero_directions_review.png. Their engine integration and directional walk
cycles are pending. The left profile is explicitly a mirrored right profile.
The corrected scooter is a kick scooter; the glider/parachute use the same
illustrated human hero. Rejected photorealistic and inconsistent attempts are
retained as originals but excluded from the imported atlas.

Do not infer acceptance from the existence of a source PNG. Generation,
segmentation, import, visual review and actual integration are separate steps.

Authorized generator: the existing ComfyUI instance on gx10-2 only.
No imagegen, hosted API, package installation, service restart, or interruption
of another session. The pipeline never calls /interrupt or deletes a queue.
Only this art worker submits heavy GPU jobs; music jobs are coordinated with it.

Production sequence
-------------------
1. Read API availability and installed node/model schemas:
   python3 games/luma_adventure/art/comfy_pipeline.py --discover
2. Generate one sheet at a time (each call preserves originals and its job ID):
   python3 games/luma_adventure/art/comfy_pipeline.py --only terrain_sheet
   python3 games/luma_adventure/art/comfy_pipeline.py --only scenery_sheet
   python3 games/luma_adventure/art/comfy_pipeline.py --only hero_sheet
   python3 games/luma_adventure/art/comfy_pipeline.py --only cast_sheet
   python3 games/luma_adventure/art/comfy_pipeline.py --only travel_sheet
3. Inspect every source PNG at its original resolution. Verify subject count,
   intended cell placement, clean magenta isolation, readable silhouettes,
   unclipped figures, coherent camera and lighting. Do not import failed cells.
4. Import only visually reviewed sheets; include all reviewed sprite sheets in
   each later import because atlas.png is rebuilt deterministically:
   Use the complete import_command in acceptance.json. Omitting accepted
   sheets would silently remove their sprites from the rebuilt atlas.
   Then run each additional_import_commands entry to pack and merge the
   reviewed sanctuary mechanisms and indoor materials. The merge verifies
   that every pre-existing sprite and outdoor material keeps its pixels.
5. Inspect atlas_review.png and terrain.png. Have the engine worker rebuild and
   verify actual game previews at 800x480 and 1280x720 before hardware testing.

If a job timed out, --resume uses its saved prompt_id; it does not intentionally
resubmit an in-flight job. A source PNG already present is never overwritten by
the generator. A failed source requires a new explicit variant name and seed.

Runtime contract
----------------
atlas.json: {image:"atlas.png",sprites:[{id,x,y,w,h,anchor_x,anchor_y,...}]}.
RGBA sprites use cells64x64, floor anchor(32,62). Terrain uses32x32 RGB cells and
terrain.json adds char for the world ASCII mapping. H is grass below authored
buildings, t is forest ground; the engine must keep tree canopies over that tile.
Original sheets are retained at their native 1024x1024 or 512x512. Cropping,
native ComfyUI BiRefNet segmentation, resizing and packing are
an import step, not claimed as a separate generated image.

The first pass maps shrine_lit/chest_open aliases to the corresponding base
sprite. These aliases are explicitly recorded; they are not separate artwork.
Custom residents and guardians have distinct sprite IDs in the authored worlds.

The sanctuary set adds crate, switch, plate, target, lamp and turret, with
real switch_lit/plate_lit/target_lit/lamp_lit artwork. Sequences use lamp states.
The indoor_floor and indoor_wall keys each have four material variants. Their
source borders are excluded, and their32px repetition is reviewed separately.
Sources, rejected close-up, segmentation, state selection and import records
are preserved under source/candidates/sanctuary_r1/. Actual engine captures
must still verify these assets after the content rebuild.

Evidence
--------
brief.json records direction, exact prompts, seeds, cell order and dimensions.
workflows/ stores the exact API graph submitted for each image.
provenance/ records installed models/nodes, server stats, job response/history,
timestamps, workflow SHA-256 and generated-file SHA-256.
The API discovery, rather than an assumed remote model name, selects the local
Qwen-Image2512 or Qwen-Image-Edit2509 + matching text encoder/VAE and optional
4-step Lightning LoRA. Full-quality edits retain their exact step count.
If the verified model set is absent, generation stops with a precise error.

YuE2 sources copied into provenance are read-only snapshots of the installed
native workflow and node definition for the music worker. Stable Audio is not
used. Two YuE2 pilots and six regional ambiences have actually been generated;
their native outputs, exact workflows and histories are under music_staging/.
The audio worker owns their PCM imports and technical QA under ../audio/.
The rejected clipped nuages attempt is retained beside its passing revision.
Technical QA does not establish musical quality: listening remains pending.
