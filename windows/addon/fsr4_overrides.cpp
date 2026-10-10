// SPDX-License-Identifier: GPL-2.0-or-later
// fsr4_overrides: a ReShade add-on that swaps compute shaders by their DXIL hash when a D3D12
// pipeline is created. It is the Windows counterpart of VKD3D_SHADER_OVERRIDE on Linux: AMD's
// FSR 4.1.1 DLL stays untouched, and the faster replacements for its postpass and model pass 11
// are loaded from the "fsr4-overrides" folder next to this add-on.
//
// A replacement is a signed DXIL container named after the shader it replaces: the 16-byte hash
// stored in the original container's header, as 32 hex digits, plus ".dxil".
//
// If the folder "fsr4-overrides\dump" exists, every FSR 4 compute shader the game creates is also
// saved there under the same name, as input for dxil/build_dxil_overrides.sh when a game uses a
// variant that has no replacement yet.
//
// Modeled on ReShade's example add-on "06-shader_replace" (Patrick Mours, BSD-3-Clause OR MIT).
#include <reshade.hpp>

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

using namespace reshade::api;

namespace {

std::wstring g_directory;                                      // ...\fsr4-overrides\ (with the separator)
bool g_dump = false;                                           // ...\fsr4-overrides\dump\ exists
std::mutex g_mutex;
std::unordered_map<std::string, std::vector<uint8_t>> g_cache; // hash -> replacement (empty: none)
thread_local std::vector<const std::vector<uint8_t>*> t_in_use;

void Log(reshade::log::level level, const std::string& text) {
    reshade::log::message(level, text.c_str());
}

/// The hash a DXBC/DXIL container carries in its header, or "" if this is not such a container.
std::string ContainerHash(const void* code, size_t size) {
    const auto* bytes = static_cast<const uint8_t*>(code);
    if (size < 32 || std::memcmp(bytes, "DXBC", 4) != 0)
        return {};
    char text[33];
    for (int i = 0; i < 16; ++i)
        std::snprintf(text + 2 * i, 3, "%02x", bytes[4 + i]);
    return text;
}

/// Saves an original FSR 4 shader (recognized by the entry point names AMD's DLL uses).
void Dump(const std::string& hash, const void* code, size_t size) {
    static const char marker[] = "fsr4_model_";
    const auto* bytes = static_cast<const char*>(code);
    bool fsr = false;
    for (size_t i = 0; i + sizeof(marker) - 1 <= size && !fsr; ++i)
        fsr = bytes[i] == marker[0] && std::memcmp(bytes + i, marker, sizeof(marker) - 1) == 0;
    if (!fsr)
        return;
    const std::wstring path = g_directory + L"dump\\" + std::wstring(hash.begin(), hash.end()) + L".dxil";
    if (FILE* file = _wfopen(path.c_str(), L"wb")) {
        std::fwrite(code, 1, size, file);
        std::fclose(file);
    }
}

/// The replacement for a shader hash: read from disk once, then kept for the whole run (pipelines
/// are created rarely, and ReShade may read the code after the callback returns).
const std::vector<uint8_t>* Replacement(const std::string& hash) {
    std::lock_guard<std::mutex> lock(g_mutex);
    auto it = g_cache.find(hash);
    if (it == g_cache.end()) {
        std::vector<uint8_t> data;
        const std::wstring path = g_directory + std::wstring(hash.begin(), hash.end()) + L".dxil";
        if (FILE* file = _wfopen(path.c_str(), L"rb")) {
            std::fseek(file, 0, SEEK_END);
            const long size = std::ftell(file);
            std::fseek(file, 0, SEEK_SET);
            if (size > 32) {
                data.resize(size_t(size));
                if (std::fread(data.data(), 1, data.size(), file) != data.size())
                    data.clear();
            }
            std::fclose(file);
            if (data.empty() || std::memcmp(data.data(), "DXBC", 4) != 0) {
                Log(reshade::log::level::error, "fsr4_overrides: " + hash + ".dxil is not a DXIL container, ignored");
                data.clear();
            } else {
                Log(reshade::log::level::info, "fsr4_overrides: replacing compute shader " + hash);
            }
        }
        it = g_cache.emplace(hash, std::move(data)).first;
    }
    return it->second.empty() ? nullptr : &it->second;
}

bool OnCreatePipeline(device*, pipeline_layout, uint32_t count, const pipeline_subobject* subobjects) {
    // No call into ReShade's C++ interfaces here: this add-on is also built with MinGW, and only
    // plain structures and ReShade's C exports are safe across compilers. Non-D3D12 shaders are
    // skipped by the container check instead.
    bool replaced = false;
    for (uint32_t i = 0; i < count; ++i) {
        if (subobjects[i].type != pipeline_subobject_type::compute_shader || subobjects[i].data == nullptr)
            continue;
        for (uint32_t k = 0; k < subobjects[i].count; ++k) {
            auto& desc = static_cast<shader_desc*>(subobjects[i].data)[k];
            const std::string hash = ContainerHash(desc.code, desc.code_size);
            if (hash.empty())
                continue;
            if (g_dump)
                Dump(hash, desc.code, desc.code_size);
            if (const std::vector<uint8_t>* data = Replacement(hash)) {
                desc.code = data->data();
                desc.code_size = data->size();
                replaced = true;
            }
        }
    }
    return replaced;
}

} // namespace

extern "C" __declspec(dllexport) const char* NAME = "FSR 4 shader overrides";
extern "C" __declspec(dllexport) const char* DESCRIPTION =
    "Replaces FSR 4.1.1 compute shaders with faster, bit-exact versions from the \"fsr4-overrides\" folder next to this add-on.";

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    switch (reason) {
    case DLL_PROCESS_ATTACH: {
        if (!reshade::register_addon(module))
            return FALSE;
        wchar_t path[MAX_PATH] = L"";
        GetModuleFileNameW(module, path, MAX_PATH);
        g_directory = path;
        g_directory.erase(g_directory.find_last_of(L"\\/") + 1);
        g_directory += L"fsr4-overrides\\";
        const DWORD attributes = GetFileAttributesW((g_directory + L"dump").c_str());
        g_dump = attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
        reshade::register_event<reshade::addon_event::create_pipeline>(OnCreatePipeline);
        break;
    }
    case DLL_PROCESS_DETACH:
        reshade::unregister_addon(module);
        break;
    }
    return TRUE;
}
