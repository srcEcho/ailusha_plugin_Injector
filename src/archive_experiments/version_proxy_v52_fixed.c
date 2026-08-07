/**
 * v52-fixed: plugins.js rebuild — track by handle, inject before ];
 * Uses "var $plugins" to identify plugins.js (not main.js).
 */
#include <windows.h>
#include "MinHook.h"

static HANDLE g_log = INVALID_HANDLE_VALUE;
static void Log(const char *fmt, ...) {
    if (g_log == INVALID_HANDLE_VALUE) return;
    char buf[256]; DWORD w; va_list ap; va_start(ap, fmt);
    int len = wvsprintfA(buf, fmt, ap); va_end(ap);
    WriteFile(g_log, buf, len, &w, NULL); FlushFileBuffers(g_log);
}

// ============================================================
// Config
// ============================================================
#define MAX_STR 260
static char g_plugins[64][MAX_STR]; static int g_plugin_count = 0;
static volatile LONG g_config_loaded = 0;

static void LoadConfig(void) {
    if (InterlockedCompareExchange(&g_config_loaded, 1, 0) != 0) return;
    lstrcpyA(g_plugins[0], "TestPluginA"); g_plugin_count = 1;
    HANDLE hf = CreateFileA("elsmod_data/injector_config.json", GENERIC_READ,
                            FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hf == INVALID_HANDLE_VALUE) { Log("config: hardcoded %s\n", g_plugins[0]); return; }
    DWORD sz = GetFileSize(hf, NULL);
    if (sz == 0 || sz > 8192) { CloseHandle(hf); return; }
    char *buf = (char *)HeapAlloc(GetProcessHeap(), 0, sz + 1);
    if (!buf) { CloseHandle(hf); return; }
    DWORD r; ReadFile(hf, buf, sz, &r, NULL); CloseHandle(hf); buf[r] = 0;
    char *p = strstr(buf, "\"plugins\"");
    if (p) { p = strchr(p + 9, '['); if (p) { p++; g_plugin_count = 0;
    while (*p && g_plugin_count < 64) {
        while (*p && *p != '"' && *p != ']') p++; if (*p == ']') break;
        if (*p == '"') { p++; int i = 0;
        while (*p && *p != '"' && i < MAX_STR - 1) g_plugins[g_plugin_count][i++] = *p++;
        if (*p == '"') p++; g_plugins[g_plugin_count][i] = 0; g_plugin_count++; }
    }}}
    HeapFree(GetProcessHeap(), 0, buf);
    Log("config: %d plugins\n", g_plugin_count);
}

// ============================================================
// Plugins.js rebuild — track by handle, inject on ];
// ============================================================
typedef BOOL (WINAPI *RF_t)(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
static RF_t g_RealRF = NULL;
static HANDLE g_plugins_handle = INVALID_HANDLE_VALUE;
static volatile LONG g_inject_done = 0;
static int g_rf_calls = 0;

static int BuildPush(char *out, int max) {
    int len = 0;
    for (int i = 0; i < g_plugin_count; i++) {
        int add = wsprintfA(out + len,
            "$plugins.push({\"name\":\"%s\",\"status\":true,"
            "\"description\":\"\",\"parameters\":{}});\r\n", g_plugins[i]);
        if (len + add < max) len += add;
    }
    return len;
}

static BOOL WINAPI H_RF(HANDLE hf, LPVOID buf, DWORD nb, LPDWORD lpb, LPOVERLAPPED lo) {
    BOOL r = g_RealRF(hf, buf, nb, lpb, lo);
    g_rf_calls++;
    if (g_inject_done || !r || !buf || nb < 80) return r;
    DWORD actual = lpb ? *lpb : nb;
    if (actual < 80 || actual > 0x2000000 || IsBadReadPtr(buf, 200)) return r;
    char *p = (char *)buf;

    // Detect plugins.js: "var $plugins" NOT "PluginManager.setup($plugins)"
    int isPluginsJS = 0;
    for (DWORD i = 0; i + 13 <= actual && i < 512; i++) {
        if (memcmp(p + i, "var $plugins", 12) == 0) { isPluginsJS = 1; break; }
    }
    if (isPluginsJS && g_plugins_handle == INVALID_HANDLE_VALUE) {
        g_plugins_handle = hf;
        LoadConfig();
        Log("plugins.js TRACKED handle=%p call=%d actual=%d\n", hf, g_rf_calls, actual);
    }

    // Only process chunks for the tracked plugins.js handle
    if (hf != g_plugins_handle) return r;

    // Search for ]; — closing of $plugins array
    char *closing = NULL;
    for (char *s = p + actual - 2; s > p; s--) {
        if (s[0] == ']' && s[1] == ';') { closing = s; break; }
    }
    if (!closing) { Log("  chunk actual=%d, no ]; yet\n", actual); return r; }

    Log("  ]; found at offset %d, actual=%d nb=%d\n", (int)(closing - p), actual, nb);

    if (g_plugin_count == 0) { Log("  no plugins to inject\n"); g_inject_done = 1; return r; }

    char push[4096]; int plen = BuildPush(push, 4096);
    if (plen == 0) { g_inject_done = 1; return r; }

    // Insert push code BEFORE ];
    // After: ...plugin_entries...,\r\n$plugins.push(...);\r\n];
    int tailLen = (int)(p + actual - closing); // bytes including and after ];
    int newTail = plen + 2; // push code + ];
    int shift = newTail - tailLen;

    Log("  plen=%d tail=%d newTail=%d shift=%d\n", plen, tailLen, newTail, shift);

    if (shift > 0 && actual + shift > (DWORD)nb) {
        Log("  no room in buffer (need %d, have %d)\n", actual + shift, nb);
        return r;
    }

    DWORD old; VirtualProtect(buf, nb, PAGE_READWRITE, &old);
    if (shift != 0) {
        // Move content AFTER ]; to make room
        memmove(closing + newTail, closing + tailLen,
                actual - (DWORD)(closing - p) - tailLen);
    }
    memcpy(closing, push, plen);
    closing[plen] = ']';
    closing[plen + 1] = ';';
    VirtualProtect(buf, nb, old, &old);
    *lpb = actual + shift;
    InterlockedExchange(&g_inject_done, 1);
    Log("  INJECTED new actual=%d\n", *lpb);
    return r;
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD r, LPVOID p) {
    if (r == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);
        g_log = CreateFileA("v52_fixed.log", GENERIC_WRITE, FILE_SHARE_READ, NULL,
                             CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        Log("=== v52-fixed ===\n");
        MH_Initialize();
        MH_CreateHookApi(L"kernel32.dll", "ReadFile", H_RF, (LPVOID *)&g_RealRF);
        MH_EnableHook(MH_ALL_HOOKS);
    } else if (r == DLL_PROCESS_DETACH) {
        Log("=== DETACH RF=%d ===\n", g_rf_calls);
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
