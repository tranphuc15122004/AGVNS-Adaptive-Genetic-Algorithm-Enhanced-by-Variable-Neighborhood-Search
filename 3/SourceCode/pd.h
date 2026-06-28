#pragma once
#include "probdata.h"
#include "solverdata.h"
#include "scheduler.h"

constexpr int PDNODE_DUMMY_BEIGN = 0;
constexpr int PDNODE_DUMMY_END = 1;
constexpr int PDNODE_PICKUP   = 2;
constexpr int PDNODE_DELIVERY = 3;
constexpr int PDNODE_CI_DELIVERY = 4;  // delivery of carried item

struct PDNode
{
	cPtr package;
	PDNode* pickup_pair;
	PDNode* delivery_pair;
	PDNode* route_pred;
	PDNode* route_succ;
	SchNode* sch_node;
	const int node_type;
	PDNode(cPtr _pack, int _node_type)
		: package( _pack ), pickup_pair(NULL), delivery_pair(NULL),route_pred(NULL), route_succ(NULL), sch_node(NULL), node_type(_node_type)
	{

	}
	inline int get_node_type() const
	{
		return node_type;
	}
	inline bool pickup_node() const
	{
		return node_type == PDNODE_PICKUP;
	}
	inline bool delivery_node() const
	{
		return node_type == PDNODE_DELIVERY|| node_type == PDNODE_CI_DELIVERY;
	}
	inline bool dummy_begin_node() const
	{
		return node_type == PDNODE_DUMMY_BEIGN;
	}
	inline bool dummy_end_node() const
	{
		return node_type == PDNODE_DUMMY_END;
	}
	inline const Factory* getFactory() const
	{
		switch( node_type )
		{
			case PDNODE_PICKUP:
			return package->original_order->pickup_factory;
			case PDNODE_DELIVERY:
			case PDNODE_CI_DELIVERY:
			return package->original_order->delivery_factory;
			case PDNODE_DUMMY_BEIGN:
			case PDNODE_DUMMY_END:
			default:
			return NULL;
		}
	}
};

struct PDRoute
{
	int vehicle_id;
	PDNode* const begin, * const end;
	bool good_route;
	SchRoute* sch_route;
	double initial_residual_capacity;
	const Factory* first_pickup_factory;

	PDRoute();
	~PDRoute();

	void insert_node_before(PDNode* node, PDNode* before);
	void insert_node_after(PDNode* node, PDNode* after);
	void remove_node(PDNode* node);
	void insert_interval_after(PDNode* first, PDNode* last, PDNode* after);
	void remove_interval(PDNode* first, PDNode* last);
	void update_sch_route();
	inline void push_back(PDNode* node)
	{
		insert_node_before(node, end);
	}
	bool check_capacity() const;

};

typedef std::vector<PDRoute> PDRouteVect;

class PD
{
	const ProbData& data;
	std::vector<Package*>& packages;
	// pickup and delivery nodes of the packages
	PDNode** pickup_nodes, ** delivery_nodes;
	// vehicle_ids for the packages
	int* vehicle_ids;
	std::vector<SchRoute*> sch_routes;
	Scheduler &scheduler;

public:
	PDRouteVect routes;

	PD(const ProbData& _data, std::vector<Package*>& _packages, Scheduler& _scheduler);
	~PD();
	void move(cPtr _package, int to_vehicle_id, PDNode* pickup_after, PDNode* delivery_before);
	void move_interval(cPtr _package, int to_vehicle_id, PDNode* pickup_after);
	double evaluate();
	void import_schedule();
	void insert( cPtr _package, int to_vehicle_id, PDNode* pickup_after, PDNode* delivery_before );
	void insert_interval( PDNode *first, PDNode *last, int to_vehicle_id, PDNode* pickup_after );
	void remove(cPtr package );
	void remove_interval( PDNode *first, PDNode *last );

	void insert_two_intervals(PDNode* first1, PDNode* last1, PDNode* first2, PDNode* last2,  int to_vehicle_id, PDNode* pickup_after1, PDNode *delivery_before2);
	void remove_two_intervals(PDNode* first1, PDNode* last1, PDNode* first2, PDNode* last2);

	PDNode * get_first_insertion_point(int to_vehicle_id);

public:
	inline const PDRoute& getRoute( int vehicle_id ) const
	{
		return routes[vehicle_id];
	}

	inline PDNode* getPickupNode( const Package* package ) const
	{
		return pickup_nodes[package->id];
	}

	inline PDNode* getDeliveryNode( const Package* package ) const
	{
		return delivery_nodes[package->id];
	}

	inline int getVehicleID( const Package* package ) const
	{
		return vehicle_ids[package->id];
	}

	inline const Scheduler& getScheduler() const
	{
		return scheduler;
	}
};
