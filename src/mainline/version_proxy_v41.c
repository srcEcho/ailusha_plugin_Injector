/**
 * v41: PostMessage test (no version proxy, no ghost).
 *
 * Browser process has the game's main window + message pump.
 * Find the window via EnumWindows, subclass it, PostMessage a test.
 *
 * Compile (MSYS2):
 *   gcc -shared -s -Os -static -Wl,--kill-at -o version.dll version_proxy_v41.c -lkernel32 -luser32
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

/* main.js injection */
static const char SIG_MAINJS[]="// main.js";
static const char PAYLOAD[]="$plugins.push({\"name\":\"QuestLog\",\"status\":true,\"description\":\"\",\"parameters\":{}});\r\n";
static const char SIG_SETUP[]="PluginManager.setup($plugins)";
static volatile LONG g_inject_done=0;

typedef BOOL(WINAPI*RF_t)(HANDLE,LPVOID,DWORD,LPDWORD,LPOVERLAPPED);
static RF_t g_RealRF=NULL;static BYTE *gA_RF=NULL,gO_RF[5];

/* PostMessage test */
#define WM_QL_TEST (WM_APP+0x42)
static volatile LONG g_pm_received=0;
static HWND g_gameWnd=NULL;
static WNDPROC g_oldWndProc=NULL;

static LRESULT CALLBACK WndProcHook(HWND hwnd,UINT msg,WPARAM wp,LPARAM lp){
    if(msg==WM_QL_TEST){
        InterlockedIncrement(&g_pm_received);
        char b[128];wsprintfA(b,"*** WM_QL_TEST received! wp=%p lp=%p ***\n",(void*)wp,(void*)lp);L(b);
        return 42;
    }
    return CallWindowProcA(g_oldWndProc,hwnd,msg,wp,lp);
}

static BOOL CALLBACK FindGameWindow(HWND hwnd,LPARAM lp){
    DWORD pid;GetWindowThreadProcessId(hwnd,&pid);
    if(pid==GetCurrentProcessId()){
        if(IsWindowVisible(hwnd)&&GetWindow(hwnd,GW_OWNER)==NULL){
            char title[128];GetWindowTextA(hwnd,title,127);
            LONG style=GetWindowLongA(hwnd,GWL_STYLE);
            if(style&WS_CAPTION||title[0]){
                g_gameWnd=hwnd;
                {char b[200];wsprintfA(b,"Found window: %p title=\"%s\"\n",hwnd,title);L(b);}
                return FALSE;
            }
        }
    }
    return TRUE;
}

static DWORD WINAPI PostMessageTest(LPVOID p){
    Sleep(5000);
    L("PostMessage: enumerating...\n");
    EnumWindows(FindGameWindow,0);
    if(!g_gameWnd){L("ERROR: no window\n");return 1;}
    g_oldWndProc=(WNDPROC)(LONG_PTR)SetWindowLongPtrA(g_gameWnd,GWLP_WNDPROC,(LONG_PTR)WndProcHook);
    if(!g_oldWndProc){L("ERROR: SetWindowLongPtr failed\n");return 1;}
    L("Window subclassed\n");
    L("Posting WM_QL_TEST...\n");
    PostMessageA(g_gameWnd,WM_QL_TEST,0x1234,0x5678);
    L("PostMessage OK, waiting 2s...\n");
    Sleep(2000);
    SetWindowLongPtrA(g_gameWnd,GWLP_WNDPROC,(LONG_PTR)g_oldWndProc);
    {char b[128];wsprintfA(b,"PostMessage done: received=%d\n",g_pm_received);L(b);}
    return 0;
}

static void LazyInit(void){
    if(InterlockedCompareExchange(&g_initialized,1,0)!=0)return;
    InitializeCriticalSection(&g_cs);g_csInit=1;
    g_log=CreateFileA("version_hook.log",GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    L("=== v41: PostMessage ===\n");
    HANDLE pt=CreateThread(NULL,0,PostMessageTest,NULL,0,NULL);if(pt)CloseHandle(pt);
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

__declspec(dllexport) BOOL  WINAPI GetFileVersionInfoA(LPCSTR a,DWORD b,DWORD c,LPVOID d)  {return 0;}
__declspec(dllexport) BOOL  WINAPI GetFileVersionInfoW(LPCWSTR a,DWORD b,DWORD c,LPVOID d){return 0;}
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeA(LPCSTR a,LPDWORD b)            {return 0;}
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeW(LPCWSTR a,LPDWORD b)           {return 0;}
__declspec(dllexport) BOOL  WINAPI VerQueryValueA(LPCVOID a,LPCSTR b,LPVOID*c,PUINT d)    {return 0;}
__declspec(dllexport) BOOL  WINAPI VerQueryValueW(LPCVOID a,LPCWSTR b,LPVOID*c,PUINT d)   {return 0;}
