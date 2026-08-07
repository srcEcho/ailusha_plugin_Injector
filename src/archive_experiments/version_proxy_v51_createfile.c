/**
 * v51: MinHook + ReadFile(main.js注入) + CreateFileW(路径重定向)
 *
 * Compile (MSYS2):
 *   gcc -shared -s -Os -static -Wl,--kill-at \
 *     -I src/minhook \
 *     -o version.dll \
 *     src/mainline/version_proxy_v51_createfile.c \
 *     src/minhook/hde32.c src/minhook/buffer.c \
 *     src/minhook/hook.c src/minhook/trampoline.c \
 *     -lkernel32
 */
#include <windows.h>
#include "MinHook.h"

// ============================================================
// Helpers
// ============================================================
static void P5(BYTE *a, void *t) {
    DWORD o; VirtualProtect(a, 5, PAGE_EXECUTE_READWRITE, &o);
    a[0] = 0xE9; *(DWORD *)(a + 1) = (DWORD)t - (DWORD)a - 5;
    VirtualProtect(a, 5, o, &o); FlushInstructionCache(GetCurrentProcess(), a, 5);
}
static void U5(BYTE *a, BYTE *b) {
    DWORD o; VirtualProtect(a, 5, PAGE_EXECUTE_READWRITE, &o);
    memcpy(a, b, 5); VirtualProtect(a, 5, o, &o); FlushInstructionCache(GetCurrentProcess(), a, 5);
}

// ============================================================
// Payload (main.js injection)
// ============================================================
#define MAX_PLUGINS 32
#define MAX_PAYLOAD 4096
static char g_payload[MAX_PAYLOAD];
static int g_payload_len = 0;
static volatile LONG g_payload_ready = 0;

static void BuildPayload(void) {
    if (InterlockedCompareExchange(&g_payload_ready, 1, 0) != 0) return;
    HANDLE hf = CreateFileA("elsmod_data/enabled_plugins.txt", GENERIC_READ,
                            FILE_SHARE_READ, NULL, OPEN_EXISTING,
                            FILE_ATTRIBUTE_NORMAL, NULL);
    if (hf == INVALID_HANDLE_VALUE) return;
    DWORD sz = GetFileSize(hf, NULL);
    if (sz == 0 || sz > 8192) { CloseHandle(hf); return; }
    char buf[8192] = {0}; DWORD read = 0;
    ReadFile(hf, buf, sz, &read, NULL); CloseHandle(hf);
    char *line = strtok(buf, "\r\n");
    while (line) {
        if (line[0] && line[0] != '#') {
            while (*line == ' ' || *line == '\t') line++;
            int len = lstrlenA(line);
            while (len > 0 && (line[len-1] == ' ' || line[len-1] == '\t')) { line[len-1] = 0; len--; }
            if (len > 0) {
                int add = wsprintfA(g_payload + g_payload_len,
                    "$plugins.push({\"name\":\"%s\",\"status\":true,"
                    "\"description\":\"\",\"parameters\":{}});\r\n", line);
                if (g_payload_len + add < MAX_PAYLOAD - 10) g_payload_len += add;
            }
        }
        line = strtok(NULL, "\r\n");
    }
}

// ============================================================
// Redirect rules (CreateFileW path redirection)
// ============================================================
#define MAX_REDIRECTS 64
#define REDIRECT_PATH_LEN 260

typedef struct {
    WCHAR target[REDIRECT_PATH_LEN];   // e.g., L"www\\js\\plugins\\EventInformation.js"
    WCHAR source[REDIRECT_PATH_LEN];   // e.g., L"elsmod_data\\www\\js\\plugins\\ModFile.js"
} RedirectRule;

static RedirectRule g_redirects[MAX_REDIRECTS];
static int g_redirect_count = 0;
static volatile LONG g_redirects_loaded = 0;

// Normalize a path: replace '/' with '\'
static void NormalizePathW(WCHAR *path) {
    for (; *path; path++) { if (*path == L'/') *path = L'\\'; }
}

// Get path relative to www\ or return original
// e.g. "D:\game\www\js\plugins\Kart.js" → "www\js\plugins\Kart.js"
//      "www\js\plugins\Kart.js" → "www\js\plugins\Kart.js"
static WCHAR *GetRelativePathW(WCHAR *path) {
    // Try to find "\www\" and return from that point (skipping the backslash)
    WCHAR *p = path;
    while (*p) {
        if ((*p == L'\\' || *p == L'/') &&
            (p[1] == L'w' || p[1] == L'W') &&
            (p[2] == L'w' || p[2] == L'W') &&
            (p[3] == L'w' || p[3] == L'W') &&
            (p[4] == L'\\' || p[4] == L'/')) {
            // Found "\www\" at p, return from "www\..."
            p[4] = L'\\';  // normalize separator
            return p + 1;
        }
        p++;
    }
    // No "\www\" found — check if it starts with "www\"
    if ((path[0] == L'w' || path[0] == L'W') &&
        (path[1] == L'w' || path[1] == L'W') &&
        (path[2] == L'w' || path[2] == L'W') &&
        (path[3] == L'\\' || path[3] == L'/')) {
        path[3] = L'\\';
        return path;
    }
    return path;
}

static void LoadRedirects(void) {
    if (InterlockedCompareExchange(&g_redirects_loaded, 1, 0) != 0) return;

    HANDLE hf = CreateFileA("elsmod_data/redirects.txt", GENERIC_READ,
                            FILE_SHARE_READ, NULL, OPEN_EXISTING,
                            FILE_ATTRIBUTE_NORMAL, NULL);
    if (hf == INVALID_HANDLE_VALUE) return;

    DWORD sz = GetFileSize(hf, NULL);
    if (sz == 0 || sz > 32768) { CloseHandle(hf); return; }

    char *buf = (char *)HeapAlloc(GetProcessHeap(), 0, sz + 1);
    if (!buf) { CloseHandle(hf); return; }

    DWORD read = 0;
    ReadFile(hf, buf, sz, &read, NULL);
    CloseHandle(hf);
    buf[read] = 0;

    char *line = strtok(buf, "\r\n");
    while (line && g_redirect_count < MAX_REDIRECTS) {
        // Format: target|source  (pipe-separated, backslash paths)
        // Lines starting with # are comments
        if (line[0] && line[0] != '#') {
            char *sep = strchr(line, '|');
            if (sep) {
                *sep = 0;
                char *target = line;
                char *source = sep + 1;
                // Trim whitespace
                while (*target == ' ' || *target == '\t') target++;
                while (*source == ' ' || *source == '\t') source++;
                // Convert ANSI to wide
                MultiByteToWideChar(CP_ACP, 0, target, -1,
                    g_redirects[g_redirect_count].target, REDIRECT_PATH_LEN);
                MultiByteToWideChar(CP_ACP, 0, source, -1,
                    g_redirects[g_redirect_count].source, REDIRECT_PATH_LEN);
                NormalizePathW(g_redirects[g_redirect_count].target);
                NormalizePathW(g_redirects[g_redirect_count].source);
                g_redirect_count++;
            }
        }
        line = strtok(NULL, "\r\n");
    }
    HeapFree(GetProcessHeap(), 0, buf);
}

// ============================================================
// ReadFile hook (main.js injection — same as v50)
// ============================================================
static const char SIG_MAINJS[] = "// main.js";
static const char SIG_SETUP[] = "PluginManager.setup($plugins)";
static volatile LONG g_inject_done = 0;
typedef BOOL (WINAPI *RF_t)(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
static RF_t g_RealRF = NULL;
static volatile LONG g_rf_initialized = 0;

static void LazyInitRF(void) {
    if (InterlockedCompareExchange(&g_rf_initialized, 1, 0) != 0) return;
    BuildPayload();
}

static BOOL WINAPI H_RF(HANDLE hf, LPVOID buf, DWORD nb, LPDWORD lpb, LPOVERLAPPED lo) {
    LazyInitRF();
    BOOL r = g_RealRF(hf, buf, nb, lpb, lo);
    if (g_inject_done || !r || !buf || nb < 80) return r;
    DWORD actual = lpb ? *lpb : nb;
    if (actual < 80 || actual > 0x2000000 || IsBadReadPtr(buf, 200)) return r;
    char *p = (char *)buf;
    int mlen = (int)(sizeof(SIG_MAINJS) - 1), has = 0;
    for (DWORD i = 0; i + mlen <= actual && i < 200; i++) {
        if (memcmp(p + i, SIG_MAINJS, mlen) == 0) { has = 1; break; }
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
// CreateFileW hook (path redirection)
// ============================================================
typedef HANDLE (WINAPI *CFW_t)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES,
                                DWORD, DWORD, HANDLE);
static CFW_t g_RealCFW = NULL;

static HANDLE WINAPI H_CFW(LPCWSTR fn, DWORD dwDesiredAccess, DWORD dwShareMode,
                            LPSECURITY_ATTRIBUTES lpSA, DWORD dwCreationDisposition,
                            DWORD dwFlagsAndAttributes, HANDLE hTemplateFile) {
    LoadRedirects();

    if (g_redirect_count > 0 && fn) {
        // Get relative path
        WCHAR relPath[REDIRECT_PATH_LEN];
        WCHAR *rel = GetRelativePathW((WCHAR *)fn);
        lstrcpyW(relPath, rel);
        NormalizePathW(relPath);

        // Check against redirect table
        for (int i = 0; i < g_redirect_count; i++) {
            if (lstrcmpiW(relPath, g_redirects[i].target) == 0) {
                // Redirect to source path
                return g_RealCFW(g_redirects[i].source,
                                 dwDesiredAccess, dwShareMode, lpSA,
                                 dwCreationDisposition, dwFlagsAndAttributes, hTemplateFile);
            }
        }
    }

    // Pass through
    return g_RealCFW(fn, dwDesiredAccess, dwShareMode, lpSA,
                     dwCreationDisposition, dwFlagsAndAttributes, hTemplateFile);
}

// ============================================================
// DllMain
// ============================================================
BOOL WINAPI DllMain(HINSTANCE h, DWORD r, LPVOID p) {
    if (r == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);

        MH_STATUS status = MH_Initialize();
        if (status != MH_OK && status != MH_ERROR_ALREADY_INITIALIZED) return 1;

        // Hook ReadFile
        status = MH_CreateHookApi(L"kernel32.dll", "ReadFile",
                                   H_RF, (LPVOID *)&g_RealRF);
        if (status != MH_OK) return 1;

        // Hook CreateFileW
        status = MH_CreateHookApi(L"kernel32.dll", "CreateFileW",
                                   H_CFW, (LPVOID *)&g_RealCFW);
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
