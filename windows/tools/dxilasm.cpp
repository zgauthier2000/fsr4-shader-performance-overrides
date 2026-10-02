// SPDX-License-Identifier: GPL-2.0-or-later
// dxilasm <libdxcompiler.so> <in.ll> <out.dxil>
// Assembles LLVM IR text (as printed by "dxc -dumpbin") into a DXIL container and has DXC's
// validator check and sign it, using Microsoft's documented IDxcAssembler / IDxcValidator.
#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>
#include <dlfcn.h>
#include "dxc/dxcapi.h"

static IDxcBlob* take(IDxcOperationResult* result, const char* what) {
    if (!result) return nullptr;
    IDxcBlobEncoding* errors = nullptr;
    result->GetErrorBuffer(&errors);
    if (errors && errors->GetBufferSize())
        std::fwrite(errors->GetBufferPointer(), 1, errors->GetBufferSize(), stderr);
    HRESULT status = -1;
    result->GetStatus(&status);
    if (status < 0) { std::fprintf(stderr, "%s failed: 0x%x\n", what, unsigned(status)); return nullptr; }
    IDxcBlob* blob = nullptr;
    result->GetResult(&blob);
    return blob;
}

int main(int argc, char** argv) {
    if (argc != 4) { std::fprintf(stderr, "usage: dxilasm <libdxcompiler.so> <in.ll> <out.dxil>\n"); return 2; }
    void* lib = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!lib) { std::fprintf(stderr, "%s\n", dlerror()); return 2; }
    auto create = reinterpret_cast<DxcCreateInstanceProc>(dlsym(lib, "DxcCreateInstance"));
    if (!create) return 2;
    std::ifstream in(argv[2], std::ios::binary);
    std::string text((std::istreambuf_iterator<char>(in)), {});
    if (text.empty()) { std::fprintf(stderr, "cannot read %s\n", argv[2]); return 2; }

    IDxcUtils* utils = nullptr;
    IDxcAssembler* assembler = nullptr;
    IDxcValidator* validator = nullptr;
    if (create(CLSID_DxcUtils, __uuidof(IDxcUtils), reinterpret_cast<void**>(&utils)) < 0 ||
        create(CLSID_DxcAssembler, __uuidof(IDxcAssembler), reinterpret_cast<void**>(&assembler)) < 0 ||
        create(CLSID_DxcValidator, __uuidof(IDxcValidator), reinterpret_cast<void**>(&validator)) < 0)
        return 3;
    IDxcBlobEncoding* source = nullptr;
    if (utils->CreateBlob(text.data(), UINT32(text.size()), DXC_CP_UTF8, &source) < 0) return 3;

    IDxcOperationResult* result = nullptr;
    if (assembler->AssembleToContainer(source, &result) < 0) return 4;
    IDxcBlob* container = take(result, "assemble");
    if (!container) return 5;
    result = nullptr;
    if (validator->Validate(container, DxcValidatorFlags_InPlaceEdit, &result) < 0) return 4;
    HRESULT status = -1;
    IDxcBlobEncoding* errors = nullptr;
    result->GetErrorBuffer(&errors);
    if (errors && errors->GetBufferSize())
        std::fwrite(errors->GetBufferPointer(), 1, errors->GetBufferSize(), stderr);
    result->GetStatus(&status);
    if (status < 0) { std::fprintf(stderr, "validation failed: 0x%x\n", unsigned(status)); return 5; }

    std::ofstream out(argv[3], std::ios::binary);
    out.write(static_cast<const char*>(container->GetBufferPointer()), std::streamsize(container->GetBufferSize()));
    return out ? 0 : 6;
}
