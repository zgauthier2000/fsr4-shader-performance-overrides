// SPDX-License-Identifier: GPL-2.0-or-later
// reads the AMD driver's PM log sensors (ADL) for every adapter, a sample every <ms>; prints supported sensor indices and values
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
typedef void* (__stdcall *ALLOC)(int);
static void* __stdcall Alloc(int n) { return malloc(n); }
typedef struct { int supported; int value; } Sensor;
typedef struct { int size; Sensor sensors[256]; } PMLog;
typedef int (*Create_t)(ALLOC, int, void**);
typedef int (*NumAd_t)(void*, int*);
typedef int (*Query_t)(void*, int, PMLog*);
int main(int argc, char** argv) {
    int ms = argc > 1 ? atoi(argv[1]) : 250, count = argc > 2 ? atoi(argv[2]) : 1, only = argc > 3 ? atoi(argv[3]) : -1;
    HMODULE h = LoadLibraryA("atiadlxx.dll"); if (!h) { printf("no atiadlxx.dll\n"); return 1; }
    Create_t create = (Create_t)GetProcAddress(h, "ADL2_Main_Control_Create");
    NumAd_t num = (NumAd_t)GetProcAddress(h, "ADL2_Adapter_NumberOfAdapters_Get");
    Query_t q = (Query_t)GetProcAddress(h, "ADL2_New_QueryPMLogData_Get");
    void* ctx = NULL; int n = 0;
    if (!create || !num || !q || create(Alloc, 1, &ctx) != 0) { printf("ADL init failed\n"); return 1; }
    num(ctx, &n);
    for (int s = 0; s < count; ++s) {
        for (int a = 0; a < n; ++a) {
            if (only >= 0 && a != only) continue;
            PMLog d; memset(&d, 0, sizeof(d)); d.size = sizeof(d);
            if (q(ctx, a, &d) != 0) continue;
            printf("%llu a%d", GetTickCount64(), a);
            for (int i = 0; i < 256; ++i) if (d.sensors[i].supported) printf(" %d=%d", i, d.sensors[i].value);
            printf("\n");
        }
        fflush(stdout);
        if (s + 1 < count) Sleep(ms);
    }
    return 0;
}
