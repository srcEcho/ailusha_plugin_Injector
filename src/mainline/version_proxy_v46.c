/**
 * v46: Dynamic plugin loader — no logging, no version proxy, no ghost.
 * Reads elsmod_data/enabled_plugins.txt at injection time.
 *
 * Compile (MSYS2):
 *   gcc -shared -s -Os -static -Wl,--kill-at -o version.dll version_proxy_v46.c -lkernel32
 */
#include <windows.h>

static void P5(BYTE*a,void*t){DWORD o;VirtualProtect(a,5,PAGE_EXECUTE_READWRITE,&o);a[0]=0xE9;*(DWORD*)(a+1)=(DWORD)t-(DWORD)a-5;VirtualProtect(a,5,o,&o);FlushInstructionCache(GetCurrentProcess(),a,5);}
static void U5(BYTE*a,BYTE*b){DWORD o;VirtualProtect(a,5,PAGE_EXECUTE_READWRITE,&o);memcpy(a,b,5);VirtualProtect(a,5,o,&o);FlushInstructionCache(GetCurrentProcess(),a,5);}

#define MAX_PLUGINS 32
#define MAX_PAYLOAD 4096
static char g_payload[MAX_PAYLOAD];
static int g_payload_len=0;
static volatile LONG g_payload_ready=0;

static void BuildPayload(void){
    if(InterlockedCompareExchange(&g_payload_ready,1,0)!=0)return;

    HANDLE hf=CreateFileA("elsmod_data/enabled_plugins.txt",GENERIC_READ,
                           FILE_SHARE_READ,NULL,OPEN_EXISTING,
                           FILE_ATTRIBUTE_NORMAL,NULL);
    if(hf==INVALID_HANDLE_VALUE)return;

    DWORD sz=GetFileSize(hf,NULL);
    if(sz==0||sz>8192){CloseHandle(hf);return;}

    char buf[8192]={0};
    DWORD read=0;
    ReadFile(hf,buf,sz,&read,NULL);
    CloseHandle(hf);

    int count=0;
    char*line=strtok(buf,"\r\n");
    while(line&&count<MAX_PLUGINS){
        if(line[0]&&line[0]!='#'){
            while(*line==' '||*line=='\t')line++;
            int len=lstrlenA(line);
            while(len>0&&(line[len-1]==' '||line[len-1]=='\t')){line[len-1]=0;len--;}
            if(len>0){
                int add=wsprintfA(g_payload+g_payload_len,
                    "$plugins.push({\"name\":\"%s\",\"status\":true,"
                    "\"description\":\"\",\"parameters\":{}});\r\n",line);
                if(g_payload_len+add<MAX_PAYLOAD-10)g_payload_len+=add;
            }
        }
        line=strtok(NULL,"\r\n");
    }
}

static const char SIG_MAINJS[]="// main.js";
static const char SIG_SETUP[]="PluginManager.setup($plugins)";
static volatile LONG g_inject_done=0;

typedef BOOL(WINAPI*RF_t)(HANDLE,LPVOID,DWORD,LPDWORD,LPOVERLAPPED);
static RF_t g_RealRF=NULL;static BYTE *gA_RF=NULL,gO_RF[5];
static volatile LONG g_initialized=0;

static void LazyInit(void){
    if(InterlockedCompareExchange(&g_initialized,1,0)!=0)return;
    BuildPayload();
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
    if(g_payload_len==0)return r;

    int slen=sizeof(SIG_SETUP)-1,ins=-1;
    for(DWORD i=0;i+slen<=actual&&i<32768;i++){if(memcmp(p+i,SIG_SETUP,slen)==0){ins=(int)i;break;}}
    if(ins<0||ins+g_payload_len+(int)actual>32768)return r;

    DWORD old;VirtualProtect(buf,32768,PAGE_READWRITE,&old);
    memmove(p+ins+g_payload_len,p+ins,actual-ins);
    memcpy(p+ins,g_payload,g_payload_len);
    VirtualProtect(buf,32768,old,&old);
    if(lpb)*lpb=actual+g_payload_len;
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
