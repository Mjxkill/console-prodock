/* SPDX-License-Identifier: MIT */
#ifndef LUMA_AUDIO_H
#define LUMA_AUDIO_H

/* PC: call init after SDL video initialization. Board builds expose silent stubs.
 * Return 1 on success, 0 if unavailable, -1 for a play/load error.
 * The caller selects only ready cues. Diagnostic audition of generated cues
 * must be explicit; this module never edits or approves the manifest.
 * WAV loading/conversion occurs on the game thread, only on a cue change.
 */
int luma_audio_init(void);
int luma_audio_play(const char *wav_path, int loop);
void luma_audio_pause(int paused);
void luma_audio_transition(unsigned milliseconds);
void luma_audio_shutdown(void);
const char *luma_audio_error(void);

#endif
