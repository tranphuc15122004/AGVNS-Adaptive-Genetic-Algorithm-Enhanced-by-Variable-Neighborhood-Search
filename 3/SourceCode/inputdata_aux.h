#ifndef _DPDP_INPUTDATA_AUX_H_
#define _DPDP_INPUTDATA_AUX_H_

#include "dpdp.h"

#include <list>

#include "rapidjson/document.h"

struct InputOrderItem
{
	std::string id;
	std::string type;
	std::string order_id;
	double demand;
	std::string pickup_factory_id;
	std::string delivery_factory_id;
	double creation_time;
	double committed_completion_time;
	int load_time;
	int unload_time;
	int delivery_state;

	InputOrderItem() : id( "" ), type( "" ), order_id( "" ), demand( .0 ), pickup_factory_id( "" ), delivery_factory_id( "" ),
		creation_time( .0 ), committed_completion_time( .0 ), load_time( 0 ), unload_time( 0 ), delivery_state( 0 )
	{
	}

	static InputOrderItem parse( const rapidjson::Value& object )
	{
		DPDP_ASSERT_ABORT( object.HasMember( "id" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "type" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "order_id" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "demand" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "pickup_factory_id" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "delivery_factory_id" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "creation_time" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "committed_completion_time" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "load_time" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "unload_time" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "delivery_state" ) );

		InputOrderItem item;

		item.id = object["id"].GetString();
		item.type = object["type"].GetString();
		item.order_id = object["order_id"].GetString();
		item.demand = object["demand"].GetDouble();
		item.pickup_factory_id = object["pickup_factory_id"].GetString();
		item.delivery_factory_id = object["delivery_factory_id"].GetString();
		item.creation_time = object["creation_time"].GetDouble();
		item.committed_completion_time = object["committed_completion_time"].GetDouble();
		item.load_time = object["load_time"].GetInt();
		item.unload_time = object["unload_time"].GetInt();
		item.delivery_state = object["delivery_state"].GetInt();

		return item;
	}
};

struct InputNode
{
	std::string factory_id;
	std::list<std::string> delivery_item_list;
	std::list<std::string> pickup_item_list;
	double arrive_time;
	double leave_time;

	InputNode() : factory_id( "" ), arrive_time( .0 ), leave_time( .0 )
	{
	}

	static InputNode parse( const rapidjson::Value& object )
	{
		DPDP_ASSERT_ABORT( object.HasMember( "factory_id" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "delivery_item_list" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "pickup_item_list" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "arrive_time" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "leave_time" ) );

		InputNode node;

		node.factory_id = object["factory_id"].GetString();
		for( rapidjson::Value::ConstValueIterator it = object["delivery_item_list"].Begin(); it != object["delivery_item_list"].End(); ++it )
			node.delivery_item_list.push_back( it->GetString() );
		for( rapidjson::Value::ConstValueIterator it = object["pickup_item_list"].Begin(); it != object["pickup_item_list"].End(); ++it )
			node.pickup_item_list.push_back( it->GetString() );
		node.arrive_time = object["arrive_time"].GetDouble();
		node.leave_time = object["leave_time"].GetDouble();

		return node;
	}
};

struct InputVehicle
{
	std::string id;                        // id of vehicle
	int operation_time;                    // operation time of vehicle (unit: hours)
	int capacity;                          // capacity of vehicle (unit: standard pallets) TODO : double would be better !
	std::string gps_id;                    // id of GPS equipment
	double update_time;                    // update time of the current position and status of the vehicle (unit: unix timestamp)
	std::string cur_factory_id;            // the factory id where the vehicle is currently located or "" if the vehicle currently is not in any factory
	double arrive_time_at_current_factory; // the time when the vehicle arrives at the current factory (unit: unix timestamp)
	double leave_time_at_current_factory;  // the time when the vehicle leaves the current factory (unit: unix timestamp)
	std::list<std::string> carrying_items; // list of items loaded on the vehicle in the order of loading
	bool has_destination;                  // 
	InputNode destination;                 // current destination of the vehicle or null if the vehicle is parked

	InputVehicle() : id( "" ), capacity( 0 ), operation_time( 0 ), gps_id( "" ), update_time( .0 ), cur_factory_id( "" ), arrive_time_at_current_factory( .0 ), leave_time_at_current_factory( .0 ), has_destination( false )
	{
	}

	static InputVehicle parse( const rapidjson::Value& object )
	{
		DPDP_ASSERT_ABORT( object.HasMember( "id" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "operation_time" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "capacity" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "gps_id" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "update_time" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "cur_factory_id" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "arrive_time_at_current_factory" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "leave_time_at_current_factory" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "carrying_items" ) );
		DPDP_ASSERT_ABORT( object.HasMember( "destination" ) );

		InputVehicle vehicle;

		vehicle.id = object["id"].GetString();
		vehicle.operation_time = object["operation_time"].GetInt();
		vehicle.capacity = object["capacity"].GetInt();
		vehicle.gps_id = object["gps_id"].GetString();
		vehicle.update_time = object["update_time"].GetDouble();
		vehicle.cur_factory_id = object["cur_factory_id"].GetString();
		vehicle.arrive_time_at_current_factory = object["arrive_time_at_current_factory"].GetDouble();
		vehicle.leave_time_at_current_factory = object["leave_time_at_current_factory"].GetDouble();

		const rapidjson::Value& carrying_items = object["carrying_items"];
		for( rapidjson::Value::ConstValueIterator cit = carrying_items.Begin(); cit != carrying_items.End(); ++cit )
			vehicle.carrying_items.push_back( cit->GetString() );

		vehicle.has_destination = !object["destination"].IsNull();

		if( vehicle.has_destination )
			vehicle.destination = InputNode::parse( object["destination"] );

		return vehicle;
	}
};

struct InputMapEntity
{
	std::string route_code;       // id of route
	std::string start_factory_id; // start factory id of the route
	std::string end_factory_id;   // end factory id of the route
	double distance;              // distance of the route (unit: km)
	int time;                     // transportation time of the route (unit: seconds)

	InputMapEntity() : route_code( "" ), start_factory_id( "" ), end_factory_id( "" ), distance( .0 ), time( 0 )
	{
	}
};

struct InputFactory
{
	std::string id;   // id of factory
	double longitude; // longitude
	double latitude;  // latitude
	int port_num;     // the number of ports used for loading and unloading of vehicle cargoes

	InputFactory() : id( "" ), longitude( .0 ), latitude( .0 ), port_num( 0 )
	{
	}
};

#endif
