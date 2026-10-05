// SPDX-License-Identifier: GPL-2.0-or-later
// Times the FSR 4.1.1 prepass as dumped from vkd3d-proton and compares variants (4K output).
//   ./pbench a.spv [b.spv ...]     (sampled images moved to set 1 binding 0, see prep.sh)
// Inputs: constant colour/history, constant depth, small constant motion, pseudo-random weights.
// Each variant runs from the same scratch buffer; the reprojected image and the scratch buffer
// are read back and compared with the first variant's, then the pass is timed in a long burst.
#define main postpass_bench_main
#include "bench.c"
#undef main

int main(int argc, char** argv) {
    if (argc < 2) { fprintf(stderr, "usage: pbench a.spv [b.spv ...]\n"); return 1; }
    uint32_t ow = 3840, oh = 2160, rw = 2560, rh = 1440;
    if (getenv("OUT")) { sscanf(getenv("OUT"), "%ux%u", &ow, &oh); rw = ow * 2 / 3; rh = oh * 2 / 3; }
    if (getenv("RENDER")) sscanf(getenv("RENDER"), "%ux%u", &rw, &rh);
    int nv = argc - 1;
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
    vkGetPhysicalDeviceProperties(phys, &props);
    vkGetPhysicalDeviceMemoryProperties(phys, &memprops);
    float prio = 1;
    VkDeviceQueueCreateInfo qi = {VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO, .queueFamilyIndex = 0, .queueCount = 1, .pQueuePriorities = &prio};
    VkPhysicalDeviceVulkan13Features f13 = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES, .shaderIntegerDotProduct = 1};
    VkPhysicalDeviceVulkan12Features f12 = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES, &f13,
        .shaderFloat16 = 1, .shaderInt8 = 1, .descriptorIndexing = 1, .runtimeDescriptorArray = 1,
        .descriptorBindingPartiallyBound = 1, .bufferDeviceAddress = 1, .shaderStorageBufferArrayNonUniformIndexing = 1,
        .shaderSampledImageArrayNonUniformIndexing = 1, .shaderStorageImageArrayNonUniformIndexing = 1};
    VkPhysicalDeviceFeatures2 f2 = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2, &f12,
        .features = {.shaderInt16 = 1, .shaderStorageBufferArrayDynamicIndexing = 1, .shaderStorageImageWriteWithoutFormat = 1,
                     .shaderStorageImageArrayDynamicIndexing = 1, .shaderSampledImageArrayDynamicIndexing = 1}};
    VkDeviceCreateInfo dci = {VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, &f2, .queueCreateInfoCount = 1, .pQueueCreateInfos = &qi};
    CHECK(vkCreateDevice(phys, &dci, 0, &dev));
    vkGetDeviceQueue(dev, 0, 0, &queue);
    VkCommandPoolCreateInfo pci = {VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO, .queueFamilyIndex = 0};
    CHECK(vkCreateCommandPool(dev, &pci, 0, &pool));

    VkDeviceSize scratch_size = 83232256, init_size = 131072, cbv_size = 65536, image_bytes = (VkDeviceSize)ow * oh * 8;
    VkDeviceMemory m_staging, m_scratch, m_init, m_cbv, m_read;
    VkBuffer staging = buffer(scratch_size + init_size + cbv_size, VK_BUFFER_USAGE_TRANSFER_SRC_BIT, 1, &m_staging);
    VkBuffer scratch = buffer(scratch_size, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT | VK_BUFFER_USAGE_TRANSFER_SRC_BIT, 0, &m_scratch);
    VkBuffer init = buffer(init_size, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT, 0, &m_init);
    VkBuffer cbv = buffer(cbv_size, VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT | VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT, 0, &m_cbv);
    VkBuffer readback = buffer(scratch_size + image_bytes, VK_BUFFER_USAGE_TRANSFER_DST_BIT, 1, &m_read);
    uint8_t *map, *read_map;
    CHECK(vkMapMemory(dev, m_staging, 0, VK_WHOLE_SIZE, 0, (void**)&map));
    CHECK(vkMapMemory(dev, m_read, 0, VK_WHOLE_SIZE, 0, (void**)&read_map));
    memset(map, 0, scratch_size);
    uint32_t seed = 777;
    // Weights: the pass reads them as floats, so keep them small finite numbers.
    float* wts = (float*)(map + scratch_size);
    for (VkDeviceSize i = 0; i < init_size / 4; i++) { seed = seed * 1664525u + 1013904223u; wts[i] = ((int)(seed >> 20) - 2048) / 4096.0f; }
    struct {
        float inv_size[2], scale[2], inv_scale[2], jitter[2], mv_scale[2], tex_size[2], max_render_size[2], mv_jitter_cancellation[2];
        uint32_t width, height, reset, width_lr, height_lr;
        float pre_exposure, previous_pre_exposure;
        uint32_t rcas_enabled;
        float rcas_sharpness;
    } c = {{1.0f / ow, 1.0f / oh}, {(float)ow / rw, (float)oh / rh}, {(float)rw / ow, (float)rh / oh}, {0.21f, -0.13f},
           {1.0f / rw, 1.0f / rh}, {ow, oh}, {ow, oh}, {0, 0}, ow, oh, 0, rw, rh, 1.0f, 1.0f, 0, 0.0f};
    memset(map + scratch_size + init_size, 0, cbv_size);
    memcpy(map + scratch_size + init_size, &c, sizeof(c));

    Img color = image(VK_FORMAT_R16G16B16A16_SFLOAT, rw, rh, VK_IMAGE_USAGE_SAMPLED_BIT);
    Img exposure = image(VK_FORMAT_R32_SFLOAT, 2, 1, VK_IMAGE_USAGE_SAMPLED_BIT);
    Img depth = image(VK_FORMAT_R32_SFLOAT, rw, rh, VK_IMAGE_USAGE_SAMPLED_BIT);
    Img velocity = image(VK_FORMAT_R16G16_SFLOAT, rw, rh, VK_IMAGE_USAGE_SAMPLED_BIT);
    Img history = image(VK_FORMAT_R16G16B16A16_SFLOAT, ow, oh, VK_IMAGE_USAGE_SAMPLED_BIT);
    Img reprojected = image(VK_FORMAT_R16G16B16A16_SFLOAT, ow, oh, VK_IMAGE_USAGE_STORAGE_BIT);
    // Heap slots by guesswork from the fetch patterns: 0 sampled once, 1 one texel, 2 a 3x3
    // neighbourhood, 3 a 2x2 neighbourhood, 4 sampled nine times. Override with SLOTS=c,e,d,v,h.
    Img* srv[5] = {&color, &exposure, &depth, &velocity, &history};
    if (getenv("SLOTS")) {
        Img* by[256] = {0};
        by['c'] = &color; by['e'] = &exposure; by['d'] = &depth; by['v'] = &velocity; by['h'] = &history;
        for (int i = 0; i < 5; i++) srv[i] = by[(unsigned char)getenv("SLOTS")[i * 2]];
    }
    VkSamplerCreateInfo sci = {VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO, .magFilter = VK_FILTER_LINEAR, .minFilter = VK_FILTER_LINEAR,
        .addressModeU = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE, .addressModeV = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,
        .addressModeW = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE};
    VkSampler sampler;
    CHECK(vkCreateSampler(dev, &sci, 0, &sampler));

    VkCommandBuffer cb = begin();
    VkBufferCopy c_scratch = {0, 0, scratch_size}, c_init = {scratch_size, 0, init_size}, c_cbv = {scratch_size + init_size, 0, cbv_size};
    vkCmdCopyBuffer(cb, staging, init, 1, &c_init);
    vkCmdCopyBuffer(cb, staging, cbv, 1, &c_cbv);
    VkImageSubresourceRange range = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
    VkClearColorValue clears[5] = {{{0.4f, 0.3f, 0.2f, 1.0f}}, {{1.0f, 0, 0, 0}}, {{0.5f, 0, 0, 0}}, {{0.002f, -0.001f, 0, 0}}, {{0.35f, 0.33f, 0.25f, 1.0f}}};
    Img* all[5] = {&color, &exposure, &depth, &velocity, &history};
    for (int i = 0; i < 5; i++) {
        layout(cb, all[i]->image, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL);
        vkCmdClearColorImage(cb, all[i]->image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, &clears[i], 1, &range);
        layout(cb, all[i]->image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);
    }
    layout(cb, reprojected.image, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_GENERAL);
    submit(cb);

    VkDescriptorBindingFlags partial[2] = {VK_DESCRIPTOR_BINDING_PARTIALLY_BOUND_BIT, VK_DESCRIPTOR_BINDING_PARTIALLY_BOUND_BIT};
    VkDescriptorSetLayoutBindingFlagsCreateInfo flags2 = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_BINDING_FLAGS_CREATE_INFO, 0, 2, partial};
    VkDescriptorSetLayoutBindingFlagsCreateInfo flags1 = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_BINDING_FLAGS_CREATE_INFO, 0, 1, partial};
    VkDescriptorSetLayoutBinding b1[2] = {{0, VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, 32, VK_SHADER_STAGE_COMPUTE_BIT},
                                          {1, VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, 16, VK_SHADER_STAGE_COMPUTE_BIT}};
    VkDescriptorSetLayoutBinding b2 = {0, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 32, VK_SHADER_STAGE_COMPUTE_BIT};
    VkDescriptorSetLayoutBinding b3 = {0, VK_DESCRIPTOR_TYPE_SAMPLER, 1, VK_SHADER_STAGE_COMPUTE_BIT};
    VkDescriptorSetLayoutCreateInfo l0 = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};
    VkDescriptorSetLayoutCreateInfo l1 = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO, &flags2, 0, 2, b1};
    VkDescriptorSetLayoutCreateInfo l2 = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO, &flags1, 0, 1, &b2};
    VkDescriptorSetLayoutCreateInfo l3 = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO, 0, 0, 1, &b3};
    VkDescriptorSetLayout sl[4];
    CHECK(vkCreateDescriptorSetLayout(dev, &l0, 0, &sl[0]));
    CHECK(vkCreateDescriptorSetLayout(dev, &l1, 0, &sl[1]));
    CHECK(vkCreateDescriptorSetLayout(dev, &l2, 0, &sl[2]));
    CHECK(vkCreateDescriptorSetLayout(dev, &l3, 0, &sl[3]));
    VkPushConstantRange pcr = {VK_SHADER_STAGE_COMPUTE_BIT, 0, 16};
    VkPipelineLayoutCreateInfo pli = {VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, .setLayoutCount = 4, .pSetLayouts = sl,
        .pushConstantRangeCount = 1, .pPushConstantRanges = &pcr};
    VkPipelineLayout pl;
    CHECK(vkCreatePipelineLayout(dev, &pli, 0, &pl));
    VkDescriptorPoolSize sizes[4] = {{VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, 32}, {VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, 16},
                                     {VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 32}, {VK_DESCRIPTOR_TYPE_SAMPLER, 1}};
    VkDescriptorPoolCreateInfo dpi = {VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO, .maxSets = 4, .poolSizeCount = 4, .pPoolSizes = sizes};
    VkDescriptorPool dp;
    CHECK(vkCreateDescriptorPool(dev, &dpi, 0, &dp));
    VkDescriptorSetAllocateInfo dai = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO, 0, dp, 4, sl};
    VkDescriptorSet sets[4];
    CHECK(vkAllocateDescriptorSets(dev, &dai, sets));
    VkDescriptorImageInfo ii[5], i_out = {0, reprojected.view, VK_IMAGE_LAYOUT_GENERAL}, i_smp = {sampler, 0, 0};
    VkDescriptorBufferInfo i_s = {scratch, 0, VK_WHOLE_SIZE}, i_w = {init, 0, VK_WHOLE_SIZE};
    VkWriteDescriptorSet w[9];
    for (int i = 0; i < 5; i++) {
        ii[i] = (VkDescriptorImageInfo){0, srv[i]->view, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
        w[i] = (VkWriteDescriptorSet){VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, 0, sets[1], 0, i, 1, VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, &ii[i]};
    }
    w[5] = (VkWriteDescriptorSet){VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, 0, sets[1], 1, 3, 1, VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, &i_out};
    w[6] = (VkWriteDescriptorSet){VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, 0, sets[2], 0, 11, 1, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 0, &i_s};
    w[7] = (VkWriteDescriptorSet){VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, 0, sets[2], 0, 18, 1, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 0, &i_w};
    w[8] = (VkWriteDescriptorSet){VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, 0, sets[3], 0, 0, 1, VK_DESCRIPTOR_TYPE_SAMPLER, &i_smp};
    {   // every sampled slot gets a valid image first (other prepass versions read slots 6 and 17: exposure)
        VkDescriptorImageInfo d = {0, exposure.view, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
        for (int i = 0; i < 32; i++) {
            VkWriteDescriptorSet x = {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, 0, sets[1], 0, i, 1, VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, &d};
            vkUpdateDescriptorSets(dev, 1, &x, 0, 0);
        }
    }
    vkUpdateDescriptorSets(dev, 9, w, 0, 0);
    VkBufferDeviceAddressInfo bai = {VK_STRUCTURE_TYPE_BUFFER_DEVICE_ADDRESS_INFO, 0, cbv};
    struct { uint64_t cbv; uint32_t a, b; } push = {vkGetBufferDeviceAddress(dev, &bai), 0, 0};

    VkQueryPoolCreateInfo qpi = {VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO, .queryType = VK_QUERY_TYPE_TIMESTAMP, .queryCount = 2};
    VkQueryPool qp;
    CHECK(vkCreateQueryPool(dev, &qpi, 0, &qp));
    uint32_t gx = (ow + 15) / 16, gy = (oh + 15) / 16;
    enum { RUNS = 9 };
    int dispatches = getenv("N_DISP") ? atoi(getenv("N_DISP")) : 60;
    uint8_t* first = 0;
    VkPipeline pipes[16];
    for (int v = 0; v < nv; v++) pipes[v] = pipeline(argv[1 + v], pl);
    for (int round = 0; round < 2; round++)
    for (int v = 0; v < nv; v++) {
        VkPipeline pipe = pipes[v];
        size_t diff_buf = 0, diff_img = 0, nonzero = 0;
        if (round == 0) {
            cb = begin();
            vkCmdCopyBuffer(cb, staging, scratch, 1, &c_scratch);
            VkClearColorValue sentinel = {{0.75f, 0.75f, 0.75f, 0.75f}};
            vkCmdClearColorImage(cb, reprojected.image, VK_IMAGE_LAYOUT_GENERAL, &sentinel, 1, &range);
            barrier(cb);
            vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pipe);
            vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pl, 0, 4, sets, 0, 0);
            vkCmdPushConstants(cb, pl, VK_SHADER_STAGE_COMPUTE_BIT, 0, 16, &push);
            vkCmdDispatch(cb, gx, gy, 1);
            barrier(cb);
            vkCmdCopyBuffer(cb, scratch, readback, 1, &c_scratch);
            VkBufferImageCopy region = {.bufferOffset = scratch_size, .imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1}, .imageExtent = {ow, oh, 1}};
            vkCmdCopyImageToBuffer(cb, reprojected.image, VK_IMAGE_LAYOUT_GENERAL, readback, 1, &region);
            submit(cb);
            if (v == 0) { first = malloc(scratch_size + image_bytes); memcpy(first, read_map, scratch_size + image_bytes); }
            for (VkDeviceSize i = 0; i < scratch_size; i++) { diff_buf += read_map[i] != first[i]; nonzero += read_map[i] != 0; }
            for (VkDeviceSize i = scratch_size; i < scratch_size + image_bytes; i++) diff_img += read_map[i] != first[i];
            if (v == 0) {
                size_t sent = 0;
                for (VkDeviceSize i = scratch_size; i < scratch_size + image_bytes; i += 8) sent += !memcmp(read_map + i, "\x00\x3a\x00\x3a\x00\x3a\x00\x3a", 8);
                printf("reference: %zu nonzero tensor bytes, %zu of %u image pixels left unwritten\n", nonzero, sent, ow * oh);
            }
        }
        double ms[RUNS];
        for (int run = 0; run < RUNS; run++) {
            cb = begin();
            vkCmdResetQueryPool(cb, qp, 0, 2);
            vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pipe);
            vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pl, 0, 4, sets, 0, 0);
            vkCmdPushConstants(cb, pl, VK_SHADER_STAGE_COMPUTE_BIT, 0, 16, &push);
            for (int d = 0; d < 10; d++) { vkCmdDispatch(cb, gx, gy, 1); barrier(cb); }     // warm-up
            vkCmdWriteTimestamp(cb, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, qp, 0);
            for (int d = 0; d < dispatches; d++) { vkCmdDispatch(cb, gx, gy, 1); barrier(cb); }
            vkCmdWriteTimestamp(cb, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, qp, 1);
            submit(cb);
            uint64_t t[2];
            CHECK(vkGetQueryPoolResults(dev, qp, 0, 2, sizeof(t), t, 8, VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT));
            ms[run] = (double)(t[1] - t[0]) * props.limits.timestampPeriod / 1e6 / dispatches;
        }
        qsort(ms, RUNS, sizeof(double), cmp_double);
        printf("round %d  %-22s median %.3f ms (min %.3f, max %.3f)", round, argv[1 + v], ms[RUNS / 2], ms[0], ms[RUNS - 1]);
        if (round == 0) printf("  %s", v == 0 ? "reference" : diff_buf || diff_img ? "DIFFERS" : "IDENTICAL to reference");
        printf("\n");
        if (round == 0 && (diff_buf || diff_img)) printf("    tensor bytes differing: %zu, image bytes differing: %zu\n", diff_buf, diff_img);
    }
    return 0;
}
