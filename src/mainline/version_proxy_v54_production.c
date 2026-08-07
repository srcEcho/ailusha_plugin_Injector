/**
 * v54 Production: MinHook + ReadFile(optional) + CreateFileW(optional)
 * Reads elsmod_data/injector_config.json at init.
 *
 * Config fields:
 *   injection_mode: "bootstrap" | "mainjs_push"
 *   plugins: ["PluginA", "PluginB"]
 *   redirects: [{"target":"www\\js\\plugins\\X.js","source":"X_bootstrap.js"}]
 *
 * Compile (MSYS2):
 *   gcc -shared -s -Os -static -Wl,--kill-at \
 *     -I src/minhook \
 *     -o version.dll \
 *     src/mainline/version_proxy_v54_production.c \
 *     src/minhook/hde32.c src/minhook/buffer.c \
 *     src/minhook/hook.c src/minhook/trampoline.c \
 *     -lkernel32
 */
#include <windows.h>
#include "MinHook.h"

// ============================================================
// Config
// ============================================================
#define MAX_ITEMS 64
#define MAX_STR 260

static char  g_plugins[MAX_ITEMS][MAX_STR]; static int g_plugin_count = 0;
static WCHAR g_redir_target[MAX_ITEMS][MAX_STR];
static WCHAR g_redir_source[MAX_ITEMS][MAX_STR];
static int g_redirect_count = 0;
static int g_mode_bootstrap = 0;  // 1=bootstrap, 0=mainjs_push
static volatile LONG g_config_loaded = 0;

static char *JsonStr(char *p, char *dst, int max) {
    while (*p && *p != '"') p++; if (*p != '"') return NULL; p++;
    int i = 0; while (*p && *p != '"' && i < max - 1) dst[i++] = *p++;
    dst[i] = 0; if (*p == '"') p++; return p;
}
static char *JsonStrW(char *p, WCHAR *dst, int max) {
    char t[MAX_STR]; p = JsonStr(p, t, MAX_STR); if (!p) return NULL;
    MultiByteToWideChar(CP_UTF8, 0, t, -1, dst, max);
    for (WCHAR *w = dst; *w; w++) if (*w == L'/') *w = L'\\';
    return p;
}

static void ParseJSON(char *buf) {
    g_plugin_count = 0; g_redirect_count = 0; g_mode_bootstrap = 0;
    char *p = buf;

    // injection_mode
    p = strstr(buf, "\"injection_mode\"");
    if (p) { p = strchr(p + 15, '"'); if (p) { p++;
        if (memcmp(p, "bootstrap", 9) == 0) g_mode_bootstrap = 1;
    }}

    // plugins array
    p = strstr(buf, "\"plugins\""); if (p) { p = strchr(p + 9, '[');
    if (p) { p++; while (*p && g_plugin_count < MAX_ITEMS) {
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n' || *p == ',') p++;
        if (*p == ']' || *p == 0) break;
        p = JsonStr(p, g_plugins[g_plugin_count], MAX_STR);
        if (!p) break; g_plugin_count++;
    }}}

    // redirects array
    p = strstr(buf, "\"redirects\""); if (p) { p = strchr(p + 11, '[');
    if (p) { p++; while (*p && g_redirect_count < MAX_ITEMS) {
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n' || *p == ',') p++;
        if (*p == ']' || *p == 0) break;
        if (*p == '{') { p++; WCHAR t[MAX_STR]={0}, s[MAX_STR]={0};
        p = strstr(p, "\"target\""); if (p) { p += 8; p = strchr(p, '"');
        if (p) p = JsonStrW(p, t, MAX_STR); }
        p = strstr(p, "\"source\""); if (p) { p += 8; p = strchr(p, '"');
        if (p) p = JsonStrW(p, s, MAX_STR); }
        if (t[0] && s[0]) { lstrcpyW(g_redir_target[g_redirect_count], t);
        lstrcpyW(g_redir_source[g_redirect_count], s); g_redirect_count++; }
        while (*p && *p != '}') p++; if (*p == '}') p++;
    }}}}
}

static void LoadConfig(void) {
    if (InterlockedCompareExchange(&g_config_loaded, 1, 0) != 0) return;
    HANDLE hf = CreateFileA("elsmod_data/injector_config.json", GENERIC_READ,
                            FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hf == INVALID_HANDLE_VALUE) return;
    DWORD sz = GetFileSize(hf, NULL);
    if (sz == 0 || sz > 8192) { CloseHandle(hf); return; }
    char *buf = (char *)HeapAlloc(GetProcessHeap(), 0, sz + 1);
    if (!buf) { CloseHandle(hf); return; }
    DWORD r; ReadFile(hf, buf, sz, &r, NULL); CloseHandle(hf); buf[r] = 0;
    ParseJSON(buf);
    HeapFree(GetProcessHeap(), 0, buf);
}

// ============================================================
// CreateFileW hook (bootstrap mode: path redirect)
// ============================================================
typedef HANDLE (WINAPI *CFW_t)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES,
                                DWORD, DWORD, HANDLE);
static CFW_t g_RealCFW = NULL;

static HANDLE WINAPI H_CFW(LPCWSTR fn, DWORD a, DWORD b, LPSECURITY_ATTRIBUTES c,
                            DWORD d, DWORD e, HANDLE f) {
    LoadConfig();
    if (g_redirect_count > 0 && fn) {
        int len = lstrlenW(fn);
        LPCWSTR name = fn + len;
        while (name > fn && *(name-1) != L'\\' && *(name-1) != L'/') name--;
        for (int i = 0; i < g_redirect_count; i++) {
            if (lstrcmpiW(name, g_redir_target[i]) == 0 &&
                !wcsstr(fn, L"originals")) {
                WCHAR np[512]; int j;
                for (j = 0; j < (int)(name - fn) && j < 510; j++) np[j] = fn[j];
                lstrcpyW(np + j, g_redir_source[i]);
                return g_RealCFW(np, a, b, c, d, e, f);
            }
        }
    }
    return g_RealCFW(fn, a, b, c, d, e, f);
}

// ============================================================
// ReadFile hook (mainjs_push mode: main.js injection)
// ============================================================
typedef BOOL (WINAPI *RF_t)(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
static RF_t g_RealRF = NULL;

#define MAX_PAYLOAD 4096
static char g_payload[MAX_PAYLOAD]; static int g_payload_len = 0;
static volatile LONG g_payload_built = 0;
static const char SIG_MAIN[] = "// main.js";
static const char SIG_SETUP[] = "PluginManager.setup($plugins)";
static volatile LONG g_inject_done = 0;

static void BuildPayload(void) {
    if (InterlockedCompareExchange(&g_payload_built, 1, 0) != 0) return;
    LoadConfig();
    for (int i = 0; i < g_plugin_count; i++) {
        int add = wsprintfA(g_payload + g_payload_len,
            "$plugins.push({\"name\":\"%s\",\"status\":true,"
            "\"description\":\"\",\"parameters\":{}});\r\n", g_plugins[i]);
        if (g_payload_len + add < MAX_PAYLOAD - 10) g_payload_len += add;
    }
}

static BOOL WINAPI H_RF(HANDLE hf, LPVOID buf, DWORD nb, LPDWORD lpb, LPOVERLAPPED lo) {
    LoadConfig();
    if (g_mode_bootstrap) {
        // Bootstrap mode: pass through, no ReadFile modification
        return g_RealRF(hf, buf, nb, lpb, lo);
    }
    // mainjs_push mode
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
    return r;
}

// ============================================================
// DllMain
// ============================================================
BOOL WINAPI DllMain(HINSTANCE h, DWORD r, LPVOID p) {
    if (r == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);
        MH_Initialize();
        MH_CreateHookApi(L"kernel32.dll", "ReadFile", H_RF, (LPVOID *)&g_RealRF);
        MH_CreateHookApi(L"kernel32.dll", "CreateFileW", H_CFW, (LPVOID *)&g_RealCFW);
        MH_EnableHook(MH_ALL_HOOKS);
    } else if (r == DLL_PROCESS_DETACH) {
        MH_DisableHook(MH_ALL_HOOKS); MH_Uninitialize();
    }
    return 1;
}

__declspec(dllexport) BOOL  WINAPI GetFileVersionInfoA(LPCSTR a,DWORD b,DWORD c,LPVOID d)  {return 0;}
__declspec(dllexport) BOOL  WINAPI GetFileVersionInfoW(LPCWSTR a,DWORD b,DWORD c,LPVOID d){return 0;}
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeA(LPCSTR a,LPDWORD b)            {return 0;}
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeW(LPCWSTR a,LPDWORD b)           {return 0;}
__declspec(dllexport) BOOL  WINAPI VerQueryValueA(LPCVOID a,LPCSTR b,LPVOID*c,PUINT d)    {return 0;}
__declspec(dllexport) BOOL  WINAPI VerQueryValueW(LPCVOID a,LPCWSTR b,LPVOID*c,PUINT d)   {return 0;}
