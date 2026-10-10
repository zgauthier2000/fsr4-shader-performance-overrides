// SPDX-License-Identifier: GPL-2.0-or-later
// fsr4cap.c of bbport (https://github.com/deadinside28/bloodborne_pc, tools/fsr4cap, GPL-2.0-or-later)
// with an "image" mode added: per-frame color from img/color_NNN.raw (RGBA16F) and jitter from
// img/jitter.txt, sharpening off; capture hooks stubbed out. If img/motion_NNN.raw (RG16F, render
// pixels) and img/depth_NNN.raw (R32F) exist they are used for that frame (gen_motion.py writes
// them); otherwise motion is zero and depth constant.
//   fsr4img.exe 4.1.1 2260x1272 3840x2160 32 image
// Build: x86_64-w64-mingw32-gcc -std=c11 -O1 -I<FidelityFX SDK>/Kits/FidelityFX/api/include
//   -I<...>/upscalers/include fsr4img.c -o fsr4img.exe -ld3d12 -ldxguid -static
// Environment variables: FSR_IMG_DIR (input folder next to the exe, default img), FSR_KEEP=N (also
// write the last N frames as output_WxH_fNNN.raw), and, for reaching other shader versions
// (dll/test/run_all_variants.sh), FSR_CTX_FLAGS, FSR_DISP_FLAGS, FSR_SHARPEN (0 or 1).
// bbport: fsr4cap.exe — runs AMD's FSR 4 upscaler DLL through the FidelityFX API on D3D12 (under
// Wine/Proton with vkd3d-proton) on synthetic inputs, for recording what it does (docs/upscaler.md,
// FSR 4.1.1). Step 1: list the upscaler versions, create a context with a chosen version, run
// frames, read back the output.
//
//   fsr4cap.exe [version substring, default FSR4] [render WxH] [output WxH] [frames] [noise]
// noise: the benchmark's pseudo-random inputs (tools/fsr4_bench.cpp, BENCH_NOISE) and the output
// after the last frame in output_<output WxH>.raw (RGBA16F rows), for comparing the replay.
// The loader (amd_fidelityfx_loader_dx12.dll) and the upscaler DLL are next to the exe.
#define COBJMACROS
#define WIDL_C_INLINE_WRAPPERS
#define WIN32_LEAN_AND_MEAN
#define _WINDOWS
#include <windows.h>
#include <d3d12.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "ffx_api.h"
#include "ffx_api_loader.h"
#include "ffx_upscale.h"
#include "dx12/ffx_api_dx12.h"
#include <d3d12.h>
// image mode build: no capture
static void CaptureInstall(ID3D12Device* d, ID3D12GraphicsCommandList* l, const char* dir) { (void)d; (void)l; (void)dir; }
static void CaptureMark(const char* t) { (void)t; }
static void CaptureNoteResource(ID3D12Resource* r, const char* n) { (void)r; (void)n; }

#define CHECK(x)                                                                                  \
    do {                                                                                          \
        HRESULT hr_ = (x);                                                                        \
        if (FAILED(hr_)) {                                                                        \
            fprintf(stderr, "%s failed: 0x%08lx (line %d)\n", #x, (unsigned long)hr_, __LINE__);  \
            exit(1);                                                                              \
        }                                                                                         \
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
    D3D12_RESOURCE_DESC desc = {
        .Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D,
        .Width = w,
        .Height = h,
        .DepthOrArraySize = 1,
        .MipLevels = 1,
        .Format = format,
        .SampleDesc = {1, 0},
        .Flags = uav ? D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS : D3D12_RESOURCE_FLAG_NONE,
    };
    ID3D12Resource* r;
    CHECK(ID3D12Device_CreateCommittedResource(device, &heap, D3D12_HEAP_FLAG_NONE, &desc,
                                               D3D12_RESOURCE_STATE_COMMON, NULL,
                                               &IID_ID3D12Resource, (void**)&r));
    return r;
}

static struct FfxApiResource Resource(ID3D12Resource* r, uint32_t format, uint32_t state) {
    D3D12_RESOURCE_DESC desc = ID3D12Resource_GetDesc(r);
    struct FfxApiResource out = {0};
    out.resource = r;
    out.state = state;
    out.description.type = FFX_API_RESOURCE_TYPE_TEXTURE2D;
    out.description.format = format;
    out.description.width = (uint32_t)desc.Width;
    out.description.height = desc.Height;
    out.description.depth = 1;
    out.description.mipCount = 1;
    out.description.usage = state == FFX_API_RESOURCE_STATE_UNORDERED_ACCESS ? FFX_API_RESOURCE_USAGE_UAV : 0;
    return out;
}

// The benchmark's test data generator (tools/fsr4_bench.cpp): same seed, order and conversion.
static uint16_t Half(float f) {
    uint32_t x;
    memcpy(&x, &f, 4);
    const uint32_t sign = (x >> 16) & 0x8000u;
    const int exp = (int)((x >> 23) & 0xffu) - 127 + 15;
    if (exp <= 0) return (uint16_t)sign;
    return (uint16_t)(sign | ((uint32_t)exp << 10) | ((x >> 13) & 0x3ffu));
}

static uint32_t seed = 12345u;
static float Next(void) {
    seed = seed * 1664525u + 1013904223u;
    return (float)(seed >> 8) / (float)(1u << 24);
}

static ID3D12Resource* Buffer(D3D12_HEAP_TYPE type, UINT64 size) {
    D3D12_HEAP_PROPERTIES heap = {.Type = type};
    D3D12_RESOURCE_DESC desc = {.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER, .Width = size, .Height = 1,
                                .DepthOrArraySize = 1, .MipLevels = 1, .SampleDesc = {1, 0},
                                .Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR};
    ID3D12Resource* r;
    CHECK(ID3D12Device_CreateCommittedResource(device, &heap, D3D12_HEAP_FLAG_NONE, &desc,
                                               type == D3D12_HEAP_TYPE_UPLOAD ? D3D12_RESOURCE_STATE_GENERIC_READ
                                                                              : D3D12_RESOURCE_STATE_COPY_DEST,
                                               NULL, &IID_ID3D12Resource, (void**)&r));
    return r;
}

// Fills `tex` (w x h, bpp bytes per texel) row by row from `fill`, through an upload buffer.
static void Upload(ID3D12Resource* tex, UINT w, UINT h, UINT bpp, void (*fill)(uint8_t* row, UINT w)) {
    const UINT pitch = (w * bpp + 255) & ~255u;
    ID3D12Resource* up = Buffer(D3D12_HEAP_TYPE_UPLOAD, (UINT64)pitch * h);
    uint8_t* data;
    CHECK(ID3D12Resource_Map(up, 0, NULL, (void**)&data));
    for (UINT y = 0; y < h; ++y) fill(data + (size_t)y * pitch, w);
    ID3D12Resource_Unmap(up, 0, NULL);
    D3D12_RESOURCE_DESC desc = ID3D12Resource_GetDesc(tex);
    D3D12_TEXTURE_COPY_LOCATION dst = {.pResource = tex, .Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX};
    D3D12_TEXTURE_COPY_LOCATION src = {.pResource = up, .Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT};
    src.PlacedFootprint.Footprint.Format = desc.Format;
    src.PlacedFootprint.Footprint.Width = w;
    src.PlacedFootprint.Footprint.Height = h;
    src.PlacedFootprint.Footprint.Depth = 1;
    src.PlacedFootprint.Footprint.RowPitch = pitch;
    ID3D12GraphicsCommandList_CopyTextureRegion(list, &dst, 0, 0, 0, &src, NULL);
    Submit();
    ID3D12Resource_Release(up);
}

static void FillColor(uint8_t* row, UINT w) {
    uint16_t* p = (uint16_t*)row;
    for (UINT x = 0; x < w; ++x) {
        p[4 * x + 0] = Half(Next() * 1.5f);
        p[4 * x + 1] = Half(Next() * 1.5f);
        p[4 * x + 2] = Half(Next() * 1.5f);
        p[4 * x + 3] = Half(1.0f);
    }
}
static FILE* img_file;
static void FillFromFile(uint8_t* row, UINT w) { if (fread(row, 8, w, img_file) != w) memset(row, 0, 8 * (size_t)w); }
static void FillFromFile4(uint8_t* row, UINT w) { if (fread(row, 4, w, img_file) != w) memset(row, 0, 4 * (size_t)w); }
static void FillZero2(uint8_t* row, UINT w) { memset(row, 0, 4 * (size_t)w); }
static void FillDepthConst(uint8_t* row, UINT w) { float* p = (float*)row; for (UINT x = 0; x < w; ++x) p[x] = 0.5f; }
static void FillMotion(uint8_t* row, UINT w) {
    uint16_t* p = (uint16_t*)row;
    for (UINT x = 0; x < 2 * w; ++x) p[x] = Half(Next() * 4.0f - 2.0f);
}
static void FillDepth(uint8_t* row, UINT w) {
    float* p = (float*)row;
    for (UINT x = 0; x < w; ++x) p[x] = 0.9f + Next() * 0.1f;
}

// Reads `output` back and writes it next to the exe: output_WxH.raw, or output_WxH_fNNN.raw for a kept frame.
static void WriteOutput(ID3D12Resource* output, UINT ow, UINT oh, int frame) {
    const UINT pitch = (ow * 8 + 255) & ~255u;
    static ID3D12Resource* rb;
    if (!rb) rb = Buffer(D3D12_HEAP_TYPE_READBACK, (UINT64)pitch * oh);
    D3D12_TEXTURE_COPY_LOCATION src = {.pResource = output, .Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX};
    D3D12_TEXTURE_COPY_LOCATION dst = {.pResource = rb, .Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT};
    dst.PlacedFootprint.Footprint.Format = DXGI_FORMAT_R16G16B16A16_FLOAT;
    dst.PlacedFootprint.Footprint.Width = ow;
    dst.PlacedFootprint.Footprint.Height = oh;
    dst.PlacedFootprint.Footprint.Depth = 1;
    dst.PlacedFootprint.Footprint.RowPitch = pitch;
    D3D12_RESOURCE_BARRIER b = {.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION};
    b.Transition.pResource = output;
    b.Transition.StateBefore = D3D12_RESOURCE_STATE_UNORDERED_ACCESS;
    b.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_SOURCE;
    ID3D12GraphicsCommandList_ResourceBarrier(list, 1, &b);
    ID3D12GraphicsCommandList_CopyTextureRegion(list, &dst, 0, 0, 0, &src, NULL);
    b.Transition.StateBefore = D3D12_RESOURCE_STATE_COPY_SOURCE;
    b.Transition.StateAfter = D3D12_RESOURCE_STATE_UNORDERED_ACCESS;
    ID3D12GraphicsCommandList_ResourceBarrier(list, 1, &b);
    Submit();
    uint8_t* data;
    CHECK(ID3D12Resource_Map(rb, 0, NULL, (void**)&data));
    char path[MAX_PATH];
    GetModuleFileNameA(NULL, path, MAX_PATH);
    if (frame < 0) snprintf(strrchr(path, '\\') + 1, 64, "output_%ux%u.raw", ow, oh);
    else snprintf(strrchr(path, '\\') + 1, 64, "output_%ux%u_f%03d.raw", ow, oh, frame);
    FILE* f = fopen(path, "wb");
    for (UINT y = 0; f && y < oh; ++y) fwrite(data + (size_t)y * pitch, 1, (size_t)ow * 8, f);
    if (f) fclose(f);
    ID3D12Resource_Unmap(rb, 0, NULL);
    printf("output written to %s\n", path);
}

static void Message(uint32_t type, const wchar_t* message) {
    fprintf(stderr, "FFX %s: %ls\n", type == FFX_API_MESSAGE_TYPE_ERROR ? "error" : "warning", message);
}

int main(int argc, char** argv) {
    // Proton does not pass the console through: log next to the exe.
    char log_path[MAX_PATH];
    GetModuleFileNameA(NULL, log_path, MAX_PATH);
    strcpy(strrchr(log_path, '\\') + 1, "fsr4cap.log");
    freopen(log_path, "w", stdout);
    setvbuf(stdout, NULL, _IONBF, 0);
    *stderr = *stdout;
    const char* want = argc > 1 ? argv[1] : "FSR4";
    uint32_t rw = 1280, rh = 720, ow = 1920, oh = 1080;
    int frames = argc > 4 ? atoi(argv[4]) : 4;
    if (argc > 2) sscanf(argv[2], "%ux%u", &rw, &rh);
    if (argc > 3) sscanf(argv[3], "%ux%u", &ow, &oh);

    CHECK(D3D12CreateDevice(NULL, D3D_FEATURE_LEVEL_12_0, &IID_ID3D12Device, (void**)&device));
    D3D12_COMMAND_QUEUE_DESC qd = {.Type = D3D12_COMMAND_LIST_TYPE_DIRECT};
    CHECK(ID3D12Device_CreateCommandQueue(device, &qd, &IID_ID3D12CommandQueue, (void**)&queue));
    CHECK(ID3D12Device_CreateCommandAllocator(device, D3D12_COMMAND_LIST_TYPE_DIRECT,
                                              &IID_ID3D12CommandAllocator, (void**)&allocator));
    CHECK(ID3D12Device_CreateCommandList(device, 0, D3D12_COMMAND_LIST_TYPE_DIRECT, allocator, NULL,
                                         &IID_ID3D12GraphicsCommandList, (void**)&list));
    CHECK(ID3D12Device_CreateFence(device, 0, D3D12_FENCE_FLAG_NONE, &IID_ID3D12Fence, (void**)&fence));
    fence_event = CreateEventA(NULL, FALSE, FALSE, NULL);

    // Record everything the upscaler does with the device (capture/ next to the exe).
    char capture_dir[MAX_PATH];
    GetModuleFileNameA(NULL, capture_dir, MAX_PATH);
    // Test runs with pseudo-random inputs (verify.sh) record next to, not over, the captures.
    snprintf(strrchr(capture_dir, '\\') + 1, 64, "%scapture_%ux%u_%ux%u",
             argc > 5 && strcmp(argv[5], "noise") == 0 ? "noise_" : "", rw, rh, ow, oh);
    CaptureInstall(device, list, capture_dir);

    HMODULE loader = LoadLibraryA("amd_fidelityfx_loader_dx12.dll");
    if (!loader) {
        fprintf(stderr, "no amd_fidelityfx_loader_dx12.dll\n");
        return 1;
    }
    ffxFunctions ffx;
    ffxLoadFunctions(&ffx, loader);

    // Versions of the upscaler.
    uint64_t count = 0;
    struct ffxQueryDescGetVersions versions = {0};
    versions.header.type = FFX_API_QUERY_DESC_TYPE_GET_VERSIONS;
    versions.createDescType = FFX_API_CREATE_CONTEXT_DESC_TYPE_UPSCALE;
    versions.device = device;
    versions.outputCount = &count;
    ffx.Query(NULL, &versions.header);
    uint64_t ids[32];
    const char* names[32];
    if (count > 32) count = 32;
    versions.versionIds = ids;
    versions.versionNames = names;
    ffx.Query(NULL, &versions.header);
    uint64_t chosen = 0;
    for (uint64_t i = 0; i < count; ++i) {
        printf("version %llu: id 0x%llx %s\n", (unsigned long long)i, (unsigned long long)ids[i], names[i]);
        if (!chosen && strstr(names[i], want)) chosen = ids[i];
    }
    if (!chosen) {
        fprintf(stderr, "no version matching '%s'\n", want);
        return 1;
    }

    struct ffxCreateBackendDX12Desc backend = {0};
    backend.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_DX12;
    backend.device = device;
    struct ffxOverrideVersion override = {0};
    override.header.type = FFX_API_DESC_TYPE_OVERRIDE_VERSION;
    override.versionId = chosen;
    override.header.pNext = &backend.header;
    struct ffxCreateContextDescUpscale create = {0};
    create.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_UPSCALE;
    create.header.pNext = &override.header;
    create.flags = FFX_UPSCALE_ENABLE_HIGH_DYNAMIC_RANGE | FFX_UPSCALE_ENABLE_AUTO_EXPOSURE;
    if (getenv("FSR_CTX_FLAGS")) create.flags = (uint32_t)strtoul(getenv("FSR_CTX_FLAGS"), NULL, 0);   // variant tests
    create.maxRenderSize.width = ow;
    create.maxRenderSize.height = oh;
    create.maxUpscaleSize.width = ow;
    create.maxUpscaleSize.height = oh;
    create.fpMessage = Message;
    ffxContext context = NULL;
    ffxReturnCode_t rc = ffx.CreateContext(&context, &create.header, NULL);
    printf("create context: %d\n", (int)rc);
    if (rc != FFX_API_RETURN_OK) return 1;
    struct ffxQueryGetProviderVersion provider = {0};
    provider.header.type = FFX_API_QUERY_DESC_TYPE_GET_PROVIDER_VERSION;
    ffx.Query(&context, &provider.header);
    printf("provider: %s (0x%llx)\n", provider.versionName ? provider.versionName : "?",
           (unsigned long long)provider.versionId);

    ID3D12Resource* color = Texture(DXGI_FORMAT_R16G16B16A16_FLOAT, rw, rh, false);
    ID3D12Resource* depth = Texture(DXGI_FORMAT_R32_FLOAT, rw, rh, false);
    ID3D12Resource* motion = Texture(DXGI_FORMAT_R16G16_FLOAT, rw, rh, false);
    ID3D12Resource* output = Texture(DXGI_FORMAT_R16G16B16A16_FLOAT, ow, oh, true);
    CaptureNoteResource(color, "color");
    CaptureNoteResource(depth, "depth");
    CaptureNoteResource(motion, "motion");
    CaptureNoteResource(output, "output");
    const bool noise = argc > 5 && strcmp(argv[5], "noise") == 0;
    if (noise) {
        Upload(color, rw, rh, 8, FillColor);
        Upload(motion, rw, rh, 4, FillMotion);
        Upload(depth, rw, rh, 4, FillDepth);
    }
    const bool image = argc > 5 && strcmp(argv[5], "image") == 0;
    FILE* jit = NULL;
    char base[MAX_PATH];
    GetModuleFileNameA(NULL, base, MAX_PATH);
    *(strrchr(base, '\\') + 1) = 0;
    const char* dir = getenv("FSR_IMG_DIR") ? getenv("FSR_IMG_DIR") : "img";   // input folder next to the exe
    const int keep = getenv("FSR_KEEP") ? atoi(getenv("FSR_KEEP")) : 0;       // also write the last N frames
    if (image) {
        char p[MAX_PATH];
        snprintf(p, sizeof(p), "%s%s\\jitter.txt", base, dir);
        jit = fopen(p, "r");
        if (!jit) { fprintf(stderr, "no img/jitter.txt\n"); return 1; }
        Upload(motion, rw, rh, 4, FillZero2);
        Upload(depth, rw, rh, 4, FillDepthConst);
    }
    for (int frame = 0; frame < frames; ++frame) {
        float jx = 0.25f * (float)(frame % 4) - 0.375f, jy = 0.125f;
        if (image) {
            char p[MAX_PATH];
            snprintf(p, sizeof(p), "%s%s\\color_%03d.raw", base, dir, frame);
            img_file = fopen(p, "rb");
            if (!img_file || fscanf(jit, "%f %f", &jx, &jy) != 2) { fprintf(stderr, "missing input for frame %d\n", frame); return 1; }
            Upload(color, rw, rh, 8, FillFromFile);
            fclose(img_file);
            // optional per-frame motion vectors (RG16F, render pixels) and depth (R32F)
            snprintf(p, sizeof(p), "%s%s\\motion_%03d.raw", base, dir, frame);
            if ((img_file = fopen(p, "rb"))) { Upload(motion, rw, rh, 4, FillFromFile4); fclose(img_file); }
            snprintf(p, sizeof(p), "%s%s\\depth_%03d.raw", base, dir, frame);
            if ((img_file = fopen(p, "rb"))) { Upload(depth, rw, rh, 4, FillFromFile4); fclose(img_file); }
        }
        char mark[32];
        snprintf(mark, sizeof(mark), "frame %d", frame);
        CaptureMark(mark);
        struct ffxDispatchDescUpscale d = {0};
        d.header.type = FFX_API_DISPATCH_DESC_TYPE_UPSCALE;
        d.commandList = list;
        d.color = Resource(color, FFX_API_SURFACE_FORMAT_R16G16B16A16_FLOAT, FFX_API_RESOURCE_STATE_COMMON);
        d.depth = Resource(depth, FFX_API_SURFACE_FORMAT_R32_FLOAT, FFX_API_RESOURCE_STATE_COMMON);
        d.motionVectors = Resource(motion, FFX_API_SURFACE_FORMAT_R16G16_FLOAT, FFX_API_RESOURCE_STATE_COMMON);
        d.output = Resource(output, FFX_API_SURFACE_FORMAT_R16G16B16A16_FLOAT, FFX_API_RESOURCE_STATE_UNORDERED_ACCESS);
        d.jitterOffset.x = jx;
        d.jitterOffset.y = jy;
        d.motionVectorScale.x = d.motionVectorScale.y = 1.0f;
        d.renderSize.width = rw;
        d.renderSize.height = rh;
        d.upscaleSize.width = ow;
        d.upscaleSize.height = oh;
        d.enableSharpening = !image;
        if (getenv("FSR_SHARPEN")) d.enableSharpening = atoi(getenv("FSR_SHARPEN")) != 0;
        if (getenv("FSR_DISP_FLAGS")) d.flags = (uint32_t)strtoul(getenv("FSR_DISP_FLAGS"), NULL, 0);
        d.sharpness = 0.5f;
        d.frameTimeDelta = 10.0f;
        d.preExposure = 1.0f;
        d.reset = frame == 0;
        d.cameraNear = 0.05f;
        d.cameraFar = 3000.0f;
        d.cameraFovAngleVertical = 0.75f;
        d.viewSpaceToMetersFactor = 1.0f;
        rc = ffx.Dispatch(&context, &d.header);
        if (rc != FFX_API_RETURN_OK) {
            printf("dispatch %d: %d\n", frame, (int)rc);
            return 1;
        }
        Submit();
        if (image && frame >= frames - keep) WriteOutput(output, ow, oh, frame);
    }
    CaptureMark("end");
    if (noise || image) WriteOutput(output, ow, oh, -1);
    printf("%d frames done\n", frames);
    ffx.DestroyContext(&context, NULL);
    return 0;
}
