// SPDX-License-Identifier: GPL-2.0-or-later
// vkrun.c: the timing kit's Vulkan run (see vkrun.h). One DLL (amd_fidelityfx_upscaler_vk.dll next to the program), every size and
// scene of fsr4time.c's RunOne, the same made-up frames, the same timing (a GPU timestamp before and one after each upscale call,
// WARM calls, then TIMED calls, each submitted and waited for alone) and the same "G|", "R|", "F|" and picture lines.
// Build: x86_64-w64-mingw32-clang -std=c11 -O1 -c -I<Vulkan-Headers>/include -I<FidelityFX SDK 2.4.0>/api/include -I<...>/upscalers/include vkrun.c
#define WIN32_LEAN_AND_MEAN
#define _WINDOWS
#include <windows.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define VK_NO_PROTOTYPES
#include <vulkan/vulkan.h>
#include "ffx_api.h"
#include "ffx_api_loader.h"
#include "ffx_upscale.h"
#include "vk/ffx_api_vk.h"
#include "vkrun.h"

static const struct VkRunHost* H;
#define FAIL(...) do { char m_[256]; snprintf(m_, sizeof(m_), __VA_ARGS__); H->Say("R|%s|FAILED|%s\n", run_label, m_); return 1; } while (0)
static const char* run_label = "?";

static PFN_vkGetInstanceProcAddr gipa;
#define F(n) static PFN_##n n;
F(vkCreateInstance) F(vkEnumeratePhysicalDevices) F(vkGetPhysicalDeviceProperties) F(vkGetPhysicalDeviceProperties2) F(vkGetPhysicalDeviceQueueFamilyProperties)
F(vkGetPhysicalDeviceFeatures2) F(vkEnumerateDeviceExtensionProperties) F(vkCreateDevice) F(vkGetDeviceProcAddr) F(vkGetPhysicalDeviceMemoryProperties)
F(vkGetDeviceQueue) F(vkCreateImage) F(vkDestroyImage) F(vkGetImageMemoryRequirements) F(vkAllocateMemory) F(vkBindImageMemory) F(vkCreateBuffer)
F(vkGetBufferMemoryRequirements) F(vkBindBufferMemory) F(vkMapMemory) F(vkUnmapMemory) F(vkCreateCommandPool) F(vkAllocateCommandBuffers)
F(vkBeginCommandBuffer) F(vkEndCommandBuffer) F(vkQueueSubmit) F(vkQueueWaitIdle) F(vkResetCommandBuffer) F(vkCmdPipelineBarrier)
F(vkCmdCopyBufferToImage) F(vkCmdCopyImageToBuffer) F(vkDestroyBuffer) F(vkFreeMemory) F(vkCreateQueryPool) F(vkCmdResetQueryPool)
F(vkCmdWriteTimestamp) F(vkGetQueryPoolResults)
#undef F
static VkInstance inst; static VkPhysicalDevice phys; static VkDevice dev; static VkQueue queue; static uint32_t qfam;
static VkCommandBuffer cmd; static VkPhysicalDeviceMemoryProperties memprops;
static bool vk_ok = true;
#define VKC(x) do { VkResult r_ = (x); if (r_ != VK_SUCCESS && vk_ok) { vk_ok = false; H->Say("R|%s|FAILED|%s: Vulkan error %d\n", run_label, #x, (int)r_); } } while (0)

static uint32_t MemType(uint32_t bits, VkMemoryPropertyFlags want) {
    for (uint32_t i = 0; i < memprops.memoryTypeCount; ++i)
        if ((bits & (1u << i)) && (memprops.memoryTypes[i].propertyFlags & want) == want) return i;
    return 0;
}
static void Begin(void) {
    VKC(vkResetCommandBuffer(cmd, 0));
    VkCommandBufferBeginInfo bi = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO, .flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT};
    VKC(vkBeginCommandBuffer(cmd, &bi));
}
static void Submit(void) {
    VKC(vkEndCommandBuffer(cmd));
    VkSubmitInfo si = {.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO, .commandBufferCount = 1, .pCommandBuffers = &cmd};
    VKC(vkQueueSubmit(queue, 1, &si, VK_NULL_HANDLE));
    VKC(vkQueueWaitIdle(queue));
}
static void FullBarrier(void) {
    VkMemoryBarrier mb = {.sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER, .srcAccessMask = VK_ACCESS_MEMORY_WRITE_BIT | VK_ACCESS_MEMORY_READ_BIT,
                          .dstAccessMask = VK_ACCESS_MEMORY_WRITE_BIT | VK_ACCESS_MEMORY_READ_BIT};
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0, 1, &mb, 0, NULL, 0, NULL);
}
typedef struct { VkImage img; VkDeviceMemory mem; uint32_t w, h; } Tex;
static Tex Texture(VkFormat fmt, uint32_t w, uint32_t h) {      // every image lives in GENERAL (the FidelityFX API's COMMON / UNORDERED_ACCESS on Vulkan)
    Tex t = {.w = w, .h = h};
    VkImageCreateInfo ci = {.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO, .imageType = VK_IMAGE_TYPE_2D, .format = fmt, .extent = {w, h, 1}, .mipLevels = 1,
                            .arrayLayers = 1, .samples = VK_SAMPLE_COUNT_1_BIT, .tiling = VK_IMAGE_TILING_OPTIMAL,
                            .usage = VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT,
                            .initialLayout = VK_IMAGE_LAYOUT_UNDEFINED};
    VKC(vkCreateImage(dev, &ci, NULL, &t.img));
    VkMemoryRequirements mr; vkGetImageMemoryRequirements(dev, t.img, &mr);
    VkMemoryAllocateInfo ai = {.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, .allocationSize = mr.size, .memoryTypeIndex = MemType(mr.memoryTypeBits, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)};
    VKC(vkAllocateMemory(dev, &ai, NULL, &t.mem)); VKC(vkBindImageMemory(dev, t.img, t.mem, 0));
    Begin();
    VkImageMemoryBarrier b = {.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER, .dstAccessMask = VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT,
                              .oldLayout = VK_IMAGE_LAYOUT_UNDEFINED, .newLayout = VK_IMAGE_LAYOUT_GENERAL, .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                              .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED, .image = t.img, .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0, 0, NULL, 0, NULL, 1, &b);
    Submit();
    return t;
}
static void FreeTex(Tex t) { vkDestroyImage(dev, t.img, NULL); vkFreeMemory(dev, t.mem, NULL); }
typedef struct { VkBuffer buf; VkDeviceMemory mem; uint8_t* ptr; } HostBuf;
static HostBuf HostMem(VkDeviceSize size, bool cached);
static HostBuf Host(VkDeviceSize size) { return HostMem(size, false); }
// (2026-11-14, user: "the timing kit is still using lots of cpu and hardly any gpu") the READBACK buffer must be CPU-cached memory: the picture checks read
// every output value several times, and from uncached (write-combined) memory that took 3.4 s at 1080p and 13.8 s at 4K per size and scene under Proton
// (most of a Vulkan run; one CPU core busy, the GPU idle). Direct3D 12's readback heap is cached, which is why only the Vulkan runs did this.
static HostBuf Readback(VkDeviceSize size) { return HostMem(size, true); }
static HostBuf HostMem(VkDeviceSize size, bool cached) {
    HostBuf h = {0};
    VkBufferCreateInfo ci = {.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, .size = size, .usage = VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT};
    VKC(vkCreateBuffer(dev, &ci, NULL, &h.buf));
    VkMemoryRequirements mr; vkGetBufferMemoryRequirements(dev, h.buf, &mr);
    VkMemoryAllocateInfo ai = {.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, .allocationSize = mr.size,
                               .memoryTypeIndex = MemType(mr.memoryTypeBits, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)};
    if (cached) {      // prefer a cached host-visible type (coherent if there is one); MemType returns 0 when nothing matches, so check the flags
        for (uint32_t i = 0; i < memprops.memoryTypeCount; ++i) {
            const VkMemoryPropertyFlags f = memprops.memoryTypes[i].propertyFlags;
            if ((mr.memoryTypeBits & (1u << i)) && (f & VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT) && (f & VK_MEMORY_PROPERTY_HOST_CACHED_BIT) && (f & VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) { ai.memoryTypeIndex = i; break; }
        }
    }
    VKC(vkAllocateMemory(dev, &ai, NULL, &h.mem)); VKC(vkBindBufferMemory(dev, h.buf, h.mem, 0));
    VKC(vkMapMemory(dev, h.mem, 0, VK_WHOLE_SIZE, 0, (void**)&h.ptr));
    return h;
}
static void FreeHost(HostBuf h) { vkUnmapMemory(dev, h.mem); vkDestroyBuffer(dev, h.buf, NULL); vkFreeMemory(dev, h.mem, NULL); }
// (2026-11-14) one staging buffer, kept mapped and reused for every upload (it grows when a bigger upload comes). Before, each upload allocated, mapped and freed
// its own host buffer, so every page of every new buffer page-faulted (Proton: ~2,500 major faults/s, one CPU core busy, the GPU idle between the timed calls).
static HostBuf stage; static VkDeviceSize stage_size;
static void FreeStage(void) { if (stage_size) { FreeHost(stage); stage_size = 0; } }
static void UploadRows(Tex t, uint32_t bpp, const uint8_t* src) {
    const VkDeviceSize n = (VkDeviceSize)t.w * t.h * bpp;
    if (n > stage_size) { FreeStage(); stage = Host(n); stage_size = n; }
    memcpy(stage.ptr, src, (size_t)n);
    Begin(); FullBarrier();
    VkBufferImageCopy r = {.imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1}, .imageExtent = {t.w, t.h, 1}};
    vkCmdCopyBufferToImage(cmd, stage.buf, t.img, VK_IMAGE_LAYOUT_GENERAL, 1, &r);
    FullBarrier(); Submit();
}
static struct FfxApiResource Resource(Tex t, uint32_t format, uint32_t state) {
    struct FfxApiResource out = {0};
    out.resource = (void*)t.img; out.state = state;
    out.description.type = FFX_API_RESOURCE_TYPE_TEXTURE2D; out.description.format = format;
    out.description.width = t.w; out.description.height = t.h; out.description.depth = 1; out.description.mipCount = 1;
    out.description.usage = state == FFX_API_RESOURCE_STATE_UNORDERED_ACCESS ? FFX_API_RESOURCE_USAGE_UAV : 0;
    return out;
}
static void Message(uint32_t type, const wchar_t* message) { H->Say("  FFX %s: %ls\n", type == FFX_API_MESSAGE_TYPE_ERROR ? "error" : "warning", message); }
static int CmpD(const void* a, const void* b) { double x = *(const double*)a, y = *(const double*)b; return x < y ? -1 : x > y; }
static double Median(double* v, int n) { qsort(v, n, sizeof(double), CmpD); return n ? v[n / 2] : 0; }

// device extensions turned on when the GPU offers them (what FSR 4's shaders and the FidelityFX Vulkan backend may use)
static const char* WANT_EXT[] = {
    "VK_KHR_shader_integer_dot_product", "VK_KHR_shader_float16_int8", "VK_KHR_16bit_storage", "VK_KHR_8bit_storage", "VK_EXT_subgroup_size_control",
    "VK_KHR_shader_subgroup_extended_types", "VK_KHR_variable_pointers", "VK_KHR_vulkan_memory_model", "VK_EXT_descriptor_indexing", "VK_KHR_maintenance4",
    "VK_KHR_synchronization2", "VK_KHR_get_memory_requirements2", "VK_KHR_dedicated_allocation", "VK_KHR_shader_non_semantic_info", "VK_KHR_push_descriptor",
    "VK_KHR_cooperative_matrix", "VK_EXT_shader_float8", "VK_NV_cooperative_matrix2", "VK_KHR_shader_bfloat16", "VK_EXT_shader_image_atomic_int64",
    "VK_KHR_shader_expect_assume", "VK_KHR_buffer_device_address", "VK_EXT_shader_atomic_float", "VK_KHR_shader_float_controls", "VK_KHR_storage_buffer_storage_class",
};
static float timestamp_ns;
static int CreateDevice(char* gpu, size_t n) {
    HMODULE vk = LoadLibraryA("vulkan-1.dll");
    if (!vk) FAIL("no Vulkan on this PC (vulkan-1.dll not found)");
    gipa = (PFN_vkGetInstanceProcAddr)(void*)GetProcAddress(vk, "vkGetInstanceProcAddr");
    if (!gipa) FAIL("vulkan-1.dll has no vkGetInstanceProcAddr");
    vkCreateInstance = (PFN_vkCreateInstance)gipa(NULL, "vkCreateInstance");
    VkApplicationInfo app = {.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO, .pApplicationName = "fsr4time", .apiVersion = VK_API_VERSION_1_3};
    VkInstanceCreateInfo ici = {.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, .pApplicationInfo = &app};
    if (vkCreateInstance(&ici, NULL, &inst) != VK_SUCCESS) FAIL("no Vulkan 1.3 instance");
#define I(x) x = (PFN_##x)gipa(inst, #x); if (!x) FAIL("no " #x);
    I(vkEnumeratePhysicalDevices) I(vkGetPhysicalDeviceProperties) I(vkGetPhysicalDeviceProperties2) I(vkGetPhysicalDeviceQueueFamilyProperties) I(vkGetPhysicalDeviceFeatures2)
    I(vkEnumerateDeviceExtensionProperties) I(vkCreateDevice) I(vkGetDeviceProcAddr) I(vkGetPhysicalDeviceMemoryProperties)
#undef I
    uint32_t np = 0; vkEnumeratePhysicalDevices(inst, &np, NULL);
    VkPhysicalDevice pds[16]; if (np > 16) np = 16; vkEnumeratePhysicalDevices(inst, &np, pds);
    int pick = -1, discrete = -1;      // the graphics the Direct3D 12 runs use (same PCI ids), else the first discrete one, else the first
    for (uint32_t i = 0; i < np; ++i) {
        VkPhysicalDeviceProperties p; vkGetPhysicalDeviceProperties(pds[i], &p);
        if (pick < 0 && p.vendorID == H->ven && p.deviceID == H->dev) pick = (int)i;
        if (discrete < 0 && p.deviceType == VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU) discrete = (int)i;
    }
    if (pick < 0) pick = discrete >= 0 ? discrete : 0;
    if (!np) FAIL("no Vulkan graphics found");
    phys = pds[pick];
    VkPhysicalDeviceDriverProperties drv = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES};
    VkPhysicalDeviceProperties2 pp = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2, .pNext = &drv};
    vkGetPhysicalDeviceProperties2(phys, &pp);
    if (pp.properties.apiVersion < VK_API_VERSION_1_3) FAIL("the graphics' Vulkan driver offers Vulkan %u.%u, FSR 4's Vulkan DLL needs 1.3", VK_API_VERSION_MAJOR(pp.properties.apiVersion), VK_API_VERSION_MINOR(pp.properties.apiVersion));
    timestamp_ns = pp.properties.limits.timestampPeriod;
    vkGetPhysicalDeviceMemoryProperties(phys, &memprops);
    VkDeviceSize vram = 0;
    for (uint32_t i = 0; i < memprops.memoryHeapCount; ++i) if (memprops.memoryHeaps[i].flags & VK_MEMORY_HEAP_DEVICE_LOCAL_BIT && memprops.memoryHeaps[i].size > vram) vram = memprops.memoryHeaps[i].size;
    snprintf(gpu, n, "%s (PCI %04x:%04x, %u MB), Vulkan %u.%u.%u, driver %s %s", pp.properties.deviceName, pp.properties.vendorID, pp.properties.deviceID, (unsigned)(vram >> 20),
             VK_API_VERSION_MAJOR(pp.properties.apiVersion), VK_API_VERSION_MINOR(pp.properties.apiVersion), VK_API_VERSION_PATCH(pp.properties.apiVersion), drv.driverName, drv.driverInfo);
    uint32_t nq = 0; vkGetPhysicalDeviceQueueFamilyProperties(phys, &nq, NULL);
    VkQueueFamilyProperties qp[16]; if (nq > 16) nq = 16; vkGetPhysicalDeviceQueueFamilyProperties(phys, &nq, qp);
    qfam = UINT32_MAX;
    for (uint32_t i = 0; i < nq; ++i) if ((qp[i].queueFlags & (VK_QUEUE_GRAPHICS_BIT | VK_QUEUE_COMPUTE_BIT)) == (VK_QUEUE_GRAPHICS_BIT | VK_QUEUE_COMPUTE_BIT) && qp[i].timestampValidBits) { qfam = i; break; }
    if (qfam == UINT32_MAX) FAIL("no graphics + compute queue with timestamps");
    // every core feature the graphics has (Vulkan 1.0 to 1.3), passed back as is; cooperative matrices too when offered
    VkPhysicalDeviceVulkan13Features f13 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES};
    VkPhysicalDeviceVulkan12Features f12 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES, .pNext = &f13};
    VkPhysicalDeviceVulkan11Features f11 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_1_FEATURES, .pNext = &f12};
    VkPhysicalDeviceCooperativeMatrixFeaturesKHR fcm = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_COOPERATIVE_MATRIX_FEATURES_KHR};
    VkPhysicalDeviceFeatures2 f2 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2, .pNext = &f11};
    uint32_t ne = 0; vkEnumerateDeviceExtensionProperties(phys, NULL, &ne, NULL);
    VkExtensionProperties* ep = calloc(ne ? ne : 1, sizeof *ep); vkEnumerateDeviceExtensionProperties(phys, NULL, &ne, ep);
    const char* exts[64]; uint32_t nx = 0; bool coop = false;
    for (size_t k = 0; k < sizeof WANT_EXT / sizeof *WANT_EXT; ++k)
        for (uint32_t i = 0; i < ne; ++i)
            if (!strcmp(ep[i].extensionName, WANT_EXT[k])) { exts[nx++] = WANT_EXT[k]; if (!strcmp(WANT_EXT[k], "VK_KHR_cooperative_matrix")) coop = true; break; }
    free(ep);
    if (coop) { fcm.pNext = f2.pNext; f2.pNext = &fcm; }
    vkGetPhysicalDeviceFeatures2(phys, &f2);
    float prio = 1.0f;
    VkDeviceQueueCreateInfo qci = {.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO, .queueFamilyIndex = qfam, .queueCount = 1, .pQueuePriorities = &prio};
    VkDeviceCreateInfo dci = {.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, .pNext = &f2, .queueCreateInfoCount = 1, .pQueueCreateInfos = &qci,
                              .enabledExtensionCount = nx, .ppEnabledExtensionNames = exts};
    VkResult r = vkCreateDevice(phys, &dci, NULL, &dev);
    if (r != VK_SUCCESS) FAIL("Vulkan device creation failed (%d)", (int)r);
#define D(x) x = (PFN_##x)vkGetDeviceProcAddr(dev, #x); if (!x) FAIL("no " #x);
    D(vkGetDeviceQueue) D(vkCreateImage) D(vkDestroyImage) D(vkGetImageMemoryRequirements) D(vkAllocateMemory) D(vkBindImageMemory) D(vkCreateBuffer)
    D(vkGetBufferMemoryRequirements) D(vkBindBufferMemory) D(vkMapMemory) D(vkUnmapMemory) D(vkCreateCommandPool) D(vkAllocateCommandBuffers)
    D(vkBeginCommandBuffer) D(vkEndCommandBuffer) D(vkQueueSubmit) D(vkQueueWaitIdle) D(vkResetCommandBuffer) D(vkCmdPipelineBarrier)
    D(vkCmdCopyBufferToImage) D(vkCmdCopyImageToBuffer) D(vkDestroyBuffer) D(vkFreeMemory) D(vkCreateQueryPool) D(vkCmdResetQueryPool)
    D(vkCmdWriteTimestamp) D(vkGetQueryPoolResults)
#undef D
    vkGetDeviceQueue(dev, qfam, 0, &queue);
    VkCommandPool pool;
    VkCommandPoolCreateInfo pci = {.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO, .flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT, .queueFamilyIndex = qfam};
    VKC(vkCreateCommandPool(dev, &pci, NULL, &pool));
    VkCommandBufferAllocateInfo cai = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO, .commandPool = pool, .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY, .commandBufferCount = 1};
    VKC(vkAllocateCommandBuffers(dev, &cai, &cmd));
    return vk_ok ? 0 : 1;
}

static void PresetSize(ffxFunctions* fx, uint32_t ow, uint32_t oh, uint32_t mode, double ratio, uint32_t* rw, uint32_t* rh, int* phases) {      // as fsr4time.c
    uint32_t w = 0, h = 0; int32_t n = 0;
    struct ffxQueryDescUpscaleGetRenderResolutionFromQualityMode q = {0};
    q.header.type = FFX_API_QUERY_DESC_TYPE_UPSCALE_GETRENDERRESOLUTIONFROMQUALITYMODE; q.displayWidth = ow; q.displayHeight = oh; q.qualityMode = mode;
    q.pOutRenderWidth = &w; q.pOutRenderHeight = &h;
    if (fx->Query(NULL, &q.header) != FFX_API_RETURN_OK || !w || !h) { w = (uint32_t)(ow / ratio); h = (uint32_t)(oh / ratio); }
    struct ffxQueryDescUpscaleGetJitterPhaseCount j = {0};
    j.header.type = FFX_API_QUERY_DESC_TYPE_UPSCALE_GETJITTERPHASECOUNT; j.renderWidth = w; j.displayWidth = ow; j.pOutPhaseCount = &n;
    if (fx->Query(NULL, &j.header) != FFX_API_RETURN_OK || n <= 0) n = (int32_t)(8.0 * ((double)ow / w) * ((double)ow / w));
    if (n > H->phases_max) n = H->phases_max;
    *rw = w; *rh = h; *phases = n;
}

int RunOneVk(const struct VkRunHost* host, const char* name, bool quick) {
    H = host; run_label = name;
    char gpu[512];
    if (CreateDevice(gpu, sizeof(gpu))) return 1;
    HMODULE loader = LoadLibraryA("amd_fidelityfx_loader_vk.dll");
    if (!loader) FAIL("no amd_fidelityfx_loader_vk.dll next to the program");
    ffxFunctions ffx;
    ffxLoadFunctions(&ffx, loader);
    VkDeviceContext dctx = {.vkDevice = dev, .vkPhysicalDevice = phys, .vkDeviceProcAddr = vkGetDeviceProcAddr};
    uint64_t count = 0, ids[32]; const char* names[32];
    struct ffxQueryDescGetVersions versions = {0};
    versions.header.type = FFX_API_QUERY_DESC_TYPE_GET_VERSIONS; versions.createDescType = FFX_API_CREATE_CONTEXT_DESC_TYPE_UPSCALE;
    versions.device = &dctx; versions.outputCount = &count;
    ffx.Query(NULL, &versions.header);
    if (count > 32) count = 32;
    versions.versionIds = ids; versions.versionNames = names;
    ffx.Query(NULL, &versions.header);
    uint64_t vid[8]; const char* vname[8]; int nv = 0;
    for (uint64_t i = 0; i < count; ++i) {      // every FSR 4 version the DLL offers on this graphics, each id once (as RunOne)
        if (nv >= 8 || !(!strncmp(names[i], "4.", 2) || !strncmp(names[i], "fsr4", 4))) continue;
        bool dup = false;
        for (int k = 0; k < nv; ++k) dup = dup || vid[k] == ids[i];
        if (!dup) { vid[nv] = ids[i]; vname[nv++] = names[i]; }
    }
    if (!nv) FAIL("this DLL offers no FSR 4 on this GPU through Vulkan (%llu versions listed)", (unsigned long long)count);
    H->Say("G|%s\n", gpu);

    struct { uint32_t ow, oh, rw, rh; int phases; const char* tag; } sizes[14] = {      // as RunOne
        {1920, 1080, 1130, 636, 16, ""}, {2560, 1440, 1506, 848, 16, ""}, {3840, 2160, 2260, 1272, 16, ""},
        {1920, 1080, 640, 360, 72, " UP"}, {2560, 1440, 853, 480, 72, " UP"}, {3840, 2160, 1280, 720, 72, " UP"}};
    int nsizes = 6;
    if (H->size800) { sizes[nsizes].ow = 1280; sizes[nsizes].oh = 800; sizes[nsizes].rw = 754; sizes[nsizes].rh = 472; sizes[nsizes].phases = 16; sizes[nsizes].tag = ""; ++nsizes; }
    if (H->all_presets)
        for (int m = 0; m < 2; ++m)
            for (int o = 0; o < 3; ++o) {
                sizes[nsizes].ow = sizes[o].ow; sizes[nsizes].oh = sizes[o].oh; sizes[nsizes].tag = m ? " P" : " Q";
                PresetSize(&ffx, sizes[o].ow, sizes[o].oh, m ? FFX_UPSCALE_QUALITY_MODE_PERFORMANCE : FFX_UPSCALE_QUALITY_MODE_QUALITY, m ? 2.0 : 1.5,
                           &sizes[nsizes].rw, &sizes[nsizes].rh, &sizes[nsizes].phases);
                ++nsizes;
            }
    VkQueryPool qpool;
    VkQueryPoolCreateInfo qi = {.sType = VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO, .queryType = VK_QUERY_TYPE_TIMESTAMP, .queryCount = 2};
    VKC(vkCreateQueryPool(dev, &qi, NULL, &qpool));
    const int WARM = H->warm, TIMED = H->timed;
    double* ms = malloc(sizeof(double) * TIMED * 3); double *even = ms + TIMED, *odd = ms + 2 * TIMED;
    float* jx = malloc(sizeof(float) * 2 * H->phases_max); float* jy = jx + H->phases_max;
    Tex* color = malloc(sizeof(Tex) * H->phases_max);

    for (int vi = 0; vi < nv && vk_ok; ++vi) {
        const uint64_t chosen = vid[vi];
        const char* chosen_name = vname[vi];
        char label[64], idtext[40] = "";
        if (nv == 1) snprintf(label, sizeof(label), "%s", name);
        else { snprintf(label, sizeof(label), "%.40s, variant %d of %d", name, vi + 1, nv); snprintf(idtext, sizeof(idtext), ", id %llx", (unsigned long long)chosen); }
        run_label = label;
        for (int si = 0; si < nsizes && vk_ok; ++si) {
            if (quick && sizes[si].ow == 2560) continue;
            const uint32_t ow = sizes[si].ow, oh = sizes[si].oh, rw = sizes[si].rw, rh = sizes[si].rh;
            const int phases = sizes[si].phases;
            char sz[24];
            snprintf(sz, sizeof(sz), "%ux%u%s", ow, oh, sizes[si].tag);
            struct ffxCreateBackendVKDesc backend = {0};
            backend.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_VK; backend.deviceContext = dctx;
            struct ffxOverrideVersion ov = {0};
            ov.header.type = FFX_API_DESC_TYPE_OVERRIDE_VERSION; ov.versionId = chosen; ov.header.pNext = &backend.header;
            for (int p = 0; p < phases; ++p) color[p] = Texture(VK_FORMAT_R16G16B16A16_SFLOAT, rw, rh);
            Tex depth = Texture(VK_FORMAT_R32_SFLOAT, rw, rh), motion = Texture(VK_FORMAT_R16G16_SFLOAT, rw, rh), output = Texture(VK_FORMAT_R16G16B16A16_SFLOAT, ow, oh);
            uint16_t* cbuf = malloc((size_t)rw * rh * 8); float* dbuf = malloc((size_t)rw * rh * 4); uint16_t* mbuf = malloc((size_t)rw * rh * 4);
            for (size_t i = 0; i < (size_t)rw * rh; ++i) dbuf[i] = 0.5f;
            UploadRows(depth, 4, (const uint8_t*)dbuf);
            HostBuf rb = Readback((VkDeviceSize)ow * oh * 8);      // cached memory: the picture checks read it
            const float sx = (float)rw / (float)ow, sy = (float)rh / (float)oh;
            for (int scene = 0; scene < 2 && vk_ok; ++scene) {      // 0: nothing moves; 1: the camera pans 12, 6 output pixels per frame
                const int vx = scene ? 12 : 0, vy = scene ? 6 : 0;
                for (size_t i = 0; i < (size_t)rw * rh; ++i) { mbuf[2 * i] = H->Half((float)vx * sx); mbuf[2 * i + 1] = H->Half((float)vy * sy); }
                UploadRows(motion, 4, (const uint8_t*)mbuf);
                for (int p = 0; p < phases; ++p) {
                    jx[p] = H->Halton(p + 1, 2) - 0.5f; jy[p] = H->Halton(p + 1, 3) - 0.5f;
                    H->Paint(cbuf, rw, rh, sx, sy, jx[p], jy[p], (float)(vx * p), (float)(vy * p));      // (2026-11-14) on all cores, same pixels
                    UploadRows(color[p], 8, (const uint8_t*)cbuf);
                }
                struct ffxCreateContextDescUpscale create = {0};
                create.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_UPSCALE; create.header.pNext = &ov.header;
                create.flags = FFX_UPSCALE_ENABLE_HIGH_DYNAMIC_RANGE | FFX_UPSCALE_ENABLE_AUTO_EXPOSURE;
                create.maxRenderSize.width = ow; create.maxRenderSize.height = oh; create.maxUpscaleSize.width = ow; create.maxUpscaleSize.height = oh;
                create.fpMessage = Message;
                ffxContext context = NULL;
                ffxReturnCode_t rc = ffx.CreateContext(&context, &create.header, NULL);
                if (rc != FFX_API_RETURN_OK) { H->Say("R|%s|FAILED|create context %d at %s\n", label, (int)rc, sz); vk_ok = false; break; }
                struct ffxQueryGetProviderVersion provider = {0};
                provider.header.type = FFX_API_QUERY_DESC_TYPE_GET_PROVIDER_VERSION;
                ffx.Query(&context, &provider.header);
                int ne = 0, no = 0;
                for (int frame = 0; frame < WARM + TIMED && vk_ok; ++frame) {
                    const int p = frame % phases;
                    struct ffxDispatchDescUpscale d = {0};
                    d.header.type = FFX_API_DISPATCH_DESC_TYPE_UPSCALE; d.commandList = (void*)cmd;
                    d.color = Resource(color[p], FFX_API_SURFACE_FORMAT_R16G16B16A16_FLOAT, FFX_API_RESOURCE_STATE_COMMON);
                    d.depth = Resource(depth, FFX_API_SURFACE_FORMAT_R32_FLOAT, FFX_API_RESOURCE_STATE_COMMON);
                    d.motionVectors = Resource(motion, FFX_API_SURFACE_FORMAT_R16G16_FLOAT, FFX_API_RESOURCE_STATE_COMMON);
                    d.output = Resource(output, FFX_API_SURFACE_FORMAT_R16G16B16A16_FLOAT, FFX_API_RESOURCE_STATE_UNORDERED_ACCESS);
                    d.jitterOffset.x = jx[p]; d.jitterOffset.y = jy[p];
                    d.motionVectorScale.x = d.motionVectorScale.y = 1.0f;
                    d.renderSize.width = rw; d.renderSize.height = rh; d.upscaleSize.width = ow; d.upscaleSize.height = oh;
                    d.enableSharpening = false; d.sharpness = 0.5f; d.frameTimeDelta = 10.0f; d.preExposure = 1.0f; d.reset = frame == 0;
                    d.cameraNear = 0.05f; d.cameraFar = 3000.0f; d.cameraFovAngleVertical = 0.75f; d.viewSpaceToMetersFactor = 1.0f;
                    Begin();
                    vkCmdResetQueryPool(cmd, qpool, 0, 2);
                    vkCmdWriteTimestamp(cmd, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT, qpool, 0);
                    rc = ffx.Dispatch(&context, &d.header);
                    if (rc != FFX_API_RETURN_OK) { H->Say("R|%s|FAILED|dispatch %d at %s\n", label, (int)rc, sz); vk_ok = false; break; }
                    vkCmdWriteTimestamp(cmd, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT, qpool, 1);
                    Submit();
                    if (frame >= WARM) {
                        uint64_t t[2] = {0, 0};
                        VKC(vkGetQueryPoolResults(dev, qpool, 0, 2, sizeof t, t, 8, VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT));
                        const double v = (double)(t[1] - t[0]) * timestamp_ns * 1e-6;
                        ms[frame - WARM] = v;
                        if (jx[p] < 0) odd[no++] = v; else even[ne++] = v;
                    }
                }
                if (!vk_ok) { ffx.DestroyContext(&context, NULL); break; }
                double sum = 0, fastest = ms[0], swing = 0;
                for (int i = 0; i < TIMED; ++i) { sum += ms[i]; if (ms[i] < fastest) fastest = ms[i]; if (i) swing += fabs(ms[i] - ms[i - 1]); }
                swing /= TIMED - 1;
                const double med = Median(ms, TIMED), me = Median(even, ne), mo = Median(odd, no);
                const double p95 = ms[(TIMED * 95) / 100], p99 = ms[(TIMED * 99) / 100];
                char key[256], pkey[64];
                snprintf(key, sizeof(key), "%s|%s%s|%s|%s", label, provider.versionName ? provider.versionName : chosen_name, idtext, sz, scene ? "moving" : "still");
                snprintf(pkey, sizeof(pkey), "%s|%ux%u|%s", sz, rw, rh, scene ? "moving" : "still");
                Begin(); FullBarrier();
                VkBufferImageCopy r = {.imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1}, .imageExtent = {ow, oh, 1}};
                vkCmdCopyImageToBuffer(cmd, output.img, VK_IMAGE_LAYOUT_GENERAL, rb.buf, 1, &r);
                FullBarrier(); Submit();
                const uint64_t hsh = H->Picture(rb.ptr, ow * 8, ow, oh, key, label, pkey);
                H->Say("R|%s|%s%s|%s|%ux%u|%s|%.4f|%.4f|%.4f|%.4f|%.4f|%016llx\n", label, provider.versionName ? provider.versionName : chosen_name, idtext, sz, rw, rh,
                       scene ? "moving" : "still", sum / TIMED, med, me, mo, fastest, (unsigned long long)hsh);
                H->Say("F|%s|%s%s|%s|%ux%u|%s|%.4f|%.4f|%.4f\n", label, provider.versionName ? provider.versionName : chosen_name, idtext, sz, rw, rh, scene ? "moving" : "still", p95, p99, swing);
                ffx.DestroyContext(&context, NULL);
            }
            FreeHost(rb); FreeStage();
            for (int p = 0; p < phases; ++p) FreeTex(color[p]);
            FreeTex(depth); FreeTex(motion); FreeTex(output);
            free(cbuf); free(dbuf); free(mbuf);
        }
    }
    free(ms); free(jx); free(color);
    return vk_ok ? 0 : 1;
}
