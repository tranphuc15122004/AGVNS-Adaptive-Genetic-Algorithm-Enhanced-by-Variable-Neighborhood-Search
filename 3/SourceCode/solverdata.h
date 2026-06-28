#pragma once
#include "dpdp.h"
#include "probdata_aux.h"

#include <list>
#include <vector>
#include <ostream>
#include <iostream>


/// <summary>
/// Order items are grouped into packages by local search.
/// Total demand of contained items should not exceed the uniform vehicle capacity!
/// </summary>
class Package
{
public:
	const Order* original_order;
	int id;
	/* pickup_dest == true if and only if the package is picked up at the "destianation factory" in the input*/
	bool pickup_dest;
private:
	std::list<const OrderItem*> items; // list of order items in LOADING order
	double total_demand;               // total demand of items

public:
	Package() : original_order( NULL ), id( -1 ), total_demand( .0 ), pickup_dest(false)
	{
	}

	void push_back( const OrderItem* item )
	{
		storeItem( item, false );
	}

	void push_front( const OrderItem* item )
	{
		storeItem( item, true );
	}

	void storeItem( const OrderItem* item, bool front )
	{
		DPDP_ASSERT_ABORT( item != NULL );

		if( NULL == original_order )
		{
			DPDP_ASSERT_ABORT( items.empty() );

			original_order = item->order;
		}
		else
		{
			DPDP_ASSERT_ABORT( !items.empty() );
			DPDP_ASSERT_ABORT( items.back()->order == item->order );
		}

		if( front )
			items.push_front( item );
		else
			items.push_back( item );

		total_demand += item->demand;
	}

	bool isSplitted() const
	{
		return false; // TODO
	}

	inline double getDemand() const
	{
		return total_demand;
	}

	const std::list<const OrderItem*>& getOrderItems() const
	{
		return items;
	}

	void printOrderItems(std::ostream& os) const
	{
		for (std::list<const OrderItem*>::const_iterator it = items.begin(); it != items.end(); ++it) {
			os << ' ' << (*it)->input_order_item->id;
		}
	}

	void printOrderItemsReversed(std::ostream& os) const
	{
		for (std::list<const OrderItem*>::const_reverse_iterator it = items.rbegin(); it != items.rend(); ++it) {
			os << ' ' << (*it)->input_order_item->id;
		}
	}
};

typedef const Package* cPtr;
typedef std::list<cPtr> PackageList;

struct LSNode
{
	const Factory* factory;                      // pointer to the factory
	std::list<const Package*> delivery_packages; // list of delivery packages in order of unloading
	std::list<const Package*> pickup_packages;   // list of pickup packages in order of loading
	int arrive_time;                             // arrive time
	int leave_time;                              // leave time

	LSNode() : factory( NULL ), arrive_time( 0 ), leave_time( 0 )
	{
	}
	LSNode(const LSNode &n) : factory(n.factory), arrive_time(n.arrive_time), leave_time(n.leave_time)
	{
		delivery_packages = n.delivery_packages;
		pickup_packages = n.pickup_packages;
	}

};

/// <summary>
/// Simple structure for routes.
/// NOTE : this structure is responsible to free all of its data!
/// </summary>
struct LSRoute
{
	std::vector<LSNode*> nodes;

	~LSRoute()
	{
		for( std::vector<LSNode*>::iterator it = nodes.begin(); it != nodes.end(); ++it )
			delete *it;
	}

	bool checkDuplicateNodes() const 
	{
		const Factory* f = NULL;
		for (std::vector<LSNode*>::const_iterator nit = nodes.begin(); nit != nodes.end(); ++nit)
		{
			const LSNode* n = *nit;
			if (f != NULL && n->factory == f) {
				return true;
			}
			f = n->factory;
		}
		return false;
	}

};

/// <summary>
/// Simple structure for solution.
/// NOTE : this structure is responsible to free all of its data!
/// </summary>
struct LSSolution
{
	std::vector<LSRoute*> routes;
	double value;

	LSSolution() : value( .0 )
	{
	}

	~LSSolution()
	{
		for( std::vector<LSRoute*>::iterator it = routes.begin(); it != routes.end(); ++it )
			delete *it;
	}
};

struct SchNode;

struct LSSending
{
	const Vehicle* sender_vehicle;
	SchNode* sender_node;
	const Vehicle* receiving_vehicle;
	std::list<const Package*> sending_list;
};

