// SPDX-License-Identifier: GPL-2.0-or-later
// fsr4time.exe: the Windows timing kit. Times FSR 4.1.1 as a game runs it, through AMD's FidelityFX API on
// Direct3D 12, with each upscaler DLL found in the folders next to it (dlls\<name>\amd_fidelityfx_upscaler_dx12.dll),
// on made-up frames. No game, no OptiScaler. Derived from research/pruning/fsr4img.c.
//
//   fsr4time.exe            runs every DLL in dlls\ at 1080p, 1440p and 4K output, still and moving picture, twice
//                           (the DLLs in name order, then in reverse order), prints a summary, saves it as
//                           results-<time>.txt and offers to send it
//   fsr4time.exe --run <name> <results file>     (used by the first form: one DLL, in a process of its own)
//   fsr4time.exe --quick    1080p and 4K only
//   fsr4time.exe --once     every DLL timed once instead of twice
//   fsr4time.exe --no-questions   asks nothing at the end and sends nothing
//   fsr4time.exe --send-test   sends one message that says it is a test (to check that sending works)
//
// What is timed: the GPU time of one upscale call (prepass, 12 model passes, postpass and the small shaders around
// them), from a timestamp before to one after, 200 calls back to back after 40 to warm up. For a lossy DLL the
// two kinds of frame are also given apart. The summary gives a fingerprint of the picture each DLL produces from
// the still scene and from the moving one (the run's last frame) and names the first DLL above it that produced the same picture, byte for byte.
//
// Build (llvm-mingw): x86_64-w64-mingw32-clang -std=c11 -O1 -I<FidelityFX>/api/include -I<FidelityFX>/upscalers/include
//                     fsr4time.c -o fsr4time.exe -ld3d12 -ldxgi -ldxguid -lwinhttp -ladvapi32 -static
// hook.inc is written by mkhook.py (the address results are sent to, scrambled; see ../submit.py).
#define COBJMACROS
#define WIDL_C_INLINE_WRAPPERS
#define WIN32_LEAN_AND_MEAN
#define _WINDOWS
#include <windows.h>
#include <winhttp.h>
#include <d3d12.h>
#include <dxgi1_6.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "ffx_api.h"
#include "ffx_api_loader.h"
#include "ffx_upscale.h"
#include "dx12/ffx_api_dx12.h"

#define KIT_VERSION "windows 2026-10-13, experimental"
#define WARM 40
#define TIMED 200
#define PHASES 16

static FILE* out;      // the results file of this run
static void Say(const char* fmt, ...) {
    va_list a;
    va_start(a, fmt); vprintf(fmt, a); va_end(a);
    if (out) { va_start(a, fmt); vfprintf(out, fmt, a); va_end(a); fflush(out); }
    fflush(stdout);
}

#define CHECK(x)                                                                                              \
    do {                                                                                                      \
        HRESULT hr_ = (x);                                                                                    \
        if (FAILED(hr_)) { Say("FAILED %s: 0x%08lx (line %d)\n", #x, (unsigned long)hr_, __LINE__); exit(1); } \
    } while (0)

static ID3D12Device* device;
static ID3D12CommandQueue* queue;
static ID3D12CommandAllocator* allocator;
static ID3D12GraphicsCommandList* list;
static ID3D12Fence* fence;
static UINT64 fence_value;
static HANDLE fence_event;

static void Submit(void) {
    CHECK(ID3D12GraphicsCommandList_Close(list));
    ID3D12CommandList* lists[] = {(ID3D12CommandList*)list};
    ID3D12CommandQueue_ExecuteCommandLists(queue, 1, lists);
    CHECK(ID3D12CommandQueue_Signal(queue, fence, ++fence_value));
    CHECK(ID3D12Fence_SetEventOnCompletion(fence, fence_value, fence_event));
    WaitForSingleObject(fence_event, INFINITE);
    CHECK(ID3D12CommandAllocator_Reset(allocator));
    CHECK(ID3D12GraphicsCommandList_Reset(list, allocator, NULL));
}

static ID3D12Resource* Texture(DXGI_FORMAT format, UINT w, UINT h, bool uav) {
    D3D12_HEAP_PROPERTIES heap = {.Type = D3D12_HEAP_TYPE_DEFAULT};
    D3D12_RESOURCE_DESC desc = {.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D, .Width = w, .Height = h, .DepthOrArraySize = 1,
                                .MipLevels = 1, .Format = format, .SampleDesc = {1, 0},
                                .Flags = uav ? D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS : D3D12_RESOURCE_FLAG_NONE};
    ID3D12Resource* r;
    CHECK(ID3D12Device_CreateCommittedResource(device, &heap, D3D12_HEAP_FLAG_NONE, &desc, D3D12_RESOURCE_STATE_COMMON, NULL,
                                               &IID_ID3D12Resource, (void**)&r));
    return r;
}

static ID3D12Resource* Buffer(D3D12_HEAP_TYPE type, UINT64 size) {
    D3D12_HEAP_PROPERTIES heap = {.Type = type};
    D3D12_RESOURCE_DESC desc = {.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER, .Width = size, .Height = 1, .DepthOrArraySize = 1,
                                .MipLevels = 1, .SampleDesc = {1, 0}, .Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR};
    ID3D12Resource* r;
    CHECK(ID3D12Device_CreateCommittedResource(device, &heap, D3D12_HEAP_FLAG_NONE, &desc,
                                               type == D3D12_HEAP_TYPE_UPLOAD ? D3D12_RESOURCE_STATE_GENERIC_READ : D3D12_RESOURCE_STATE_COPY_DEST,
                                               NULL, &IID_ID3D12Resource, (void**)&r));
    return r;
}

static struct FfxApiResource Resource(ID3D12Resource* r, uint32_t format, uint32_t state) {
    D3D12_RESOURCE_DESC desc = ID3D12Resource_GetDesc(r);
    struct FfxApiResource o = {0};
    o.resource = r; o.state = state;
    o.description.type = FFX_API_RESOURCE_TYPE_TEXTURE2D; o.description.format = format;
    o.description.width = (uint32_t)desc.Width; o.description.height = desc.Height; o.description.depth = 1; o.description.mipCount = 1;
    o.description.usage = state == FFX_API_RESOURCE_STATE_UNORDERED_ACCESS ? FFX_API_RESOURCE_USAGE_UAV : 0;
    return o;
}

static uint16_t Half(float f) {
    uint32_t x;
    memcpy(&x, &f, 4);
    const uint32_t sign = (x >> 16) & 0x8000u;
    const int exp = (int)((x >> 23) & 0xffu) - 127 + 15;
    if (exp <= 0) return (uint16_t)sign;
    return (uint16_t)(sign | ((uint32_t)exp << 10) | ((x >> 13) & 0x3ffu));
}

// The made-up picture: a function of a point of the "world", periodic with period 192 pixels of the output, so
// that a camera moving a whole number of pixels per frame repeats after 16 frames. Soft gradients, thin lines
// and fine texture, to give the model something like a game picture to work on.
static uint32_t Hash(uint32_t x, uint32_t y) {
    uint32_t h = x * 0x9E3779B1u ^ y * 0x85EBCA77u;
    h ^= h >> 15; h *= 0x2C1B3C6Du; h ^= h >> 12;
    return h;
}
static void World(float wx, float wy, float* rgb) {
    wx -= 192.0f * (float)(int)(wx / 192.0f); if (wx < 0) wx += 192.0f;
    wy -= 192.0f * (float)(int)(wy / 192.0f); if (wy < 0) wy += 192.0f;
    const uint32_t cx = (uint32_t)(wx / 6.0f), cy = (uint32_t)(wy / 6.0f);
    const float n = (float)(Hash(cx, cy) & 255u) / 255.0f, g = wx / 192.0f, v = wy / 192.0f;
    const float tri = g < 0.5f ? 2 * g : 2 - 2 * g, trv = v < 0.5f ? 2 * v : 2 - 2 * v;
    const bool line = ((uint32_t)wx % 24u) < 2u || ((uint32_t)(wx + wy) % 32u) < 2u;
    float r = 0.15f + 0.5f * tri + 0.12f * n, gr = 0.12f + 0.45f * trv + 0.10f * n, b = 0.2f + 0.3f * (1 - tri) + 0.15f * n;
    if (line) { r = 0.9f; gr = 0.85f; b = 0.7f; }
    rgb[0] = r; rgb[1] = gr; rgb[2] = b;
}
static float Halton(int i, int b) {
    float f = 1, r = 0;
    while (i > 0) { f /= (float)b; r += f * (float)(i % b); i /= b; }
    return r;
}

static void UploadRows(ID3D12Resource* tex, UINT w, UINT h, UINT bpp, const uint8_t* src) {
    const UINT pitch = (w * bpp + 255) & ~255u;
    ID3D12Resource* up = Buffer(D3D12_HEAP_TYPE_UPLOAD, (UINT64)pitch * h);
    uint8_t* data;
    CHECK(ID3D12Resource_Map(up, 0, NULL, (void**)&data));
    for (UINT y = 0; y < h; ++y) memcpy(data + (size_t)y * pitch, src + (size_t)y * w * bpp, (size_t)w * bpp);
    ID3D12Resource_Unmap(up, 0, NULL);
    D3D12_RESOURCE_DESC desc = ID3D12Resource_GetDesc(tex);
    D3D12_TEXTURE_COPY_LOCATION dst = {.pResource = tex, .Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX};
    D3D12_TEXTURE_COPY_LOCATION s = {.pResource = up, .Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT};
    s.PlacedFootprint.Footprint.Format = desc.Format; s.PlacedFootprint.Footprint.Width = w; s.PlacedFootprint.Footprint.Height = h;
    s.PlacedFootprint.Footprint.Depth = 1; s.PlacedFootprint.Footprint.RowPitch = pitch;
    ID3D12GraphicsCommandList_CopyTextureRegion(list, &dst, 0, 0, 0, &s, NULL);
    Submit();
    ID3D12Resource_Release(up);
}

// When a DLL's two runs give different pictures, the summary also says how different. Whole frames of every run would be gigabytes, so the first run
// leaves a small record per 16x16-pixel block of its last frame (a hash and the sum of its color values) in a file, and the second run compares its
// own blocks with it and reports: how many blocks differ, the area they lie in, and the largest shift of a block's mean value.
#define BLK 16
struct BlockRec { uint64_t hash; float sum; };
static float HalfToFloat(uint16_t h) {
    const int e = (h >> 10) & 31, m = h & 1023;
    float v = e == 0 ? (float)m / 1024.0f / 16384.0f : e == 31 ? 0.0f : (1.0f + (float)m / 1024.0f) * (e >= 15 ? (float)(1u << (e - 15)) : 1.0f / (float)(1u << (15 - e)));
    return (h & 0x8000) ? -v : v;
}
static void CompareBlocks(const uint8_t* data, UINT pitch, UINT ow, UINT oh, const char* key, uint64_t* whole) {
    const UINT bw = (ow + BLK - 1) / BLK, bh = (oh + BLK - 1) / BLK, n = bw * bh;
    struct BlockRec* now = (struct BlockRec*)calloc(n, sizeof(*now));
    for (UINT i = 0; i < n; ++i) now[i].hash = 1469598103934665603ull;
    for (UINT y = 0; y < oh; ++y) {
        const uint8_t* row = data + (size_t)y * pitch;
        for (UINT x = 0; x < ow; ++x) {
            struct BlockRec* b = &now[(y / BLK) * bw + x / BLK];
            for (int c = 0; c < 8; ++c) { b->hash ^= row[x * 8 + c]; b->hash *= 1099511628211ull; }
            const uint16_t* px = (const uint16_t*)(row + x * 8);
            b->sum += HalfToFloat(px[0]) + HalfToFloat(px[1]) + HalfToFloat(px[2]);
        }
    }
    uint64_t kh = 1469598103934665603ull;
    for (const char* q = key; *q; ++q) { kh ^= (uint8_t)*q; kh *= 1099511628211ull; }
    char file[64];
    snprintf(file, sizeof(file), "blocks-%016llx.tmp", (unsigned long long)kh);
    FILE* f = fopen(file, "rb");
    if (!f) {      // the first run: leave the record
        f = fopen(file, "wb");
        if (f) { fwrite(now, sizeof(*now), n, f); fclose(f); }
    } else {       // the second run: compare
        struct BlockRec* was = (struct BlockRec*)calloc(n, sizeof(*was));
        const size_t got = fread(was, sizeof(*was), n, f);
        fclose(f);
        if (getenv("FSR4TIME_POKE")) { now[bw + 5].hash ^= 1; now[bw + 5].sum += 0.768f; now[2 * bw + 7].hash ^= 1; *whole ^= 1; }      // test switch: pretend two blocks came out differently
        if (got == n) {
            UINT nd = 0, x0 = bw, y0 = bh, x1 = 0, y1 = 0;
            double worst = 0;
            for (UINT i = 0; i < n; ++i)
                if (was[i].hash != now[i].hash) {
                    const UINT bx = i % bw, by = i / bw;
                    ++nd; if (bx < x0) x0 = bx; if (bx > x1) x1 = bx; if (by < y0) y0 = by; if (by > y1) y1 = by;
                    double d = ((double)now[i].sum - (double)was[i].sum) / (BLK * BLK * 3); if (d < 0) d = -d;
                    if (d > worst) worst = d;
                }
            // key | blocks that differ | blocks in all | area in pixels: x0, y0, x1, y1 | largest shift of a block's mean value (1 = full scale)
            if (nd) Say("D|%s|%u|%u|%u|%u|%u|%u|%.6f\n", key, nd, n, x0 * BLK, y0 * BLK, (x1 + 1) * BLK - 1 < ow - 1 ? (x1 + 1) * BLK - 1 : ow - 1, (y1 + 1) * BLK - 1 < oh - 1 ? (y1 + 1) * BLK - 1 : oh - 1, worst);
        }
        free(was);
    }
    free(now);
}

static void DeleteBlockRecords(void) {      // the records the first runs leave for the second ones
    WIN32_FIND_DATAA fd;
    HANDLE fh = FindFirstFileA("blocks-*.tmp", &fd);
    if (fh != INVALID_HANDLE_VALUE) { do DeleteFileA(fd.cFileName); while (FindNextFileA(fh, &fd)); FindClose(fh); }
}

static uint64_t HashOutput(ID3D12Resource* output, UINT ow, UINT oh, const char* key) {
    const UINT pitch = (ow * 8 + 255) & ~255u;
    ID3D12Resource* rb = Buffer(D3D12_HEAP_TYPE_READBACK, (UINT64)pitch * oh);
    D3D12_TEXTURE_COPY_LOCATION src = {.pResource = output, .Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX};
    D3D12_TEXTURE_COPY_LOCATION dst = {.pResource = rb, .Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT};
    dst.PlacedFootprint.Footprint.Format = DXGI_FORMAT_R16G16B16A16_FLOAT; dst.PlacedFootprint.Footprint.Width = ow;
    dst.PlacedFootprint.Footprint.Height = oh; dst.PlacedFootprint.Footprint.Depth = 1; dst.PlacedFootprint.Footprint.RowPitch = pitch;
    D3D12_RESOURCE_BARRIER b = {.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION};
    b.Transition.pResource = output; b.Transition.StateBefore = D3D12_RESOURCE_STATE_UNORDERED_ACCESS; b.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_SOURCE;
    ID3D12GraphicsCommandList_ResourceBarrier(list, 1, &b);
    ID3D12GraphicsCommandList_CopyTextureRegion(list, &dst, 0, 0, 0, &src, NULL);
    b.Transition.StateBefore = D3D12_RESOURCE_STATE_COPY_SOURCE; b.Transition.StateAfter = D3D12_RESOURCE_STATE_UNORDERED_ACCESS;
    ID3D12GraphicsCommandList_ResourceBarrier(list, 1, &b);
    Submit();
    uint8_t* data;
    CHECK(ID3D12Resource_Map(rb, 0, NULL, (void**)&data));
    uint64_t h = 1469598103934665603ull;
    for (UINT y = 0; y < oh; ++y)
        for (UINT x = 0; x < ow * 8; ++x) { h ^= data[(size_t)y * pitch + x]; h *= 1099511628211ull; }
    if (key) CompareBlocks(data, pitch, ow, oh, key, &h);
    ID3D12Resource_Unmap(rb, 0, NULL);
    ID3D12Resource_Release(rb);
    return h;
}

static void Message(uint32_t type, const wchar_t* message) { Say("  FFX %s: %ls\n", type == FFX_API_MESSAGE_TYPE_ERROR ? "error" : "warning", message); }
static int CmpD(const void* a, const void* b) { double x = *(const double*)a, y = *(const double*)b; return x < y ? -1 : x > y; }
static double Median(double* v, int n) { qsort(v, n, sizeof(double), CmpD); return n ? v[n / 2] : 0; }

static void CreateDevice(char* gpu, size_t gpu_len) {
    IDXGIFactory6* f6 = NULL;
    IDXGIAdapter1* ad = NULL;
    if (SUCCEEDED(CreateDXGIFactory1(&IID_IDXGIFactory6, (void**)&f6)))
        IDXGIFactory6_EnumAdapterByGpuPreference(f6, 0, DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE, &IID_IDXGIAdapter1, (void**)&ad);
    CHECK(D3D12CreateDevice((IUnknown*)ad, D3D_FEATURE_LEVEL_12_0, &IID_ID3D12Device, (void**)&device));
    snprintf(gpu, gpu_len, "?");
    if (ad) {
        DXGI_ADAPTER_DESC1 d;
        LARGE_INTEGER umd = {0};
        IDXGIAdapter1_GetDesc1(ad, &d);
        IDXGIAdapter1_CheckInterfaceSupport(ad, &IID_IDXGIDevice, &umd);
        snprintf(gpu, gpu_len, "%ls (PCI %04x:%04x, %u MB), driver %u.%u.%u.%u", d.Description, d.VendorId, d.DeviceId, (unsigned)(d.DedicatedVideoMemory >> 20),
                 (unsigned)(umd.QuadPart >> 48) & 0xffff, (unsigned)(umd.QuadPart >> 32) & 0xffff, (unsigned)(umd.QuadPart >> 16) & 0xffff, (unsigned)umd.QuadPart & 0xffff);
    }
    D3D12_COMMAND_QUEUE_DESC qd = {.Type = D3D12_COMMAND_LIST_TYPE_DIRECT};
    CHECK(ID3D12Device_CreateCommandQueue(device, &qd, &IID_ID3D12CommandQueue, (void**)&queue));
    CHECK(ID3D12Device_CreateCommandAllocator(device, D3D12_COMMAND_LIST_TYPE_DIRECT, &IID_ID3D12CommandAllocator, (void**)&allocator));
    CHECK(ID3D12Device_CreateCommandList(device, 0, D3D12_COMMAND_LIST_TYPE_DIRECT, allocator, NULL, &IID_ID3D12GraphicsCommandList, (void**)&list));
    CHECK(ID3D12Device_CreateFence(device, 0, D3D12_FENCE_FLAG_NONE, &IID_ID3D12Fence, (void**)&fence));
    fence_event = CreateEventA(NULL, FALSE, FALSE, NULL);
}

// One DLL (the one next to the exe), every size and scene. Lines "R|..." are what the summary is made from.
static int RunOne(const char* name, bool quick) {
    char gpu[256];
    CreateDevice(gpu, sizeof(gpu));
    HMODULE loader = LoadLibraryA("amd_fidelityfx_loader_dx12.dll");
    if (!loader) { Say("R|%s|FAILED|no amd_fidelityfx_loader_dx12.dll next to the program\n", name); return 1; }
    ffxFunctions ffx;
    ffxLoadFunctions(&ffx, loader);
    uint64_t count = 0, ids[32];
    const char* names[32];
    struct ffxQueryDescGetVersions versions = {0};
    versions.header.type = FFX_API_QUERY_DESC_TYPE_GET_VERSIONS; versions.createDescType = FFX_API_CREATE_CONTEXT_DESC_TYPE_UPSCALE;
    versions.device = device; versions.outputCount = &count;
    ffx.Query(NULL, &versions.header);
    if (count > 32) count = 32;
    versions.versionIds = ids; versions.versionNames = names;
    ffx.Query(NULL, &versions.header);
    // every FSR 4 version the DLL offers on this GPU is timed. AMD's 4.1.1 DLL offers one here; a DLL that carries several
    // variants of the model (say one per GPU generation) gets a block of lines for each, in the order the DLL lists them
    uint64_t vid[8];
    const char* vname[8];
    int nv = 0;
    for (uint64_t i = 0; i < count; ++i)
        if (nv < 8 && !strncmp(names[i], "4.", 2)) { vid[nv] = ids[i]; vname[nv++] = names[i]; }
    if (getenv("FSR4TIME_TWICE") && nv == 1) { vid[1] = vid[0]; vname[1] = vname[0]; nv = 2; }      // for testing the lines of a DLL with two variants: the one version, listed twice
    if (!nv) { Say("R|%s|FAILED|this DLL offers no FSR 4 on this GPU (%llu versions listed)\n", name, (unsigned long long)count); return 1; }
    Say("G|%s\n", gpu);

    static const struct { UINT ow, oh, rw, rh; } sizes[] = {{1920, 1080, 1130, 636}, {2560, 1440, 1506, 848}, {3840, 2160, 2260, 1272}};
    ID3D12QueryHeap* qh;
    D3D12_QUERY_HEAP_DESC qhd = {.Type = D3D12_QUERY_HEAP_TYPE_TIMESTAMP, .Count = 2};
    CHECK(ID3D12Device_CreateQueryHeap(device, &qhd, &IID_ID3D12QueryHeap, (void**)&qh));
    ID3D12Resource* qbuf = Buffer(D3D12_HEAP_TYPE_READBACK, 16);
    UINT64 freq = 0;
    CHECK(ID3D12CommandQueue_GetTimestampFrequency(queue, &freq));

    for (int vi = 0; vi < nv; ++vi) {
        const uint64_t chosen = vid[vi];
        const char* chosen_name = vname[vi];
        char label[64], idtext[40] = "";      // with one variant the lines carry the folder's name alone, as before
        if (nv == 1) snprintf(label, sizeof(label), "%s", name);
        else { snprintf(label, sizeof(label), "%.40s, variant %d of %d", name, vi + 1, nv); snprintf(idtext, sizeof(idtext), ", id %llx", (unsigned long long)chosen); }
        for (int si = 0; si < 3; ++si) {
            if (quick && si == 1) continue;
            const UINT ow = sizes[si].ow, oh = sizes[si].oh, rw = sizes[si].rw, rh = sizes[si].rh;
            struct ffxCreateBackendDX12Desc backend = {0};
            backend.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_DX12; backend.device = device;
            struct ffxOverrideVersion ov = {0};
            ov.header.type = FFX_API_DESC_TYPE_OVERRIDE_VERSION; ov.versionId = chosen; ov.header.pNext = &backend.header;
            ID3D12Resource* color[PHASES];
            for (int p = 0; p < PHASES; ++p) color[p] = Texture(DXGI_FORMAT_R16G16B16A16_FLOAT, rw, rh, false);
            ID3D12Resource* depth = Texture(DXGI_FORMAT_R32_FLOAT, rw, rh, false);
            ID3D12Resource* motion = Texture(DXGI_FORMAT_R16G16_FLOAT, rw, rh, false);
            ID3D12Resource* output = Texture(DXGI_FORMAT_R16G16B16A16_FLOAT, ow, oh, true);
            uint16_t* cbuf = malloc((size_t)rw * rh * 8);
            float* dbuf = malloc((size_t)rw * rh * 4);
            uint16_t* mbuf = malloc((size_t)rw * rh * 4);
            for (size_t i = 0; i < (size_t)rw * rh; ++i) dbuf[i] = 0.5f;
            UploadRows(depth, rw, rh, 4, (const uint8_t*)dbuf);
            const float sx = (float)rw / (float)ow, sy = (float)rh / (float)oh;
            for (int scene = 0; scene < 2; ++scene) {            // 0: nothing moves; 1: the camera pans 12, 6 output pixels per frame
                const int vx = scene ? 12 : 0, vy = scene ? 6 : 0;
                for (size_t i = 0; i < (size_t)rw * rh; ++i) { mbuf[2 * i] = Half((float)vx * sx); mbuf[2 * i + 1] = Half((float)vy * sy); }
                UploadRows(motion, rw, rh, 4, (const uint8_t*)mbuf);
                float jx[PHASES], jy[PHASES];
                for (int p = 0; p < PHASES; ++p) {
                    jx[p] = Halton(p + 1, 2) - 0.5f; jy[p] = Halton(p + 1, 3) - 0.5f;
                    for (UINT y = 0; y < rh; ++y)
                        for (UINT x = 0; x < rw; ++x) {
                            float rgb[3];
                            World(((float)x + 0.5f - jx[p]) / sx - 0.5f + (float)(vx * p), ((float)y + 0.5f - jy[p]) / sy - 0.5f + (float)(vy * p), rgb);
                            uint16_t* q = cbuf + ((size_t)y * rw + x) * 4;
                            q[0] = Half(rgb[0]); q[1] = Half(rgb[1]); q[2] = Half(rgb[2]); q[3] = Half(1.0f);
                        }
                    UploadRows(color[p], rw, rh, 8, (const uint8_t*)cbuf);
                }
                struct ffxCreateContextDescUpscale create = {0};
                create.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_UPSCALE; create.header.pNext = &ov.header;
                create.flags = FFX_UPSCALE_ENABLE_HIGH_DYNAMIC_RANGE | FFX_UPSCALE_ENABLE_AUTO_EXPOSURE;
                create.maxRenderSize.width = ow; create.maxRenderSize.height = oh; create.maxUpscaleSize.width = ow; create.maxUpscaleSize.height = oh;
                create.fpMessage = Message;
                ffxContext context = NULL;
                ffxReturnCode_t rc = ffx.CreateContext(&context, &create.header, NULL);
                if (rc != FFX_API_RETURN_OK) { Say("R|%s|FAILED|create context %d at %ux%u\n", label, (int)rc, ow, oh); goto next_variant; }
                struct ffxQueryGetProviderVersion provider = {0};
                provider.header.type = FFX_API_QUERY_DESC_TYPE_GET_PROVIDER_VERSION;
                ffx.Query(&context, &provider.header);
                static double ms[TIMED], even[TIMED], odd[TIMED];
                int ne = 0, no = 0;
                for (int frame = 0; frame < WARM + TIMED; ++frame) {
                    const int p = frame % PHASES;
                    struct ffxDispatchDescUpscale d = {0};
                    d.header.type = FFX_API_DISPATCH_DESC_TYPE_UPSCALE; d.commandList = list;
                    d.color = Resource(color[p], FFX_API_SURFACE_FORMAT_R16G16B16A16_FLOAT, FFX_API_RESOURCE_STATE_COMMON);
                    d.depth = Resource(depth, FFX_API_SURFACE_FORMAT_R32_FLOAT, FFX_API_RESOURCE_STATE_COMMON);
                    d.motionVectors = Resource(motion, FFX_API_SURFACE_FORMAT_R16G16_FLOAT, FFX_API_RESOURCE_STATE_COMMON);
                    d.output = Resource(output, FFX_API_SURFACE_FORMAT_R16G16B16A16_FLOAT, FFX_API_RESOURCE_STATE_UNORDERED_ACCESS);
                    d.jitterOffset.x = jx[p]; d.jitterOffset.y = jy[p];
                    d.motionVectorScale.x = d.motionVectorScale.y = 1.0f;
                    d.renderSize.width = rw; d.renderSize.height = rh; d.upscaleSize.width = ow; d.upscaleSize.height = oh;
                    d.enableSharpening = false; d.sharpness = 0.5f; d.frameTimeDelta = 10.0f; d.preExposure = 1.0f; d.reset = frame == 0;
                    d.cameraNear = 0.05f; d.cameraFar = 3000.0f; d.cameraFovAngleVertical = 0.75f; d.viewSpaceToMetersFactor = 1.0f;
                    ID3D12GraphicsCommandList_EndQuery(list, qh, D3D12_QUERY_TYPE_TIMESTAMP, 0);
                    rc = ffx.Dispatch(&context, &d.header);
                    if (rc != FFX_API_RETURN_OK) { Say("R|%s|FAILED|dispatch %d at %ux%u\n", label, (int)rc, ow, oh); goto next_variant; }
                    ID3D12GraphicsCommandList_EndQuery(list, qh, D3D12_QUERY_TYPE_TIMESTAMP, 1);
                    ID3D12GraphicsCommandList_ResolveQueryData(list, qh, D3D12_QUERY_TYPE_TIMESTAMP, 0, 2, qbuf, 0);
                    Submit();
                    if (frame >= WARM) {
                        UINT64* t;
                        D3D12_RANGE rr = {0, 16};
                        CHECK(ID3D12Resource_Map(qbuf, 0, &rr, (void**)&t));
                        const double v = (double)(t[1] - t[0]) * 1000.0 / (double)freq;
                        ID3D12Resource_Unmap(qbuf, 0, NULL);
                        ms[frame - WARM] = v;
                        if (jx[p] < 0) odd[no++] = v; else even[ne++] = v;      // a lossy DLL skips the model where the jitter's x is negative
                    }
                }
                double sum = 0, fastest = ms[0];
                for (int i = 0; i < TIMED; ++i) { sum += ms[i]; if (ms[i] < fastest) fastest = ms[i]; }
                const double med = Median(ms, TIMED), me = Median(even, ne), mo = Median(odd, no);
                char key[256];      // names this DLL, version, size and scene: the same in its two runs
                snprintf(key, sizeof(key), "%s|%s%s|%ux%u|%s", label, provider.versionName ? provider.versionName : chosen_name, idtext, ow, oh, scene ? "moving" : "still");
                const uint64_t h = HashOutput(output, ow, oh, key);      // the last frame of the run: the still scene's picture, or the moving scene's after the same 240 frames
                // name | version name the DLL reports | output | render | scene | mean | median | median where jitter x >= 0 | where < 0 | fastest | picture hash
                Say("R|%s|%s%s|%ux%u|%ux%u|%s|%.4f|%.4f|%.4f|%.4f|%.4f|%016llx\n", label, provider.versionName ? provider.versionName : chosen_name, idtext, ow, oh, rw, rh,
                    scene ? "moving" : "still", sum / TIMED, med, me, mo, fastest, (unsigned long long)h);
                ffx.DestroyContext(&context, NULL);
            }
            for (int p = 0; p < PHASES; ++p) ID3D12Resource_Release(color[p]);
            ID3D12Resource_Release(depth); ID3D12Resource_Release(motion); ID3D12Resource_Release(output);
            free(cbuf); free(dbuf); free(mbuf);
        }
    next_variant:;
    }
    return 0;
}

// ---- the first form: every DLL in dlls\, each in a process of its own (the loader takes the DLL next to the exe)
#include "hook.inc"      // _hook_bytes[], _hook_key[]: where results are sent, stored scrambled (see mkhook.py)

static void HookUrl(wchar_t* host, wchar_t* path) {
    char u[256];
    const int n = (int)sizeof(_hook_bytes);
    for (int i = 0; i < n; ++i) u[i] = (char)(_hook_bytes[n - 1 - i] ^ _hook_key[i % (int)sizeof(_hook_key)] ^ (uint8_t)(i * 7));
    u[n] = 0;
    const char* h = strstr(u, "://") + 3;
    const char* p = strchr(h, '/');
    int i = 0;
    for (const char* c = h; c < p; ++c) host[i++] = (wchar_t)*c;
    host[i] = 0; i = 0;
    for (const char* c = p; *c; ++c) path[i++] = (wchar_t)*c;
    path[i] = 0;
}

static bool SendOne(const char* text, int len) {
    static char body[8192];
    int n = snprintf(body, sizeof(body), "{\"allowed_mentions\":{\"parse\":[]},\"content\":\"");
    for (int i = 0; i < len; ++i) {
        const char c = text[i];
        if (c == '"' || c == '\\') { body[n++] = '\\'; body[n++] = c; }
        else if (c == '\n') { body[n++] = '\\'; body[n++] = 'n'; }
        else if ((unsigned char)c >= 32) body[n++] = c;
    }
    n += snprintf(body + n, sizeof(body) - n, "\"}");
    wchar_t host[128], path[256];
    HookUrl(host, path);
    bool ok = false;
    HINTERNET s = WinHttpOpen(L"fsr4-timing-kit", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    HINTERNET c = s ? WinHttpConnect(s, host, INTERNET_DEFAULT_HTTPS_PORT, 0) : NULL;
    HINTERNET r = c ? WinHttpOpenRequest(c, L"POST", path, NULL, WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, WINHTTP_FLAG_SECURE) : NULL;
    if (r && WinHttpSendRequest(r, L"Content-Type: application/json\r\n", (DWORD)-1, body, (DWORD)n, (DWORD)n, 0) && WinHttpReceiveResponse(r, NULL)) {
        DWORD code = 0, len2 = sizeof(code);
        WinHttpQueryHeaders(r, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER, NULL, &code, &len2, NULL);
        ok = code >= 200 && code < 300;
    }
    if (r) WinHttpCloseHandle(r);
    if (c) WinHttpCloseHandle(c);
    if (s) WinHttpCloseHandle(s);
    return ok;
}

// The channel takes 2000 characters a message: the summary goes in pieces that end at a line end.
static bool Send(const char* text) {
    const int total = (int)strlen(text);
    bool ok = true;
    for (int at = 0; at < total && ok;) {
        int len = total - at > 1800 ? 1800 : total - at;
        if (at + len < total)
            while (len > 1 && text[at + len - 1] != '\n') --len;
        ok = SendOne(text + at, len);
        at += len;
        Sleep(600);
    }
    return ok;
}

struct Row { char name[64], ver[64], size[16], scene[8]; double mean, med, even, odd; char hash[20]; int n; double mean2; bool hashdiff; char diff[160]; };
// the figure the summary gives: the mean of a DLL's two runs (or its one run, if the other failed)
static double Val(const struct Row* w) { return w->n == 2 ? 0.5 * (w->mean + w->mean2) : w->mean; }

int main(int argc, char** argv) {
    char base[MAX_PATH];
    GetModuleFileNameA(NULL, base, MAX_PATH);
    *(strrchr(base, '\\') + 1) = 0;
    SetCurrentDirectoryA(base);
    if (argc >= 4 && !strcmp(argv[1], "--run")) {
        out = fopen(argv[3], "a");
        return RunOne(argv[2], argc > 4 && !strcmp(argv[4], "quick"));
    }
    if (argc > 1 && !strcmp(argv[1], "--send-test")) {      // for the project: checks that sending works, with a message that says what it is
        const bool ok = Send("Test message from the timing kit's Windows program (kit " KIT_VERSION "), sent by the project while setting it up.\nNot a result: please ignore.");
        FILE* t = fopen("send-test.txt", "w");
        if (t) { fprintf(t, "%s\n", ok ? "sent" : "failed"); fclose(t); }
        printf("%s\n", ok ? "sent" : "failed");
        return ok ? 0 : 1;
    }
    bool quick = false, unattended = false, once = false;
    for (int a = 1; a < argc; ++a) {
        if (!strcmp(argv[a], "--quick")) quick = true;
        if (!strcmp(argv[a], "--no-questions")) unattended = true;
        if (!strcmp(argv[a], "--once")) once = true;
    }
    SYSTEMTIME st;
    GetLocalTime(&st);
    char results[MAX_PATH], raw[MAX_PATH];
    snprintf(results, sizeof(results), "%sresults-%04d%02d%02d-%02d%02d%02d.txt", base, st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);
    snprintf(raw, sizeof(raw), "%sresults-raw.txt", base);
    DeleteFileA(raw);
    printf("FSR 4.1.1 timing kit (%s). This takes a few minutes; please leave the PC alone and close games,\nbrowsers and video while it runs.\n\n", KIT_VERSION);

    // the DLLs: AMD's shaders first (the reference), then the rest in name order
    char names[16][64];
    int nd = 0;
    WIN32_FIND_DATAA fd;
    HANDLE f = FindFirstFileA("dlls\\*", &fd);
    if (f != INVALID_HANDLE_VALUE) {
        do {
            if ((fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) && fd.cFileName[0] != '.' && nd < 16) snprintf(names[nd++], 64, "%s", fd.cFileName);
        } while (FindNextFileA(f, &fd));
        FindClose(f);
    }
    for (int i = 0; i < nd; ++i)
        for (int j = i + 1; j < nd; ++j)
            if (strcmp(names[j], names[i]) < 0) { char t[64]; strcpy(t, names[i]); strcpy(names[i], names[j]); strcpy(names[j], t); }
    if (!nd) { printf("No folders in dlls\\ next to the program.\n"); return 1; }
    // two rounds, the second in reverse order: a DLL's two runs then sit at mirrored places in the sequence, so a drift
    // over the run (the card warming up, something starting in the background) shows as a difference between them
    DeleteBlockRecords();      // none left over from a run that was cut short
    for (int k = 0; k < (once ? nd : 2 * nd); ++k) {
        const int i = k < nd ? k : 2 * nd - 1 - k;
        char src[MAX_PATH], cmd[1024];
        snprintf(src, sizeof(src), "dlls\\%s\\amd_fidelityfx_upscaler_dx12.dll", names[i]);
        if (!CopyFileA(src, "amd_fidelityfx_upscaler_dx12.dll", FALSE)) { printf("%s: no amd_fidelityfx_upscaler_dx12.dll in that folder, skipped\n", names[i]); continue; }
        printf("%s (run %d of %d) ...\n", names[i], k < nd ? 1 : 2, once ? 1 : 2); fflush(stdout);
        snprintf(cmd, sizeof(cmd), "\"%sfsr4time.exe\" --run \"%s\" \"%s\"%s", base, names[i], raw, quick ? " quick" : "");
        STARTUPINFOA si = {.cb = sizeof(si)};
        PROCESS_INFORMATION pi;
        if (!CreateProcessA(NULL, cmd, NULL, NULL, TRUE, 0, NULL, NULL, &si, &pi)) { printf("could not start a run for %s\n", names[i]); continue; }
        WaitForSingleObject(pi.hProcess, INFINITE);
        CloseHandle(pi.hProcess); CloseHandle(pi.hThread);
    }
    DeleteFileA("amd_fidelityfx_upscaler_dx12.dll");
    DeleteBlockRecords();

    // summary
    static struct Row rows[256];
    int nr = 0;
    char gpu[256] = "?", line[512];
    static char summary[16384];
    int sn = 0;
    FILE* r = fopen(raw, "r");
    static char fails[1024];
    int fl = 0;
    while (r && fgets(line, sizeof(line), r)) {
        line[strcspn(line, "\r\n")] = 0;
        if (line[0] == 'G' && line[1] == '|') snprintf(gpu, sizeof(gpu), "%s", line + 2);
        if (line[0] == 'D' && line[1] == '|') {      // how a DLL's second run differed from its first (see CompareBlocks)
            char dn[64], dv[64], ds[16], dc[8]; unsigned nd, nb, x0, y0, x1, y1; double worst;
            if (sscanf(line, "D|%63[^|]|%63[^|]|%15[^|]|%7[^|]|%u|%u|%u|%u|%u|%u|%lf", dn, dv, ds, dc, &nd, &nb, &x0, &y0, &x1, &y1, &worst) == 11)
                for (int j = 0; j < nr; ++j)
                    if (!strcmp(rows[j].name, dn) && !strcmp(rows[j].ver, dv) && !strcmp(rows[j].size, ds) && !strcmp(rows[j].scene, dc))
                        snprintf(rows[j].diff, sizeof(rows[j].diff), ": %u of %u blocks of %dx%d pixels differ, within x %u..%u y %u..%u, largest shift of a block's mean %.6f of full scale", nd, nb, BLK, BLK, x0, x1, y0, y1, worst);
            continue;
        }
        if (line[0] != 'R' || line[1] != '|') continue;
        if (strstr(line, "|FAILED|")) { fl += snprintf(fails + fl, sizeof(fails) - fl, "%s\n", line + 2); continue; }
        struct Row* w = &rows[nr];
        char render[16];
        double fastest;
        if (nr < 256 && sscanf(line, "R|%63[^|]|%63[^|]|%15[^|]|%15[^|]|%7[^|]|%lf|%lf|%lf|%lf|%lf|%19s", w->name, w->ver, w->size, render, w->scene, &w->mean, &w->med, &w->even,
                               &w->odd, &fastest, w->hash) == 11) {
            struct Row* first = NULL;      // this DLL's first run at this size and scene, if this line is its second
            for (int j = 0; j < nr && !first; ++j)
                if (!strcmp(rows[j].name, w->name) && !strcmp(rows[j].size, w->size) && !strcmp(rows[j].scene, w->scene) && rows[j].n == 1) first = &rows[j];
            if (first) {
                first->n = 2; first->mean2 = w->mean; first->even = 0.5 * (first->even + w->even); first->odd = 0.5 * (first->odd + w->odd);
                first->hashdiff = strcmp(first->hash, w->hash) != 0;
            } else { w->n = 1; w->hashdiff = false; ++nr; }
        }
    }
    if (r) fclose(r);
    OSVERSIONINFOEXW vi = {.dwOSVersionInfoSize = sizeof(vi)};
    typedef LONG(WINAPI * RtlGetVersionFn)(OSVERSIONINFOEXW*);
    RtlGetVersionFn rgv = (RtlGetVersionFn)(void*)GetProcAddress(GetModuleHandleA("ntdll.dll"), "RtlGetVersion");
    if (rgv) rgv(&vi);
    char cpu[128] = "?";
    DWORD cl = sizeof(cpu);
    RegGetValueA(HKEY_LOCAL_MACHINE, "HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0", "ProcessorNameString", RRF_RT_REG_SZ, NULL, cpu, &cl);
    const bool wine = GetProcAddress(GetModuleHandleA("ntdll.dll"), "wine_get_version") != NULL;
#define ADD(...) sn += snprintf(summary + sn, sizeof(summary) - sn, __VA_ARGS__)
    ADD("kit %s\nGPU: %s\nsystem: Windows %lu.%lu build %lu%s; CPU: %s\n", KIT_VERSION, gpu, vi.dwMajorVersion, vi.dwMinorVersion, vi.dwBuildNumber, wine ? " (Wine/Proton)" : "", cpu);
    ADD("upscaler time per frame, ms: mean (for a lossy DLL also: frame that runs the model / skipped frame); vs the first\n");
    if (once) ADD("each DLL was timed once (--once)\n");
    else ADD("each DLL is timed twice (all in order, then all in reverse order); the figure is the mean of the two, and both are\ngiven where they differ by more than 3%%\n");
    for (int i = 0; i < nr; ++i) {
        const struct Row* w = &rows[i];
        const struct Row* ref = NULL;
        for (int j = 0; j < nr; ++j)
            if (!strcmp(rows[j].size, w->size) && !strcmp(rows[j].scene, w->scene)) { ref = &rows[j]; break; }
        if (i == 0 || strcmp(rows[i - 1].name, w->name)) ADD("%s [%s]\n", w->name, w->ver);
        ADD("  %s %-6s %.3f", w->size, w->scene, Val(w));
        if (w->even > 1.25 * w->odd || w->odd > 1.25 * w->even) ADD(" (%.3f / %.3f)", w->even > w->odd ? w->even : w->odd, w->even > w->odd ? w->odd : w->even);
        if (ref && ref != w) {
            ADD("  %+.0f%%", 100.0 * Val(w) / Val(ref) - 100.0);
        }
        if (w->n == 2 && (w->mean > 1.03 * w->mean2 || w->mean2 > 1.03 * w->mean)) ADD("  [two runs: %.3f, %.3f]", w->mean, w->mean2);
        if (w->n == 1 && !once) ADD("  [one run only]");
        {
            // the picture's fingerprint (the run's last frame), and the first DLL above that produced the same one
            const struct Row* same = NULL;
            for (int j = 0; j < i && !same; ++j)
                if (!strcmp(rows[j].size, w->size) && !strcmp(rows[j].scene, w->scene) && !strcmp(rows[j].hash, w->hash)) same = &rows[j];
            ADD("  picture %s", w->hash);
            if (w->hashdiff) ADD(" (NOT the same picture in its two runs%s)", w->diff);
            if (same) ADD(" = %s", same->name);
            else if (ref && ref != w) ADD(" (differs from those above)");
        }
        ADD("\n");
    }
    if (fl) ADD("did not run:\n%s", fails);
    printf("\n=== summary\n%s", summary);
    if (!unattended) {
        char in[256];
        printf("\nOptional: if you have looked at OptiScaler's overlay in a game, what upscaler time (ms) did it show with AMD's file\nand with this project's? One line, for example:   3.8 2.9 Cyberpunk 2077, 4K Balanced\n(Enter to skip) > ");
        fflush(stdout);
        if (fgets(in, sizeof(in), stdin) && in[0] != '\n' && in[0] != '\r') { in[strcspn(in, "\r\n")] = 0; ADD("in a game (tester, AMD ms / ours ms / where): %.200s\n", in); }
    }
    FILE* o = fopen(results, "w");
    if (o) { fputs(summary, o); fclose(o); }
    printf("\nSaved as %s\n", results);
    if (!unattended) {
        char in[16];
        printf("\nSend this summary (and nothing else) to the project's results channel? [Y/n] ");
        fflush(stdout);
        if (fgets(in, sizeof(in), stdin) && in[0] != 'n' && in[0] != 'N') {
            // optional: a name for the project's thank-you list; sent with the summary only if one is typed
            char name[128], clean[48]; int k = 0;
            printf("\nThank you for testing. Your help is a valued part of this project.\nIf you would like to be named on the project's thank-you page, type a name or nickname. It would be published there.\n(Optional. Enter to skip, and nothing but the summary is sent) > ");
            fflush(stdout);
            if (fgets(name, sizeof(name), stdin))
                for (const char* c = name; *c && *c != '\r' && *c != '\n' && k < 40; ++c)
                    if ((unsigned char)*c >= 32 && !strchr("`*_~|<>@#\\\"", *c) && !(*c == ' ' && (k == 0 || clean[k - 1] == ' '))) clean[k++] = *c;
            while (k > 0 && clean[k - 1] == ' ') --k;
            clean[k] = 0;
            if (k) ADD("thank-you list (the tester asked to be named): %s\n", clean);
            if (getenv("FSR4TIME_DRYSEND")) { FILE* t = fopen(getenv("FSR4TIME_DRYSEND"), "w"); if (t) { fputs(summary, t); fclose(t); } printf("Test: written to %s, nothing sent.\n", getenv("FSR4TIME_DRYSEND")); }      // for testing: the text that would be sent goes to this file instead
            else printf(Send(summary) ? "Sent. Thank you: your help is a valued part of this project.\n" : "Could not send it. Please post the results file on the project's GitHub page or Discord instead.\n");
        }
        printf("\nPress Enter to close.");
        fflush(stdout);
        fgets(in, sizeof(in), stdin);
    }
    return 0;
}
