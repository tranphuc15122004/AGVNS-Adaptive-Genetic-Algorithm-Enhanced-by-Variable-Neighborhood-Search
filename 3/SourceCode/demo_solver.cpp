#include "demo_solver.h"

#include "probdata.h"

#include <set>

#include "config.h"

DemoSolver::DemoSolver() : probdata( NULL )
{
}

int DemoSolver::init( const ProbData * _probdata )
{
	DPDP_ASSERT( NULL == probdata );

	probdata = _probdata;

	return 0;
}

int DemoSolver::run()
{
	Solution solution( probdata->getNumVehicles() );

	/* dealing with the carrying items of vehicles */
	for( int v = 0; v < probdata->getNumVehicles(); ++v )
	{
		RouteEntity* curr_entity = NULL;
		const Vehicle* vehicle = probdata->getVehicle( v );

		for( std::list<const OrderItem*>::const_reverse_iterator cit = vehicle->carrying_items.crbegin(); cit != vehicle->carrying_items.crend(); ++cit )
		{
			const OrderItem* item = *cit;
			
			if( NULL == curr_entity || curr_entity->factory != item->delivery_factory )
			{
				/* create new entity */
				RouteEntity* new_entity = new RouteEntity();
				new_entity->factory = item->delivery_factory;

				if( vehicle->destination != NULL )
					new_entity->arrive_time = vehicle->destination->arrive_time;

				solution.append( v, new_entity );

				curr_entity = new_entity;
			}

			curr_entity->delivery_item_list.push_back( item );
		}
	}

	/* for the empty vehicle, it has been allocated to the order, but have not yet arrived at the pickup factory */
	std::set<std::string> allocated_items;
	
	for( int v = 0; v < probdata->getNumVehicles(); ++v )
	{
		const Vehicle* vehicle = probdata->getVehicle( v );

		if( vehicle->carrying_items.empty() && vehicle->destination != NULL && !vehicle->destination->pickup_items.empty() )
		{
			const OrderItem* first_item = vehicle->destination->pickup_items.front();

			RouteEntity* p_entity = new RouteEntity();
			RouteEntity* d_entity = new RouteEntity();
			p_entity->factory = first_item->pickup_factory;
			p_entity->arrive_time = vehicle->destination->arrive_time;
			d_entity->factory = first_item->delivery_factory;

			for( std::list<const OrderItem*>::const_iterator it = vehicle->destination->pickup_items.cbegin(); it != vehicle->destination->pickup_items.cend(); ++it )
			{
				const OrderItem* item = *it;
				DPDP_ASSERT( item != NULL );
				DPDP_ASSERT( item->pickup_factory == first_item->pickup_factory );
				DPDP_ASSERT( item->delivery_factory == first_item->delivery_factory );

				p_entity->pickup_item_list.push_back( item );
				d_entity->delivery_item_list.insert( d_entity->delivery_item_list.begin(), item );

				allocated_items.insert( item->input_order_item->id );
			}

			solution.append( v, p_entity );
			solution.append( v, d_entity );
		}
	}

	/* dispatch unallocated orders to vehicles */
	const double capacity = probdata->getVehicle( 0 )->input_vehicle->capacity;

	std::map<std::string, DemoOrder> str_to_order;

	for( int i = probdata->getNumOngoingOrderItems(); i < probdata->getNumOrderItems(); ++i )
	{
		const OrderItem* item = probdata->getOrderItem( i );

		if( allocated_items.find( item->input_order_item->id ) != allocated_items.end() )
			continue;

		std::map<std::string, DemoOrder>::iterator find = str_to_order.find( item->input_order_item->order_id );

		if( find != str_to_order.end() )
		{
			find->second.addItem( item );
		}
		else
		{
			DemoOrder new_order( item->input_order_item->order_id, capacity );
			new_order.addItem( item );
			str_to_order.insert( std::make_pair( new_order.id, new_order ) );
		}
	}

	int vehicle_id = 0;

	for( std::map<std::string, DemoOrder>::iterator it = str_to_order.begin(); it != str_to_order.end(); ++it )
	{
		for( std::vector< std::vector<const OrderItem*> >::iterator vit = it->second.items.begin(); vit != it->second.items.end(); ++vit )
		{
			if( vit->empty() )
				continue;

			const OrderItem* first_item = vit->front();

			RouteEntity* p_entity = new RouteEntity();
			RouteEntity* d_entity = new RouteEntity();
			p_entity->factory = first_item->pickup_factory;
			d_entity->factory = first_item->delivery_factory;
			
			for( std::vector<const OrderItem*>::iterator iit = vit->begin(); iit != vit->end(); ++iit )
			{
				DPDP_ASSERT( (*iit)->pickup_factory == first_item->pickup_factory );
				DPDP_ASSERT( (*iit)->delivery_factory == first_item->delivery_factory );

				p_entity->pickup_item_list.push_back( *iit );
				d_entity->delivery_item_list.insert( d_entity->delivery_item_list.begin(), *iit );
			}

			solution.append( vehicle_id, p_entity );
			solution.append( vehicle_id, d_entity );

			vehicle_id = (vehicle_id + 1) % probdata->getNumVehicles();
		}
	}

	/* write files */
	DPDP_CALL( writeDestinationFile( solution ) );
	DPDP_CALL( writeRouteFile( solution ) );

	return 0;
}

int DemoSolver::writeDestinationFile( const Solution& solution )
{
	FILE* file = NULL;
	char filebuffer[255];

	/* open file */
	file = fopen( OUTPUT_DESTINATION_FILE, "w" );

	if( NULL == file )
	{
		dpdpPrintfError( "could not open solution file \"%s\" for writing!\n", OUTPUT_DESTINATION_FILE );
		return ERROR_FILE_NOTFOUND;
	}

	fputs( "{\n", file ); // main object >>>

	for( int v = 0; v < probdata->getNumVehicles(); ++v )
	{
		if( solution.routes[v] != NULL )
		{
			snprintf( filebuffer, 255, "\"%s\":\n", probdata->getVehicle( v )->input_vehicle->id.c_str() );
			fputs( filebuffer, file );

			DPDP_CALL( writeRouteEntity( solution.routes[v], file ) );
		}
		else
		{
			snprintf( filebuffer, 255, "\"%s\": null", probdata->getVehicle( v )->input_vehicle->id.c_str() );
			fputs( filebuffer, file );
		}

		if( v < probdata->getNumVehicles() - 1 )
			fputs( ",\n", file );
		else
			fputs( "\n", file );
	}

	fputs( "}\n", file ); // <<< main object

	fclose( file );

	return 0;
}

int DemoSolver::writeRouteFile( const Solution& solution )
{
	FILE* file = NULL;
	char filebuffer[255];

	/* open file */
	file = fopen( OUTPUT_ROUTE_FILE, "w" );

	if( NULL == file )
	{
		dpdpPrintfError( "could not open solution file \"%s\" for writing!\n", OUTPUT_DESTINATION_FILE );
		return ERROR_FILE_NOTFOUND;
	}

	fputs( "{\n", file ); // main object >>>

	for( int v = 0; v < probdata->getNumVehicles(); ++v )
	{
		snprintf( filebuffer, 255, "\"%s\": [\n", probdata->getVehicle( v )->input_vehicle->id.c_str() );
		fputs( filebuffer, file );

		if( solution.routes[v] != NULL )
		{
			for( RouteEntity* entity = solution.routes[v]->succ; entity != NULL; entity = entity->succ )
			{
				DPDP_CALL( writeRouteEntity( entity, file ) );
				if( entity->succ != NULL )
					fputs( ",\n", file );
				else
					fputs( "\n", file );
			}
		}

		if( v < probdata->getNumVehicles() - 1 )
			fputs( "],\n", file );
		else
			fputs( "]\n", file );
	}

	fputs( "}\n", file ); // <<< main object

	fclose( file );

	return 0;
}

int DemoSolver::writeRouteEntity( const RouteEntity * entity, FILE * file )
{
	char filebuffer[255];

	fputs( "{\n", file ); // main object >>>

	snprintf( filebuffer, 255, "\"factory_id\": \"%s\",\n", entity->factory->inputfactory->id.c_str() );
	fputs( filebuffer, file );

	snprintf( filebuffer, 255, "\"lng\": %f,\n", entity->factory->inputfactory->longitude );
	fputs( filebuffer, file );

	snprintf( filebuffer, 255, "\"lat\": %f,\n", entity->factory->inputfactory->latitude );
	fputs( filebuffer, file );

	snprintf( filebuffer, 255, "\"arrive_time\": %d,\n", entity->arrive_time );
	fputs( filebuffer, file );

	snprintf( filebuffer, 255, "\"leave_time\": %d,\n", entity->leave_time );
	fputs( filebuffer, file );

	fputs( "\"pickup_item_list\": [\n", file );
	for( int i = 0; i < entity->pickup_item_list.size(); ++i )
	{
		snprintf( filebuffer, 255, "\"%s\"", entity->pickup_item_list[i]->input_order_item->id.c_str() );
		fputs( filebuffer, file );

		if( i < entity->pickup_item_list.size() - 1 )
			fputs( ",\n", file );
		else
			fputs( "\n", file );
	}
	fputs( "],\n", file );

	fputs( "\"delivery_item_list\": [\n", file );
	for( int i = 0; i < entity->delivery_item_list.size(); ++i )
	{
		snprintf( filebuffer, 255, "\"%s\"", entity->delivery_item_list[i]->input_order_item->id.c_str() );
		fputs( filebuffer, file );

		if( i < entity->delivery_item_list.size() - 1 )
			fputs( ",\n", file );
		else
			fputs( "\n", file );
	}
	fputs( "]\n", file );

	fputs( "}\n", file ); // <<< main object

	return 0;
}
