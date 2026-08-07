/**
 * v52-simple: MinHook + main.js injection + optional CreateFileW redirect.
 * Uses the PROVEN v50 ReadFile approach for injection.
 * CreateFileW is only active if redirects are configured.
 *
 * Compile:
 *   gcc -shared -s -Os -static -Wl,--kill-at -I. -Ihde -o v52.dll v52.c \
 *     buffer.c hook.c trampoline.c hde/hde32.c -lkernel32
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
static char  g_plugins[64][MAX_STR]; static int g_plugin_count = 0;
static WCHAR g_redir_target[64][MAX_STR]; static WCHAR g_redir_source[64][MAX_STR];
static int g_redirect_count = 0;
static volatile LONG g_config_loaded = 0;

static void LoadConfig(void) {
    if (InterlockedCompareExchange(&g_config_loaded, 1, 0) != 0) return;
    lstrcpyA(g_plugins[0], "TestPluginA"); g_plugin_count = 1;

    HANDLE hf = CreateFileA("elsmod_data/injector_config.json", GENERIC_READ,
                            FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hf == INVALID_HANDLE_VALUE) { Log("Config: using hardcoded %s\n", g_plugins[0]); return; }
    DWORD sz = GetFileSize(hf, NULL);
    if (sz == 0 || sz > 8192) { CloseHandle(hf); return; }
    char *buf = (char *)HeapAlloc(GetProcessHeap(), 0, sz + 1);
    if (!buf) { CloseHandle(hf); return; }
    DWORD rr; ReadFile(hf, buf, sz, &rr, NULL); CloseHandle(hf); buf[rr] = 0;
    Log("Config: read %d bytes\n", rr);

    char *p = buf;
    // Simple token scanner — find strings in "plugins":[...]
    {
        p = strstr(p, "\"plugins\"");
        if (p) { p = strchr(p + 9, '['); if (p) { p++;
        g_plugin_count = 0;
        while (*p && g_plugin_count < 64) {
            while (*p && *p != '"' && *p != ']') p++;
            if (*p == ']') break;
            if (*p == '"') { p++; int i = 0;
                while (*p && *p != '"' && i < MAX_STR - 1) g_plugins[g_plugin_count][i++] = *p++;
                if (*p == '"') p++; g_plugins[g_plugin_count][i] = 0; g_plugin_count++;
            }
        }}}
    }
    // Parse redirects
    {
        p = buf;
        p = strstr(p, "\"redirects\"");
        if (p) { p = strchr(p + 11, '['); if (p) { p++;
        g_redirect_count = 0;
        while (*p && g_redirect_count < 64) {
            while (*p && *p != '{' && *p != ']') p++;
            if (*p == ']') break;
            if (*p == '{') { p++;
                WCHAR t[MAX_STR]={0}, s[MAX_STR]={0};
                { p = strstr(p, "\"target\""); if (p) { p = strchr(p + 8, '"');
                  if (p) { p++; int i = 0; while (*p && *p != '"' && i < MAX_STR-1) t[i++]=(WCHAR)*p++;
                  t[i]=0; if (*p == '"') p++; }}}
                { p = strstr(p, "\"source\""); if (p) { p = strchr(p + 8, '"');
                  if (p) { p++; int i = 0; while (*p && *p != '"' && i < MAX_STR-1) s[i++]=(WCHAR)*p++;
                  s[i]=0; if (*p == '"') p++; }}}
                for (WCHAR *w = t; *w; w++) if (*w == L'/') *w = L'\\';
                for (WCHAR *w = s; *w; w++) if (*w == L'/') *w = L'\\';
                if (t[0] && s[0]) { lstrcpyW(g_redir_target[g_redirect_count], t);
                    lstrcpyW(g_redir_source[g_redirect_count], s); g_redirect_count++; }
                while (*p && *p != '}') p++; if (*p == '}') p++;
            }
        }}}
    }
    HeapFree(GetProcessHeap(), 0, buf);
    Log("Config: plugins=%d redirects=%d\n", g_plugin_count, g_redirect_count);
    for (int i = 0; i < g_plugin_count; i++) Log("  plugin[%d]=%s\n", i, g_plugins[i]);
}

// ============================================================
// main.js injection (PROVEN v50 approach)
// ============================================================
#define MAX_PAYLOAD 4096
static char g_payload[MAX_PAYLOAD]; static int g_payload_len = 0;
static volatile LONG g_payload_built = 0;

static void BuildPayload(void) {
    if (InterlockedCompareExchange(&g_payload_built, 1, 0) != 0) return;
    LoadConfig();
    for (int i = 0; i < g_plugin_count; i++) {
        int add = wsprintfA(g_payload + g_payload_len,
            "$plugins.push({\"name\":\"%s\",\"status\":true,"
            "\"description\":\"v52\",\"parameters\":{}});\r\n", g_plugins[i]);
        if (g_payload_len + add < MAX_PAYLOAD - 10) g_payload_len += add;
    }
    Log("Payload: %d bytes for %d plugins\n", g_payload_len, g_plugin_count);
}

static const char SIG_MAIN[] = "// main.js";
static const char SIG_SETUP[] = "PluginManager.setup($plugins)";
static volatile LONG g_inject_done = 0;
typedef BOOL (WINAPI *RF_t)(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
static RF_t g_RealRF = NULL;

static BOOL WINAPI H_RF(HANDLE hf, LPVOID buf, DWORD nb, LPDWORD lpb, LPOVERLAPPED lo) {
    BuildPayload();
    BOOL r = g_RealRF(hf, buf, nb, lpb, lo);
    if (g_inject_done || !r || !buf || nb < 80) return r;
    DWORD actual = lpb ? *lpb : nb;
    if (actual < 80 || actual > 0x2000000 || IsBadReadPtr(buf, 200)) return r;
    char *p = (char *)buf; int mlen = (int)(sizeof(SIG_MAIN) - 1), has = 0;
    for (DWORD i = 0; i + mlen <= actual && i < 200; i++) {
        if (memcmp(p + i, SIG_MAIN, mlen) == 0) { has = 1; break; }
    }
    if (!has || g_payload_len == 0) return r;
    int slen = (int)(sizeof(SIG_SETUP) - 1), ins = -1;
    for (DWORD i = 0; i + slen <= actual && i < 32768; i++) {
        if (memcmp(p + i, SIG_SETUP, slen) == 0) { ins = (int)i; break; }
    }
    if (ins < 0 || ins + g_payload_len + (int)actual > 32768) return r;
    DWORD old; VirtualProtect(buf, 32768, PAGE_READWRITE, &old);
    memmove(p + ins + g_payload_len, p + ins, actual - ins);
    memcpy(p + ins, g_payload, g_payload_len);
    VirtualProtect(buf, 32768, old, &old);
    if (lpb) *lpb = actual + g_payload_len;
    InterlockedExchange(&g_inject_done, 1);
    Log("Injection: DONE main.js modified actual=%d\n", *lpb);
    return r;
}

// ============================================================
// CreateFileW redirect
// ============================================================
typedef HANDLE (WINAPI *CFW_t)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES,
                                DWORD, DWORD, HANDLE);
static CFW_t g_RealCFW = NULL;

static void NormW(WCHAR *p) { for (; *p; p++) if (*p == L'/') *p = L'\\'; }
static WCHAR *RelW(WCHAR *p) {
    WCHAR *q = p;
    while (*q) { if ((*q == L'\\' || *q == L'/') && (q[1] == L'w' || q[1] == L'W') &&
         (q[2] == L'w' || q[2] == L'W') && (q[3] == L'w' || q[3] == L'W') &&
         (q[4] == L'\\' || q[4] == L'/')) { q[4] = L'\\'; return q + 1; } q++; }
    if ((p[0] == L'w' || p[0] == L'W') && (p[1] == L'w' || p[1] == L'W') &&
        (p[2] == L'w' || p[2] == L'W') && (p[3] == L'\\' || p[3] == L'/'))
        { p[3] = L'\\'; return p; }
    return p;
}

static HANDLE WINAPI H_CFW(LPCWSTR fn, DWORD a, DWORD b, LPSECURITY_ATTRIBUTES c,
                            DWORD d, DWORD e, HANDLE f) {
    LoadConfig();
    if (g_redirect_count > 0 && fn) {
        WCHAR rel[MAX_STR]; lstrcpyW(rel, RelW((WCHAR *)fn)); NormW(rel);
        for (int i = 0; i < g_redirect_count; i++) {
            if (lstrcmpiW(rel, g_redir_target[i]) == 0) {
                Log("CFW: REDIRECT %S -> %S\n", rel, g_redir_source[i]);
                return g_RealCFW(g_redir_source[i], a, b, c, d, e, f);
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
        g_log = CreateFileA("v52_log.log", GENERIC_WRITE, FILE_SHARE_READ, NULL,
                             CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        Log("=== v52-simple ATTACH ===\n");

        MH_STATUS s = MH_Initialize(); Log("MH_Init=%d\n", s);
        if (s != MH_OK && s != MH_ERROR_ALREADY_INITIALIZED) return 1;

        s = MH_CreateHookApi(L"kernel32.dll", "ReadFile", H_RF, (LPVOID *)&g_RealRF);
        Log("MH_RF=%d\n", s);
        if (s != MH_OK) return 1;

        s = MH_CreateHookApi(L"kernel32.dll", "CreateFileW", H_CFW, (LPVOID *)&g_RealCFW);
        Log("MH_CFW=%d\n", s);

        s = MH_EnableHook(MH_ALL_HOOKS);
        Log("MH_Enable=%d\n", s);
    } else if (r == DLL_PROCESS_DETACH) {
        Log("=== DETACH ===\n");
        MH_DisableHook(MH_ALL_HOOKS); MH_Uninitialize();
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
