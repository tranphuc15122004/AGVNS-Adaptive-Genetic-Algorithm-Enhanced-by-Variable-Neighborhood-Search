#include "config.h"

const char * FACTORY_INFO_FILE = "benchmark/factory_info.csv";
const char * ROUTEMAP_FILE = "benchmark/route_info.csv";
const char * VEHICLE_INFO_FILE = "algorithm/data_interaction/vehicle_info.json";
const char * ONGOING_ORDER_ITEMS_INFO_FILE = "algorithm/data_interaction/ongoing_order_items.json";
const char * UNALLOCATED_ORDER_ITEMS_FILE = "algorithm/data_interaction/unallocated_order_items.json";

const char * OUTPUT_ROUTE_FILE = "algorithm/data_interaction/output_route.json";
const char * OUTPUT_DESTINATION_FILE = "algorithm/data_interaction/output_destination.json";

double LOAD_SPEED = 0.25;            // unit is standard pallet per minute
double UNLOAD_SPEED = 0.25;          // unit is standard pallet per minute
int    DOCK_APPROACHING_TIME = 1800; // seconds

int CONFIG_LAMBDA = 10000;

int getLoadingSeconds( double standard_pallet )
{
	return (int)ceil( 60.0 * standard_pallet / LOAD_SPEED );
}

int getUnloadingSeconds( double standard_pallet )
{
	return (int)ceil( 60 * standard_pallet / UNLOAD_SPEED );
}
