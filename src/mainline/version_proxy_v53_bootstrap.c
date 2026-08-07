/**
 * v53-bootstrap: CreateFileW redirect test.
 * Hardcoded: EventInformation.js → TestPluginA.js
 * If TestPluginA alert pops, CreateFileW redirect works.
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

typedef HANDLE (WINAPI *CFW_t)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES,
                                DWORD, DWORD, HANDLE);
static CFW_t g_RealCFW = NULL;
static int g_cfw_calls = 0;

static HANDLE WINAPI H_CFW(LPCWSTR fn, DWORD a, DWORD b, LPSECURITY_ATTRIBUTES c,
                            DWORD d, DWORD e, HANDLE f) {
    g_cfw_calls++;

    if (fn) {
        int len = lstrlenW(fn);
        LPCWSTR name = fn + len;
        while (name > fn && *(name-1) != L'\\' && *(name-1) != L'/') name--;

        // Check if filename is EventInformation.js (but NOT from originals dir)
        if (lstrcmpiW(name, L"EventInformation.js") == 0 &&
            !wcsstr(fn, L"originals")) {
            Log("CFW #%d: MATCH EventInformation.js\n", g_cfw_calls);
            // Replace filename only: EventInformation.js → EventInformation_bootstrap.js
            WCHAR newPath[512]; int i;
            for (i = 0; i < (int)(name - fn) && i < 510; i++) newPath[i] = fn[i];
            lstrcpyW(newPath + i, L"EventInformation_bootstrap.js");
            Log("  -> %S\n", newPath);
            return g_RealCFW(newPath, a, b, c, d, e, f);
        }
    }
    return g_RealCFW(fn, a, b, c, d, e, f);
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD r, LPVOID p) {
    if (r == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);
        g_log = CreateFileA("v53_bootstrap.log", GENERIC_WRITE, FILE_SHARE_READ, NULL,
                             CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        Log("=== v53-bootstrap ATTACH ===\n");
        MH_Initialize();
        MH_CreateHookApi(L"kernel32.dll", "CreateFileW", H_CFW, (LPVOID *)&g_RealCFW);
        MH_EnableHook(MH_ALL_HOOKS);
        Log("hooks installed\n");
    } else if (r == DLL_PROCESS_DETACH) {
        Log("=== DETACH CFW=%d ===\n", g_cfw_calls);
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
