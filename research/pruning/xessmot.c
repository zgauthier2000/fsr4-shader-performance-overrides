// SPDX-License-Identifier: GPL-2.0-or-later
// xessmot.exe: the image-input test rig of fsr4mot.c for Intel XeSS, for comparing upscalers on the same inputs.
// Runs XeSS (libxess.dll next to the exe, loaded at run time) on D3D12 over a folder of input frames written by
// gen_inputs.py / gen_motion.py: color_NNN.raw (RGBA16F, linear), optional motion_NNN.raw (RG16F, render pixels, from a pixel
// to where it was a frame ago) and depth_NNN.raw (R32F), jitter.txt. Writes the last FSR_KEEP frames as output_WxH_fNNN.raw.
//
//   xessmot.exe <quality: uperf|perf|balanced|quality|uq|uqp|aa> <render WxH> <output WxH> <frames> image
// Environment: FSR_IMG_DIR, FSR_KEEP as for fsr4mot.exe; XESS_FLAGS (init flags, default 0: HDR linear color, render-resolution
// motion vectors, normal depth), XESS_JITTER "sx sy" and XESS_MV "sx sy" (scales for the jitter and the motion vectors, default
// "1 1"), XESS_TIME=1 (GPU time of each XeSS call from timestamp queries, mean of the frames after the first 8).
// Build (llvm-mingw): x86_64-w64-mingw32-clang -std=c11 -O1 -I<XeSS SDK>/inc xessmot.c -o xessmot.exe -ld3d12 -ldxguid -static
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

#include "xess/xess.h"
#include "xess/xess_d3d12.h"
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


#define X(name) static __typeof__(&name) p_##name;
X(xessGetVersion) X(xessD3D12CreateContext) X(xessD3D12BuildPipelines) X(xessD3D12Init) X(xessD3D12Execute) X(xessDestroyContext)
X(xessSetJitterScale) X(xessSetVelocityScale) X(xessSetLoggingCallback)
#undef X
static void XessLog(const char* message, xess_logging_level_t level) { if (level >= XESS_LOGGING_LEVEL_WARNING) printf("XeSS: %s\n", message); }

static void Barrier(ID3D12Resource* r, D3D12_RESOURCE_STATES before, D3D12_RESOURCE_STATES after) {
    D3D12_RESOURCE_BARRIER b = {.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION};
    b.Transition.pResource = r;
    b.Transition.StateBefore = before;
    b.Transition.StateAfter = after;
    ID3D12GraphicsCommandList_ResourceBarrier(list, 1, &b);
}

int main(int argc, char** argv) {
    char log_path[MAX_PATH];
    GetModuleFileNameA(NULL, log_path, MAX_PATH);
    strcpy(strrchr(log_path, '\\') + 1, "xessmot.log");
    freopen(log_path, "w", stdout);
    setvbuf(stdout, NULL, _IONBF, 0);
    *stderr = *stdout;
    const char* want = argc > 1 ? argv[1] : "quality";
    uint32_t rw = 1280, rh = 720, ow = 1920, oh = 1080;
    int frames = argc > 4 ? atoi(argv[4]) : 4;
    if (argc > 2) sscanf(argv[2], "%ux%u", &rw, &rh);
    if (argc > 3) sscanf(argv[3], "%ux%u", &ow, &oh);
    static const struct { const char* name; xess_quality_settings_t q; } Q[] = {{"uperf", XESS_QUALITY_SETTING_ULTRA_PERFORMANCE}, {"perf", XESS_QUALITY_SETTING_PERFORMANCE},
        {"balanced", XESS_QUALITY_SETTING_BALANCED}, {"quality", XESS_QUALITY_SETTING_QUALITY}, {"uq", XESS_QUALITY_SETTING_ULTRA_QUALITY},
        {"uqp", XESS_QUALITY_SETTING_ULTRA_QUALITY_PLUS}, {"aa", XESS_QUALITY_SETTING_AA}};
    xess_quality_settings_t quality = XESS_QUALITY_SETTING_QUALITY;
    for (int i = 0; i < 7; ++i) if (!strcmp(want, Q[i].name)) quality = Q[i].q;

    CHECK(D3D12CreateDevice(NULL, D3D_FEATURE_LEVEL_12_0, &IID_ID3D12Device, (void**)&device));
    D3D12_COMMAND_QUEUE_DESC qd = {.Type = D3D12_COMMAND_LIST_TYPE_DIRECT};
    CHECK(ID3D12Device_CreateCommandQueue(device, &qd, &IID_ID3D12CommandQueue, (void**)&queue));
    CHECK(ID3D12Device_CreateCommandAllocator(device, D3D12_COMMAND_LIST_TYPE_DIRECT, &IID_ID3D12CommandAllocator, (void**)&allocator));
    CHECK(ID3D12Device_CreateCommandList(device, 0, D3D12_COMMAND_LIST_TYPE_DIRECT, allocator, NULL, &IID_ID3D12GraphicsCommandList, (void**)&list));
    CHECK(ID3D12Device_CreateFence(device, 0, D3D12_FENCE_FLAG_NONE, &IID_ID3D12Fence, (void**)&fence));
    fence_event = CreateEventA(NULL, FALSE, FALSE, NULL);

    HMODULE lib = LoadLibraryA("libxess.dll");
    if (!lib) { fprintf(stderr, "no libxess.dll next to the exe\n"); return 1; }
#define X(name) if (!(p_##name = (void*)GetProcAddress(lib, #name))) { fprintf(stderr, "libxess.dll has no " #name "\n"); return 1; }
    X(xessGetVersion) X(xessD3D12CreateContext) X(xessD3D12BuildPipelines) X(xessD3D12Init) X(xessD3D12Execute) X(xessDestroyContext)
    X(xessSetJitterScale) X(xessSetVelocityScale) X(xessSetLoggingCallback)
#undef X
    xess_version_t ver = {0};
    p_xessGetVersion(&ver);
    printf("XeSS %u.%u.%u\n", (unsigned)ver.major, (unsigned)ver.minor, (unsigned)ver.patch);
    xess_context_handle_t ctx = NULL;
    xess_result_t rc = p_xessD3D12CreateContext(device, &ctx);
    if (rc != XESS_RESULT_SUCCESS) { printf("xessD3D12CreateContext: %d\n", (int)rc); return 1; }
    p_xessSetLoggingCallback(ctx, XESS_LOGGING_LEVEL_WARNING, XessLog);
    const uint32_t flags = getenv("XESS_FLAGS") ? (uint32_t)strtoul(getenv("XESS_FLAGS"), NULL, 0) : 0;
    rc = p_xessD3D12BuildPipelines(ctx, NULL, true, flags);
    if (rc < 0) { printf("xessD3D12BuildPipelines: %d\n", (int)rc); return 1; }
    xess_d3d12_init_params_t init = {0};
    init.outputResolution.x = ow;
    init.outputResolution.y = oh;
    init.qualitySetting = quality;
    init.initFlags = flags;
    rc = p_xessD3D12Init(ctx, &init);
    if (rc < 0) { printf("xessD3D12Init: %d\n", (int)rc); return 1; }
    float jsx = 1, jsy = 1, msx = 1, msy = 1;
    if (getenv("XESS_JITTER")) sscanf(getenv("XESS_JITTER"), "%f %f", &jsx, &jsy);
    if (getenv("XESS_MV")) sscanf(getenv("XESS_MV"), "%f %f", &msx, &msy);
    p_xessSetJitterScale(ctx, jsx, jsy);
    p_xessSetVelocityScale(ctx, msx, msy);
    printf("quality %s, render %ux%u -> %ux%u, flags 0x%x, jitter scale %g %g, velocity scale %g %g\n", want, rw, rh, ow, oh, flags, jsx, jsy, msx, msy);

    ID3D12Resource* color = Texture(DXGI_FORMAT_R16G16B16A16_FLOAT, rw, rh, false);
    ID3D12Resource* depth = Texture(DXGI_FORMAT_R32_FLOAT, rw, rh, false);
    ID3D12Resource* motion = Texture(DXGI_FORMAT_R16G16_FLOAT, rw, rh, false);
    ID3D12Resource* output = Texture(DXGI_FORMAT_R16G16B16A16_FLOAT, ow, oh, true);
    Barrier(output, D3D12_RESOURCE_STATE_COMMON, D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
    Submit();
    const bool timing = getenv("XESS_TIME") != NULL;
    ID3D12QueryHeap* qheap = NULL;
    ID3D12Resource* qbuf = NULL;
    UINT64 freq = 1;
    if (timing) {
        D3D12_QUERY_HEAP_DESC qh = {.Type = D3D12_QUERY_HEAP_TYPE_TIMESTAMP, .Count = 2};
        CHECK(ID3D12Device_CreateQueryHeap(device, &qh, &IID_ID3D12QueryHeap, (void**)&qheap));
        qbuf = Buffer(D3D12_HEAP_TYPE_READBACK, 16);
        CHECK(ID3D12CommandQueue_GetTimestampFrequency(queue, &freq));
    }
    double ms_sum = 0, ms_even = 0, ms_odd = 0;
    int ms_n = 0;
    FILE* jit = NULL;
    char base[MAX_PATH];
    GetModuleFileNameA(NULL, base, MAX_PATH);
    *(strrchr(base, '\\') + 1) = 0;
    const char* dir = getenv("FSR_IMG_DIR") ? getenv("FSR_IMG_DIR") : "img";
    const int keep = getenv("FSR_KEEP") ? atoi(getenv("FSR_KEEP")) : 0;
    char p[MAX_PATH];
    snprintf(p, sizeof(p), "%s%s\\jitter.txt", base, dir);
    jit = fopen(p, "r");
    if (!jit) { fprintf(stderr, "no jitter.txt in the input folder\n"); return 1; }
    Upload(motion, rw, rh, 4, FillZero2);
    Upload(depth, rw, rh, 4, FillDepthConst);
    for (int frame = 0; frame < frames; ++frame) {
        float jx = 0, jy = 0;
        snprintf(p, sizeof(p), "%s%s\\color_%03d.raw", base, dir, frame);
        img_file = fopen(p, "rb");
        if (!img_file || fscanf(jit, "%f %f", &jx, &jy) != 2) { fprintf(stderr, "missing input for frame %d\n", frame); return 1; }
        Upload(color, rw, rh, 8, FillFromFile);
        fclose(img_file);
        snprintf(p, sizeof(p), "%s%s\\motion_%03d.raw", base, dir, frame);
        if ((img_file = fopen(p, "rb"))) { Upload(motion, rw, rh, 4, FillFromFile4); fclose(img_file); }
        snprintf(p, sizeof(p), "%s%s\\depth_%03d.raw", base, dir, frame);
        if ((img_file = fopen(p, "rb"))) { Upload(depth, rw, rh, 4, FillFromFile4); fclose(img_file); }
        Barrier(color, D3D12_RESOURCE_STATE_COMMON, D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
        Barrier(motion, D3D12_RESOURCE_STATE_COMMON, D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
        Barrier(depth, D3D12_RESOURCE_STATE_COMMON, D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
        xess_d3d12_execute_params_t e = {0};
        e.pColorTexture = color;
        e.pVelocityTexture = motion;
        e.pDepthTexture = depth;
        e.pOutputTexture = output;
        e.jitterOffsetX = jx;
        e.jitterOffsetY = jy;
        e.exposureScale = 1.0f;
        e.resetHistory = frame == 0;
        e.inputWidth = rw;
        e.inputHeight = rh;
        if (timing) ID3D12GraphicsCommandList_EndQuery(list, qheap, D3D12_QUERY_TYPE_TIMESTAMP, 0);
        rc = p_xessD3D12Execute(ctx, list, &e);
        if (rc < 0) { printf("xessD3D12Execute, frame %d: %d\n", frame, (int)rc); return 1; }
        if (timing) {
            ID3D12GraphicsCommandList_EndQuery(list, qheap, D3D12_QUERY_TYPE_TIMESTAMP, 1);
            ID3D12GraphicsCommandList_ResolveQueryData(list, qheap, D3D12_QUERY_TYPE_TIMESTAMP, 0, 2, qbuf, 0);
        }
        Barrier(color, D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE, D3D12_RESOURCE_STATE_COMMON);
        Barrier(motion, D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE, D3D12_RESOURCE_STATE_COMMON);
        Barrier(depth, D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE, D3D12_RESOURCE_STATE_COMMON);
        Submit();
        if (timing) {
            UINT64* t;
            CHECK(ID3D12Resource_Map(qbuf, 0, NULL, (void**)&t));
            const double ms = (double)(t[1] - t[0]) * 1000.0 / (double)freq;
            ID3D12Resource_Unmap(qbuf, 0, NULL);
            if (frame >= 8) { ms_sum += ms; ++ms_n; }
        }
        if (frame >= frames - keep) WriteOutput(output, ow, oh, frame);
    }
    (void)ms_even; (void)ms_odd;
    if (timing && ms_n) printf("GPU time per XeSS call: mean %.3f ms over %d frames\n", ms_sum / ms_n, ms_n);
    printf("%d frames done\n", frames);
    p_xessDestroyContext(ctx);
    return 0;
}
