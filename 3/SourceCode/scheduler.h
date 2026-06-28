#pragma once

#include "dpdp.h"
#include "probdata.h"
#include "solverdata.h"
#include "config.h"

#include <queue>
#include <list>
#include <set>

constexpr int SCH_UNCHECKED_STATUS = -1;
constexpr int SCH_VALID_ROUTE = 0;
constexpr int SCH_CAPACITY_VIOLATION = 1;
constexpr int SCH_BAD_PACKAGE_ORDER = 2;
constexpr int SCH_EMPTY_NODE = 3;

constexpr auto UNSPECIFIED_NODE = -1;
constexpr auto CURRENT_NODE = 0;
constexpr auto DESTINATION_NODE = 1;
constexpr auto GENERAL_NODE = 2;

extern const char *node_type_to_string;


struct SchNode
{

	const Factory* factory;                       // pointer to the factory
	std::list<const Package*> delivery_packages; // list of delivery packages in order of unloading
	std::list<const Package*> pickup_packages;   // list of pickup packages in order of loading
	int arrive_time;                              // arrive time
	int leave_time;                               // leave time
	int pos;									  // position in the route
	bool carried_items;
	int node_type;
	SchNode* prev;
	SchNode* succ;
	int duration;
	double pickup_qty;
	double delivery_qty;
	int waiting_time;

	void add_pickup(const Package* p)
	{
		pickup_packages.push_back(p);
		pickup_qty += p->getDemand();
	}
	void remove_pickup(const Package* p)
	{
		pickup_packages.remove(p);
		pickup_qty -= p->getDemand();
	}
	void remove_last_pickup()
	{
		const Package* pack = pickup_packages.back();
		pickup_qty -= pack->getDemand();
		pickup_packages.pop_back();
	}
	void add_delivery(const Package* p)
	{
		delivery_packages.push_front(p);
		delivery_qty += p->getDemand();
	}
	void append_delivery(const Package* p) // use with caution!!
	{
		delivery_packages.push_back(p);
		delivery_qty += p->getDemand();
	}
	void remove_delivery(const Package* p)
	{
		delivery_packages.remove(p);
		delivery_qty -= p->getDemand();
	}
	void remove_first_delivery()
	{
		const Package* pack = delivery_packages.front();
		delivery_qty -= pack->getDemand();
		delivery_packages.pop_front();
	}
	int getLoadingTime() const
	{
		double load = 0;
		for (std::list<const Package*>::const_iterator package_it = pickup_packages.cbegin(); package_it != pickup_packages.cend(); ++package_it)
			load += (*package_it)->getDemand();

		return getLoadingSeconds(load);
	}

	int getUnloadingTime() const
	{
		double unload = 0;
		for (std::list<const Package*>::const_iterator package_it = delivery_packages.cbegin(); package_it != delivery_packages.cend(); ++package_it)
			unload += (*package_it)->getDemand();

		return getUnloadingSeconds(unload);
	}

	SchNode( int _node_type, const Factory *_factory )
		: factory(_factory), arrive_time(0), leave_time(0), pos(-1), carried_items(false), node_type(_node_type), prev( NULL ), succ( NULL ), duration(0), pickup_qty(0), delivery_qty(0), waiting_time(0)
	{
	}

	SchNode(const SchNode& n)
		: prev(NULL), succ(NULL)
	{
		node_type = n.node_type;
		factory = n.factory;
		carried_items = n.carried_items;
		pickup_packages = n.pickup_packages;
		delivery_packages = n.delivery_packages;
		duration = n.duration;
		pickup_qty = n.pickup_qty;
		delivery_qty = n.delivery_qty;
		arrive_time = n.arrive_time;
		leave_time = n.leave_time;
		pos = n.pos;
		waiting_time = n.waiting_time;
	}

	static inline double sum_demand(const std::list<const Package*>& p)
	{
		double d = 0;
		for (std::list<const Package*>::const_iterator pit = p.cbegin(); pit != p.cend(); ++pit)
			d += (*pit)->getDemand();
		return d;
	}

	bool verify_total_pickup_and_delivery() const;
};

struct SchRoute
{
	const std::list<const Package*> & carrying_packages;
	const Vehicle *vehicle;
	SchNode* first;
	SchNode* last;
	int len;

	SchRoute(const std::list<const Package*> &_carrying_packages, const Vehicle *_vehicle ) 
		: carrying_packages(_carrying_packages), vehicle( _vehicle ), first( NULL ), last( NULL ), len( 0 )
	{
	}

	~SchRoute();

	void insert( SchNode* after, SchNode* node );

	void remove( SchNode* node );

	void push_back( SchNode* node );

	void clear();

	SchRoute* copy() const;

	void move_to(SchRoute& route);

	inline bool empty() const
	{
		return first == 0;
	}

	inline size_t size() const
	{
		return len;
	}

	inline SchNode* back() const
	{
		return last;
	}

	bool verifyRoute( int &status ) const;

	bool verify_pickup_and_delivery_quantities() const;

};

//std::ostream& operator << ( std::ostream&, const SchRoute& );

struct SchEvent
{
	int time;
	SchNode * node;
	int event_type;

	SchEvent( int _time, SchNode* _node, int _event_type ) : time( _time ), node( _node ), event_type( _event_type )
	{
	}
};

struct greater_time
{
	bool operator() ( const SchEvent* a, const SchEvent* b ) const
	{
		return a->time > b->time;
	}
};

struct SchResourceSlot
{
	int start;
	int end;
	SchNode* node;

	SchResourceSlot( int s, int e, SchNode* n ) : start( s ), end( e ), node( n )
	{
	}
};

class SchResource
{
private:
	std::list<SchResourceSlot> nodes;

public:
	int id;
	int cap;

	SchResource() : id( -1 ), cap( 0 )
	{
	}

	void add( SchNode* node, int duration, std::priority_queue<SchEvent*, std::vector<SchEvent*>, greater_time>& q, bool force = false );
	
	void remove( SchNode* node );
	
	void clear()
	{
		nodes.clear();
	}
};


class Scheduler
{
public:
	const ProbData& data;

private:
	std::vector<SchRoute*> routes;
	std::vector<SchResource> resources;
	const std::vector<LSNode*>& destinations;
	const std::vector<std::list<const Package*> >& carrying_packages;
	const std::vector<Package*>& allpackages;
	std::vector<SchNode*> pickup_nodes, delivery_nodes;
	int* order_lateness;
	std::set<int>* visitors;
	int* number_of_dockings;

	bool lateness_squared;

	void splitPackagesToDeliveryNodes( const std::list<const Package*>& packages, const std::list<const Package*>::const_reverse_iterator& from, SchRoute & route, bool carried_items );

	void insert_package( const Package* package, SchRoute &route, SchNode* after, SchNode*& from_node, SchNode*& to_node, bool &new_from_node, bool &new_to_node );

	bool evaluate_insert( const Package* packages, int vehicle_id, SchNode* after, double &value );

	bool evaluate_insert(std::list<const Package*>& packages, int vehicle_id, SchNode* after, double& value);
	bool remove_packages(std::list<const Package*>& packages, int from_vehicle_id, bool final_remove = false);
public:
	Scheduler( const ProbData& _data, const std::vector<Package*> &_packages, const std::vector< LSNode* >& _destinations, const std::vector< std::list<const Package*> >& _carrying_packages );

	~Scheduler();

	inline void use_squared_term(bool b)
	{
		lateness_squared = b;
	}
	void init_routes();
	void init_vehicle_route(int vehiccle_id, bool insert_pickups_at_destination_node);

	inline  SchRoute* getRoute( int vehicle_id ) 
	{
		return routes[vehicle_id];
	}

	// order_larenesses is a pointer to an array of data.getNumOrders() integers. May be NULL. 
	double evaluate( int* _order_latenesses = NULL);

	bool find_best_insert_pos( const Package* package, int vehicle_id, SchNode * & best_pos, double &best_value );

	bool find_best_insert_pos(std::list<const Package*> & _package, int vehicle_id, SchNode*& best_pos, double& best_value);

	bool find_best_move(std::list<const Package*>& packages_to_move, int from_vehicle_id, SchNode* from_pos, int to_vehicle_id, SchNode*& best_pos, double& best_value);

	void move_packages(std::list<const Package*>& packages_to_move, int from_vehicle_id, SchNode* from_pos, int to_vehicle_id, SchNode* to_pos);

	void insert_package( const Package* package, int vehicle_id, SchNode* after, SchNode*& from_node, SchNode*& to_node, bool& new_from_node, bool& new_to_node );

	void insert_packages(std::list<const Package* >& _packages, SchRoute& route, SchNode* after, SchNode*& from_node, SchNode*& to_node, bool& new_from_node, bool& new_to_node);

	bool add_package_with_test( const Package* package, int vehicle_id, SchNode* from_node, SchNode* to_node );

	bool find_factory_nodes(int vehicle_id, const Factory* from_f, const Factory* to_f, SchNode*& from_node, SchNode*& to_node, double& residual_capapcity);

	bool insert_package(const Package* package, int vehicle_id, SchNode* from_node, SchNode* to_node);

	void save(std::vector<SchRoute*>& best_routes);

	void remove_all_packages(int vehicle_id, std::list<const Package *>&packages_to_process);

	void remove_packages(int vehicle_id, std::list<const Package*>& packages_to_process);

	bool swap_successors(const int vehicle_id, SchNode* node, SchNode* succ1, SchNode *succ2);
	bool swap_predecessors(const int vehicle_id, SchNode* node, SchNode* pred1, SchNode* pred2);

	/* remove all nodes such that both the picup and the delivery lists are mepty */
	void simplify_route(int vehicle_id);

	inline int travel_time( const Package* package ) const
	{
		return data.getTravelTime( package->original_order->pickup_factory, package->original_order->delivery_factory );
	}

	inline SchNode* getPickupNode(const Package* package) const
	{
		return pickup_nodes[package->id];
	}
	inline SchNode* getDeliveryNode(const Package* package) const
	{
		return delivery_nodes[package->id];
	}

	void printRoute(std::ostream& os, int vehicle_id, bool original_items) const;

	double calculateLevelAtNodeAfterLoading( const SchRoute* route, const SchNode* node ) const;
};

