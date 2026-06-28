#ifndef _DPDP_PROBDATA_H_
#define _DPDP_PROBDATA_H_

#include "probdata_aux.h"

#include <map>
#include <list>

typedef std::map<std::string, int> StrToIntMap;

class InputData;

class ProbData
{
public:
	const InputData* inputdata;

private:
	Factory** factories;            // array of factory pointers
	int num_factories;              // number of factories
	int factories_size;             // size of array factories
	StrToIntMap factory_str_to_int; // factory map : long ID -> short ID

	Factory* createFactory( const InputFactory& inputfactory );
	void storeFactory( Factory* factory );
	int createFactories();

private:
	OrderItem** order_items;            // array of order item pointers
																			// ongoing items : order_items[0] .. order_items[num_ongoing_order_items-1]
																			// unallocated items : order_items[num_ongoing_order_items] .. order_items[num_order_items-1]
	int num_order_items;                // number of order items : num_order_items = num_ongoing_order_items + num_unallocated_order_items
	int num_ongoing_order_items;        // number of ongoing order items
	int num_unallocated_order_items;    // number of unallocated order items
	int order_items_size;               // size of array order_items
	StrToIntMap order_items_str_to_int; // order item map : long ID -> short ID

	OrderItem* createOrderItem( const InputOrderItem& input_item, const int status );
	void storeOrderItem( OrderItem* order_item );
	int createOrderItems();

private:
	Order** orders;               // array of orders
	int num_orders;               // number of orders
	int orders_size;              // size of array orders
	StrToIntMap order_str_to_int; // order map : long ID -> short ID

	Order* createOrder( std::string order_id );
	void storeOrder( Order* order );

private:
	Vehicle** vehicles;              // array of vehicles
	int num_vehicles;                // number of vehicles
	int vehicles_size;               // size of array vehicles
	StrToIntMap vehicles_str_to_int; // vehicle map : long ID -> short ID

	Vehicle* createVehicle( const InputVehicle& vehicle );
	void storeVehicle( Vehicle* vehicle );
	int createVehicles();

private:
	double** distance_mtx; // distance_mtx[a][b] : distance from factory a to factory b
	int** traveltime_mtx;  // traveltime_mtx[a][b] : travel time from factory a to factory b

	void allocateDistanceMtx();
	void allocateTraveltimeMtx();

	void setDistance( int start_factory, int end_factory, double value );
	void setTravelTime( int start_factory, int end_factory, int value );

	int createMtxsByRoutes();
	int createMtxsByRoutes( const char* route_info_filename );

public:
	ProbData();
	~ProbData();

public:
	int build( const InputData& _inputdata, const char* route_info_filename = NULL );

public:
	/// <summary>
	/// Returns the number of factories.
	/// </summary>
	/// <returns>Number of factories</returns>
	inline int getNumFactories() const
	{
		return num_factories;
	}

	/// <summary>
	/// Returns the factory with the given ID.
	/// </summary>
	/// <param name="factory_id">Short ID of the factory item to get</param>
	/// <returns></returns>
	inline const Factory* getFactory( int factory_id ) const
	{
		DPDP_ASSERT_ABORT( 0 <= factory_id && factory_id < num_factories );

		return factories[factory_id];
	}

	/// <summary>
	/// Returns the factory with the given ID.
	/// </summary>
	/// <param name="factory_id">Long ID of the factory item to get</param>
	/// <returns></returns>
	inline const Factory* getFactory( std::string factory_id ) const
	{
		const int short_id = getFactoryShortID( factory_id );

		return 0 <= short_id ? factories[short_id] : NULL;
	}


	/// <summary>
	/// Returns the short ID of the given factory.
	/// </summary>
	/// <param name="factory_id">String ID</param>
	/// <returns>Short ID (may be -1)</returns>
	inline int getFactoryShortID( const std::string factory_id ) const
	{
		StrToIntMap::const_iterator it = factory_str_to_int.find( factory_id );

		if( it != factory_str_to_int.cend() )
			return it->second;

		return -1;
	}

	/// <summary>
	/// Returns the number of (ongoing or allocated) order items.
	/// </summary>
	/// <returns></returns>
	inline int getNumOrderItems() const
	{
		return num_order_items;
	}

	/// <summary>
	/// Returns the number of ongoing order items.
	/// </summary>
	/// <returns></returns>
	inline int getNumOngoingOrderItems() const
	{
		return num_ongoing_order_items;
	}

	/// <summary>
	/// Returns the number of unallocated order items.
	/// </summary>
	/// <returns></returns>
	inline int getNumUnallocatedOrderItems() const
	{
		return num_unallocated_order_items;
	}

	/// <summary>
	/// Returns the order item with the given ID.
	/// </summary>
	/// <param name="order_item_id">Short ID of the order item to get</param>
	/// <returns></returns>
	inline const OrderItem* getOrderItem( int order_item_id ) const
	{
		DPDP_ASSERT_ABORT( 0 <= order_item_id && order_item_id < num_order_items );

		return order_items[order_item_id];
	}

	inline const OrderItem* getOngoingOrderItem( int order_item_id ) const
	{
		DPDP_ASSERT_ABORT( 0 <= order_item_id && order_item_id < num_ongoing_order_items );

		return order_items[order_item_id];
	}

	inline const OrderItem* getUnallocatedOrderItem( int order_item_id ) const
	{
		DPDP_ASSERT_ABORT( 0 <= order_item_id && order_item_id < num_unallocated_order_items );

		return order_items[order_item_id + num_ongoing_order_items];
	}

	/// <summary>
	/// Returns the order item with the given ID.
	/// </summary>
	/// <param name="order_item_id">Long ID of the order item to get</param>
	/// <returns></returns>
	inline const OrderItem* getOrderItem( std::string order_item_id ) const
	{
		const int short_id = getOrderItemShortID( order_item_id );

		return 0 <= short_id ? order_items[short_id] : NULL;
	}

	/// <summary>
	/// Returns the short ID of the given order item.
	/// </summary>
	/// <param name="order_item_id">String ID</param>
	/// <returns>Short ID (may be -1)</returns>
	inline int getOrderItemShortID( std::string order_item_id ) const
	{
		StrToIntMap::const_iterator it = order_items_str_to_int.find( order_item_id );

		if( it != order_items_str_to_int.cend() )
			return it->second;

		return -1;
	}

	/// <summary>
	/// Returns the short ID of the given order.
	/// </summary>
	/// <param name="order_item_id">String ID</param>
	/// <returns>Short ID (may be -1)</returns>
	inline int getOrderShortID( std::string order_id ) const
	{
		StrToIntMap::const_iterator it = order_str_to_int.find( order_id );

		if( it != order_str_to_int.cend() )
			return it->second;

		return -1;
	}

	/// <summary>
	/// Returns the order with the given ID.
	/// </summary>
	/// <param name="order_id">Long ID of the order to get.</param>
	/// <returns></returns>
	inline const Order* getOrder( std::string order_id ) const
	{
		const int short_id = getOrderShortID( order_id );

		return 0 <= short_id ? orders[short_id] : NULL;
	}

	/// <summary>
	/// Returns the order with the given ID.
	/// </summary>
	/// <param name="order_id">Short ID of the order to get.</param>
	/// <returns></returns>
	inline const Order* getOrder( int order_id ) const
	{
		DPDP_ASSERT_ABORT( 0 <= order_id && order_id < num_orders );

		return orders[order_id];
	}

	/// <summary>
	/// Returns the number of orders.
	/// </summary>
	/// <returns></returns>
	inline int getNumOrders() const
	{
		return num_orders;
	}

	/// <summary>
	/// Returns the number of vehicles.
	/// </summary>
	/// <returns></returns>
	inline int getNumVehicles() const
	{
		return num_vehicles;
	}

	/// <summary>
	/// Returns the vehicle with the given ID.
	/// </summary>
	/// <param name="vehicle_id">Short ID of the vehicle to get</param>
	/// <returns></returns>
	inline const Vehicle* getVehicle( int vehicle_id ) const
	{
		DPDP_ASSERT_ABORT( 0 <= vehicle_id && vehicle_id < num_vehicles );

		return vehicles[vehicle_id];
	}

	/// <summary>
	/// Returns the short ID of the given vehicle.
	/// </summary>
	/// <param name="order_item_id">String ID</param>
	/// <returns>Short ID (may be -1)</returns>
	inline int getVehicleShortID( std::string vehicle_id ) const
	{
		StrToIntMap::const_iterator it = vehicles_str_to_int.find( vehicle_id );

		if( it != vehicles_str_to_int.cend() )
			return it->second;

		return -1;
	}

public:
	/// <summary>
	/// Returns the distance between the given factories.
	/// </summary>
	/// <param name="start_factory">Start factory</param>
	/// <param name="end_factory">Destination factory</param>
	/// <returns>Distance between start and destination factories.</returns>
	double getDistance( int start_factory, int end_factory ) const
	{
		DPDP_ASSERT_ABORT( distance_mtx != NULL );
		DPDP_ASSERT_ABORT( 0 <= start_factory && start_factory < getNumFactories() );
		DPDP_ASSERT_ABORT( 0 <= end_factory && end_factory < getNumFactories() );

		return distance_mtx[start_factory][end_factory];
	}

	/// <summary>
	/// Returns the distance between the given factories.
	/// </summary>
	/// <param name="start_factory">Start factory</param>
	/// <param name="end_factory">Destination factory</param>
	/// <returns>Distance between start and destination factories.</returns>
	double getDistance( const Factory* start_factory, const Factory* end_factory ) const
	{
		DPDP_ASSERT_ABORT( start_factory != NULL );
		DPDP_ASSERT_ABORT( end_factory != NULL );

		return getDistance( start_factory->id, end_factory->id );
	}

	/// <summary>
	/// Returns the travel time between the given factories.
	/// </summary>
	/// <param name="start_factory">Start factory</param>
	/// <param name="end_factory">Destination factory</param>
	/// <returns>Travel time between start and destination factories.</returns>
	int getTravelTime( int start_factory, int end_factory ) const
	{
		DPDP_ASSERT_ABORT( traveltime_mtx != NULL );
		DPDP_ASSERT_ABORT( 0 <= start_factory && start_factory < getNumFactories() );
		DPDP_ASSERT_ABORT( 0 <= end_factory && end_factory < getNumFactories() );

		return traveltime_mtx[start_factory][end_factory];
	}

	/// <summary>
	/// Returns the travel time between the given factories.
	/// </summary>
	/// <param name="start_factory">Start factory</param>
	/// <param name="end_factory">Destination factory</param>
	/// <returns>Travel time between start and destination factories.</returns>
	int getTravelTime( const Factory* start_factory, const Factory* end_factory ) const
	{
		DPDP_ASSERT_ABORT( start_factory != NULL );
		DPDP_ASSERT_ABORT( end_factory != NULL );

		return getTravelTime( start_factory->id, end_factory->id );
	}

	int calculateLatestUpdateTime() const
	{
		int lastUpdateTime = -1;

		for( int vehicle_id = 0; vehicle_id < num_vehicles; ++vehicle_id )
		{
			if( lastUpdateTime < vehicles[vehicle_id]->update_time )
				lastUpdateTime = vehicles[vehicle_id]->update_time;
		}

		return lastUpdateTime;
	}

};

#endif
