/**
 * v55 winhttp.dll Production: MinHook + ReadFile(optional) + CreateFileW(optional)
 *
 * IDENTICAL to v54, except it ships as **winhttp.dll** instead of version.dll.
 * Why: third-party launchers like MTOOL delete/overwrite version.dll (and winmm.dll)
 * for their own side-load injection, so our version.dll is removed and the hook never
 * fires. The game's unpacked main exe also imports winhttp.dll — a DLL MTOOL does not
 * manage — so we side-load that instead. All WinHTTP exports are forwarded to the real
 * System32 winhttp.dll so the game's networking is unchanged.
 *
 * Config fields (elsmod_data/injector_config.json):
 *   injection_mode: "bootstrap" | "mainjs_push"
 *   plugins: ["PluginA", "PluginB"]
 *   redirects: [{"target":"www\\js\\plugins\\X.js","source":"X_bootstrap.js"}]
 *
 * Compile (MSYS2):
 *   gcc -shared -s -Os -static -Wl,--kill-at \
 *     -I src/minhook \
 *     -o winhttp.dll \
 *     src/mainline/version_proxy_v55_winhttp.c \
 *     src/minhook/hde32.c src/minhook/buffer.c \
 *     src/minhook/hook.c src/minhook/trampoline.c \
 *     -lkernel32
 */
#include <windows.h>
#define WINHTTPAPI  /* neutralize dllimport so we can dllexport our forwarders */
#include <winhttp.h>
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

    p = strstr(buf, "\"injection_mode\"");
    if (p) { p += 16; p = strchr(p, '"'); if (p) { p++;
        if (memcmp(p, "bootstrap", 9) == 0) g_mode_bootstrap = 1;
    }}

    p = strstr(buf, "\"plugins\""); if (p) { p = strchr(p + 9, '[');
    if (p) { p++; while (*p && g_plugin_count < MAX_ITEMS) {
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n' || *p == ',') p++;
        if (*p == ']' || *p == 0) break;
        p = JsonStr(p, g_plugins[g_plugin_count], MAX_STR);
        if (!p) break; g_plugin_count++;
    }}}

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

static int GetExeDir(WCHAR *dir, int max) {
    WCHAR exe[MAX_PATH];
    DWORD n = GetModuleFileNameW(NULL, exe, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) { dir[0] = 0; return 0; }
    int i;
    for (i = (int)n - 1; i >= 0; i--)
        if (exe[i] == L'\\' || exe[i] == L'/') break;
    if (i < 0) { dir[0] = 0; return 0; }
    int len = i + 1;
    if (len >= max) len = max - 1;
    memcpy(dir, exe, len * sizeof(WCHAR));
    dir[len] = 0;
    return 1;
}

static void WCatInt(WCHAR *dst, int v) {
    WCHAR tmp[16]; int n = 0;
    if (v == 0) { tmp[n++] = L'0'; }
    else {
        int neg = (v < 0);
        if (neg) v = -v;
        while (v > 0) { tmp[n++] = (WCHAR)(L'0' + (v % 10)); v /= 10; }
        if (neg) tmp[n++] = L'-';
    }
    while (n > 0) {
        int k = (int)lstrlenW(dst);
        dst[k] = tmp[--n]; dst[k + 1] = 0;
    }
}

static void DllLogConfig(const WCHAR *exedir, int cfg_found) {
    WCHAR cwd[MAX_PATH], dir[MAX_PATH], logpath[MAX_PATH], msg[1024];
    if (!GetCurrentDirectoryW(MAX_PATH, cwd)) cwd[0] = 0;

    msg[0] = 0;
    lstrcatW(msg, L"[injector] cfg=");   WCatInt(msg, cfg_found);
    lstrcatW(msg, L" redirects=");        WCatInt(msg, g_redirect_count);
    lstrcatW(msg, L" plugins=");          WCatInt(msg, g_plugin_count);
    lstrcatW(msg, L" mode=");
    lstrcatW(msg, g_mode_bootstrap ? L"bootstrap" : L"mainjs_push");
    lstrcatW(msg, L" dll=winhttp");
    lstrcatW(msg, L"\r\nexe_dir=");       lstrcatW(msg, exedir);
    lstrcatW(msg, L"\r\ncwd=");           lstrcatW(msg, cwd);
    lstrcatW(msg, L"\r\n");

    lstrcpyW(dir, exedir);
    lstrcatW(dir, L"elsmod_data\\logs");
    CreateDirectoryW(dir, NULL);
    lstrcpyW(logpath, dir);
    lstrcatW(logpath, L"\\injector_dll.log");
    HANDLE hf = CreateFileW(logpath, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE,
                            NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hf == INVALID_HANDLE_VALUE) return;
    DWORD sz0 = GetFileSize(hf, NULL);
    DWORD w;
    if (sz0 == 0) { WCHAR bom = 0xFEFF; WriteFile(hf, &bom, sizeof(WCHAR), &w, NULL); }
    WriteFile(hf, msg, lstrlenW(msg) * sizeof(WCHAR), &w, NULL);
    CloseHandle(hf);
}

static void DllLogRedirect(const WCHAR *target, const WCHAR *source) {
    WCHAR exedir[MAX_PATH], dir[MAX_PATH], logpath[MAX_PATH], msg[1024];
    if (!GetExeDir(exedir, MAX_PATH)) return;

    msg[0] = 0;
    lstrcatW(msg, L"[injector] REDIRECT ");
    lstrcatW(msg, target);
    lstrcatW(msg, L" -> ");
    lstrcatW(msg, source);
    lstrcatW(msg, L" (pid="); WCatInt(msg, (int)GetCurrentProcessId()); lstrcatW(msg, L")");
    lstrcatW(msg, L"\r\n");

    lstrcpyW(dir, exedir);
    lstrcatW(dir, L"elsmod_data\\logs");
    CreateDirectoryW(dir, NULL);
    lstrcpyW(logpath, dir);
    lstrcatW(logpath, L"\\injector_dll.log");
    HANDLE hf = CreateFileW(logpath, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE,
                            NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hf == INVALID_HANDLE_VALUE) return;
    DWORD sz0 = GetFileSize(hf, NULL);
    DWORD w;
    if (sz0 == 0) { WCHAR bom = 0xFEFF; WriteFile(hf, &bom, sizeof(WCHAR), &w, NULL); }
    WriteFile(hf, msg, lstrlenW(msg) * sizeof(WCHAR), &w, NULL);
    CloseHandle(hf);
}

static void LoadConfig(void) {
    if (InterlockedCompareExchange(&g_config_loaded, 1, 0) != 0) return;

    WCHAR exedir[MAX_PATH], cfgpath[MAX_PATH];
    if (!GetExeDir(exedir, MAX_PATH)) return;

    lstrcpyW(cfgpath, exedir);
    lstrcatW(cfgpath, L"elsmod_data\\injector_config.json");

    HANDLE hf = CreateFileW(cfgpath, GENERIC_READ, FILE_SHARE_READ, NULL,
                            OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hf == INVALID_HANDLE_VALUE) { DllLogConfig(exedir, 0); return; }
    DWORD sz = GetFileSize(hf, NULL);
    if (sz == 0 || sz > 8192) { CloseHandle(hf); DllLogConfig(exedir, 0); return; }
    char *buf = (char *)HeapAlloc(GetProcessHeap(), 0, sz + 1);
    if (!buf) { CloseHandle(hf); DllLogConfig(exedir, 0); return; }
    DWORD r; ReadFile(hf, buf, sz, &r, NULL); CloseHandle(hf); buf[r] = 0;
    ParseJSON(buf);
    HeapFree(GetProcessHeap(), 0, buf);
    DllLogConfig(exedir, 1);
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
                DllLogRedirect(g_redir_target[i], g_redir_source[i]);
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
        return g_RealRF(hf, buf, nb, lpb, lo);
    }
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
// WinHTTP forwarding — load the real System32 winhttp.dll and
// forward every export we name, so the game's networking is untouched.
// ============================================================
static HMODULE g_realWinhttp = NULL;

static void LoadRealWinhttp(void) {
    if (g_realWinhttp) return;
    WCHAR sys[MAX_PATH];
    if (GetSystemDirectoryW(sys, MAX_PATH)) {
        lstrcatW(sys, L"\\winhttp.dll");
        g_realWinhttp = LoadLibraryW(sys);
    }
}

#define FORWARD_DEF(name, ret, params, args) \
    static ret (WINAPI *fp_##name) params = NULL; \
    __declspec(dllexport) ret WINAPI name params { \
        if (!fp_##name) { LoadRealWinhttp(); if (g_realWinhttp) \
            fp_##name = (ret (WINAPI *) params)GetProcAddress(g_realWinhttp, #name); } \
        if (!fp_##name) { SetLastError(127); return (ret)0; } \
        return fp_##name args; \
    }

FORWARD_DEF(WinHttpOpen,
    HINTERNET, (LPCWSTR a, DWORD b, LPCWSTR c, LPCWSTR d, DWORD e), (a, b, c, d, e))
FORWARD_DEF(WinHttpConnect,
    HINTERNET, (HINTERNET a, LPCWSTR b, INTERNET_PORT c, DWORD d), (a, b, c, d))
FORWARD_DEF(WinHttpOpenRequest,
    HINTERNET, (HINTERNET a, LPCWSTR b, LPCWSTR c, LPCWSTR d, LPCWSTR e, LPCWSTR FAR *f, DWORD g), (a, b, c, d, e, f, g))
FORWARD_DEF(WinHttpAddRequestHeaders,
    BOOL, (HINTERNET a, LPCWSTR b, DWORD c, DWORD d), (a, b, c, d))
FORWARD_DEF(WinHttpSendRequest,
    BOOL, (HINTERNET a, LPCWSTR b, DWORD c, LPVOID d, DWORD e, DWORD f, DWORD_PTR g), (a, b, c, d, e, f, g))
FORWARD_DEF(WinHttpWriteData,
    BOOL, (HINTERNET a, LPCVOID b, DWORD c, LPDWORD d), (a, b, c, d))
FORWARD_DEF(WinHttpReadData,
    BOOL, (HINTERNET a, LPVOID b, DWORD c, LPDWORD d), (a, b, c, d))
FORWARD_DEF(WinHttpReceiveResponse,
    BOOL, (HINTERNET a, LPVOID b), (a, b))
FORWARD_DEF(WinHttpCloseHandle,
    BOOL, (HINTERNET a), (a))
FORWARD_DEF(WinHttpQueryHeaders,
    BOOL, (HINTERNET a, DWORD b, LPCWSTR c, LPVOID d, LPDWORD e, LPDWORD f), (a, b, c, d, e, f))
FORWARD_DEF(WinHttpCrackUrl,
    BOOL, (LPCWSTR a, DWORD b, DWORD c, LPURL_COMPONENTS d), (a, b, c, d))
FORWARD_DEF(WinHttpSetTimeouts,
    BOOL, (HINTERNET a, int b, int c, int d, int e), (a, b, c, d, e))
/* nw.dll delay-loads these two — missing them crashed the game (exit 127) */
FORWARD_DEF(WinHttpGetProxyForUrl,
    BOOL, (HINTERNET a, LPCWSTR b, WINHTTP_AUTOPROXY_OPTIONS *c, WINHTTP_PROXY_INFO *d), (a, b, c, d))
FORWARD_DEF(WinHttpGetIEProxyConfigForCurrentUser,
    BOOL, (WINHTTP_CURRENT_USER_IE_PROXY_CONFIG *a), (a))
/* Chromium resolves these via GetProcAddress — forward for safety */
FORWARD_DEF(WinHttpSetStatusCallback,
    WINHTTP_STATUS_CALLBACK, (HINTERNET a, WINHTTP_STATUS_CALLBACK b, DWORD c, DWORD_PTR d), (a, b, c, d))
FORWARD_DEF(WinHttpQueryDataAvailable,
    BOOL, (HINTERNET a, LPDWORD b), (a, b))
FORWARD_DEF(WinHttpSetOption,
    BOOL, (HINTERNET a, DWORD b, LPVOID c, DWORD d), (a, b, c, d))
FORWARD_DEF(WinHttpQueryOption,
    BOOL, (HINTERNET a, DWORD b, LPVOID c, LPDWORD d), (a, b, c, d))
FORWARD_DEF(WinHttpQueryAuthSchemes,
    BOOL, (HINTERNET a, LPDWORD b, LPDWORD c, LPDWORD d), (a, b, c, d))
FORWARD_DEF(WinHttpGetDefaultProxyConfiguration,
    BOOL, (WINHTTP_PROXY_INFO *a), (a))
FORWARD_DEF(WinHttpSetDefaultProxyConfiguration,
    BOOL, (WINHTTP_PROXY_INFO *a), (a))
FORWARD_DEF(WinHttpSetCredentials,
    BOOL, (HINTERNET a, DWORD b, DWORD c, LPCWSTR d, LPCWSTR e, LPVOID f), (a, b, c, d, e, f))
FORWARD_DEF(WinHttpTimeFromSystemTime,
    BOOL, (const SYSTEMTIME *a, LPWSTR b), (a, b))
FORWARD_DEF(WinHttpTimeToSystemTime,
    BOOL, (LPCWSTR a, SYSTEMTIME *b), (a, b))
FORWARD_DEF(WinHttpCreateUrl,
    BOOL, (LPURL_COMPONENTS a, DWORD b, LPWSTR c, LPDWORD d), (a, b, c, d))
FORWARD_DEF(WinHttpDetectAutoProxyConfigUrl,
    BOOL, (DWORD a, LPWSTR *b), (a, b))
FORWARD_DEF(WinHttpCheckPlatform,
    BOOL, (void), ())

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
