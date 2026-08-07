/**
 * v52-v2: CreateFileW approach for plugins.js rebuild.
 * NO ReadFile buffer modification. NO chunk complexity.
 *
 * Strategy:
 *   1. At startup, read injector_config.json
 *   2. Find plugins.js on disk / in VFS
 *   3. Build modified plugins.js (append $plugins.push() calls at end)
 *   4. Write to elsmod_data/_patched_plugins.js
 *   5. Hook CreateFileW: when path ends with "plugins.js", redirect
 *
 * Compile same as v52: gcc -shared -s -Os -static -Wl,--kill-at -I. -Ihde ...
 */
#include <windows.h>
#include "MinHook.h"

// ============================================================
// Logging
// ============================================================
static HANDLE g_log = INVALID_HANDLE_VALUE;
static void Log(const char *fmt, ...) {
    if (g_log == INVALID_HANDLE_VALUE) return;
    char buf[512]; DWORD w; va_list ap; va_start(ap, fmt);
    int len = wvsprintfA(buf, fmt, ap); va_end(ap);
    WriteFile(g_log, buf, len, &w, NULL); FlushFileBuffers(g_log);
}

// ============================================================
// Config
// ============================================================
#define MAX_STR 260
static char g_plugins[64][MAX_STR];
static int g_plugin_count = 0;
static WCHAR g_patched_path[MAX_STR];
static volatile LONG g_ready = 0;

static void LoadConfig(void) {
    if (InterlockedCompareExchange(&g_ready, 1, 0) != 0) return;
    lstrcpyA(g_plugins[0], "TestPluginA"); g_plugin_count = 1;
    Log("v52-v2: hardcoded=%s\n", g_plugins[0]);

    // Try injector_config.json
    HANDLE hf = CreateFileA("elsmod_data/injector_config.json", GENERIC_READ,
                            FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hf != INVALID_HANDLE_VALUE) {
        DWORD sz = GetFileSize(hf, NULL);
        if (sz > 0 && sz < 8192) {
            char *buf = (char *)HeapAlloc(GetProcessHeap(), 0, sz + 1);
            if (buf) {
                DWORD r; ReadFile(hf, buf, sz, &r, NULL); buf[r] = 0; CloseHandle(hf);
                // Simple JSON parse for "plugins"
                char *p = strstr(buf, "\"plugins\"");
                if (p) { p += 9; while (*p && *p != '[') p++; if (*p == '[') { p++; g_plugin_count = 0;
                while (*p && g_plugin_count < 64) {
                    while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n' || *p == ',') p++;
                    if (*p == ']' || *p == 0) break;
                    if (*p == '"') { p++; int i = 0;
                    while (*p && *p != '"' && i < MAX_STR - 1) g_plugins[g_plugin_count][i++] = *p++;
                    g_plugins[g_plugin_count][i] = 0; if (*p == '"') p++; g_plugin_count++; }}
                }}}
                Log("v52-v2: config plugins=%d\n", g_plugin_count);
                HeapFree(GetProcessHeap(), 0, buf);
                return;
            }
        }
        CloseHandle(hf);
    }
}

// ============================================================
// Build patched plugins.js
// ============================================================
static int PreparePatchedPlugins(void) {
    LoadConfig();
    if (g_plugin_count == 0) return 0;

    // First, try to read the original plugins.js from www/js/plugins.js on disk
    // (Enigma VFS won't serve this path to us in DllMain, but the disk might have it
    //  if the game is unpacked. For packed, we need a different source.)
    // For now: just build a minimal plugins.js that ONLY has our push calls.
    // The push calls will execute AFTER the real plugins.js loads.

    // Actually, we should build a file that gets eval'd AFTER plugins.js.
    // Simpler approach: the patched file is just the push calls.
    HANDLE hf = CreateFileA("elsmod_data/_patched_plugins.js",
                            GENERIC_WRITE, FILE_SHARE_READ, NULL,
                            CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hf == INVALID_HANDLE_VALUE) {
        Log("v52-v2: cannot create patched plugins.js\n");
        return 0;
    }

    // Build $plugins.push(...) calls
    char push[4096]; int len = 0;
    for (int i = 0; i < g_plugin_count; i++) {
        len += wsprintfA(push + len,
            "$plugins.push({\"name\":\"%s\",\"status\":true,"
            "\"description\":\"v52 test\",\"parameters\":{}});\r\n",
            g_plugins[i]);
    }

    DWORD w;
    WriteFile(hf, push, len, &w, NULL);
    CloseHandle(hf);
    Log("v52-v2: wrote patched plugins.js (%d bytes)\n", w);

    // Get full path
    GetFullPathNameA("elsmod_data/_patched_plugins.js", MAX_STR,
                     (char *)g_patched_path, NULL);
    Log("v52-v2: patched path = %s\n", (char *)g_patched_path);
    return 1;
}

// ============================================================
// CreateFileW hook
// ============================================================
typedef HANDLE (WINAPI *CFW_t)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES,
                                DWORD, DWORD, HANDLE);
static CFW_t g_RealCFW = NULL;
static volatile LONG g_patch_ready = 0;

static HANDLE WINAPI H_CFW(LPCWSTR fn, DWORD a, DWORD b, LPSECURITY_ATTRIBUTES c,
                            DWORD d, DWORD e, HANDLE f) {
    // Lazy prepare the patched file
    if (InterlockedCompareExchange(&g_patch_ready, 1, 0) == 0) {
        PreparePatchedPlugins();
    }

    // Check if this is plugins.js
    if (fn && g_patched_path[0]) {
        int len = lstrlenW(fn);
        if (len >= 10) {
            // Check if path ends with "plugins.js" (case-insensitive)
            LPCWSTR tail = fn + len - 10;
            if ((tail[0] == L'p' || tail[0] == L'P') &&
                (tail[8] == L'j' || tail[8] == L'J') &&
                (tail[9] == L's' || tail[9] == L'S')) {
                // Quick check: it's plugins.js
                if (lstrcmpiW(tail, L"plugins.js") == 0) {
                    Log("v52-v2 H_CFW: REDIRECT plugins.js -> _patched_plugins.js\n");
                    return g_RealCFW(g_patched_path, a, b, c, d, e, f);
                }
            }
        }
    }
    return g_RealCFW(fn, a, b, c, d, e, f);
}

// ============================================================
// DllMain
// ============================================================
BOOL WINAPI DllMain(HINSTANCE h, DWORD r, LPVOID p) {
    if (r == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);
        g_log = CreateFileA("v52_v2_debug.log", GENERIC_WRITE, FILE_SHARE_READ, NULL,
                             CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        Log("=== v52-v2 ATTACH ===\n");

        MH_STATUS s = MH_Initialize();
        Log("MH_Init=%d\n", s);
        if (s != MH_OK && s != MH_ERROR_ALREADY_INITIALIZED) return 1;

        s = MH_CreateHookApi(L"kernel32.dll", "CreateFileW", H_CFW, (LPVOID *)&g_RealCFW);
        Log("MH_CFW=%d\n", s);
        if (s != MH_OK) return 1;

        s = MH_EnableHook(MH_ALL_HOOKS);
        Log("MH_Enable=%d\n", s);
    } else if (r == DLL_PROCESS_DETACH) {
        Log("=== v52-v2 DETACH ===\n");
        MH_DisableHook(MH_ALL_HOOKS);
        MH_Uninitialize();
        if (g_log != INVALID_HANDLE_VALUE) CloseHandle(g_log);
    }
    return 1;
}

__declspec(dllexport) BOOL  WINAPI GetFileVersionInfoA(LPCSTR a, DWORD b, DWORD c, LPVOID d)  { return 0; }
__declspec(dllexport) BOOL  WINAPI GetFileVersionInfoW(LPCWSTR a, DWORD b, DWORD c, LPVOID d) { return 0; }
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeA(LPCSTR a, LPDWORD b)             { return 0; }
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeW(LPCWSTR a, LPDWORD b)            { return 0; }
__declspec(dllexport) BOOL  WINAPI VerQueryValueA(LPCVOID a, LPCSTR b, LPVOID *c, PUINT d)   { return 0; }
__declspec(dllexport) BOOL  WINAPI VerQueryValueW(LPCVOID a, LPCWSTR b, LPVOID *c, PUINT d)  { return 0; }
