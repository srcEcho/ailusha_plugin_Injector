/**
 * v50: MinHook-based ReadFile hook — zero race condition.
 * Replaces P5/U5 with MinHook permanent trampoline. Hook never unhooks.
 * Same functionality as v46: dynamic plugin loading from enabled_plugins.txt.
 *
 * Compile (MSYS2):
 *   gcc -shared -s -Os -static -Wl,--kill-at \
 *     -I src/minhook \
 *     -o version.dll \
 *     src/mainline/version_proxy_v50_minhook.c \
 *     src/minhook/hde32.c src/minhook/buffer.c \
 *     src/minhook/hook.c src/minhook/trampoline.c \
 *     -lkernel32
 */
#include <windows.h>
#include "MinHook.h"

// --- Payload ---
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
    int count = 0; char *line = strtok(buf, "\r\n");
    while (line && count < MAX_PLUGINS) {
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

// --- Hook state ---
static const char SIG_MAINJS[] = "// main.js";
static const char SIG_SETUP[] = "PluginManager.setup($plugins)";
static volatile LONG g_inject_done = 0;
typedef BOOL (WINAPI *RF_t)(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
static RF_t g_RealRF = NULL;   // MinHook trampoline (NOT raw kernel32 address)
static volatile LONG g_initialized = 0;

static void LazyInit(void) {
    if (InterlockedCompareExchange(&g_initialized, 1, 0) != 0) return;
    BuildPayload();
}

// --- H_RF: MinHook trampoline handles the real ReadFile call ---
// NO unhook/rehook. NO U5/P5. g_RealRF is MinHook's trampoline.
static BOOL WINAPI H_RF(HANDLE hf, LPVOID buf, DWORD nb, LPDWORD lpb, LPOVERLAPPED lo) {
    LazyInit();

    // Call original ReadFile through MinHook trampoline — zero race!
    BOOL r = g_RealRF(hf, buf, nb, lpb, lo);

    if (g_inject_done || !r || !buf || nb < 80) return r;
    DWORD actual = lpb ? *lpb : nb;
    if (actual < 80 || actual > 0x2000000 || IsBadReadPtr(buf, 200)) return r;
    char *p = (char *)buf; int mlen = sizeof(SIG_MAINJS) - 1, has = 0;
    for (DWORD i = 0; i + mlen <= actual && i < 200; i++) {
        if (memcmp(p + i, SIG_MAINJS, mlen) == 0) { has = 1; break; }
    }
    if (!has) return r;
    if (g_payload_len == 0) return r;

    int slen = sizeof(SIG_SETUP) - 1, ins = -1;
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

BOOL WINAPI DllMain(HINSTANCE h, DWORD r, LPVOID p) {
    if (r == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);

        MH_STATUS status = MH_Initialize();
        if (status != MH_OK && status != MH_ERROR_ALREADY_INITIALIZED) return 1;

        status = MH_CreateHookApi(
            L"kernel32.dll", "ReadFile",
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

// Version API stubs: prevent ghost process, no proxy forwarding.
__declspec(dllexport) BOOL  WINAPI GetFileVersionInfoA(LPCSTR a, DWORD b, DWORD c, LPVOID d)  { return 0; }
__declspec(dllexport) BOOL  WINAPI GetFileVersionInfoW(LPCWSTR a, DWORD b, DWORD c, LPVOID d) { return 0; }
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeA(LPCSTR a, LPDWORD b)             { return 0; }
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeW(LPCWSTR a, LPDWORD b)            { return 0; }
__declspec(dllexport) BOOL  WINAPI VerQueryValueA(LPCVOID a, LPCSTR b, LPVOID *c, PUINT d)   { return 0; }
__declspec(dllexport) BOOL  WINAPI VerQueryValueW(LPCVOID a, LPCWSTR b, LPVOID *c, PUINT d)  { return 0; }
