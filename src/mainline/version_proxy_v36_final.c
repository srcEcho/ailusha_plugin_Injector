/**
 * v36-final: Clean base — no version proxy, ReadFile hook + main.js injection.
 *
 * Key decisions:
 *   - Version exports return 0. No proxy forwarding. Prevents ghost process.
 *   - ReadFile hook for main.js injection (only hook needed).
 *   - Enigma VFS disk fallback handles QuestLog file loading automatically.
 *   - DllMain ATTACH: install ReadFile hook + create exit event. No thread, no I/O.
 *   - Lazy init on first ReadFile call: open log file.
 *
 * Compile (MSYS2):
 *   gcc -shared -s -Os -static -Wl,--kill-at -o version.dll version_proxy_v36_final.c -lkernel32
 */
#include <windows.h>

static void P5(BYTE*a,void*t){DWORD o;VirtualProtect(a,5,PAGE_EXECUTE_READWRITE,&o);a[0]=0xE9;*(DWORD*)(a+1)=(DWORD)t-(DWORD)a-5;VirtualProtect(a,5,o,&o);FlushInstructionCache(GetCurrentProcess(),a,5);}
static void U5(BYTE*a,BYTE*b){DWORD o;VirtualProtect(a,5,PAGE_EXECUTE_READWRITE,&o);memcpy(a,b,5);VirtualProtect(a,5,o,&o);FlushInstructionCache(GetCurrentProcess(),a,5);}

static HANDLE g_log=INVALID_HANDLE_VALUE;
static HANDLE g_exitEvent=NULL;
static volatile LONG g_initialized=0;
static CRITICAL_SECTION g_cs;static volatile LONG g_csInit=0;

static void L(const char*m){
    if(g_log==INVALID_HANDLE_VALUE)return;
    if(g_csInit)EnterCriticalSection(&g_cs);
    DWORD w;WriteFile(g_log,m,lstrlenA(m),&w,NULL);FlushFileBuffers(g_log);
    if(g_csInit)LeaveCriticalSection(&g_cs);
}

/* ---- main.js injection ---- */
static const char SIG_MAINJS[]="// main.js";
static const char PAYLOAD[]="$plugins.push({\"name\":\"QuestLog\",\"status\":true,\"description\":\"\",\"parameters\":{}});\r\n";
static const char SIG_SETUP[]="PluginManager.setup($plugins)";
static volatile LONG g_inject_done=0;

typedef BOOL(WINAPI*RF_t)(HANDLE,LPVOID,DWORD,LPDWORD,LPOVERLAPPED);
static RF_t g_RealRF=NULL;static BYTE *gA_RF=NULL,gO_RF[5];

static void LazyInit(void){
    if(InterlockedCompareExchange(&g_initialized,1,0)!=0)return;
    InitializeCriticalSection(&g_cs);g_csInit=1;
    g_log=CreateFileA("version_hook.log",GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    L("=== v36-final ===\n");
}

static BOOL WINAPI H_RF(HANDLE hf,LPVOID buf,DWORD nb,LPDWORD lpb,LPOVERLAPPED lo){
    LazyInit();
    U5(gA_RF,gO_RF);BOOL r=g_RealRF(hf,buf,nb,lpb,lo);P5(gA_RF,H_RF);
    if(g_inject_done||!r||!buf||nb<80)return r;
    DWORD actual=lpb?*lpb:nb;
    if(actual<80||actual>0x2000000||IsBadReadPtr(buf,200))return r;
    char*p=(char*)buf;int mlen=sizeof(SIG_MAINJS)-1,has=0;
    for(DWORD i=0;i+mlen<=actual&&i<200;i++){if(memcmp(p+i,SIG_MAINJS,mlen)==0){has=1;break;}}
    if(!has)return r;
    L("*** MAIN.JS DETECTED! ***\n");
    int slen=sizeof(SIG_SETUP)-1,ins=-1;
    for(DWORD i=0;i+slen<=actual&&i<32768;i++){if(memcmp(p+i,SIG_SETUP,slen)==0){ins=(int)i;break;}}
    if(ins<0)return r;
    int pl=sizeof(PAYLOAD)-1;
    if(ins+pl+(int)actual>32768)return r;
    DWORD old;VirtualProtect(buf,32768,PAGE_READWRITE,&old);
    memmove(p+ins+pl,p+ins,actual-ins);memcpy(p+ins,PAYLOAD,pl);
    VirtualProtect(buf,32768,old,&old);
    if(lpb)*lpb=actual+pl;
    {char b[200];wsprintfA(b,"*** INJECTED old=%u new=%u ***\n",actual,*lpb);L(b);}
    FlushFileBuffers(g_log);
    InterlockedExchange(&g_inject_done,1);
    return r;
}

BOOL WINAPI DllMain(HINSTANCE h,DWORD r,LPVOID p){
    if(r==DLL_PROCESS_ATTACH){
        g_exitEvent=CreateEventA(NULL,TRUE,FALSE,NULL);
        HMODULE k32=GetModuleHandleA("kernel32.dll");
        if(k32){gA_RF=(BYTE*)GetProcAddress(k32,"ReadFile");if(gA_RF){memcpy(gO_RF,gA_RF,5);g_RealRF=(RF_t)gA_RF;P5(gA_RF,H_RF);}}
    }else if(r==DLL_PROCESS_DETACH){
        if(g_exitEvent)SetEvent(g_exitEvent);
        if(gA_RF)U5(gA_RF,gO_RF);
        if(g_log!=INVALID_HANDLE_VALUE)CloseHandle(g_log);
    }
    return 1;
}

/* Version exports — return 0 (no proxy). Prevents ghost process. */
__declspec(dllexport) BOOL  WINAPI GetFileVersionInfoA(LPCSTR a,DWORD b,DWORD c,LPVOID d)  {return 0;}
__declspec(dllexport) BOOL  WINAPI GetFileVersionInfoW(LPCWSTR a,DWORD b,DWORD c,LPVOID d){return 0;}
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeA(LPCSTR a,LPDWORD b)            {return 0;}
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeW(LPCWSTR a,LPDWORD b)           {return 0;}
__declspec(dllexport) BOOL  WINAPI VerQueryValueA(LPCVOID a,LPCSTR b,LPVOID*c,PUINT d)    {return 0;}
__declspec(dllexport) BOOL  WINAPI VerQueryValueW(LPCVOID a,LPCWSTR b,LPVOID*c,PUINT d)   {return 0;}
