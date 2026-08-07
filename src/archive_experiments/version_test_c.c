/** Test C: Version stubs + ReadFile hook with HARDCODED payload (no file I/O in hook).
 *  Directly compares against v46 which does BuildPayload(ReadFile) inside hook. */
#include <windows.h>

static void P5(BYTE*a,void*t){DWORD o;VirtualProtect(a,5,PAGE_EXECUTE_READWRITE,&o);a[0]=0xE9;*(DWORD*)(a+1)=(DWORD)t-(DWORD)a-5;VirtualProtect(a,5,o,&o);FlushInstructionCache(GetCurrentProcess(),a,5);}
static void U5(BYTE*a,BYTE*b){DWORD o;VirtualProtect(a,5,PAGE_EXECUTE_READWRITE,&o);memcpy(a,b,5);VirtualProtect(a,5,o,&o);FlushInstructionCache(GetCurrentProcess(),a,5);}

static const char SIG_MAINJS[]="// main.js";
static const char SIG_SETUP[]="PluginManager.setup($plugins)";
static volatile LONG g_inject_done=0;
typedef BOOL(WINAPI*RF_t)(HANDLE,LPVOID,DWORD,LPDWORD,LPOVERLAPPED);
static RF_t g_RealRF=NULL;static BYTE *gA_RF=NULL,gO_RF[5];

static const char PAYLOAD[]="$plugins.push({\"name\":\"QuestLog\",\"status\":true,\"description\":\"\",\"parameters\":{}});\r\n";

static BOOL WINAPI H_RF(HANDLE hf,LPVOID buf,DWORD nb,LPDWORD lpb,LPOVERLAPPED lo){
    U5(gA_RF,gO_RF);BOOL r=g_RealRF(hf,buf,nb,lpb,lo);P5(gA_RF,H_RF);
    if(g_inject_done||!r||!buf||nb<80)return r;
    DWORD actual=lpb?*lpb:nb;
    if(actual<80||actual>0x2000000||IsBadReadPtr(buf,200))return r;
    char*p=(char*)buf;int mlen=sizeof(SIG_MAINJS)-1,has=0;
    for(DWORD i=0;i+mlen<=actual&&i<200;i++){if(memcmp(p+i,SIG_MAINJS,mlen)==0){has=1;break;}}
    if(!has)return r;
    int slen=sizeof(SIG_SETUP)-1,ins=-1;
    for(DWORD i=0;i+slen<=actual&&i<32768;i++){if(memcmp(p+i,SIG_SETUP,slen)==0){ins=(int)i;break;}}
    if(ins<0)return r;
    int pl=sizeof(PAYLOAD)-1;
    if(ins+pl+(int)actual>32768)return r;
    DWORD old;VirtualProtect(buf,32768,PAGE_READWRITE,&old);
    memmove(p+ins+pl,p+ins,actual-ins);memcpy(p+ins,PAYLOAD,pl);
    VirtualProtect(buf,32768,old,&old);
    if(lpb)*lpb=actual+pl;
    InterlockedExchange(&g_inject_done,1);
    return r;
}

BOOL WINAPI DllMain(HINSTANCE h,DWORD r,LPVOID p){
    if(r==DLL_PROCESS_ATTACH){
        DisableThreadLibraryCalls(h);
        HMODULE k32=GetModuleHandleA("kernel32.dll");
        if(k32){gA_RF=(BYTE*)GetProcAddress(k32,"ReadFile");if(gA_RF){memcpy(gO_RF,gA_RF,5);g_RealRF=(RF_t)gA_RF;P5(gA_RF,H_RF);}}
    }else if(r==DLL_PROCESS_DETACH){
        if(gA_RF)U5(gA_RF,gO_RF);
    }
    return 1;
}

__declspec(dllexport) BOOL  WINAPI GetFileVersionInfoA(LPCSTR a,DWORD b,DWORD c,LPVOID d)  {return 0;}
__declspec(dllexport) BOOL  WINAPI GetFileVersionInfoW(LPCWSTR a,DWORD b,DWORD c,LPVOID d){return 0;}
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeA(LPCSTR a,LPDWORD b)            {return 0;}
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeW(LPCWSTR a,LPDWORD b)           {return 0;}
__declspec(dllexport) BOOL  WINAPI VerQueryValueA(LPCVOID a,LPCSTR b,LPVOID*c,PUINT d)    {return 0;}
__declspec(dllexport) BOOL  WINAPI VerQueryValueW(LPCVOID a,LPCWSTR b,LPVOID*c,PUINT d)   {return 0;}
