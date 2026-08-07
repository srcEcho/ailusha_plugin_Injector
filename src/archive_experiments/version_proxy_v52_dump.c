/**
 * v52-dump: DUMP plugins.js ReadFile chunks to disk files.
 * No modification — just capture what each chunk looks like.
 */
#include <windows.h>
#include "MinHook.h"

static HANDLE g_log = INVALID_HANDLE_VALUE;
static void Log(const char *fmt, ...) {
    if (g_log == INVALID_HANDLE_VALUE) return;
    char buf[512]; DWORD w; va_list ap; va_start(ap, fmt);
    int len = wvsprintfA(buf, fmt, ap); va_end(ap);
    WriteFile(g_log, buf, len, &w, NULL); FlushFileBuffers(g_log);
}

typedef BOOL (WINAPI *RF_t)(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
static RF_t g_RealRF = NULL;
static int g_rf_calls = 0;
static int g_chunk_idx = 0;
#define MAX_TRACKED 4
static HANDLE g_tracked[MAX_TRACKED];
static int g_tracked_count = 0;

static BOOL WINAPI H_RF(HANDLE hf, LPVOID buf, DWORD nb, LPDWORD lpb, LPOVERLAPPED lo) {
    BOOL r = g_RealRF(hf, buf, nb, lpb, lo);
    g_rf_calls++;
    if (!r || !buf || nb < 80) return r;
    DWORD actual = lpb ? *lpb : nb;
    char *p = (char *)buf;

    // Track handles that read plugins.js or main.js ($plugins signature)
    int hasSig = 0;
    for (DWORD i = 0; i + 8 <= actual && i < 2048; i++) {
        if (memcmp(p + i, "$plugins", 8) == 0) { hasSig = 1; break; }
    }
    if (hasSig && g_tracked_count < MAX_TRACKED) {
        int found = 0;
        for (int i = 0; i < g_tracked_count; i++) { if (g_tracked[i] == hf) { found = 1; break; } }
        if (!found) {
            g_tracked[g_tracked_count++] = hf;
            Log("TRACKING handle=%p (call #%d, actual=%d, first chars: %.60s)\n",
                hf, g_rf_calls, actual, p);
        }
    }

    // Dump ALL reads for tracked handles
    int tracked = 0;
    for (int i = 0; i < g_tracked_count; i++) { if (g_tracked[i] == hf) { tracked = 1; break; } }
    if (tracked) {
        char fname[64];
        wsprintfA(fname, "v52_dump_%d.bin", g_chunk_idx++);
        HANDLE hd = CreateFileA(fname, GENERIC_WRITE, FILE_SHARE_READ, NULL,
                                CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        if (hd != INVALID_HANDLE_VALUE) {
            DWORD w; WriteFile(hd, buf, actual, &w, NULL); CloseHandle(hd);
        }
        Log("DUMP #%d chunk=%d actual=%d hasSig=%d tail=%.50s\n",
            g_rf_calls, g_chunk_idx - 1, actual, hasSig, p + (actual > 50 ? actual - 50 : 0));
    }
    return r;
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD r, LPVOID p) {
    if (r == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);
        g_log = CreateFileA("v52_dump.log", GENERIC_WRITE, FILE_SHARE_READ, NULL,
                             CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        Log("=== v52-dump ===\n");
        MH_Initialize();
        MH_CreateHookApi(L"kernel32.dll", "ReadFile", H_RF, (LPVOID *)&g_RealRF);
        MH_EnableHook(MH_ALL_HOOKS);
    } else if (r == DLL_PROCESS_DETACH) {
        Log("=== DETACH RF=%d chunks=%d ===\n", g_rf_calls, g_chunk_idx);
        MH_DisableHook(MH_ALL_HOOKS); MH_Uninitialize();
        if (g_log != INVALID_HANDLE_VALUE) CloseHandle(g_log);
    }
    return 1;
}

__declspec(dllexport) BOOL WINAPI GetFileVersionInfoA(LPCSTR a,DWORD b,DWORD c,LPVOID d){return 0;}
__declspec(dllexport) BOOL WINAPI GetFileVersionInfoW(LPCWSTR a,DWORD b,DWORD c,LPVOID d){return 0;}
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeA(LPCSTR a,LPDWORD b){return 0;}
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeW(LPCWSTR a,LPDWORD b){return 0;}
__declspec(dllexport) BOOL WINAPI VerQueryValueA(LPCVOID a,LPCSTR b,LPVOID*c,PUINT d){return 0;}
__declspec(dllexport) BOOL WINAPI VerQueryValueW(LPCVOID a,LPCWSTR b,LPVOID*c,PUINT d){return 0;}
