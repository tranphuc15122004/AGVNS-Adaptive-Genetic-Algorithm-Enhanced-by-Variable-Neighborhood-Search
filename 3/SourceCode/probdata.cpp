#include "probdata.h"

#include "config.h"
#include "dpdp.h"
#include "inputdata.h"

#include <fstream>
#include <sstream>

constexpr int ROUTEMAP_COLUMN_ROUTECODE = 0;
constexpr int ROUTEMAP_COLUMN_STARTID = 1;
constexpr int ROUTEMAP_COLUMN_ENDID = 2;
constexpr int ROUTEMAP_COLUMN_DISTANCE = 3;
constexpr int ROUTEMAP_COLUMN_TIME = 4;
constexpr int ROUTEMAP_COLUMN_END = 5;

constexpr int FACTORIES_INITIAL_SIZE = 256;
constexpr int ORDER_ITEMS_INITIAL_SIZE = 256;
constexpr int VEHICLES_INITIAL_SIZE = 256;
constexpr int ORDERS_INITIAL_SIZE = 32;

ProbData::ProbData() : inputdata( NULL ),
factories( NULL ), num_factories( 0 ), factories_size( 0 ),
order_items( NULL ), num_order_items( 0 ), num_ongoing_order_items( 0 ), num_unallocated_order_items( 0 ), order_items_size( 0 ),
orders( NULL ), num_orders( 0 ), orders_size( 0 ),
vehicles( NULL ), num_vehicles( 0 ), vehicles_size( 0 ),
distance_mtx( NULL ), traveltime_mtx( NULL )
{
}

ProbData::~ProbData()
{
	if( factories )
	{
		for( int f = 0; f < num_factories; ++f )
		{
			if( factories[f] )
				delete factories[f];
		}
		delete[] factories;
	}

	if( order_items )
	{
		for( int item_id = 0; item_id < num_order_items; ++item_id )
		{
			if( order_items[item_id] )
				delete order_items[item_id];
		}
		delete[] order_items;
	}

	if( orders )
	{
		for( int order_id = 0; order_id < num_orders; ++order_id )
		{
			if( orders[order_id] )
				delete orders[order_id];
		}
		delete[] orders;
	}

	if( vehicles )
	{
		for( int v = 0; v < num_vehicles; ++v )
		{
			if( vehicles[v] )
				delete vehicles[v];
		}
		delete[] vehicles;
	}

	if( distance_mtx )
	{
		for( int f = 0; f < getNumFactories(); ++f )
		{
			if( distance_mtx[f] )
				delete[] distance_mtx[f];
		}
		delete[] distance_mtx;
	}

	if( traveltime_mtx )
	{
		for( int f = 0; f < getNumFactories(); ++f )
		{
			if( traveltime_mtx[f] )
				delete[] traveltime_mtx[f];
		}
		delete[] traveltime_mtx;
	}
}

Factory* ProbData::createFactory( const InputFactory & inputfactory )
{
	Factory* factory = NULL;

	if( 0 <= getFactoryShortID( inputfactory.id ) )
		return NULL; // factory has been already created

	factory = new Factory();

	factory->inputfactory = &inputfactory;

	storeFactory( factory ); // sets ID

	return factory;
}

void ProbData::storeFactory( Factory * factory )
{
	DPDP_ASSERT_ABORT( factory != NULL );

	/* reacllocate memory, if needed */
	if( num_factories == factories_size )
	{
		factories_size *= 2;
		Factory** new_factories = new Factory * [factories_size];
		std::memset( new_factories, 0, factories_size * sizeof( Factory* ) );
		std::memcpy( new_factories, factories, num_factories * sizeof( Factory* ) );
		delete[] factories;
		factories = new_factories;
	}

	/* store order */
	factory->id = num_factories;
	factories[factory->id] = factory;
	++num_factories;

	factory_str_to_int.insert( std::make_pair( factory->inputfactory->id, factory->id ) );
}

int ProbData::createFactories()
{
	DPDP_ASSERT( 0 == num_factories );
	DPDP_ASSERT( NULL == factories );

	/* allocate memory */
	factories_size = FACTORIES_INITIAL_SIZE;
	factories = new Factory * [factories_size];
	std::memset( factories, 0, factories_size * sizeof( Factory* ) );

	///* collect relevant factories (used by orders) */
	//std::set<std::string> relevant_factories;

	//for( std::list<InputOrder>::const_iterator cit = inputdata->orders.cbegin(); cit != inputdata->orders.cend(); ++cit )
	//{
	//	relevant_factories.insert( cit->pickup_id );
	//	relevant_factories.insert( cit->delivery_id );
	//}

	/* create factories */
	for( std::list<InputFactory>::const_iterator cit = inputdata->factories.cbegin(); cit != inputdata->factories.cend(); ++cit )
	{
		//std::set<std::string>::iterator find = relevant_factories.find( cit->factory_id );

		//if( find == relevant_factories.end() )
		//	continue;

		createFactory( *cit );
	}

	return 0;
}

OrderItem* ProbData::createOrderItem( const InputOrderItem & input_item, const int status )
{
	OrderItem* item = NULL;

	if( 0 <= getOrderItemShortID( input_item.id ) )
		return NULL; // order item has been already created

	item = new OrderItem();

	item->input_order_item = &input_item;

	if( input_item.type.compare( "PALLET" ) != 0 )
		item->type = ORDER_ITEM_TYPE_STANDARD;
	else if( input_item.type.compare( "HALF_PALLET" ) != 0 )
		item->type = ORDER_ITEM_TYPE_SMALL;
	else if( input_item.type.compare( "BOX" ) != 0 )
		item->type = ORDER_ITEM_TYPE_BOX;
	else
	{
		dpdpPrintfError( "unexpected order item type: \"%s\"!\n", input_item.type.c_str() );
		goto TERMINATE_WITH_ERROR;
	}

	item->demand = input_item.demand;
	item->pickup_factory = getFactory( input_item.pickup_factory_id );
	item->delivery_factory = getFactory( input_item.delivery_factory_id );
	item->creation_time = (int)input_item.creation_time;
	item->completion_time = (int)input_item.committed_completion_time;
	item->load_time = (int)input_item.load_time;
	item->unload_time = (int)input_item.unload_time;
	item->delivery_state = input_item.delivery_state;
	item->status = status;

	if( NULL == item->pickup_factory )
	{
		dpdpPrintfError( "could not find pickup factory id \"%s\" of order \"%s\"!\n", input_item.pickup_factory_id.c_str(), input_item.order_id.c_str() );
		goto TERMINATE_WITH_ERROR;
	}

	if( NULL == item->delivery_factory )
	{
		dpdpPrintfError( "could not find delivery factory id \"%s\" of order \"%s\"!\n", input_item.delivery_factory_id.c_str(), input_item.order_id.c_str() );
		goto TERMINATE_WITH_ERROR;
	}

	storeOrderItem( item ); // sets ID

	return item;

TERMINATE_WITH_ERROR:
	if( item ) delete item;
	return NULL;
}

void ProbData::storeOrderItem( OrderItem * order_item )
{
	DPDP_ASSERT_ABORT( order_item != NULL );

	/* reacllocate memory, if needed */
	if( num_order_items == order_items_size )
	{
		order_items_size *= 2;
		OrderItem** new_items = new OrderItem * [order_items_size];
		std::memset( new_items, 0, order_items_size * sizeof( OrderItem* ) );
		std::memcpy( new_items, order_items, num_order_items * sizeof( OrderItem* ) );
		delete[] order_items;
		order_items = new_items;
	}

	/* store order item */
	order_item->id = num_order_items;
	order_items[order_item->id] = order_item;
	++num_order_items;

	order_items_str_to_int.insert( std::make_pair( order_item->input_order_item->id, order_item->id ) );
}

int ProbData::createOrderItems()
{
	DPDP_ASSERT( 0 == num_order_items );
	DPDP_ASSERT( NULL == order_items );
	DPDP_ASSERT( factories != NULL );

	/* allcoate memory */
	order_items_size = ORDER_ITEMS_INITIAL_SIZE;
	order_items = new OrderItem * [order_items_size];
	std::memset( order_items, 0, order_items_size * sizeof( OrderItem* ) );

	orders_size = ORDERS_INITIAL_SIZE;
	orders = new Order * [orders_size];
	std::memset( orders, 0, orders_size * sizeof( Order* ) );

	/* create order items (ongoing items) */
	num_ongoing_order_items = 0;

	for( std::list<InputOrderItem>::const_iterator cit = inputdata->ongoing_order_items.cbegin(); cit != inputdata->ongoing_order_items.cend(); ++cit )
	{
		OrderItem* item = createOrderItem( *cit, ORDER_ITEM_STATUS_ONGOING );

		if( NULL == item )
		{
			dpdpPrintfError( "could not create order items due to data inconsistency!\n" );
			return ERROR_DATA_GENERAL;
		}

		++num_ongoing_order_items;

		/* set order item <-> parent order links */
		Order* order = NULL;
		StrToIntMap::iterator it = order_str_to_int.find( item->input_order_item->order_id );

		if( it != order_str_to_int.cend() )
			order = orders[it->second];
		else
		{
			order = createOrder( item->input_order_item->order_id );
			storeOrder( order );
		}

		order->storeItem( item );
		item->order = order;
	}

	/* create order items (unallocated items) */
	num_unallocated_order_items = 0;

	for( std::list<InputOrderItem>::const_iterator cit = inputdata->unallocated_order_items.cbegin(); cit != inputdata->unallocated_order_items.cend(); ++cit )
	{
		OrderItem* item = createOrderItem( *cit, ORDER_ITEM_STATUS_UNALLOCATED );

		if( NULL == item )
		{
			dpdpPrintfError( "could not create order items due to data inconsistency!\n" );
			return ERROR_DATA_GENERAL;
		}

		++num_unallocated_order_items;

		/* set order item <-> parent order links */
		Order* order = NULL;
		StrToIntMap::iterator it = order_str_to_int.find( item->input_order_item->order_id );

		if( it != order_str_to_int.cend() )
			order = orders[it->second];
		else
		{
			order = createOrder( item->input_order_item->order_id );
			storeOrder( order );
		}

		order->storeItem( item );
		item->order = order;
	}

	return 0;
}

Order* ProbData::createOrder( std::string order_id )
{
	Order* order = new Order();
	order->long_id = order_id;

	return order;
}

void ProbData::storeOrder( Order * order )
{
	DPDP_ASSERT_ABORT( order != NULL );

	/* reacllocate memory, if needed */
	if( num_orders == orders_size )
	{
		orders_size *= 2;
		Order** new_orders = new Order * [orders_size];
		std::memset( new_orders, 0, orders_size * sizeof( OrderItem* ) );
		std::memcpy( new_orders, orders, num_orders * sizeof( OrderItem* ) );
		delete[] orders;
		orders = new_orders;
	}

	/* store order */
	order->id = num_orders;
	orders[order->id] = order;
	++num_orders;

	order_str_to_int.insert( std::make_pair( order->long_id, order->id ) );
}

Vehicle* ProbData::createVehicle( const InputVehicle & input_vehicle )
{
	Vehicle* vehicle = NULL;

	if( 0 <= getVehicleShortID( input_vehicle.id ) )
		return NULL; // vehicle has been already created

	vehicle = new Vehicle();

	vehicle->input_vehicle = &input_vehicle;
	vehicle->capacity = (double)input_vehicle.capacity;
	vehicle->current_factory = getFactory( input_vehicle.cur_factory_id );
	vehicle->update_time = (int)input_vehicle.update_time;
	vehicle->arrive_time = (int)input_vehicle.arrive_time_at_current_factory;
	vehicle->leave_time = (int)input_vehicle.leave_time_at_current_factory;
	for( std::list<std::string>::const_iterator cit = input_vehicle.carrying_items.cbegin(); cit != input_vehicle.carrying_items.cend(); ++cit )
		vehicle->carrying_items.push_back( getOrderItem( *cit ) );
	vehicle->destination = NULL;

	if( input_vehicle.has_destination )
	{
		vehicle->destination = new Node();
		vehicle->destination->factory = getFactory( input_vehicle.destination.factory_id );
		vehicle->destination->arrive_time = (int)input_vehicle.destination.arrive_time;
		vehicle->destination->leave_time = (int)input_vehicle.destination.leave_time;
		for( std::list<std::string>::const_iterator cit = input_vehicle.destination.pickup_item_list.cbegin(); cit != input_vehicle.destination.pickup_item_list.cend(); ++cit )
		{
			const OrderItem* item = getOrderItem( *cit );
			DPDP_ASSERT_ABORT( item != NULL );
			vehicle->destination->pickup_items.push_back( item );
		}
		for( std::list<std::string>::const_iterator cit = input_vehicle.destination.delivery_item_list.cbegin(); cit != input_vehicle.destination.delivery_item_list.cend(); ++cit )
		{
			const OrderItem* item = getOrderItem( *cit );
			DPDP_ASSERT_ABORT( item != NULL );
			vehicle->destination->delivery_items.push_back( item );
		}
	}

	storeVehicle( vehicle ); // sets ID

	return vehicle;
}

void ProbData::storeVehicle( Vehicle * vehicle )
{
	DPDP_ASSERT_ABORT( vehicle != NULL );

	/* reacllocate memory, if needed */
	if( num_vehicles == vehicles_size )
	{
		vehicles_size *= 2;
		Vehicle** new_vehicles = new Vehicle * [vehicles_size];
		std::memset( new_vehicles, 0, vehicles_size * sizeof( Vehicle* ) );
		std::memcpy( new_vehicles, vehicles, num_vehicles * sizeof( Vehicle* ) );
		delete[] vehicles;
		vehicles = new_vehicles;
	}

	/* store order */
	vehicle->id = num_vehicles;
	vehicles[vehicle->id] = vehicle;
	++num_vehicles;

	vehicles_str_to_int.insert( std::make_pair( vehicle->input_vehicle->id, vehicle->id ) );
}

int ProbData::createVehicles()
{
	DPDP_ASSERT( 0 == num_vehicles );
	DPDP_ASSERT( NULL == vehicles );

	/* allocate memory */
	vehicles_size = VEHICLES_INITIAL_SIZE;
	vehicles = new Vehicle * [vehicles_size];
	std::memset( vehicles, 0, vehicles_size * sizeof( Vehicle* ) );

	/* create vehicles */
	for( std::list<InputVehicle>::const_iterator cit = inputdata->vehicles.cbegin(); cit != inputdata->vehicles.cend(); ++cit )
	{
		createVehicle( *cit );
	}

	return 0;
}

void ProbData::allocateDistanceMtx()
{
	DPDP_ASSERT_ABORT( 0 < num_factories );
	DPDP_ASSERT_ABORT( NULL == distance_mtx );
	DPDP_ASSERT_ABORT( NULL == traveltime_mtx );

	distance_mtx = new double*[num_factories];

	for( int f = 0; f < num_factories; ++f )
	{
		distance_mtx[f] = new double[num_factories];

		for( int g = 0; g < num_factories; ++g )
			distance_mtx[f][g] = f != g ? DPDP_INFINITY_DBL : .0;
	}
}

void ProbData::allocateTraveltimeMtx()
{
	DPDP_ASSERT_ABORT( 0 < num_factories );
	DPDP_ASSERT_ABORT( NULL == traveltime_mtx );

	traveltime_mtx = new int*[num_factories];

	for( int f = 0; f < num_factories; ++f )
	{
		traveltime_mtx[f] = new int[num_factories];

		for( int g = 0; g < num_factories; ++g )
			traveltime_mtx[f][g] = f != g ? DPDP_INFINITY_INT : 0;
	}
}

void ProbData::setDistance( int start_factory, int end_factory, double value )
{
	DPDP_ASSERT_ABORT( distance_mtx != NULL );
	DPDP_ASSERT_ABORT( 0 <= start_factory && start_factory < getNumFactories() );
	DPDP_ASSERT_ABORT( 0 <= end_factory && end_factory < getNumFactories() );

	distance_mtx[start_factory][end_factory] = value;
}

void ProbData::setTravelTime( int start_factory, int end_factory, int value )
{
	DPDP_ASSERT_ABORT( traveltime_mtx != NULL );
	DPDP_ASSERT_ABORT( 0 <= start_factory && start_factory < getNumFactories() );
	DPDP_ASSERT_ABORT( 0 <= end_factory && end_factory < getNumFactories() );

	traveltime_mtx[start_factory][end_factory] = value;
}

int ProbData::createMtxsByRoutes()
{
	int start_id = -1;
	int end_id = -1;

	/* allocate memory */
	allocateDistanceMtx();
	allocateTraveltimeMtx();

	/* set vlaues in both matrices */
	for( std::list<InputMapEntity>::const_iterator cit = inputdata->mapentities.cbegin(); cit != inputdata->mapentities.cend(); ++cit )
	{
		start_id = getFactoryShortID( cit->start_factory_id );

		if( start_id < 0 )
		{
			dpdpPrintfError( "invalid short ID for factory\"%s\"!\n", cit->start_factory_id.c_str() );
			return ERROR_DATA_GENERAL;
		}

		end_id = getFactoryShortID( cit->end_factory_id );

		if( end_id < 0 )
		{
			dpdpPrintfError( "invalid short ID for factory\"%s\"!\n", cit->end_factory_id.c_str() );
			return ERROR_DATA_GENERAL;
		}

		setDistance( start_id, end_id, cit->distance );
		setTravelTime( start_id, end_id, cit->time );
	}

	return 0;
}

int ProbData::createMtxsByRoutes( const char * route_info_filename )
{
	/* allocate memory */
	allocateDistanceMtx();
	allocateTraveltimeMtx();

	/* reading */
	dpdpPrintfTrace( "start reading route map...\n" );

	std::string line;
	int num_entities = 0;

	/* open file */
	DPDP_ASSERT( route_info_filename != NULL );

	std::fstream fstr( route_info_filename );

	if( !fstr.good() )
	{
		dpdpPrintfError( "could not open file \"%s\"!\n", route_info_filename );
		return ERROR_FILE_NOTFOUND;
	}

	/* read header, if any */
	std::getline( fstr, line );

	/* read data */
	while( std::getline( fstr, line ) )
	{
		std::stringstream lstr( line );
		std::string field;

		int field_cntr = 0;

		/* split line */
		int start_factory_id = -1;
		int end_factory_id = -1;
		double distance = .0;
		int travel_time = 0;

		while( std::getline( lstr, field, ',' ) )
		{
			switch( field_cntr )
			{
				case ROUTEMAP_COLUMN_ROUTECODE:
				break;
				case ROUTEMAP_COLUMN_STARTID:
				start_factory_id = getFactoryShortID( field );
				break;
				case ROUTEMAP_COLUMN_ENDID:
				end_factory_id = getFactoryShortID( field );
				break;
				case ROUTEMAP_COLUMN_DISTANCE:
				distance = std::stod( field );
				break;
				case ROUTEMAP_COLUMN_TIME:
				travel_time = std::stoi( field );
				break;
				case ROUTEMAP_COLUMN_END:
				default:
				dpdpPrintfError( "too many columns in Route map!\n" );
				return ERROR_FILE_PARSE;
			}

			++field_cntr;
		}

		if( field_cntr != ROUTEMAP_COLUMN_END )
		{
			dpdpPrintfError( "too few columns in Route map!\n" );
			return ERROR_FILE_PARSE;
		}

		DPDP_ASSERT( 0 <= start_factory_id );
		DPDP_ASSERT( 0 <= end_factory_id );

		setDistance( start_factory_id, end_factory_id, distance );
		setTravelTime( start_factory_id, end_factory_id, travel_time );

		++num_entities;
	}

	dpdpPrintfTrace( "reading route map has been ended\n" );
	dpdpPrintfDebug( "%d map entities have been read\n", num_entities );

	return 0;
}

int ProbData::build( const InputData & _inputdata, const char* route_info_filename )
{
	dpdpPrintfTrace( "start building problem data...\n" );

	DPDP_ASSERT( NULL == inputdata );

	inputdata = &_inputdata;

	DPDP_CALL( createFactories() );
	DPDP_CALL( createOrderItems() );
	DPDP_CALL( createVehicles() );

	if( route_info_filename != NULL )
		DPDP_CALL( createMtxsByRoutes( route_info_filename ) );
	else
		DPDP_CALL( createMtxsByRoutes() );

	//DPDP_CALL( calculateLeastTimeTravels() );

	dpdpPrintfTrace( "building problem data has been ended\n" );

	return 0;
}
