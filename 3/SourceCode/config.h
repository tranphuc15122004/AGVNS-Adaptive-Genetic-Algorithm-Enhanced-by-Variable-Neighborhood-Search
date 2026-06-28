#ifndef _DPDP_CONFIG_H_
#define _DPDP_CONFIG_H_

#include <math.h>

extern const char* FACTORY_INFO_FILE;
extern const char* ROUTEMAP_FILE;
extern const char* VEHICLE_INFO_FILE;
extern const char* ONGOING_ORDER_ITEMS_INFO_FILE;
extern const char* UNALLOCATED_ORDER_ITEMS_FILE;
extern const char* OUTPUT_ROUTE_FILE;
extern const char* OUTPUT_DESTINATION_FILE;

extern double LOAD_SPEED;
extern double UNLOAD_SPEED;
extern int  DOCK_APPROACHING_TIME;
extern int CONFIG_LAMBDA;

/// <summary>
/// Returns the loading time (in seconds) of the given amount of standard pallets.
/// </summary>
/// <param name="standard_pallet"></param>
/// <returns></returns>
int getLoadingSeconds( double standard_pallet );

/// <summary>
/// Returns the unloading time (in seconds) of the given amount of standard pallets.
/// </summary>
/// <param name="standard_pallet"></param>
/// <returns></returns>
int getUnloadingSeconds( double standard_pallet );

#endif
