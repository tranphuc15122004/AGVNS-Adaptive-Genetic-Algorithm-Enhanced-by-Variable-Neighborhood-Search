#pragma once

/* common includes */
#include <cstddef>  // NULL
#include <string>   // std::string
#include <limits>

/* print utils */
#ifdef DPDP_PRINT
#define dpdpPrintfInfo  printf("INFO  : "), printf
#define dpdpPrintfWarn  printf("WARN  : "), printf
#define dpdpPrintfError printf("ERROR : [%s:%d] ", __FUNCTION__, __LINE__ ), printf
#define dpdpPrintfDebug printf("DEBUG : "), printf
#define dpdpPrintfTrace printf("TRACE : "), printf
#else
#define dpdpPrintfInfo  
#define dpdpPrintfWarn  
#define dpdpPrintfError 
#define dpdpPrintfDebug 
#define dpdpPrintfTrace 
#endif

/* error codes */
constexpr int ERROR_ASSERTATION     = 100; // assertation error
constexpr int ERROR_ARGUMENT_TOOFEW = 200; // argument : too few arguments
constexpr int ERROR_FILE_NOTFOUND   = 300; // file : file not found
constexpr int ERROR_FILE_PARSE      = 301; // file : parse error
constexpr int ERROR_DATA_GENERAL    = 400; // data : general error
constexpr int ERROR_SOLVING_GENERAL = 500; // solving : general error

/* function calling utils */
#define DPDP_CALL(func) do {                                        \
  int _retcode_;                                                    \
  if( (_retcode_ = (func)) != 0 )  {                                \
    dpdpPrintfError( "error (%d) in function call!\n", _retcode_ ); \
    return _retcode_;                                               \
  }                                                                 \
} while( false )

#define DPDP_CALL_TERM(func,retcode,label) do {                             \
	if( ( retcode = ( func ) ) != 0 ) {                                       \
		dpdpPrintfError( "error (%d) in function call %s!\n", retcode, #func ); \
		goto label;                                                             \
	}                                                                         \
} while( false )

#define DPDP_CALL_THROW(func) do {                                            \
  int _retcode_;                                                              \
	if( ( _retcode_ = ( func ) ) != 0 ) {                                       \
		dpdpPrintfError( "error (%d) in function call %s!\n", _retcode_, #func ); \
		throw "error";                                                            \
	}                                                                           \
}  while( false );

#ifdef DPDP_DEBUG
#define DPDP_ASSERT( expr ) do {                            \
  if( !(expr) ) {                                           \
    dpdpPrintfError( "assertation '%s' failed!\n", #expr ); \
    return ERROR_ASSERTATION;                               \
  }                                                         \
} while( false )
#else
#define DPDP_ASSERT( expr ) ( expr )
#endif

#ifdef DPDP_DEBUG
#define DPDP_ASSERT_ABORT( expr ) do {                      \
  if( !(expr) ) {                                           \
    dpdpPrintfError( "assertation '%s' failed!\n", #expr ); \
    abort();                                                \
  }                                                         \
} while( false )
#else
#define DPDP_ASSERT_ABORT( expr ) ( expr )
#endif

/* value utils */
constexpr double DPDP_EPSILON      = 1e-6;
constexpr double DPDP_INFINITY_DBL = 1e40;
constexpr int    DPDP_INFINITY_INT = std::numeric_limits<int>::max();
    
