/**
 * v52-debug: plugins.js rebuild + CreateFileW redirect + detailed logging
 * Fix: track plugins.js by file handle, find ]; in ANY chunk, inject there.
 */
#include <windows.h>
#include "MinHook.h"

// ============================================================
// Logging
// ============================================================
static HANDLE g_log = INVALID_HANDLE_VALUE;
static CRITICAL_SECTION g_log_cs;
static volatile LONG g_log_cs_init = 0;
static void Log(const char *fmt, ...) {
    if (g_log == INVALID_HANDLE_VALUE) return;
    if (InterlockedCompareExchange(&g_log_cs_init, 1, 0) == 0) InitializeCriticalSection(&g_log_cs);
    EnterCriticalSection(&g_log_cs);
    char buf[512]; DWORD w; va_list ap; va_start(ap, fmt);
    int len = wvsprintfA(buf, fmt, ap); va_end(ap);
    WriteFile(g_log, buf, len, &w, NULL); FlushFileBuffers(g_log);
    LeaveCriticalSection(&g_log_cs);
}

// ============================================================
// JSON parser
// ============================================================
#define MAX_JSON_SIZE 8192
#define MAX_ITEMS 64
#define MAX_STR_LEN 260
static char g_plugins[MAX_ITEMS][MAX_STR_LEN];
static int g_plugin_count = 0;
static WCHAR g_redirects_target[MAX_ITEMS][MAX_STR_LEN];
static WCHAR g_redirects_source[MAX_ITEMS][MAX_STR_LEN];
static int g_redirect_count = 0;
static volatile LONG g_config_loaded = 0;

static char *SkipWS(char *p) { while (*p==' '||*p=='\t'||*p=='\r'||*p=='\n') p++; return p; }
static char *ExtractStr(char *p, char *dst, int maxlen) {
    p=SkipWS(p); if(*p!='"')return NULL; p++; int i=0;
    while(*p&&*p!='"'&&i<maxlen-1){if(*p=='\\'&&p[1]){p++;dst[i++]=*p++;}else{dst[i++]=*p++;}}
    dst[i]=0; if(*p=='"')p++; return p;
}
static char *ExtractStrW(char *p, WCHAR *dst, int maxlen) {
    char tmp[MAX_STR_LEN]; p=ExtractStr(p,tmp,MAX_STR_LEN); if(!p)return NULL;
    MultiByteToWideChar(CP_UTF8,0,tmp,-1,dst,maxlen);
    for(WCHAR*w=dst;*w;w++)if(*w==L'/')*w=L'\\'; return p;
}
static void ParseConfig(char *json) {
    g_plugin_count=0; g_redirect_count=0; char *p=json;
    p=strstr(p,"\"plugins\""); if(p){p+=9;p=SkipWS(p);if(*p==':'){p++;p=SkipWS(p);if(*p=='['){p++;
    while(g_plugin_count<MAX_ITEMS){p=SkipWS(p);if(*p==']'||*p==0)break;if(*p==','){p++;continue;}
    p=ExtractStr(p,g_plugins[g_plugin_count],MAX_STR_LEN); if(!p)break; g_plugin_count++;}}}}
    p=json; p=strstr(p,"\"redirects\""); if(p){p+=11;p=SkipWS(p);if(*p==':'){p++;p=SkipWS(p);if(*p=='['){p++;
    while(g_redirect_count<MAX_ITEMS){p=SkipWS(p);if(*p==']'||*p==0)break;if(*p==','){p++;continue;}
    if(*p=='{'){p++; WCHAR t[MAX_STR_LEN]={0},s[MAX_STR_LEN]={0};
    p=strstr(p,"\"target\"");if(p){p+=8;p=SkipWS(p);if(*p==':'){p++;p=ExtractStrW(p,t,MAX_STR_LEN);}}
    p=strstr(p,"\"source\"");if(p){p+=8;p=SkipWS(p);if(*p==':'){p++;p=ExtractStrW(p,s,MAX_STR_LEN);}}
    if(t[0]&&s[0]){lstrcpyW(g_redirects_target[g_redirect_count],t);lstrcpyW(g_redirects_source[g_redirect_count],s);g_redirect_count++;}
    while(*p&&*p!='}'&&*p!=']')p++; if(*p=='}')p++;}}}}}
}
static void LoadConfig(void) {
    if(InterlockedCompareExchange(&g_config_loaded,1,0)!=0)return;
    lstrcpyA(g_plugins[0],"TestPluginA"); g_plugin_count=1;
    Log("LoadConfig: hardcoded=%s count=%d\n",g_plugins[0],g_plugin_count);
    HANDLE hf=CreateFileA("elsmod_data/injector_config.json",GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    if(hf==INVALID_HANDLE_VALUE){Log("LoadConfig: no json, using hardcoded\n");return;}
    DWORD sz=GetFileSize(hf,NULL); if(sz==0||sz>MAX_JSON_SIZE){CloseHandle(hf);return;}
    char *buf=(char*)HeapAlloc(GetProcessHeap(),0,sz+1); if(!buf){CloseHandle(hf);return;}
    DWORD read=0; ReadFile(hf,buf,sz,&read,NULL); CloseHandle(hf); buf[read]=0;
    Log("LoadConfig: read %d bytes\n",read);
    ParseConfig(buf); Log("LoadConfig: plugins=%d redirects=%d\n",g_plugin_count,g_redirect_count);
    for(int i=0;i<g_plugin_count;i++)Log("  plugin[%d]=%s\n",i,g_plugins[i]);
    HeapFree(GetProcessHeap(),0,buf);
}

// ============================================================
// CreateFileW hook
// ============================================================
typedef HANDLE(WINAPI*CFW_t)(LPCWSTR,DWORD,DWORD,LPSECURITY_ATTRIBUTES,DWORD,DWORD,HANDLE);
static CFW_t g_RealCFW=NULL; static int g_cfw_calls=0;
static void NormW(WCHAR*p){for(;*p;p++)if(*p==L'/')*p=L'\\';}
static WCHAR*RelW(WCHAR*p){
    WCHAR*q=p; while(*q){if((*q==L'\\'||*q==L'/')&&(q[1]==L'w'||q[1]==L'W')&&(q[2]==L'w'||q[2]==L'W')&&(q[3]==L'w'||q[3]==L'W')&&(q[4]==L'\\'||q[4]==L'/')){q[4]=L'\\';return q+1;}q++;}
    if((p[0]==L'w'||p[0]==L'W')&&(p[1]==L'w'||p[1]==L'W')&&(p[2]==L'w'||p[2]==L'W')&&(p[3]==L'\\'||p[3]==L'/')){p[3]=L'\\';return p;} return p;
}
static HANDLE WINAPI H_CFW(LPCWSTR fn,DWORD a,DWORD b,LPSECURITY_ATTRIBUTES c,DWORD d,DWORD e,HANDLE f){
    LoadConfig(); g_cfw_calls++;
    if(g_redirect_count>0&&fn){WCHAR rel[MAX_STR_LEN];lstrcpyW(rel,RelW((WCHAR*)fn));NormW(rel);
    for(int i=0;i<g_redirect_count;i++){if(lstrcmpiW(rel,g_redirects_target[i])==0){
        Log("H_CFW REDIRECT %S -> %S\n",rel,g_redirects_source[i]); return g_RealCFW(g_redirects_source[i],a,b,c,d,e,f);}}}
    if(fn&&(g_cfw_calls%50==0)){WCHAR rel[MAX_STR_LEN];lstrcpyW(rel,RelW((WCHAR*)fn));Log("H_CFW #%d: %S\n",g_cfw_calls,rel);}
    return g_RealCFW(fn,a,b,c,d,e,f);
}

// ============================================================
// ReadFile hook — plugins.js track-by-handle + inject on ];
// ============================================================
typedef BOOL(WINAPI*RF_t)(HANDLE,LPVOID,DWORD,LPDWORD,LPOVERLAPPED);
static RF_t g_RealRF=NULL; static int g_rf_calls=0;
static HANDLE g_pluginsHandle=INVALID_HANDLE_VALUE;
static volatile LONG g_push_done=0;

static int BuildPush(char *out,int maxLen){
    int len=0;
    for(int i=0;i<g_plugin_count;i++){
        int add=wsprintfA(out+len,"$plugins.push({\"name\":\"%s\",\"status\":true,\"description\":\"v52 test\",\"parameters\":{}});\r\n",g_plugins[i]);
        if(len+add<maxLen)len+=add;
    }
    return len;
}

static BOOL WINAPI H_RF(HANDLE hf,LPVOID buf,DWORD nb,LPDWORD lpb,LPOVERLAPPED lo){
    LoadConfig();
    BOOL r=g_RealRF(hf,buf,nb,lpb,lo); g_rf_calls++;
    if(g_push_done||!r||!buf||nb<80)return r;
    DWORD actual=lpb?*lpb:nb;
    if(actual<80||actual>0x2000000||IsBadReadPtr(buf,200))return r;
    char*p=(char*)buf;

    // Detect plugins.js by "$plugins" in first 2KB, remember handle
    int hasSig=0;
    for(DWORD i=0;i+8<=actual&&i<2048;i++){if(memcmp(p+i,"$plugins",8)==0){hasSig=1;break;}}
    if(hasSig&&g_pluginsHandle==INVALID_HANDLE_VALUE){
        g_pluginsHandle=hf; Log("H_RF #%d: plugins.js TRACKED handle=%p\n",g_rf_calls,hf);
    }

    // Only process reads for the tracked plugins.js handle
    if(hf!=g_pluginsHandle)return r;

    // Search for ]; (closing of $plugins array)
    char*closing=NULL;
    for(char*s=p+actual-2;s>p;s--){if(s[0]==']'&&s[1]==';'){closing=s;break;}}
    if(!closing){Log("H_RF #%d: plugins.js actual=%d, no ]; yet\n",g_rf_calls,actual);return r;}

    Log("H_RF #%d: ]; at offset %d, actual=%d\n",g_rf_calls,(int)(closing-p),actual);

    char script[MAX_JSON_SIZE]; int slen=BuildPush(script,MAX_JSON_SIZE);
    if(!slen)return r;

    int tailLen=(int)(p+actual-closing), newTail=slen+2, shift=newTail-tailLen;
    Log("  tail=%d newTail=%d shift=%d slen=%d\n",tailLen,newTail,shift,slen);

    if(actual+shift>32768||actual+shift<0){Log("  size limit\n");return r;}

    DWORD old;VirtualProtect(buf,32768,PAGE_READWRITE,&old);
    if(shift!=0)memmove(closing+newTail,closing+tailLen,actual-(DWORD)(closing-p)-tailLen);
    memcpy(closing,script,slen); closing[slen]=']'; closing[slen+1]=';';
    VirtualProtect(buf,32768,old,&old);
    *lpb=actual+shift; InterlockedExchange(&g_push_done,1);
    Log("  DONE new actual=%d\n",*lpb);
    return r;
}

// ============================================================
// DllMain
// ============================================================
BOOL WINAPI DllMain(HINSTANCE h,DWORD r,LPVOID p){
    if(r==DLL_PROCESS_ATTACH){
        DisableThreadLibraryCalls(h);
        g_log=CreateFileA("v52_debug.log",GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
        Log("=== v52-debug ATTACH ===\n");
        MH_STATUS s=MH_Initialize(); Log("MH_Init=%d\n",s);
        if(s!=MH_OK&&s!=MH_ERROR_ALREADY_INITIALIZED)return 1;
        s=MH_CreateHookApi(L"kernel32.dll","CreateFileW",H_CFW,(LPVOID*)&g_RealCFW); Log("MH_CFW=%d\n",s);
        s=MH_CreateHookApi(L"kernel32.dll","ReadFile",H_RF,(LPVOID*)&g_RealRF); Log("MH_RF=%d\n",s);
        s=MH_EnableHook(MH_ALL_HOOKS); Log("MH_Enable=%d\n",s);
    }else if(r==DLL_PROCESS_DETACH){
        Log("=== v52-debug DETACH CFW=%d RF=%d ===\n",g_cfw_calls,g_rf_calls);
        MH_DisableHook(MH_ALL_HOOKS); MH_Uninitialize();
        if(g_log!=INVALID_HANDLE_VALUE)CloseHandle(g_log);
    }
    return 1;
}
__declspec(dllexport) BOOL WINAPI GetFileVersionInfoA(LPCSTR a,DWORD b,DWORD c,LPVOID d){return 0;}
__declspec(dllexport) BOOL WINAPI GetFileVersionInfoW(LPCWSTR a,DWORD b,DWORD c,LPVOID d){return 0;}
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeA(LPCSTR a,LPDWORD b){return 0;}
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeW(LPCWSTR a,LPDWORD b){return 0;}
__declspec(dllexport) BOOL WINAPI VerQueryValueA(LPCVOID a,LPCSTR b,LPVOID*c,PUINT d){return 0;}
__declspec(dllexport) BOOL WINAPI VerQueryValueW(LPCVOID a,LPCWSTR b,LPVOID*c,PUINT d){return 0;}
