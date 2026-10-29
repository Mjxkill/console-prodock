/* SPDX-License-Identifier: MIT */
#include "luma_audio.h"

#ifdef LUMA_HOST
#include <SDL.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define AUDIO_RATE 48000
#define AUDIO_MAX_SOURCE (128u * 1024u * 1024u)
typedef struct {
    Sint16 *pcm;
    Uint32 frames, position;
    int loop;
    float gain, target, step;
    unsigned ramp;
} AudioVoice;
static struct {
    SDL_AudioDeviceID device;
    AudioVoice voices[2];
    unsigned current, transition_ms, pause_ramp;
    float pause_gain, pause_step;
    int paused, owns_subsystem;
    uint64_t frames, nonzero_samples;
    char path[1024], error[256];
} state;

static void ramp(AudioVoice *voice, float target, unsigned frames)
{
    voice->ramp = frames ? frames : 1;
    voice->target = target;
    voice->step = (target - voice->gain) / voice->ramp;
}

static Sint16 quantize(float value)
{
    if (value > 32767.0f) return 32767;
    if (value < -32768.0f) return -32768;
    return (Sint16)value;
}

static void callback(void *unused, Uint8 *bytes, int byte_count)
{
    (void)unused;
    Sint16 *out = (Sint16 *)bytes;
    unsigned frames = (unsigned)byte_count / 4;
    SDL_memset(bytes, 0, (size_t)byte_count);
    for (unsigned i = 0; i < frames; ++i) {
        if (state.pause_ramp) {
            state.pause_gain += state.pause_step;
            if (!--state.pause_ramp) state.pause_gain = state.paused ? 0.0f : 1.0f;
        }
        if (state.paused && !state.pause_ramp) continue;
        float left = 0, right = 0;
        for (unsigned n = 0; n < 2; ++n) {
            AudioVoice *voice = &state.voices[n];
            if (!voice->pcm) continue;
            if (voice->ramp) {
                voice->gain += voice->step;
                if (!--voice->ramp) voice->gain = voice->target;
            }
            if (voice->gain <= 0) continue;
            if (voice->position >= voice->frames) {
                if (voice->loop) voice->position = 0;
                else continue;
            }
            left += voice->pcm[voice->position * 2] * voice->gain;
            right += voice->pcm[voice->position * 2 + 1] * voice->gain;
            ++voice->position;
        }
        float master = 0.65f * state.pause_gain;
        out[i * 2] = quantize(left * master);
        out[i * 2 + 1] = quantize(right * master);
        state.nonzero_samples += out[i * 2] != 0;
        state.nonzero_samples += out[i * 2 + 1] != 0;
    }
    state.frames += frames;
}

static int error(const char *message)
{
    SDL_snprintf(state.error, sizeof(state.error), "%s", message);
    return -1;
}

int luma_audio_init(void)
{
    if (state.device) return 1;
    SDL_memset(&state, 0, sizeof(state));
    state.owns_subsystem = !(SDL_WasInit(SDL_INIT_AUDIO) & SDL_INIT_AUDIO);
    if (state.owns_subsystem && SDL_InitSubSystem(SDL_INIT_AUDIO)) {
        error(SDL_GetError());
        return 0;
    }
    SDL_AudioSpec desired, obtained;
    SDL_zero(desired);
    desired.freq = AUDIO_RATE;
    desired.format = AUDIO_S16SYS;
    desired.channels = 2;
    desired.samples = 1024;
    desired.callback = callback;
    state.device = SDL_OpenAudioDevice(NULL, 0, &desired, &obtained, 0);
    if (!state.device) {
        error(SDL_GetError());
        if (state.owns_subsystem) SDL_QuitSubSystem(SDL_INIT_AUDIO);
        state.owns_subsystem = 0;
        return 0;
    }
    state.transition_ms = 1800;
    state.pause_gain = 1.0f;
    SDL_PauseAudioDevice(state.device, 0);
    return 1;
}

int luma_audio_play(const char *wav_path, int loop)
{
    if (!state.device) return 0;
    if (!wav_path || !*wav_path) {
        SDL_LockAudioDevice(state.device);
        for (unsigned n = 0; n < 2; ++n) ramp(&state.voices[n], 0, state.transition_ms * 48);
        state.path[0] = 0;
        SDL_UnlockAudioDevice(state.device);
        return 1;
    }
    if (loop && state.voices[state.current].loop && !strcmp(wav_path, state.path)) return 1;
    if (strlen(wav_path) >= sizeof(state.path)) return error("Audio path is too long");
    SDL_AudioSpec source_spec;
    Uint8 *source = NULL;
    Uint32 source_size = 0;
    if (!SDL_LoadWAV(wav_path, &source_spec, &source, &source_size)) return error(SDL_GetError());
    if (!source_size || source_size > AUDIO_MAX_SOURCE) {
        SDL_FreeWAV(source);
        return error("Audio WAV is empty or exceeds the PC per-track limit");
    }
    SDL_AudioCVT conversion;
    if (SDL_BuildAudioCVT(&conversion, source_spec.format, source_spec.channels, source_spec.freq,
                         AUDIO_S16SYS, 2, AUDIO_RATE) < 0) {
        SDL_FreeWAV(source);
        return error(SDL_GetError());
    }
    size_t capacity = (size_t)source_size * (unsigned)conversion.len_mult;
    if (capacity > INT_MAX) {
        SDL_FreeWAV(source);
        return error("Converted audio exceeds SDL buffer limit");
    }
    conversion.buf = SDL_malloc(capacity);
    if (!conversion.buf) { SDL_FreeWAV(source); return error("Cannot allocate audio track"); }
    conversion.len = (int)source_size;
    SDL_memcpy(conversion.buf, source, source_size);
    SDL_FreeWAV(source);
    if (conversion.needed && SDL_ConvertAudio(&conversion) < 0) {
        SDL_free(conversion.buf);
        return error(SDL_GetError());
    }
    Uint32 converted = (Uint32)(conversion.needed ? conversion.len_cvt : conversion.len);
    if (!converted || converted % 4) {
        SDL_free(conversion.buf);
        return error("Converted audio is not aligned stereo PCM16");
    }
    SDL_LockAudioDevice(state.device);
    unsigned slot = state.voices[0].gain <= state.voices[1].gain ? 0 : 1;
    AudioVoice *voice = &state.voices[slot];
    SDL_free(voice->pcm);
    SDL_memset(voice, 0, sizeof(*voice));
    voice->pcm = (Sint16 *)conversion.buf;
    voice->frames = converted / 4;
    voice->loop = !!loop;
    ramp(voice, 1, state.transition_ms * 48);
    ramp(&state.voices[1-slot], 0, state.transition_ms * 48);
    state.current = slot;
    SDL_snprintf(state.path, sizeof(state.path), "%s", wav_path);
    state.error[0] = 0;
    SDL_UnlockAudioDevice(state.device);
    return 1;
}

void luma_audio_pause(int paused)
{
    if (!state.device || state.paused == !!paused) return;
    SDL_LockAudioDevice(state.device);
    state.paused = !!paused;
    state.pause_ramp = 2400; /* 50 ms fade, then freeze the music playheads. */
    state.pause_step = ((paused ? 0.0f : 1.0f) - state.pause_gain) / state.pause_ramp;
    SDL_UnlockAudioDevice(state.device);
}

void luma_audio_transition(unsigned milliseconds)
{
    if (milliseconds > 10000) milliseconds = 10000;
    if (state.device) SDL_LockAudioDevice(state.device);
    state.transition_ms = milliseconds;
    if (state.device) SDL_UnlockAudioDevice(state.device);
}

void luma_audio_shutdown(void)
{
    if (state.device) SDL_CloseAudioDevice(state.device);
    state.device = 0;
    for (unsigned n = 0; n < 2; ++n) {
        SDL_free(state.voices[n].pcm);
        state.voices[n].pcm = NULL;
    }
    if (state.owns_subsystem) SDL_QuitSubSystem(SDL_INIT_AUDIO);
    state.owns_subsystem = 0;
}

const char *luma_audio_error(void) { return state.error; }

#ifdef LUMA_AUDIO_SMOKE
int main(int argc, char **argv)
{
    if (argc != 2) { fprintf(stderr, "Usage: %s diagnostic.wav\n", argv[0]); return 2; }
    SDL_setenv("SDL_AUDIODRIVER", "dummy", 1);
    if (!luma_audio_init()) { fprintf(stderr, "%s\n", luma_audio_error()); return 1; }
    luma_audio_transition(30);
    if (luma_audio_play(argv[1], 1) != 1) { fprintf(stderr, "%s\n", luma_audio_error()); luma_audio_shutdown(); return 1; }
    SDL_Delay(120);
    SDL_LockAudioDevice(state.device);
    int looping = state.voices[state.current].position < state.voices[state.current].frames;
    SDL_UnlockAudioDevice(state.device);
    luma_audio_pause(1);
    SDL_Delay(100);
    SDL_LockAudioDevice(state.device);
    Uint32 paused_position = state.voices[state.current].position;
    SDL_UnlockAudioDevice(state.device);
    SDL_Delay(70);
    SDL_LockAudioDevice(state.device);
    int frozen = paused_position == state.voices[state.current].position;
    SDL_UnlockAudioDevice(state.device);
    luma_audio_pause(0);
    SDL_Delay(100);
    if (luma_audio_play(argv[1], 0) != 1) { luma_audio_shutdown(); return 1; }
    SDL_Delay(100);
    SDL_LockAudioDevice(state.device);
    int oneshot = state.voices[state.current].frames >= 4800 ||
                  state.voices[state.current].position == state.voices[state.current].frames;
    SDL_UnlockAudioDevice(state.device);
    luma_audio_play(NULL, 0);
    SDL_Delay(100);
    SDL_LockAudioDevice(state.device);
    uint64_t samples_after_stop = state.nonzero_samples;
    SDL_UnlockAudioDevice(state.device);
    SDL_Delay(70);
    SDL_LockAudioDevice(state.device);
    uint64_t frames = state.frames, samples = state.nonzero_samples;
    int stopped = samples_after_stop == samples && state.voices[0].gain == 0 && state.voices[1].gain == 0;
    SDL_UnlockAudioDevice(state.device);
    luma_audio_shutdown();
    if (!looping || !oneshot || !frozen || !stopped || !frames || !samples) { fprintf(stderr, "FAIL callback/loop/oneshot/pause/stop\n"); return 1; }
    printf("PASS SDL dummy: %llu frames, %llu nonzero samples, loop/oneshot, pause frozen, stop silent; no physical audio qualification\n",
           (unsigned long long)frames, (unsigned long long)samples);
    return 0;
}
#endif

#else
int luma_audio_init(void) { return 0; }
int luma_audio_play(const char *path, int loop) { (void)path; (void)loop; return 0; }
void luma_audio_pause(int paused) { (void)paused; }
void luma_audio_transition(unsigned ms) { (void)ms; }
void luma_audio_shutdown(void) {}
const char *luma_audio_error(void) { return "No qualified board audio backend"; }
#endif
