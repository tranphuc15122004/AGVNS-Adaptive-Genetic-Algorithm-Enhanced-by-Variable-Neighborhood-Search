#ifndef _DPDP_INPUTDATA_H_
#define _DPDP_INPUTDATA_H_

#include "inputdata_aux.h"

class InputData
{
public:
	std::list<InputVehicle> vehicles;
	std::list<InputMapEntity> mapentities;
	std::list<InputFactory> factories;
	std::list<InputOrderItem> ongoing_order_items;
	std::list<InputOrderItem> unallocated_order_items;

public:
	int readDistances( const char* routemap_file_name, const bool has_header = true );
	int readFactories( const char* factories_file_name, const bool has_header = true );

	int readStaticData( const char* factories_filename, const char* routemap_filename )
	{
		DPDP_CALL( readFactories( factories_filename, true ) );
		//DPDP_CALL( readDistances( routemap_filename, true ) );

		return 0;
	}

	int readVehicleInfo( const char* filaname );
	int readOngingOrderItems( const char* filename );
	int readUnallocatedOrderItems( const char* filename );

	int readInteractionData( const char* vehicle_info_filename, const char* ongoing_order_items_filename, const char* unallocated_order_items_filename )
	{
		DPDP_CALL( readVehicleInfo( vehicle_info_filename ) );
		DPDP_CALL( readOngingOrderItems( ongoing_order_items_filename ) );
		DPDP_CALL( readUnallocatedOrderItems( unallocated_order_items_filename ) );

		return 0;
	}
};

#endif
