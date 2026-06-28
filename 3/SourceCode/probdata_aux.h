#ifndef _DPDP_PROBDATA_AUX_H_
#define _DPDP_PROBDATA_AUX_H_

#include "dpdp.h"

#include "inputdata_aux.h"

constexpr int ORDER_ITEM_TYPE_STANDARD = 0; // standard palett / palett
constexpr int ORDER_ITEM_TYPE_SMALL    = 1; // small palett / half palett
constexpr int ORDER_ITEM_TYPE_BOX      = 2; // box

constexpr int DELIVERY_STATE_INITALIZATION = 0; // initialization
constexpr int DELIVERY_STATE_GENERATED     = 1; // item is generated
constexpr int DELIVERY_STATE_LOADED        = 3; // item has been loaded
constexpr int DELIVERY_STATE_DELIVERED     = 4; // item is delivered

constexpr int ORDER_ITEM_STATUS_ONGOING     = 0; // ongoing
constexpr int ORDER_ITEM_STATUS_UNALLOCATED = 1; // unallocated

struct Factory;
struct Order;
struct OrderItem;
struct Node;
struct Vehicle;

struct Factory
{
	const InputFactory* inputfactory;

	int id; // short id

	Factory() : inputfactory( NULL ), id( -1 )
	{
	}
};

struct OrderItem
{
	const InputOrderItem* input_order_item;

	int id;                          // id of item
	const Order* order;              // pointer to the order to which it belongs
	int type;                        // pallet type : ORDER_ITEM_TYPE_STANDARD, ORDER_ITEM_TYPE_SMALL, ORDER_ITEM_TYPE_BOX
	double demand;                   // total standard pallet amount
	const Factory* pickup_factory;   // pointer to the pickup factory
	const Factory* delivery_factory; // pointer to the delivery factory
	int creation_time;               // creation time of the corresponding order (unit: seconds)
	int completion_time;             // committed completion time of the corresponding order (unit: seconds)
	int load_time;                   // loading time of item (unit: seconds)
	int unload_time;                 // unloading time of item (unit: seconds)
	int delivery_state;              // delivery state : DELIVERY_STATE_INITALIZATION, ..., DELIVERY_STATE_DELIVERED
	int status;                      // status : ORDER_ITEM_STATUS_ONGOING, ORDER_ITEM_STATUS_UNALLOCATED

	OrderItem() : input_order_item( NULL ), id( -1 ), order( NULL ), type( -1 ), demand( .0 ), pickup_factory( NULL ), delivery_factory( NULL ), creation_time( 0 ), completion_time( 0 ), load_time( 0 ), unload_time( 0 ), delivery_state( -1 ), status( -1 )
	{
	}

	inline bool isOngoing() const
	{
		return ORDER_ITEM_STATUS_ONGOING == status;
	}

	inline bool isUnallocated() const
	{
		return ORDER_ITEM_STATUS_UNALLOCATED == status;
	}
};

struct Order
{
	int id;

	std::string long_id;
	std::list<const OrderItem*> ongoing_items;
	std::list<const OrderItem*> unallocated_items;

	const Factory* pickup_factory;
	const Factory* delivery_factory;
	int creation_time;
	int completion_time;

	Order() : id( -1 ), long_id( "" ), pickup_factory( NULL ), delivery_factory( NULL ), creation_time( 0 ), completion_time( 0 )
	{
	}

	void storeItem( const OrderItem* item )
	{
		if( NULL == pickup_factory )
		{
			pickup_factory = item->pickup_factory;
			delivery_factory = item->delivery_factory;
			creation_time = item->creation_time;
			completion_time = item->completion_time;
		}
		else
		{
			DPDP_ASSERT_ABORT( item->pickup_factory == pickup_factory );
			DPDP_ASSERT_ABORT( item->delivery_factory == delivery_factory );
			DPDP_ASSERT_ABORT( item->creation_time == creation_time );
			DPDP_ASSERT_ABORT( item->completion_time == completion_time );
		}

		if( item->isOngoing() )
			ongoing_items.push_back( item );
		else if( item->isUnallocated() )
			unallocated_items.push_back( item );
		else
			DPDP_ASSERT_ABORT( false );
	}
};

struct Node
{
	const Factory* factory;                     // pointer to the factory
	std::list<const OrderItem*> delivery_items; // list of delivery items
	std::list<const OrderItem*> pickup_items;   // list of pickup items
	int arrive_time;                            // arrive time
	int leave_time;                             // leave time

	Node() : factory( NULL ), arrive_time( 0 ), leave_time( 0 )
	{
	}
};

struct Vehicle
{
	const InputVehicle* input_vehicle;

	int id;                                     // short ID
	double capacity;                            // capacity of the vehicle
	const Factory* current_factory;             // pointer the factory where the vehicle is currently located or NULL if the vehicle currently is not in any factory
	int update_time;                            // update time of the current position and status of the vehicle (unit: unix timestamp)
	int arrive_time;                            // the time when the vehicle arrives at the current factory (unit: unix timestamp)
	int leave_time;                             // the time when the vehicle leaves the current factory (unit: unix timestamp)
	std::list<const OrderItem*> carrying_items; // list of items loaded on the vehicle sorted in the order of loading
	Node* destination;                          // current destination of the vehicle or NULL if the vehicle is parked

	Vehicle() : input_vehicle( NULL ), id( -1 ), capacity( .0 ), current_factory( NULL ), update_time( 0 ), arrive_time( 0 ), leave_time( 0 ), destination( NULL )
	{
	}

	~Vehicle()
	{
		if( destination ) delete destination;
	}

	/// <summary>
	/// Returns whether vehicle is in a current factory.
	/// </summary>
	/// <returns>true if and only if current_factory != NULL</returns>
	inline bool hasCurrentFactory() const
	{
		return current_factory != NULL;
	}

	/// <summary>
	/// Returns whether vehicle has a destination.
	/// </summary>
	/// <returns>true if and only if destination != NULL</returns>
	inline bool hasDestination() const
	{
		return destination != NULL;
	}

	/// <summary>
	/// Returns whether vehicle is carrying items.
	/// </summary>
	/// <returns>true if and only if carrying items is not empty</returns>
	inline bool isLoaded() const
	{
		return !carrying_items.empty();
	}

	/// <summary>
	/// Returns whether vehicle is currently empty.
	/// </summary>
	/// <returns>true if and only if carrying items is empty</returns>
	inline bool isEmpty() const
	{
		return carrying_items.empty();
	}

	/// <summary>
	/// Returns whether the given amount of standard pallets does not violate capacity limit.
	/// </summary>
	/// <param name="demand">Demand (unit: standard pallets)</param>
	/// <returns>true if and only if demand does not exceed the capacity</returns>
	inline bool checkCapacity( const double demand ) const
	{
		return demand < capacity + DPDP_EPSILON;
	}
};

#endif
