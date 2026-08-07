/** Test A: Version API stubs ONLY. No ReadFile hook. */
#include <windows.h>

BOOL WINAPI DllMain(HINSTANCE h,DWORD r,LPVOID p){
    if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);}
    return 1;
}

__declspec(dllexport) BOOL  WINAPI GetFileVersionInfoA(LPCSTR a,DWORD b,DWORD c,LPVOID d)  {return 0;}
__declspec(dllexport) BOOL  WINAPI GetFileVersionInfoW(LPCWSTR a,DWORD b,DWORD c,LPVOID d){return 0;}
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeA(LPCSTR a,LPDWORD b)            {return 0;}
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeW(LPCWSTR a,LPDWORD b)           {return 0;}
__declspec(dllexport) BOOL  WINAPI VerQueryValueA(LPCVOID a,LPCSTR b,LPVOID*c,PUINT d)    {return 0;}
__declspec(dllexport) BOOL  WINAPI VerQueryValueW(LPCVOID a,LPCWSTR b,LPVOID*c,PUINT d)   {return 0;}
