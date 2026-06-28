#ifndef _DPDP_SOLVER_H_
#define _DPDP_SOLVER_H_

#include "dpdp.h"

#include "probdata.h"

#include <list>
#include <vector>

struct RouteEntity
{
	const Factory* factory;
	int arrive_time;
	int leave_time;
	std::vector<const OrderItem*> delivery_item_list;
	std::vector<const OrderItem*> pickup_item_list;

	RouteEntity* prev;
	RouteEntity* succ;

	RouteEntity() : factory( NULL ), arrive_time( 0 ), leave_time( 0 ), prev( NULL ), succ( NULL )
	{
		delivery_item_list.resize( 0 );
		pickup_item_list.resize( 0 );
	}
};

struct DemoOrder
{
	std::string id;
	double capacity;
	double curr_size;
	std::vector< std::vector<const OrderItem* > > items;

	DemoOrder( std::string _id, double _capacity ) : id( _id ), capacity( _capacity ), curr_size( 0 )
	{
		items.resize( 1 );
		items[0].resize( 0 );
	}

	void addItem( const OrderItem* item )
	{
		DPDP_ASSERT_ABORT( item != NULL );

		if( capacity < item->demand + curr_size )
		{
			items.push_back( std::vector<const OrderItem*>() );
			curr_size = 0;
		}

		items[items.size() - 1].push_back( item );
		curr_size += item->demand;
	}
};

struct Solution
{
	std::vector<RouteEntity*> routes;

	Solution( int num_vehicles )
	{
		routes.resize( num_vehicles );
		for( int v = 0; v < num_vehicles; ++v )
			routes[v] = NULL;
	}

	~Solution()
	{
		for( std::vector<RouteEntity*>::iterator it = routes.begin(); it != routes.end(); ++it )
		{
			RouteEntity* next_entity = NULL;

			for( RouteEntity* ent = *it; ent != NULL; ent = next_entity )
				delete ent;
		}
	}

	void append( int vehicle_id, RouteEntity* entity )
	{
		DPDP_ASSERT_ABORT( 0 <= vehicle_id && vehicle_id < routes.size() );
		DPDP_ASSERT_ABORT( entity != NULL );

		if( routes[vehicle_id] != NULL )
		{
			RouteEntity* after = NULL;
			for( after = routes[vehicle_id]; after->succ != NULL; after = after->succ );

			after->succ = entity;
			entity->prev = after;
		}
		else
		{
			routes[vehicle_id] = entity;
		}
	}
};

class DemoSolver
{
private:
	const ProbData* probdata;

public:
	DemoSolver();

public:
	int init( const ProbData* _probdata );
	int run();

private:
	int writeDestinationFile( const Solution& solution );
	int writeRouteFile( const Solution& solution );
	int writeRouteEntity( const RouteEntity* entity, FILE* file );
};

#endif
