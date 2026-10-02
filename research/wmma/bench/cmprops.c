// SPDX-License-Identifier: GPL-2.0-or-later
// Lists the cooperative matrix (WMMA) configurations the discrete GPU's driver exposes.
#include <stdio.h>
#include <vulkan/vulkan.h>
static const char* ct(VkComponentTypeKHR t) {
    static const char* n[] = {"f16", "f32", "f64", "i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64"};
    return t <= 10 ? n[t] : t == 1000141000 ? "bf16" : "other";
}
int main(void) {
    VkApplicationInfo app = {VK_STRUCTURE_TYPE_APPLICATION_INFO, .apiVersion = VK_API_VERSION_1_3};
    VkInstanceCreateInfo ici = {VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, .pApplicationInfo = &app};
    VkInstance inst;
    if (vkCreateInstance(&ici, 0, &inst)) return 1;
    VkPhysicalDevice devs[8];
    uint32_t n = 8;
    vkEnumeratePhysicalDevices(inst, &n, devs);
    for (uint32_t i = 0; i < n; i++) {
        VkPhysicalDeviceProperties p;
        vkGetPhysicalDeviceProperties(devs[i], &p);
        if (p.deviceType != VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU) continue;
        VkPhysicalDeviceSubgroupSizeControlProperties sg = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SUBGROUP_SIZE_CONTROL_PROPERTIES};
        VkPhysicalDeviceProperties2 p2 = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2, &sg};
        vkGetPhysicalDeviceProperties2(devs[i], &p2);
        printf("%s: subgroup size %u..%u, required-size stages 0x%x\n", p.deviceName, sg.minSubgroupSize, sg.maxSubgroupSize, sg.requiredSubgroupSizeStages);
        PFN_vkGetPhysicalDeviceCooperativeMatrixPropertiesKHR get = (PFN_vkGetPhysicalDeviceCooperativeMatrixPropertiesKHR)vkGetInstanceProcAddr(inst, "vkGetPhysicalDeviceCooperativeMatrixPropertiesKHR");
        if (!get) { printf("no cooperative matrix query\n"); return 1; }
        uint32_t c = 0;
        get(devs[i], &c, 0);
        VkCooperativeMatrixPropertiesKHR props[64];
        if (c > 64) c = 64;
        for (uint32_t k = 0; k < c; k++) props[k] = (VkCooperativeMatrixPropertiesKHR){VK_STRUCTURE_TYPE_COOPERATIVE_MATRIX_PROPERTIES_KHR};
        get(devs[i], &c, props);
        for (uint32_t k = 0; k < c; k++)
            printf("  M=%u N=%u K=%u  A=%s B=%s C=%s R=%s  saturating=%u scope=%d\n", props[k].MSize, props[k].NSize, props[k].KSize,
                   ct(props[k].AType), ct(props[k].BType), ct(props[k].CType), ct(props[k].ResultType), props[k].saturatingAccumulation, props[k].scope);
    }
    return 0;
}
