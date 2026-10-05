// SPDX-License-Identifier: GPL-2.0-or-later
// Times the FSR 4.1.1 INT8 postpass as vkd3d-proton translates it (orig.spv) against the
// workgroup-memory rewrite (lds.spv) on the first AMD GPU, and compares their outputs.
// Inputs are pseudo-random; the descriptor layout follows the dumped shader (heap arrays), with
// sampled images moved to binding 0 so that no mutable descriptor type is needed.
//   gcc -std=gnu11 -O2 bench.c -o bench -lvulkan -lm && ./bench [out_w out_h render_w render_h]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vulkan/vulkan.h>

#define CHECK(x) do { VkResult r_ = (x); if (r_ != VK_SUCCESS) { fprintf(stderr, "%s: %d\n", #x, r_); exit(1); } } while (0)

static VkPhysicalDevice phys;
static VkDevice dev;
static VkQueue queue;
static VkCommandPool pool;
static VkPhysicalDeviceMemoryProperties memprops;

static VkDeviceMemory alloc(VkMemoryRequirements req, VkMemoryPropertyFlags flags, int address) {
    for (uint32_t i = 0; i < memprops.memoryTypeCount; i++) {
        if (!(req.memoryTypeBits & (1u << i)) || (memprops.memoryTypes[i].propertyFlags & flags) != flags) continue;
        VkMemoryAllocateFlagsInfo fi = {VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_FLAGS_INFO, 0, VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_BIT};
        VkMemoryAllocateInfo ai = {VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, address ? &fi : 0, req.size, i};
        VkDeviceMemory m;
        CHECK(vkAllocateMemory(dev, &ai, 0, &m));
        return m;
    }
    fprintf(stderr, "no memory type\n");
    exit(1);
}

static VkBuffer buffer(VkDeviceSize size, VkBufferUsageFlags usage, int host, VkDeviceMemory* mem) {
    VkBufferCreateInfo ci = {VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, .size = size, .usage = usage};
    VkBuffer b;
    CHECK(vkCreateBuffer(dev, &ci, 0, &b));
    VkMemoryRequirements req;
    vkGetBufferMemoryRequirements(dev, b, &req);
    *mem = alloc(req, host ? VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT
                           : VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT, (usage & VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT) != 0);
    CHECK(vkBindBufferMemory(dev, b, *mem, 0));
    return b;
}

typedef struct { VkImage image; VkImageView view; VkFormat format; uint32_t w, h; } Img;

static Img image(VkFormat format, uint32_t w, uint32_t h, VkImageUsageFlags usage) {
    Img img = {.format = format, .w = w, .h = h};
    VkImageCreateInfo ci = {VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO, .imageType = VK_IMAGE_TYPE_2D, .format = format,
        .extent = {w, h, 1}, .mipLevels = 1, .arrayLayers = 1, .samples = VK_SAMPLE_COUNT_1_BIT,
        .usage = usage | VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT};
    CHECK(vkCreateImage(dev, &ci, 0, &img.image));
    VkMemoryRequirements req;
    vkGetImageMemoryRequirements(dev, img.image, &req);
    CHECK(vkBindImageMemory(dev, img.image, alloc(req, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT, 0), 0));
    VkImageViewCreateInfo vi = {VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO, .image = img.image, .viewType = VK_IMAGE_VIEW_TYPE_2D,
        .format = format, .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};
    CHECK(vkCreateImageView(dev, &vi, 0, &img.view));
    return img;
}

static VkCommandBuffer begin(void) {
    VkCommandBufferAllocateInfo ai = {VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO, 0, pool, VK_COMMAND_BUFFER_LEVEL_PRIMARY, 1};
    VkCommandBuffer cb;
    CHECK(vkAllocateCommandBuffers(dev, &ai, &cb));
    VkCommandBufferBeginInfo bi = {VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
    CHECK(vkBeginCommandBuffer(cb, &bi));
    return cb;
}

static void submit(VkCommandBuffer cb) {
    CHECK(vkEndCommandBuffer(cb));
    VkSubmitInfo si = {VK_STRUCTURE_TYPE_SUBMIT_INFO, .commandBufferCount = 1, .pCommandBuffers = &cb};
    CHECK(vkQueueSubmit(queue, 1, &si, VK_NULL_HANDLE));
    CHECK(vkQueueWaitIdle(queue));
    vkFreeCommandBuffers(dev, pool, 1, &cb);
}

static void layout(VkCommandBuffer cb, VkImage image, VkImageLayout from, VkImageLayout to) {
    VkImageMemoryBarrier b = {VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER, .srcAccessMask = 0x1ffff, .dstAccessMask = 0x1ffff,
        .oldLayout = from, .newLayout = to, .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED, .image = image, .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};
    vkCmdPipelineBarrier(cb, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0, 0, 0, 0, 0, 1, &b);
}

static void barrier(VkCommandBuffer cb) {
    VkMemoryBarrier b = {VK_STRUCTURE_TYPE_MEMORY_BARRIER, 0, 0x1ffff, 0x1ffff};
    vkCmdPipelineBarrier(cb, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0, 1, &b, 0, 0, 0, 0);
}

static VkPipeline pipeline(const char* path, VkPipelineLayout pl) {
    FILE* f = fopen(path, "rb");
    if (!f) { perror(path); exit(1); }
    static uint32_t code[1 << 21];
    size_t size = fread(code, 1, sizeof(code), f);
    fclose(f);
    VkShaderModuleCreateInfo mi = {VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO, .codeSize = size, .pCode = code};
    VkShaderModule mod;
    CHECK(vkCreateShaderModule(dev, &mi, 0, &mod));
    VkComputePipelineCreateInfo ci = {VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO, .layout = pl,
        .stage = {VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, .stage = VK_SHADER_STAGE_COMPUTE_BIT, .module = mod, .pName = "main"}};
    VkPipeline p;
    CHECK(vkCreateComputePipelines(dev, VK_NULL_HANDLE, 1, &ci, 0, &p));
    return p;
}

static int cmp_double(const void* a, const void* b) { return (*(double*)a > *(double*)b) - (*(double*)a < *(double*)b); }

int main(int argc, char** argv) {
    uint32_t ow = argc > 2 ? atoi(argv[1]) : 3840, oh = argc > 2 ? atoi(argv[2]) : 2160;
    uint32_t rw = argc > 4 ? atoi(argv[3]) : ow * 2 / 3, rh = argc > 4 ? atoi(argv[4]) : oh * 2 / 3;
    VkFormat out_format = VK_FORMAT_R16G16B16A16_SFLOAT;
    if (getenv("OUT_FORMAT")) out_format = (VkFormat)atoi(getenv("OUT_FORMAT"));

    VkApplicationInfo app = {VK_STRUCTURE_TYPE_APPLICATION_INFO, .apiVersion = VK_API_VERSION_1_3};
    VkInstanceCreateInfo ici = {VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, .pApplicationInfo = &app};
    VkInstance inst;
    CHECK(vkCreateInstance(&ici, 0, &inst));
    VkPhysicalDevice devices[8];
    uint32_t n = 8;
    vkEnumeratePhysicalDevices(inst, &n, devices);
    VkPhysicalDeviceProperties props;
    for (uint32_t i = 0; i < n; i++) {
        vkGetPhysicalDeviceProperties(devices[i], &props);
        if (props.deviceType != VK_PHYSICAL_DEVICE_TYPE_CPU) { phys = devices[i]; break; }   /* first real GPU, integrated or not */
    }
    if (!phys) { fprintf(stderr, "no GPU found\n"); return 1; }
    vkGetPhysicalDeviceProperties(phys, &props);
    vkGetPhysicalDeviceMemoryProperties(phys, &memprops);
    printf("%s, output %ux%u, render %ux%u, output format %d\n", props.deviceName, ow, oh, rw, rh, out_format);

    VkQueueFamilyProperties qf[16];
    uint32_t nq = 16, family = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(phys, &nq, qf);
    for (uint32_t i = 0; i < nq; i++)
        if (qf[i].queueFlags & VK_QUEUE_GRAPHICS_BIT) { family = i; break; }
    float prio = 1;
    VkDeviceQueueCreateInfo qi = {VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO, .queueFamilyIndex = family, .queueCount = 1, .pQueuePriorities = &prio};
    VkPhysicalDeviceVulkan13Features f13 = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES, .shaderIntegerDotProduct = 1};
    VkPhysicalDeviceVulkan12Features f12 = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES, &f13,
        .shaderFloat16 = 1, .shaderInt8 = 1, .descriptorIndexing = 1, .runtimeDescriptorArray = 1,
        .descriptorBindingPartiallyBound = 1, .bufferDeviceAddress = 1,
        .shaderSampledImageArrayNonUniformIndexing = 1, .shaderStorageImageArrayNonUniformIndexing = 1,
        .shaderStorageBufferArrayNonUniformIndexing = 1};
    VkPhysicalDeviceFeatures2 f2 = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2, &f12,
        .features = {.shaderStorageImageWriteWithoutFormat = 1, .shaderStorageImageArrayDynamicIndexing = 1,
                     .shaderSampledImageArrayDynamicIndexing = 1, .shaderStorageBufferArrayDynamicIndexing = 1}};
    VkDeviceCreateInfo dci = {VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, &f2, .queueCreateInfoCount = 1, .pQueueCreateInfos = &qi};
    CHECK(vkCreateDevice(phys, &dci, 0, &dev));
    vkGetDeviceQueue(dev, family, 0, &queue);
    VkCommandPoolCreateInfo pci = {VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO, .queueFamilyIndex = family};
    CHECK(vkCreateCommandPool(dev, &pci, 0, &pool));

    // Resources. Tensor: rows of (1920 + 2) 16-byte pixels, (1080 + 2) rows, for the "2160" level.
    VkDeviceSize tensor_size = 30752ull * 1082, cbv_size = 65536;
    VkDeviceMemory m_staging, m_tensor, m_cbv, m_read;
    VkBuffer staging = buffer(tensor_size + cbv_size, VK_BUFFER_USAGE_TRANSFER_SRC_BIT, 1, &m_staging);
    VkBuffer tensor = buffer(tensor_size, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT, 0, &m_tensor);
    VkBuffer cbv = buffer(cbv_size, VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT |
                                        VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT, 0, &m_cbv);
    uint8_t* map;
    CHECK(vkMapMemory(dev, m_staging, 0, VK_WHOLE_SIZE, 0, (void**)&map));
    uint32_t seed = 12345;
    for (VkDeviceSize i = 0; i < tensor_size; i++) { seed = seed * 1664525u + 1013904223u; map[i] = (uint8_t)(seed >> 24); }
    struct {
        float inv_size[2], scale[2], inv_scale[2], jitter[2], mv_scale[2], tex_size[2], max_render_size[2], mv_jitter_cancellation[2];
        uint32_t width, height, reset, width_lr, height_lr;
        float pre_exposure, previous_pre_exposure;
        uint32_t rcas_enabled;
        float rcas_sharpness;
    } c = {{1.0f / ow, 1.0f / oh}, {(float)ow / rw, (float)oh / rh}, {(float)rw / ow, (float)rh / oh}, {0.21f, -0.13f},
           {1.0f / rw, 1.0f / rh}, {ow, oh}, {ow, oh}, {0, 0}, ow, oh, 0, rw, rh, 1.0f, 1.0f, getenv("RCAS") ? 1u : 0u, 0.5f};
    memset(map + tensor_size, 0, cbv_size);
    memcpy(map + tensor_size, &c, sizeof(c));

    Img input = image(VK_FORMAT_R16G16B16A16_SFLOAT, rw, rh, VK_IMAGE_USAGE_SAMPLED_BIT);
    Img reprojected = image(VK_FORMAT_R16G16B16A16_SFLOAT, ow, oh, VK_IMAGE_USAGE_SAMPLED_BIT);
    Img history = image(VK_FORMAT_R16G16B16A16_SFLOAT, ow, oh, VK_IMAGE_USAGE_STORAGE_BIT);
    Img output = image(out_format, ow, oh, VK_IMAGE_USAGE_STORAGE_BIT);
    Img recurrent = image(VK_FORMAT_R8G8B8A8_UNORM, ow, oh, VK_IMAGE_USAGE_STORAGE_BIT);
    Img exposure_in = image(VK_FORMAT_R32_SFLOAT, 2, 1, VK_IMAGE_USAGE_SAMPLED_BIT);      // variants with auto exposure
    Img exposure_out = image(VK_FORMAT_R32_SFLOAT, 2, 1, VK_IMAGE_USAGE_STORAGE_BIT);
    Img* targets[3] = {&history, &output, &recurrent};
    VkDeviceSize read_size = (VkDeviceSize)ow * oh * 8;
    VkBuffer readback = buffer(read_size, VK_BUFFER_USAGE_TRANSFER_DST_BIT, 1, &m_read);
    uint8_t* read_map;
    CHECK(vkMapMemory(dev, m_read, 0, VK_WHOLE_SIZE, 0, (void**)&read_map));

    VkCommandBuffer cb = begin();
    VkBufferCopy copy_tensor = {0, 0, tensor_size}, copy_cbv = {tensor_size, 0, cbv_size};
    vkCmdCopyBuffer(cb, staging, tensor, 1, &copy_tensor);
    vkCmdCopyBuffer(cb, staging, cbv, 1, &copy_cbv);
    VkImageSubresourceRange range = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
    VkClearColorValue grey = {{0.4f, 0.3f, 0.2f, 1.0f}}, grey2 = {{0.35f, 0.33f, 0.25f, 1.0f}};
    layout(cb, input.image, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL);
    layout(cb, reprojected.image, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL);
    vkCmdClearColorImage(cb, input.image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, &grey, 1, &range);
    vkCmdClearColorImage(cb, reprojected.image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, &grey2, 1, &range);
    layout(cb, input.image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);
    VkClearColorValue one = {{1.0f, 1.0f, 1.0f, 1.0f}};
    layout(cb, exposure_in.image, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL);
    vkCmdClearColorImage(cb, exposure_in.image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, &one, 1, &range);
    layout(cb, exposure_in.image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);
    layout(cb, exposure_out.image, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_GENERAL);
    layout(cb, reprojected.image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);
    for (int i = 0; i < 3; i++) {
        VkClearColorValue sentinel = {{0.75f, 0.75f, 0.75f, 0.75f}};
        layout(cb, targets[i]->image, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_GENERAL);
        vkCmdClearColorImage(cb, targets[i]->image, VK_IMAGE_LAYOUT_GENERAL, &sentinel, 1, &range);
    }
    submit(cb);

    // Layouts: set 0 empty, set 1 = {sampled images[16], storage images[16]}, set 2 = {storage buffers[16]}.
    VkDescriptorBindingFlags partial[2] = {VK_DESCRIPTOR_BINDING_PARTIALLY_BOUND_BIT, VK_DESCRIPTOR_BINDING_PARTIALLY_BOUND_BIT};
    VkDescriptorSetLayoutBindingFlagsCreateInfo flags2 = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_BINDING_FLAGS_CREATE_INFO, 0, 2, partial};
    VkDescriptorSetLayoutBindingFlagsCreateInfo flags1 = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_BINDING_FLAGS_CREATE_INFO, 0, 1, partial};
    VkDescriptorSetLayoutBinding b1[2] = {{0, VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, 32, VK_SHADER_STAGE_COMPUTE_BIT},
                                          {1, VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, 32, VK_SHADER_STAGE_COMPUTE_BIT}};
    VkDescriptorSetLayoutBinding b2[1] = {{0, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 16, VK_SHADER_STAGE_COMPUTE_BIT}};
    VkDescriptorSetLayoutCreateInfo l0 = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};
    VkDescriptorSetLayoutCreateInfo l1 = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO, &flags2, 0, 2, b1};
    VkDescriptorSetLayoutCreateInfo l2 = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO, &flags1, 0, 1, b2};
    VkDescriptorSetLayout sl[3];
    CHECK(vkCreateDescriptorSetLayout(dev, &l0, 0, &sl[0]));
    CHECK(vkCreateDescriptorSetLayout(dev, &l1, 0, &sl[1]));
    CHECK(vkCreateDescriptorSetLayout(dev, &l2, 0, &sl[2]));
    VkPushConstantRange pcr = {VK_SHADER_STAGE_COMPUTE_BIT, 0, 16};
    VkPipelineLayoutCreateInfo pli = {VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, .setLayoutCount = 3, .pSetLayouts = sl,
        .pushConstantRangeCount = 1, .pPushConstantRanges = &pcr};
    VkPipelineLayout pl;
    CHECK(vkCreatePipelineLayout(dev, &pli, 0, &pl));
    VkDescriptorPoolSize sizes[3] = {{VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, 32}, {VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, 32}, {VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 16}};
    VkDescriptorPoolCreateInfo dpi = {VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO, .maxSets = 3, .poolSizeCount = 3, .pPoolSizes = sizes};
    VkDescriptorPool dp;
    CHECK(vkCreateDescriptorPool(dev, &dpi, 0, &dp));
    VkDescriptorSetAllocateInfo dai = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO, 0, dp, 3, sl};
    VkDescriptorSet sets[3];
    CHECK(vkAllocateDescriptorSets(dev, &dai, sets));
    // Heap offsets as the shader adds them to its root constants (both 0 here).
    VkDescriptorImageInfo i_input = {0, input.view, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    VkDescriptorImageInfo i_reproj = {0, reprojected.view, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    VkDescriptorImageInfo i_a = {0, history.view, VK_IMAGE_LAYOUT_GENERAL}, i_b = {0, output.view, VK_IMAGE_LAYOUT_GENERAL};
    VkDescriptorImageInfo i_r = {0, recurrent.view, VK_IMAGE_LAYOUT_GENERAL};
    VkDescriptorBufferInfo i_t = {tensor, 0, VK_WHOLE_SIZE};
    VkDescriptorImageInfo i_ei = {0, exposure_in.view, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL}, i_eo = {0, exposure_out.view, VK_IMAGE_LAYOUT_GENERAL};
    VkWriteDescriptorSet w[9] = {
        {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, 0, sets[1], 0, 17, 1, VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, &i_ei},
        {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, 0, sets[1], 0, 6, 1, VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, &i_ei},
        {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, 0, sets[1], 1, 9, 1, VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, &i_eo},
        {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, 0, sets[1], 0, 3, 1, VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, &i_input},
        {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, 0, sets[1], 0, 9, 1, VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, &i_reproj},
        {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, 0, sets[1], 1, 1, 1, VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, &i_a},
        {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, 0, sets[1], 1, 2, 1, VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, &i_b},
        {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, 0, sets[1], 1, 6, 1, VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, &i_r},
        {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, 0, sets[2], 0, 11, 1, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 0, &i_t},
    };
    vkUpdateDescriptorSets(dev, 9, w, 0, 0);
    VkBufferDeviceAddressInfo bai = {VK_STRUCTURE_TYPE_BUFFER_DEVICE_ADDRESS_INFO, 0, cbv};
    struct { uint64_t cbv; uint32_t heap_uav, heap_srv; } push = {vkGetBufferDeviceAddress(dev, &bai), 0, 0};

    const char* names[2] = {getenv("A") ? getenv("A") : "orig.spv", getenv("B") ? getenv("B") : "lds.spv"};
    VkPipeline pipes[2] = {pipeline(names[0], pl), pipeline(names[1], pl)};
    VkQueryPoolCreateInfo qpi = {VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO, .queryType = VK_QUERY_TYPE_TIMESTAMP, .queryCount = 2};
    VkQueryPool qp;
    CHECK(vkCreateQueryPool(dev, &qpi, 0, &qp));
    uint32_t gx = (ow / 2 + 15) / 16, gy = (oh / 2 + 15) / 16;
    uint8_t* results[2][3];
    enum { RUNS = 15 }; int DISPATCHES = getenv("N_DISP") ? atoi(getenv("N_DISP")) : 50;

    for (int round = 0; round < 2; round++) {
        for (int v = 0; v < 2; v++) {
            double ms[RUNS];
            for (int run = 0; run < RUNS; run++) {
                cb = begin();
                vkCmdResetQueryPool(cb, qp, 0, 2);
                vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pipes[v]);
                vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pl, 0, 3, sets, 0, 0);
                vkCmdPushConstants(cb, pl, VK_SHADER_STAGE_COMPUTE_BIT, 0, 16, &push);
                vkCmdWriteTimestamp(cb, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, qp, 0);
                for (int d = 0; d < DISPATCHES; d++) { vkCmdDispatch(cb, gx, gy, 1); barrier(cb); }
                vkCmdWriteTimestamp(cb, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, qp, 1);
                submit(cb);
                uint64_t t[2];
                CHECK(vkGetQueryPoolResults(dev, qp, 0, 2, sizeof(t), t, 8, VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT));
                ms[run] = (double)(t[1] - t[0]) * props.limits.timestampPeriod / 1e6 / DISPATCHES;
            }
            qsort(ms, RUNS, sizeof(double), cmp_double);
            printf("round %d  %-8s  %ux%u groups  min %.3f ms  median %.3f ms  max %.3f ms\n", round, names[v], gx, gy,
                   ms[0], ms[RUNS / 2], ms[RUNS - 1]);
            if (round) continue;
            if (getenv("SLEEP")) { vkDeviceWaitIdle(dev); system("sleep 1"); }
            for (int i = 0; i < 3; i++) {
                VkDeviceSize bytes = (VkDeviceSize)ow * oh * (targets[i]->format == VK_FORMAT_R16G16B16A16_SFLOAT ? 8 : 4);
                cb = begin();
                VkBufferImageCopy region = {.imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1}, .imageExtent = {ow, oh, 1}};
                vkCmdCopyImageToBuffer(cb, targets[i]->image, VK_IMAGE_LAYOUT_GENERAL, readback, 1, &region);
                barrier(cb);
                VkClearColorValue zero = {{0.75f, 0.75f, 0.75f, 0.75f}};
                vkCmdClearColorImage(cb, targets[i]->image, VK_IMAGE_LAYOUT_GENERAL, &zero, 1, &range);
                submit(cb);
                results[v][i] = malloc(bytes);
                memcpy(results[v][i], read_map, bytes);
                if (getenv("DUMP")) { char nm[64]; sprintf(nm, "out_%d_%d.raw", v, i); FILE* o = fopen(nm, "wb"); fwrite(read_map, 1, bytes, o); fclose(o); }
                if (v == 1) {
                    size_t diff = 0, nonzero = 0;
                    for (VkDeviceSize k = 0; k < bytes; k++) { diff += results[0][i][k] != results[1][i][k]; nonzero += results[0][i][k] != 0; }
                    {
                        uint32_t bpp = bytes / ((VkDeviceSize)ow * oh), x0 = ow, x1 = 0, y0 = oh, y1 = 0, shown = 0;
                        size_t pix = 0, hist[4] = {0};
                        for (uint32_t y = 0; y < oh; y++) for (uint32_t x = 0; x < ow; x++) {
                            size_t o = ((size_t)y * ow + x) * bpp;
                            if (!memcmp(results[0][i] + o, results[1][i] + o, bpp)) continue;
                            pix++; hist[(y & 1) * 2 + (x & 1)]++;
                            if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
                            if (shown++ < 3) {
                                printf("    (%u,%u):", x, y);
                                for (uint32_t k = 0; k < bpp; k++) printf(" %02x", results[0][i][o + k]);
                                printf(" |");
                                for (uint32_t k = 0; k < bpp; k++) printf(" %02x", results[1][i][o + k]);
                                printf("\n");
                            }
                        }
                        printf("    %zu pixels differ, box x %u..%u y %u..%u, by 2x2 position %zu %zu %zu %zu\n", pix, x0, x1, y0, y1, hist[0], hist[1], hist[2], hist[3]);
                    }
                    printf("  image %d (%s): %zu of %llu bytes differ (%zu nonzero in the original)\n", i,
                           i == 0 ? "heap+1" : i == 1 ? "heap+2" : "heap+6, recurrent", diff, (unsigned long long)bytes, nonzero);
                }
            }
        }
    }
    return 0;
}
