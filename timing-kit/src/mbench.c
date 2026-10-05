// SPDX-License-Identifier: GPL-2.0-or-later
// Times FSR 4.1.1 INT8 model passes as dumped from vkd3d-proton and compares variants.
//   ./mbench <level 1|2|3> <a.spv> [b.spv ...]     (4K output: level 1 = 1920x1080 tensors)
// Each variant runs on the same pseudo-random scratch buffer and weights; the scratch buffer is
// read back after one dispatch and compared with the first variant's, then the pass is timed.
#define main postpass_bench_main
#include "bench.c"
#undef main

static uint64_t fnv(const uint8_t* p, size_t n) {
    uint64_t h = 1469598103934665603ull;
    for (size_t i = 0; i < n; i++) { h ^= p[i]; h *= 1099511628211ull; }
    return h;
}

int main(int argc, char** argv) {
    if (argc < 3) { fprintf(stderr, "usage: mbench <level> <a.spv> [b.spv ...]\n"); return 1; }
    uint32_t level = atoi(argv[1]), ow = 3840, oh = 2160;
    if (getenv("OUT")) sscanf(getenv("OUT"), "%ux%u", &ow, &oh);
    int nv = argc - 2;
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
    VkPhysicalDeviceCooperativeMatrixFeaturesKHR fcm = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_COOPERATIVE_MATRIX_FEATURES_KHR, .cooperativeMatrix = 1};
    VkPhysicalDeviceVulkan13Features f13 = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES, 0, .shaderIntegerDotProduct = 1, .subgroupSizeControl = 1, .computeFullSubgroups = 1};
    VkPhysicalDeviceVulkan12Features f12 = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES, &f13,
        .shaderFloat16 = 1, .shaderInt8 = 1, .storageBuffer8BitAccess = 1, .vulkanMemoryModel = 1, .descriptorIndexing = 1, .runtimeDescriptorArray = 1,
        .descriptorBindingPartiallyBound = 1, .bufferDeviceAddress = 1, .shaderStorageBufferArrayNonUniformIndexing = 1};
    VkPhysicalDeviceFeatures2 f2 = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2, &f12,
        .features = {.shaderInt16 = 1, .shaderStorageBufferArrayDynamicIndexing = 1}};
    const char* exts[] = {"VK_KHR_cooperative_matrix"};
    VkDeviceCreateInfo dci = {VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, &f2, .queueCreateInfoCount = 1, .pQueueCreateInfos = &qi, .enabledExtensionCount = 0, .ppEnabledExtensionNames = exts};
    CHECK(vkCreateDevice(phys, &dci, 0, &dev));
    vkGetDeviceQueue(dev, 0, 0, &queue);
    VkCommandPoolCreateInfo pci = {VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO, .queueFamilyIndex = 0};
    CHECK(vkCreateCommandPool(dev, &pci, 0, &pool));

    VkDeviceSize scratch_size = 83232256, init_size = 131072, cbv_size = 65536;
    VkDeviceMemory m_staging, m_scratch, m_init, m_cbv, m_read;
    VkBuffer staging = buffer(scratch_size + init_size + cbv_size, VK_BUFFER_USAGE_TRANSFER_SRC_BIT, 1, &m_staging);
    VkBuffer scratch = buffer(scratch_size, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT | VK_BUFFER_USAGE_TRANSFER_SRC_BIT, 0, &m_scratch);
    VkBuffer init = buffer(init_size, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT, 0, &m_init);
    VkBuffer cbv = buffer(cbv_size, VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT | VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT, 0, &m_cbv);
    VkBuffer readback = buffer(scratch_size, VK_BUFFER_USAGE_TRANSFER_DST_BIT, 1, &m_read);
    uint8_t *map, *read_map;
    CHECK(vkMapMemory(dev, m_staging, 0, VK_WHOLE_SIZE, 0, (void**)&map));
    CHECK(vkMapMemory(dev, m_read, 0, VK_WHOLE_SIZE, 0, (void**)&read_map));
    uint32_t seed = 4242;
    for (VkDeviceSize i = 0; i < scratch_size + init_size; i++) { seed = seed * 1664525u + 1013904223u; map[i] = (uint8_t)(seed >> 24); }
    FILE* wf = getenv("WEIGHTS") ? fopen(getenv("WEIGHTS"), "rb") : 0;
    if (wf) { if (fread(map + scratch_size, 1, init_size, wf) != init_size) { fprintf(stderr, "short weights\n"); return 1; } fclose(wf); }
    uint32_t* sizes = (uint32_t*)(map + scratch_size + init_size);
    memset(sizes, 0, cbv_size);
    static const uint32_t shift[17] = {1, 0, 1, 1, 2, 2, 2, 3, 3, 3, 2, 2, 1, 1, 0, 0, 0};
    for (int i = 0; i < 17; i++) { sizes[i * 4] = ow >> shift[i]; sizes[i * 4 + 1] = oh >> shift[i]; }
    VkBufferCopy c_scratch = {0, 0, scratch_size}, c_init = {scratch_size, 0, init_size}, c_cbv = {scratch_size + init_size, 0, cbv_size};
    VkCommandBuffer cb = begin();
    vkCmdCopyBuffer(cb, staging, init, 1, &c_init);
    vkCmdCopyBuffer(cb, staging, cbv, 1, &c_cbv);
    submit(cb);

    VkDescriptorBindingFlags partial = VK_DESCRIPTOR_BINDING_PARTIALLY_BOUND_BIT;
    VkDescriptorSetLayoutBindingFlagsCreateInfo flags = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_BINDING_FLAGS_CREATE_INFO, 0, 1, &partial};
    VkDescriptorSetLayoutBinding b2 = {0, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 32, VK_SHADER_STAGE_COMPUTE_BIT};
    VkDescriptorSetLayoutCreateInfo l0 = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};
    VkDescriptorSetLayoutCreateInfo l2 = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO, &flags, 0, 1, &b2};
    VkDescriptorSetLayout sl[3];
    CHECK(vkCreateDescriptorSetLayout(dev, &l0, 0, &sl[0]));
    CHECK(vkCreateDescriptorSetLayout(dev, &l0, 0, &sl[1]));
    CHECK(vkCreateDescriptorSetLayout(dev, &l2, 0, &sl[2]));
    VkPushConstantRange pcr = {VK_SHADER_STAGE_COMPUTE_BIT, 0, 16};
    VkPipelineLayoutCreateInfo pli = {VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, .setLayoutCount = 3, .pSetLayouts = sl,
        .pushConstantRangeCount = 1, .pPushConstantRanges = &pcr};
    VkPipelineLayout pl;
    CHECK(vkCreatePipelineLayout(dev, &pli, 0, &pl));
    VkDescriptorPoolSize psize = {VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 32};
    VkDescriptorPoolCreateInfo dpi = {VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO, .maxSets = 3, .poolSizeCount = 1, .pPoolSizes = &psize};
    VkDescriptorPool dp;
    CHECK(vkCreateDescriptorPool(dev, &dpi, 0, &dp));
    VkDescriptorSetAllocateInfo dai = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO, 0, dp, 3, sl};
    VkDescriptorSet sets[3];
    CHECK(vkAllocateDescriptorSets(dev, &dai, sets));
    // Heap slots as the passes add them to their root constants (all 0 here): 11 scratch, 18 weights.
    VkDescriptorBufferInfo i_s = {scratch, 0, VK_WHOLE_SIZE}, i_w = {init, 0, VK_WHOLE_SIZE};
    VkWriteDescriptorSet w[2] = {
        {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, 0, sets[2], 0, 11, 1, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 0, &i_s},
        {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, 0, sets[2], 0, 18, 1, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 0, &i_w}};
    vkUpdateDescriptorSets(dev, 2, w, 0, 0);
    VkBufferDeviceAddressInfo bai = {VK_STRUCTURE_TYPE_BUFFER_DEVICE_ADDRESS_INFO, 0, cbv};
    uint64_t cbv_address = vkGetBufferDeviceAddress(dev, &bai);
    struct { uint64_t cbv; uint32_t a, b; } push = {cbv_address, 0, 0};

    VkQueryPoolCreateInfo qpi = {VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO, .queryType = VK_QUERY_TYPE_TIMESTAMP, .queryCount = 2};
    VkQueryPool qp;
    CHECK(vkCreateQueryPool(dev, &qpi, 0, &qp));
    if (!strcmp(argv[1], "seq")) {
        static const int lv[13] = {0, 1, 1, 2, 2, 2, 3, 3, 3, 3, 2, 2, 1};
        VkPipeline pipes[13];
        uint64_t addr[13];
        for (int k = 1; k <= 12; k++) {
            char path[512];
            snprintf(path, sizeof(path), "%s/pass%d.spv", argv[2], k);
            const char* use = (k == 11 && argc > 3) ? argv[3] : path;
            pipes[k] = pipeline(use, pl);
            FILE* sf = fopen(use, "rb");
            static char text[1 << 16];
            size_t sn = fread(text, 1, sizeof(text), sf);
            fclose(sf);
            addr[k] = 0;
            for (size_t i = 20; i + 20 <= sn; i += 4) { uint32_t q[5]; memcpy(q, text + i, 20); if (q[0] == 0x00050048u && q[2] == 1u && q[3] == 35u && q[4] == 8u) { addr[k] = cbv_address; break; } }
        }
        int frames = getenv("N_DISP") ? atoi(getenv("N_DISP")) : 10, no_barrier = getenv("NO_BARRIER") != 0;
        cb = begin();
        vkCmdCopyBuffer(cb, staging, scratch, 1, &c_scratch);
        submit(cb);
        double ms[15];
        for (int run = 0; run < 15; run++) {
            cb = begin();
            vkCmdResetQueryPool(cb, qp, 0, 2);
            vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pl, 0, 3, sets, 0, 0);
            vkCmdWriteTimestamp(cb, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, qp, 0);
            for (int f = 0; f < frames; f++)
                for (int k = 1; k <= 12; k++) {
                    push.cbv = addr[k];
                    vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pipes[k]);
                    vkCmdPushConstants(cb, pl, VK_SHADER_STAGE_COMPUTE_BIT, 0, 16, &push);
                    vkCmdDispatch(cb, ((ow >> lv[k]) + 63) / 64, oh >> lv[k], 1);
                    if (!no_barrier) barrier(cb);
                }
            vkCmdWriteTimestamp(cb, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, qp, 1);
            submit(cb);
            uint64_t t[2];
            CHECK(vkGetQueryPoolResults(dev, qp, 0, 2, sizeof(t), t, 8, VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT));
            ms[run] = (double)(t[1] - t[0]) * props.limits.timestampPeriod / 1e6 / frames;
        }
        qsort(ms, 15, sizeof(double), cmp_double);
        { printf("constants pointer passed to passes:"); for (int k = 1; k <= 12; k++) if (addr[k]) printf(" %d", k); printf("\n"); }
        printf("sequence of 12 passes, pass 11 = %s%s: median %.3f ms (min %.3f, max %.3f)\n", argc > 3 ? argv[3] : "original",
               no_barrier ? ", no barriers" : "", ms[7], ms[0], ms[14]);
        return 0;
    }
    uint32_t gx = ((ow >> level) + 63) / 64, gy = oh >> level;
    enum { RUNS = 9 };
    int dispatches = getenv("N_DISP") ? atoi(getenv("N_DISP")) : 20;
    uint64_t first_hash = 0;
    uint8_t* first = 0;
    for (int v = 0; v < nv; v++) {
        VkPipeline pipe = pipeline(argv[2 + v], pl);
        // Passes without a constant buffer have only the two heap offsets as root constants.
        {
            FILE* sf = fopen(argv[2 + v], "rb");
            static char text[1 << 20];
            size_t sn = fread(text, 1, sizeof(text), sf);
            fclose(sf);
            int has_cbv = 0;
            for (size_t i = 20; i + 20 <= sn; i += 4) { uint32_t q[5]; memcpy(q, text + i, 20); if (q[0] == 0x00050048u && q[2] == 1u && q[3] == 35u && q[4] == 8u) { has_cbv = 1; break; } }
            if (!has_cbv) push.cbv = 0;
            else push.cbv = cbv_address;
        }
        // One dispatch from the reference scratch state, read back.
        cb = begin();
        vkCmdCopyBuffer(cb, staging, scratch, 1, &c_scratch);
        barrier(cb);
        vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pipe);
        vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pl, 0, 3, sets, 0, 0);
        vkCmdPushConstants(cb, pl, VK_SHADER_STAGE_COMPUTE_BIT, 0, 16, &push);
        vkCmdDispatch(cb, gx, gy, 1);
        barrier(cb);
        vkCmdCopyBuffer(cb, scratch, readback, 1, &c_scratch);
        submit(cb);
        if (getenv("DUMP_SCRATCH")) { FILE* df = fopen(getenv("DUMP_SCRATCH"), "wb"); fwrite(read_map, 1, scratch_size, df); fclose(df); }
        uint64_t h = fnv(read_map, scratch_size);
        size_t changed = 0, diff = 0;
        for (VkDeviceSize i = 0; i < scratch_size; i++) changed += read_map[i] != map[i];
        if (v == 0) { first_hash = h; first = malloc(scratch_size); memcpy(first, read_map, scratch_size); }
        else for (VkDeviceSize i = 0; i < scratch_size; i++) diff += read_map[i] != first[i];
        double ms[RUNS];
        for (int run = 0; run < RUNS; run++) {
            cb = begin();
            vkCmdResetQueryPool(cb, qp, 0, 2);
            vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pipe);
            vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pl, 0, 3, sets, 0, 0);
            vkCmdPushConstants(cb, pl, VK_SHADER_STAGE_COMPUTE_BIT, 0, 16, &push);
            vkCmdWriteTimestamp(cb, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, qp, 0);
            for (int d = 0; d < dispatches; d++) { vkCmdDispatch(cb, gx, gy, 1); barrier(cb); }
            vkCmdWriteTimestamp(cb, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, qp, 1);
            submit(cb);
            uint64_t t[2];
            CHECK(vkGetQueryPoolResults(dev, qp, 0, 2, sizeof(t), t, 8, VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT));
            ms[run] = (double)(t[1] - t[0]) * props.limits.timestampPeriod / 1e6 / dispatches;
        }
        qsort(ms, RUNS, sizeof(double), cmp_double);
        printf("%-28s %ux%u  median %.3f ms (min %.3f)  wrote %zu bytes  %s\n", argv[2 + v], gx, gy, ms[RUNS / 2], ms[0], changed,
               v == 0 ? "reference" : h == first_hash ? "IDENTICAL to reference" : "DIFFERS");
        if (v && diff) printf("    %zu bytes differ from the reference\n", diff);
    }
    return 0;
}
