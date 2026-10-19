#version 450
#extension GL_EXT_shader_explicit_arithmetic_types_int8 : require
#extension GL_EXT_shader_8bit_storage : require
#extension GL_EXT_shader_explicit_arithmetic_types_int16 : require
#extension GL_EXT_shader_16bit_storage : require
#extension GL_EXT_buffer_reference2 : require
#extension GL_EXT_nonuniform_qualifier : require
#extension GL_EXT_spirv_intrinsics : require
#extension GL_EXT_buffer_reference_uvec2 : require
layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(buffer_reference) buffer PhysicalPointerUint4NonWriteCBVArray;

layout(buffer_reference, buffer_reference_align = 16, std430) readonly buffer PhysicalPointerUint4NonWriteCBVArray
{
    uvec4 value[4096];
};

layout(set = 2, binding = 0, std430) restrict readonly buffer SSBO
{
    uint _m0[];
} _15[];

layout(set = 2, binding = 0, std430) restrict readonly buffer _18_21
{
    uvec4 _m0[];
} _21[];

layout(set = 2, binding = 0, std430) buffer _23_26
{
    uint _m0[];
} _26[];

layout(push_constant, std430) uniform RootConstants
{
    uvec2 _m0;
    uint _m1;
    uint _m2;
} registers;

spirv_instruction (extensions = ["SPV_KHR_integer_dot_product"], capabilities = [6019, 6018], id = 4450)
uint spvSDot_uint_uint_uint(uint arg0, uint arg1, spirv_literal uint packedFormat);

