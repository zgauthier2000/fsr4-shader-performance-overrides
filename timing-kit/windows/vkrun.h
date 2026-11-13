// SPDX-License-Identifier: GPL-2.0-or-later
// vkrun.h: the timing kit's Vulkan run (vkrun.c), for DLL slots named vk-...: AMD's FidelityFX upscaler DLL for Vulkan
// (amd_fidelityfx_upscaler_vk.dll, loaded by amd_fidelityfx_loader_vk.dll) timed as fsr4time.c's RunOne times the Direct3D 12 one.
// vkrun.c is built with the FidelityFX SDK 2.4.0 headers (they differ from the ones fsr4time.c uses), so it gets what it shares with
// fsr4time.c through this table.
#pragma once
#include <stdbool.h>
#include <stdint.h>

struct VkRunHost {
    void (*Say)(const char* fmt, ...);
    void (*World)(float wx, float wy, float* rgb);
    float (*Halton)(int i, int b);
    uint16_t (*Half)(float f);
    // the picture checks of the run's last frame: hash (FNV-1a over the rows), the block records and the reference pictures (as HashOutput)
    uint64_t (*Picture)(const uint8_t* data, unsigned pitch, unsigned ow, unsigned oh, const char* key, const char* label, const char* pkey);
    bool all_presets, size800;
    unsigned ven, dev;      // the graphics the Direct3D 12 runs use (DXGI's high-performance adapter): the Vulkan run picks the same
    int warm, timed, phases_max;
};
int RunOneVk(const struct VkRunHost* h, const char* name, bool quick);
