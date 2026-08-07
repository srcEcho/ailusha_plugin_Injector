/**
 * v52: MinHook + CreateFileW(路径重定向) + plugins.js(重建 $plugins)
 * Reads elsmod_data/injector_config.json at init time.
 *
 * Compile (MSYS2):
 *   gcc -shared -s -Os -static -Wl,--kill-at \
 *     -I src/minhook \
 *     -o version.dll \
 *     src/mainline/version_proxy_v52_cfw_pluginsjs.c \
 *     src/minhook/hde32.c src/minhook/buffer.c \
 *     src/minhook/hook.c src/minhook/trampoline.c \
 *     -lkernel32
 */
#include <windows.h>
#include "MinHook.h"

// ============================================================
// Minimal JSON parser — only parses ["str","str"] arrays
// ============================================================
#define MAX_JSON_SIZE 8192
#define MAX_ITEMS 64
#define MAX_STR_LEN 260

static char  g_plugins[MAX_ITEMS][MAX_STR_LEN];    // plugin names
static int   g_plugin_count = 0;
static WCHAR g_redirects_target[MAX_ITEMS][MAX_STR_LEN];
static WCHAR g_redirects_source[MAX_ITEMS][MAX_STR_LEN];
static int   g_redirect_count = 0;
static volatile LONG g_config_loaded = 0;

// Skip whitespace
static char *SkipWS(char *p) {
    while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;
    return p;
}

// Extract next JSON string value into dst (max maxlen). Returns p after closing quote.
static char *ExtractStr(char *p, char *dst, int maxlen) {
    p = SkipWS(p);
    if (*p != '"') return NULL;
    p++;
    int i = 0;
    while (*p && *p != '"' && i < maxlen - 1) {
        if (*p == '\\' && p[1]) { p++; dst[i++] = *p++; }
        else { dst[i++] = *p++; }
    }
    dst[i] = 0;
    if (*p == '"') p++;
    return p;
}

// Extract next JSON string into wide-char buffer
static char *ExtractStrW(char *p, WCHAR *dst, int maxlen) {
    char tmp[MAX_STR_LEN];
    p = ExtractStr(p, tmp, MAX_STR_LEN);
    if (!p) return NULL;
    MultiByteToWideChar(CP_UTF8, 0, tmp, -1, dst, maxlen);
    // Normalize / to \\
    for (WCHAR *w = dst; *w; w++) if (*w == L'/') *w = L'\\';
    return p;
}

// Parse json looking for "plugins":["A","B"] and "redirects":[{"target":"...","source":"..."},...]
static void ParseConfig(char *json) {
    g_plugin_count = 0;
    g_redirect_count = 0;

    char *p = json;

    // Find "plugins"
    p = strstr(p, "\"plugins\"");
    if (p) {
        p += 9; p = SkipWS(p);
        if (*p == ':') {
            p++; p = SkipWS(p);
            if (*p == '[') {
                p++;
                while (g_plugin_count < MAX_ITEMS) {
                    p = SkipWS(p);
                    if (*p == ']' || *p == 0) break;
                    if (*p == ',') { p++; continue; }
                    p = ExtractStr(p, g_plugins[g_plugin_count], MAX_STR_LEN);
                    if (!p) break;
                    g_plugin_count++;
                }
            }
        }
    }

    // Find "redirects"
    p = json;
    p = strstr(p, "\"redirects\"");
    if (p) {
        p += 11; p = SkipWS(p);
        if (*p == ':') {
            p++; p = SkipWS(p);
            if (*p == '[') {
                p++;
                while (g_redirect_count < MAX_ITEMS) {
                    p = SkipWS(p);
                    if (*p == ']' || *p == 0) break;
                    if (*p == ',') { p++; continue; }
                    if (*p == '{') {
                        p++;
                        WCHAR target[MAX_STR_LEN] = {0};
                        WCHAR source[MAX_STR_LEN] = {0};

                        // Find "target"
                        p = strstr(p, "\"target\"");
                        if (p) { p += 8; p = SkipWS(p); if (*p == ':') { p++; p = ExtractStrW(p, target, MAX_STR_LEN); } }
                        // Find "source"
                        p = strstr(p, "\"source\"");
                        if (p) { p += 8; p = SkipWS(p); if (*p == ':') { p++; p = ExtractStrW(p, source, MAX_STR_LEN); } }

                        if (target[0] && source[0]) {
                            lstrcpyW(g_redirects_target[g_redirect_count], target);
                            lstrcpyW(g_redirects_source[g_redirect_count], source);
                            g_redirect_count++;
                        }
                        // Skip to next } or ]
                        while (*p && *p != '}' && *p != ']') p++;
                        if (*p == '}') p++;
                    }
                }
            }
        }
    }
}

static void LoadConfig(void) {
    if (InterlockedCompareExchange(&g_config_loaded, 1, 0) != 0) return;

    // Hardcoded test plugin for v52 validation
    lstrcpyA(g_plugins[0], "TestPluginA");
    g_plugin_count = 1;

    HANDLE hf = CreateFileA("elsmod_data/injector_config.json", GENERIC_READ,
                            FILE_SHARE_READ, NULL, OPEN_EXISTING,
                            FILE_ATTRIBUTE_NORMAL, NULL);
    if (hf == INVALID_HANDLE_VALUE) return;  // use hardcoded defaults above

    DWORD sz = GetFileSize(hf, NULL);
    if (sz == 0 || sz > MAX_JSON_SIZE) { CloseHandle(hf); return; }

    char *buf = (char *)HeapAlloc(GetProcessHeap(), 0, sz + 1);
    if (!buf) { CloseHandle(hf); return; }

    DWORD read = 0;
    ReadFile(hf, buf, sz, &read, NULL);
    CloseHandle(hf);
    buf[read] = 0;

    ParseConfig(buf);
    HeapFree(GetProcessHeap(), 0, buf);
}

// ============================================================
// Path helpers for CreateFileW hook
// ============================================================
static void NormalizePathW(WCHAR *path) {
    for (; *path; path++) { if (*path == L'/') *path = L'\\'; }
}

// Extract "www\..." from full path, or return path as-is
static WCHAR *GetRelPathW(WCHAR *path) {
    WCHAR *p = path;
    while (*p) {
        if ((*p == L'\\' || *p == L'/') &&
            (p[1] == L'w' || p[1] == L'W') &&
            (p[2] == L'w' || p[2] == L'W') &&
            (p[3] == L'w' || p[3] == L'W') &&
            (p[4] == L'\\' || p[4] == L'/')) {
            p[4] = L'\\';
            return p + 1;
        }
        p++;
    }
    if ((path[0] == L'w' || path[0] == L'W') &&
        (path[1] == L'w' || path[1] == L'W') &&
        (path[2] == L'w' || path[2] == L'W') &&
        (path[3] == L'\\' || path[3] == L'/')) {
        path[3] = L'\\';
        return path;
    }
    return path;
}

// ============================================================
// CreateFileW hook — path redirection
// ============================================================
typedef HANDLE (WINAPI *CFW_t)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES,
                                DWORD, DWORD, HANDLE);
static CFW_t g_RealCFW = NULL;

static HANDLE WINAPI H_CFW(LPCWSTR fn, DWORD a, DWORD b, LPSECURITY_ATTRIBUTES c,
                            DWORD d, DWORD e, HANDLE f) {
    LoadConfig();

    if (g_redirect_count > 0 && fn) {
        WCHAR rel[MAX_STR_LEN];
        lstrcpyW(rel, GetRelPathW((WCHAR *)fn));
        NormalizePathW(rel);

        for (int i = 0; i < g_redirect_count; i++) {
            if (lstrcmpiW(rel, g_redirects_target[i]) == 0) {
                return g_RealCFW(g_redirects_source[i], a, b, c, d, e, f);
            }
        }
    }
    return g_RealCFW(fn, a, b, c, d, e, f);
}

// ============================================================
// ReadFile hook — plugins.js rebuild
// ============================================================
typedef BOOL (WINAPI *RF_t)(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
static RF_t g_RealRF = NULL;
static volatile LONG g_rf_initialized = 0;
static volatile LONG g_rebuild_done = 0;

// Rebuild $plugins array: preserve existing entries, append new plugins from g_plugins list.
// Strategy: find the closing ']' of $plugins array, insert our entries before it.
static BOOL RebuildPluginsJS(char *buf, DWORD *actual, DWORD bufMax) {
    // Find "$plugins"
    char *arr = strstr(buf, "$plugins");
    if (!arr) return FALSE;
    arr = strstr(arr, "[");
    if (!arr || arr - buf > 32768) return FALSE;
    arr++; // skip past '['

    // Find the matching ']'
    char *end = arr;
    int depth = 1, inString = 0;
    char strChar = 0;
    while (*end && depth > 0 && (end - buf) < 32768) {
        if (inString) {
            if (*end == '\\' && end[1]) { end++; }
            else if (*end == strChar) { inString = 0; }
        } else {
            if (*end == '"' || *end == '\'') { inString = 1; strChar = *end; }
            else if (*end == '[') { depth++; }
            else if (*end == ']') { depth--; }
        }
        end++;
    }
    if (depth != 0) return FALSE;
    // 'end' now points past ']'. The insert point is end - 1 (just before ']').
    char *closeBracket = end - 1;

    // Build insertion text: ",{\"name\":\"X\",...}" for each new plugin
    char insert[MAX_JSON_SIZE];
    int insLen = 0;
    for (int i = 0; i < g_plugin_count; i++) {
        // Quick check: is this plugin already in the array?
        char *found = strstr(buf, g_plugins[i]);
        if (found && found < closeBracket) continue;  // skip duplicates

        if (insLen + 300 < MAX_JSON_SIZE) {
            insLen += wsprintfA(insert + insLen,
                ",\r\n{\"name\":\"%s\",\"status\":true,"
                "\"description\":\"插件\",\"parameters\":{}}",
                g_plugins[i]);
        }
    }
    if (insLen == 0) return TRUE;  // nothing to add

    // Make room and insert
    DWORD old; VirtualProtect(buf, bufMax, PAGE_READWRITE, &old);
    memmove(closeBracket + insLen, closeBracket, *actual - (DWORD)(closeBracket - buf));
    memcpy(closeBracket, insert, insLen);
    VirtualProtect(buf, bufMax, old, &old);
    *actual = *actual + insLen;
    return TRUE;
}

static BOOL WINAPI H_RF(HANDLE hf, LPVOID buf, DWORD nb, LPDWORD lpb, LPOVERLAPPED lo) {
    LoadConfig();

    // Call real ReadFile via MinHook trampoline
    BOOL r = g_RealRF(hf, buf, nb, lpb, lo);

    if (g_rebuild_done || !r || !buf || nb < 80) return r;

    DWORD actual = lpb ? *lpb : nb;
    if (actual < 80 || actual > 0x2000000 || IsBadReadPtr(buf, 200)) return r;

    // Check if this is plugins.js — search for "$plugins" signature
    char *p = (char *)buf;
    int hasPluginsSig = 0;
    for (DWORD i = 0; i + 8 <= actual && i < 200; i++) {
        if (memcmp(p + i, "$plugins", 8) == 0) { hasPluginsSig = 1; break; }
    }
    if (!hasPluginsSig) return r;

    // Rebuild the $plugins array
    if (RebuildPluginsJS(p, &actual, nb > 32768 ? 32768 : nb)) {
        if (lpb) *lpb = actual;
        InterlockedExchange(&g_rebuild_done, 1);
    }

    return r;
}

// ============================================================
// DllMain
// ============================================================
BOOL WINAPI DllMain(HINSTANCE h, DWORD r, LPVOID p) {
    if (r == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);

        MH_STATUS status = MH_Initialize();
        if (status != MH_OK && status != MH_ERROR_ALREADY_INITIALIZED) return 1;

        // Hook CreateFileW
        status = MH_CreateHookApi(L"kernel32.dll", "CreateFileW",
                                   H_CFW, (LPVOID *)&g_RealCFW);
        if (status != MH_OK) return 1;

        // Hook ReadFile
        status = MH_CreateHookApi(L"kernel32.dll", "ReadFile",
                                   H_RF, (LPVOID *)&g_RealRF);
        if (status != MH_OK) return 1;

        status = MH_EnableHook(MH_ALL_HOOKS);
        if (status != MH_OK) return 1;
    } else if (r == DLL_PROCESS_DETACH) {
        MH_DisableHook(MH_ALL_HOOKS);
        MH_Uninitialize();
    }
    return 1;
}

// Version API stubs
__declspec(dllexport) BOOL  WINAPI GetFileVersionInfoA(LPCSTR a, DWORD b, DWORD c, LPVOID d)  { return 0; }
__declspec(dllexport) BOOL  WINAPI GetFileVersionInfoW(LPCWSTR a, DWORD b, DWORD c, LPVOID d) { return 0; }
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeA(LPCSTR a, LPDWORD b)             { return 0; }
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeW(LPCWSTR a, LPDWORD b)            { return 0; }
__declspec(dllexport) BOOL  WINAPI VerQueryValueA(LPCVOID a, LPCSTR b, LPVOID *c, PUINT d)   { return 0; }
__declspec(dllexport) BOOL  WINAPI VerQueryValueW(LPCVOID a, LPCWSTR b, LPVOID *c, PUINT d)  { return 0; }
