#include "scheduler.h"

#include "config.h"

#include <assert.h>
#include <stack>
#include <cfloat>
#include <algorithm>

const char *node_type_to_string = "CDG";

constexpr int SCH_EVENT_ARRIVE = 0;
constexpr int SCH_EVENT_LEAVE  = 1;

typedef std::list< const Package* > PackageList;

bool  SchNode::verify_total_pickup_and_delivery() const
{
	return std::abs(pickup_qty - sum_demand(pickup_packages)) < DPDP_EPSILON &&std::abs( delivery_qty - sum_demand(delivery_packages)) < DPDP_EPSILON;
}
void SchRoute::insert( SchNode* after, SchNode* node )
{
	DPDP_ASSERT_ABORT( after != NULL || first == NULL );

	++len;

	if( after != NULL )
	{
		node->prev = after;
		node->succ = after->succ;
		after->succ = node;
		if( node->succ )
			node->succ->prev = node;
		else
			last = node;
	}
	else
	{
		node->prev = NULL;
		node->succ = first;
		if( first )
			first->prev = node;
		else
			first = last = node;
	}
}

void SchRoute::remove( SchNode* node )
{
	--len;

	if( node == first )
	{
		first = node->succ;
		if( first )
			first->prev = NULL;
		else
			last = NULL;
	}
	else
	{
		node->prev->succ = node->succ;
		if( node->succ )
			node->succ->prev = node->prev;
		else
			last = node->prev;
	}

	node->prev = node->succ = NULL;
}

void SchRoute::push_back( SchNode* node )
{
	insert( last, node );
}

void SchRoute::clear()
{
	while( last )
	{
		SchNode* node = last;
		remove( last );
		delete node;
	}
}

SchRoute::~SchRoute()
{
	clear();
}

SchRoute* SchRoute::copy() const
{
	SchRoute* r = new SchRoute(carrying_packages, vehicle);
	for (SchNode* n = first; n; n = n->succ) {
		r->push_back(new SchNode(*n));
	}
	return r;
}

void SchRoute::move_to(SchRoute& route)
{
	route.clear();
	route.first = first;
	route.last = last;
	route.len = len;
	route.vehicle = vehicle;
	first = NULL;
	last = NULL;
	len = 0;
	vehicle = NULL;
}

Scheduler::Scheduler( const ProbData& _data, const std::vector<Package*>& _packages, const std::vector<LSNode*>& _destinations, const std::vector<std::list<const Package*>>& _carrying_packages )
	: data( _data ), allpackages(_packages), destinations( _destinations ), carrying_packages( _carrying_packages ), lateness_squared(false)
{
	routes.resize( data.getNumVehicles() );
	order_lateness = new int[data.getNumOrders()];
	number_of_dockings = new int[data.getNumFactories()];
	visitors = new std::set<int>[data.getNumFactories()];
	int id = 0;
	for( std::vector<SchRoute*>::iterator rit = routes.begin(); rit != routes.end(); ++rit, ++id ) {
		*rit = new SchRoute( carrying_packages[id], data.getVehicle( id));
	}

}

void Scheduler::printRoute(std::ostream& os, int vehicle_id, bool long_names) const
{
	const SchRoute * r = routes[vehicle_id];
	os << "V" << vehicle_id+1 << ": [\n";
	os << "carrying items: +" << SchNode::sum_demand(carrying_packages[vehicle_id]) <<" (";
	for (PackageList::const_iterator pit = carrying_packages[vehicle_id].begin(); pit != carrying_packages[vehicle_id].end(); ++pit) {
		if(long_names)
			(*pit)->printOrderItems(os);
		else
			os << ' ' << (*pit)->id;
	}
	os << ")" << std::endl;
	for (const SchNode* node = r->first; node != 0; node = node->succ) {
		os << "factory ";
		if (long_names)
			os << node->factory->inputfactory->id;
		else
			os << node->factory->id;
		os << " (" << node_type_to_string[node->node_type] << "), arrive = " << node->arrive_time << ", leave = " << node->leave_time << "\n";
		os << "\tpickup list: +" << SchNode::sum_demand(node->pickup_packages) << " (";
		for (std::list<const Package*>::const_iterator pit = node->pickup_packages.cbegin(); pit != node->pickup_packages.cend(); ++pit) {
			if (long_names)
				(*pit)->printOrderItems(os);
			else
				os << ' ' << (*pit)->id;
		}
		os << ")\n";
		os << "\tdelivery list: -" << SchNode::sum_demand(node->delivery_packages) << " (";
		for (std::list<const Package*>::const_iterator pit = node->delivery_packages.cbegin(); pit != node->delivery_packages.cend(); ++pit) {
			if (long_names)
				(*pit)->printOrderItems(os);
			else
				os << ' ' << (*pit)->id;
		}
		os << ")\n";
	}
	os << "]\n";

}

double Scheduler::calculateLevelAtNodeAfterLoading( const SchRoute* route, const SchNode* node ) const
{
	DPDP_ASSERT_ABORT( route != NULL );
	DPDP_ASSERT_ABORT( node != NULL );

	double level = .0;

	for( PackageList::const_iterator package_it = carrying_packages[route->vehicle->id].cbegin(); package_it != carrying_packages[route->vehicle->id].cend(); ++package_it )
		level += (*package_it)->getDemand();

	for( SchNode* curr_node = route->first; curr_node != NULL; curr_node = curr_node->succ )
	{
		level -= curr_node->delivery_qty;
		level += curr_node->pickup_qty;

		if( node == curr_node )
			return level;
	}

	DPDP_ASSERT_ABORT( false ); // node was not it route
	return level;
}

double Scheduler::evaluate( int* _order_lateness)
{
	const int num_orders = data.getNumOrders();
	const int num_factories = data.getNumFactories();
	bool external_orderlateness = (NULL != _order_lateness);
	int* order_lateness_ptr = (external_orderlateness ? _order_lateness : order_lateness);
	std::memset( order_lateness_ptr, 0, sizeof( int ) * num_orders );
	std::memset(number_of_dockings, 0, sizeof(int) * num_factories);
	double total_distance = .0;

	for (int f = 0; f < num_factories; ++f)
		visitors[f].clear();

	if( resources.size() != num_factories )
	{
		resources.resize(num_factories);

		int id = 0;
		for( std::vector<SchResource>::iterator rit = resources.begin(); rit != resources.end(); ++rit )
		{
			rit->cap = data.getFactory( id )->inputfactory->port_num;
			rit->id = id++;
		}
	}

	for( std::vector<SchResource>::iterator rit = resources.begin(); rit != resources.end(); ++rit )
		rit->clear();

	std::priority_queue<SchEvent*, std::vector<SchEvent*>, greater_time> pqueue;

	for( std::vector<SchRoute*>::iterator rit = routes.begin(); rit != routes.end(); ++rit )
	{
		SchRoute* route = *rit;
		if( !route->first )
			continue;

		const Vehicle* vehicle = route->vehicle;

		if( vehicle->update_time <= route->first->arrive_time )
			pqueue.push( new SchEvent( route->first->arrive_time, route->first, SCH_EVENT_ARRIVE ) );
		else
			resources[route->first->factory->id].add( route->first, 0, pqueue, true );

		for (SchNode* n = route->first; n; n = n->succ)
			n->duration = n->getLoadingTime() + n->getUnloadingTime() + DOCK_APPROACHING_TIME;

		if( lateness_squared )
		{
			for( SchNode* n = route->first; n != NULL; n = n->succ )
				visitors[n->factory->id].insert( vehicle->id );
		}
	}
	
	int total_waiting_time = 0;

	while( !pqueue.empty() )
	{
		SchEvent* ev = pqueue.top();
		pqueue.pop();
		switch( ev->event_type )
		{
			case SCH_EVENT_ARRIVE:
			{
				int duration = ev->node->duration;
				if( NULL != ev->node->prev && ev->node->factory == ev->node->prev->factory  )
					duration -= DOCK_APPROACHING_TIME;

				resources[ev->node->factory->id].add( ev->node, duration, pqueue, NULL == ev->node->prev );
				number_of_dockings[ev->node->factory->id]++;
			}
			break;
			case SCH_EVENT_LEAVE:
			{
				resources[ev->node->factory->id].remove( ev->node );
				ev->node->leave_time = ev->time;

				ev->node->waiting_time = std::max( 0, ev->time - ev->node->duration - ev->node->arrive_time );
				total_waiting_time += ev->node->waiting_time;

				if( ev->node->succ )
				{
					total_distance += data.getDistance( ev->node->factory, ev->node->succ->factory );

					if( ev->node->succ->node_type == GENERAL_NODE )
						ev->node->succ->arrive_time = ev->time + data.getTravelTime( ev->node->factory, ev->node->succ->factory );

					pqueue.push( new SchEvent( ev->node->succ->arrive_time, ev->node->succ, SCH_EVENT_ARRIVE ) );
				}

				//int comp_time = ev->time;
				int comp_time = ev->node->arrive_time;

				for( PackageList::const_reverse_iterator rit = ev->node->delivery_packages.rbegin(); rit != ev->node->delivery_packages.rend(); ++rit )
				{
					const Package* pack = *rit;
					if( comp_time > order_lateness_ptr[pack->original_order->id] )
						order_lateness_ptr[pack->original_order->id] = comp_time;
				}

			}
			break;
			default:
			DPDP_ASSERT_ABORT( false );
		}

		delete ev;
	}

	int total_lateness = 0;

	for( int ord = 0; ord < num_orders; ++ord )
	{
		order_lateness_ptr[ord] -= data.getOrder( ord )->completion_time;
		if( order_lateness_ptr[ord] > 0 ) {
			total_lateness += order_lateness_ptr[ord];
		}
	}

	double objval = ((double)CONFIG_LAMBDA / 3600.0) * (total_lateness) + (1 / (double)data.getNumVehicles()) * total_distance;

	if( lateness_squared )
	{
		int extra_visitors = 0;

		for( int factory_id = 0; factory_id < data.getNumFactories(); ++factory_id )
		{
			const Factory* factory = data.getFactory( factory_id );

			int temp = (int)visitors[factory_id].size() - (factory->inputfactory->port_num + 3); // TODO : ez csak egy otlet

			if( 0 < temp )
				extra_visitors += temp * temp;
		}

		objval += ((double)extra_visitors) * DOCK_APPROACHING_TIME * ((double)CONFIG_LAMBDA / 3600.0);
	}
	
	return objval;
}

bool Scheduler::add_package_with_test( const Package* package, int vehicle_id, SchNode* from_node, SchNode* to_node )
{
	from_node->pickup_packages.push_back(package);
	to_node->delivery_packages.push_front(package);
	
	int status = SCH_UNCHECKED_STATUS;
	if( !routes[vehicle_id]->verifyRoute( status ) )
	{
		from_node->pickup_packages.pop_back();
		to_node->delivery_packages.pop_front();

		return false;
	}
	pickup_nodes[package->id] = from_node;
	delivery_nodes[package->id] = to_node;
	from_node->pickup_qty += package->getDemand();
	to_node->delivery_qty += package->getDemand();
	return true;
}

bool Scheduler::find_factory_nodes(int vehicle_id, const Factory* from_f, const Factory* to_f, SchNode*& from_node, SchNode*& to_node, double& residual_capacity)
{
	SchRoute* r = routes[vehicle_id];
	const double capacity = data.getVehicle(vehicle_id)->capacity;
	residual_capacity = capacity - SchNode::sum_demand(r->carrying_packages);
	for (from_node = r->first; from_node; from_node = from_node->succ)
	{
		residual_capacity += (from_node->delivery_qty - from_node->pickup_qty);

		if (from_node->pickup_packages.empty()) continue;
		if (from_node->factory != from_f) continue;
		to_node = NULL;
		for (PackageList::iterator pit = from_node->pickup_packages.begin(); pit != from_node->pickup_packages.end(); ++pit)
		{
			if (to_node == delivery_nodes[(*pit)->id]) continue;
			to_node = delivery_nodes[(*pit)->id];
			DPDP_ASSERT_ABORT(to_node != NULL);
			if (to_node->factory == to_f)
			{
				double cap = residual_capacity, min_cap = residual_capacity;
				SchNode *node = NULL;
				for (node = from_node->succ; node && node != to_node; node = node->succ) {
					cap += node->delivery_qty - node->pickup_qty;
					if (cap < min_cap)
						min_cap = cap;
				}
				DPDP_ASSERT_ABORT(node == to_node);
				residual_capacity = min_cap;
				return true;
			}
		}
	}
	return false;
}

bool Scheduler::insert_package(const Package* package, int vehicle_id, SchNode* from_node, SchNode* to_node)
{
	SchRoute* r = routes[vehicle_id];
	int pos = 0;
	for (SchNode *n = r->first; n; n = n->succ) {
		n->pos = pos++;
	}
	const int pid = package->id;

	from_node->pickup_qty += package->getDemand();
	pickup_nodes[pid] = from_node;
	if (from_node->pickup_packages.empty())
	{
		from_node->pickup_packages.push_back(package);
	}
	else {
		PackageList::iterator pit;
		for (pit = from_node->pickup_packages.begin();
				pit != from_node->pickup_packages.end() && delivery_nodes[(*pit)->id]->pos > to_node->pos; ++pit);
		from_node->pickup_packages.insert(pit, package);
	}

	to_node->delivery_qty += package->getDemand();
	delivery_nodes[pid] = to_node;
	if (to_node->delivery_packages.empty())
	{
		to_node->delivery_packages.push_front(package);
	}
	else {
		PackageList::iterator pit;
		for (pit = to_node->delivery_packages.begin();
			pit != to_node->delivery_packages.end() && NULL != pickup_nodes[(*pit)->id] && pickup_nodes[(*pit)->id]->pos >= from_node->pos; ++pit);
		
		to_node->delivery_packages.insert(pit, package);
	}
	return true;
}

void Scheduler::insert_package( const Package* package, int vehicle_id, SchNode* after, SchNode*& from_node, SchNode*& to_node, bool& new_from_node, bool& new_to_node )
{
	insert_package( package, *routes[vehicle_id], after, from_node, to_node, new_from_node, new_to_node );
}

void Scheduler::insert_package( const Package* package, SchRoute& route, SchNode* after, SchNode*& from_node, SchNode*& to_node, bool& new_from_node, bool& new_to_node )
{
	DPDP_ASSERT_ABORT( after != NULL );

	new_from_node = package->original_order->pickup_factory != after->factory;

	if( new_from_node )
	{
		from_node = new SchNode( GENERAL_NODE, package->original_order->pickup_factory );
		route.insert( after, from_node );
	}
	else
		from_node = after;

	new_to_node = (from_node->succ == NULL || package->original_order->delivery_factory != from_node->succ->factory);
	
	if( new_to_node )
	{
		to_node = new SchNode( GENERAL_NODE, package->original_order->delivery_factory );
		route.insert( from_node, to_node );
	}
	else
		to_node = from_node->succ;

	pickup_nodes[package->id] = from_node;
	delivery_nodes[package->id] = to_node;
	from_node->add_pickup(package);
	to_node->add_delivery(package);
}

void Scheduler::insert_packages(std::list<const Package* >& _packages, SchRoute& route, SchNode* after, SchNode*& from_node, SchNode*& to_node, bool& new_from_node, bool& new_to_node)
{
	if (_packages.empty()) return;
	const int len = (int)_packages.size();
	const Package* package = _packages.front();
	std::list<const Package*>::iterator pit = _packages.begin();
	insert_package(package, route, after, from_node, to_node, new_from_node, new_to_node);

	for (++pit; pit != _packages.end(); ++pit) {
		bool _new_from, _new_to;
		SchNode* _from_node, * _to_node;
		insert_package(*pit, route, from_node, _from_node, _to_node, _new_from, _new_to);
		DPDP_ASSERT_ABORT(_from_node == from_node && _to_node == to_node);
	}
}


bool Scheduler::evaluate_insert( const Package* package, int vehicle_id, SchNode* after, double &value )
{
	bool new_from_node;
	bool new_to_node;
	SchNode* from_node = NULL;
	SchNode* to_node = NULL;
	SchRoute& route = *routes[vehicle_id];
	value = DBL_MAX;

	SchNode* orig_pickup = pickup_nodes[package->id];
	SchNode* orig_delivery = delivery_nodes[package->id];
	insert_package( package, route, after, from_node, to_node, new_from_node, new_to_node );

	int status = SCH_UNCHECKED_STATUS;
	route.verifyRoute(status );

	if( status == SCH_VALID_ROUTE )
		value = evaluate();

	if( new_from_node )
	{
		route.remove( from_node );
		delete from_node;
	}
	else {
		from_node->remove_last_pickup();
	}

	if( new_to_node )
	{
		route.remove( to_node );
		delete to_node;
	}
	else {
		to_node->remove_first_delivery();
	}
	pickup_nodes[package->id] = orig_pickup;
	delivery_nodes[package->id] = orig_delivery;
	return status == SCH_VALID_ROUTE;
}


bool Scheduler::evaluate_insert( std::list<const Package*>& _packages, int vehicle_id, SchNode* after, double& value )
{
	bool new_from_node;
	bool new_to_node;
	SchNode* from_node = NULL;
	SchNode* to_node = NULL;
	SchRoute& route = *routes[vehicle_id];
	value = DBL_MAX;

	if( _packages.empty() ) return false;

	int len = (int)_packages.size();
	std::vector<SchNode*> orig_pickup, orig_delivery;
	orig_pickup.reserve(len);
	orig_delivery.reserve(len);
	const Package* package = _packages.front();
	std::list<const Package*>::iterator pit = _packages.begin();
	orig_pickup.push_back(pickup_nodes[package->id]);
	orig_delivery.push_back(delivery_nodes[package->id]);
	insert_package(package, route, after, from_node, to_node, new_from_node, new_to_node);
	for( ++pit; pit != _packages.end(); ++pit ) {
		bool _new_from, _new_to;
		SchNode* _from_node, *_to_node;
		package = *pit;
		orig_pickup.push_back(pickup_nodes[package->id]);
		orig_delivery.push_back(delivery_nodes[package->id]);
		insert_package( package, route, from_node, _from_node, _to_node, _new_from, _new_to );
		DPDP_ASSERT_ABORT( _from_node == from_node && _to_node == to_node );
	}

	int status = SCH_UNCHECKED_STATUS;
	if( route.verifyRoute( status ) )
		value = evaluate();

	if( new_from_node )
	{
		route.remove( from_node );
		delete from_node;
	}
	else
	{
		for( int i = 0; i < len; ++i ) {
			from_node->remove_last_pickup();
		}
	}

	if( new_to_node )
	{
		route.remove( to_node );
		delete to_node;
	}
	else
	{
		for( int i = 0; i < len; ++i ) {
			to_node->remove_first_delivery();
		}
	}
	int i = 0;
	for (PackageList::iterator pit = _packages.begin(); pit != _packages.end(); ++pit) {
		int pid = (*pit)->id;
		pickup_nodes[pid] = orig_pickup[i];
		delivery_nodes[pid] = orig_delivery[i];
		++i;
	}
	return status == SCH_VALID_ROUTE;
}

Scheduler::~Scheduler()
{
	for (std::vector<SchRoute*>::iterator rit = routes.begin(); rit != routes.end(); ++rit)
		delete* rit;
	delete[] number_of_dockings;
	delete[] visitors;
	delete[] order_lateness;
}

bool Scheduler::find_best_insert_pos( const Package* package, int vehicle_id, SchNode*& best_pos, double& best_value )
{
	double value;
	best_pos = NULL;
	best_value = std::numeric_limits<double>::max();

	SchRoute& route = *routes[vehicle_id];

	for( SchNode* after = route.first; after != NULL; after = after->succ )
	{
		if( !evaluate_insert( package, vehicle_id, after, value ) )
			continue;

		if( value >= 0 && value < best_value )
		{
			best_pos = after;
			best_value = value;
		}
	}

	return best_pos != NULL;
}

bool Scheduler::find_best_insert_pos(std::list<const Package*>& _packages, int vehicle_id, SchNode*& best_pos, double& best_value)
{
	double value;
	best_pos = NULL;
	best_value = std::numeric_limits<double>::max();

	SchRoute& route = *routes[vehicle_id];

	for (SchNode* after = route.first; after != NULL; after = after->succ)
	{
		if (!evaluate_insert(_packages, vehicle_id, after, value))
			continue;

		if (value >= 0 && value < best_value)
		{
			best_pos = after;
			best_value = value;
		}
	}

	return best_pos != NULL;
}

bool Scheduler::find_best_move( std::list<const Package*>& _packages, int from_vehicle_id, SchNode* from_node, int to_vehicle_id, SchNode*& best_pos, double& best_value )
{
	if( _packages.empty() )
		return false;

	double value;
	best_pos = NULL;
	best_value = std::numeric_limits<double>::max();

	const Factory* pickup_factory = _packages.front()->original_order->pickup_factory;
	const Factory* delivery_factory = _packages.front()->original_order->delivery_factory;
	for( PackageList::iterator pit = _packages.begin(); pit != _packages.end(); ++pit ) {
		if( (*pit)->original_order->pickup_factory != pickup_factory || (*pit)->original_order->delivery_factory != delivery_factory )
			return false;
	}
	SchRoute& from_route = *routes[from_vehicle_id];
	SchRoute& to_route = *routes[to_vehicle_id];

	std::vector<SchNode*> original_nodes;
	std::vector<PackageList> pickup_lists, delivery_lists;
	for( SchNode* n = from_route.first; n; n = n->succ )
	{
		original_nodes.push_back( n );
		pickup_lists.push_back( PackageList() );
		pickup_lists.back().splice( pickup_lists.back().begin(), n->pickup_packages );
		n->pickup_packages = pickup_lists.back();
		delivery_lists.push_back( PackageList() );
		delivery_lists.back().splice( delivery_lists.back().begin(), n->delivery_packages );
		n->delivery_packages = delivery_lists.back();
	}

	int success = true;
	if( !remove_packages( _packages, from_vehicle_id, false ) ) {
		success = false;
		goto TERMINATE;
	}

	for( SchNode* after = to_route.first; after != NULL; after = after->succ )
	{
		if( CURRENT_NODE == after->node_type ) continue;
		if( !evaluate_insert( _packages, to_vehicle_id, after, value ) )
			continue;

		if( value >= 0 && value < best_value )
		{
			best_pos = after;
			best_value = value;
		}
	}

TERMINATE:
	from_route.len = 0;
	from_route.first = from_route.last = NULL;
	for( int i = 0; i < original_nodes.size(); ++i ) {
		from_route.push_back( original_nodes[i] );
		original_nodes[i]->delivery_packages.clear();
		original_nodes[i]->delivery_packages.splice( original_nodes[i]->delivery_packages.begin(), delivery_lists[i] );
		original_nodes[i]->delivery_qty = SchNode::sum_demand( original_nodes[i]->delivery_packages );
		original_nodes[i]->pickup_packages.clear();
		original_nodes[i]->pickup_packages.splice( original_nodes[i]->pickup_packages.begin(), pickup_lists[i] );
		original_nodes[i]->pickup_qty = SchNode::sum_demand( original_nodes[i]->pickup_packages );
	}

	return success && best_pos != NULL;
}

bool Scheduler::remove_packages( std::list<const Package*>& packages_to_remove, int from_vehicle_id, bool final_remove )
{
	SchRoute *r = routes[from_vehicle_id];
	std::vector<std::list<const Package*> > packages_at_factories(data.getNumFactories());
	for (std::list<const Package*>::iterator pit = packages_to_remove.begin(); pit != packages_to_remove.end(); ++pit) {
		const Package* package = *pit;
		SchNode* from_node = pickup_nodes[package->id];
		SchNode* to_node = delivery_nodes[package->id];

		PackageList::iterator it = std::find(from_node->pickup_packages.begin(), from_node->pickup_packages.end(), package);
		if (it == from_node->pickup_packages.end()) abort();
		from_node->pickup_packages.erase(it);

		it = std::find(to_node->delivery_packages.begin(), to_node->delivery_packages.end(), package);
		if (it == to_node->delivery_packages.end()) abort();
		to_node->delivery_packages.erase(it);

		if (final_remove) {
			pickup_nodes[package->id] = NULL;
			delivery_nodes[package->id] = NULL;
		}
	}
	SchNode *succ_node;
	for (SchNode* n = r->first; n; n = succ_node) {
		succ_node = n->succ;
		if (n->node_type == CURRENT_NODE) continue;
		if (n->pickup_packages.empty() && n->delivery_packages.empty()) {
			if ( DESTINATION_NODE == n->node_type)
				return false;

			r->remove(n);
			if( final_remove )
				delete n;
		}
	}
	return true;
}

void Scheduler::move_packages( std::list<const Package*>& packages_to_move, int from_vehicle_id, SchNode* from_pos, int to_vehicle_id, SchNode* after_node )
{
	if (packages_to_move.empty()) return;
	DPDP_ASSERT_ABORT(remove_packages(packages_to_move, from_vehicle_id, true));
	PackageList::iterator pit = packages_to_move.begin();
	SchNode* pickup_node, * delivery_node;
	bool new_pickup_node, new_delivery_node;
	insert_package(*pit, to_vehicle_id, after_node, pickup_node, delivery_node, new_pickup_node, new_delivery_node);
	for (++pit; pit != packages_to_move.end(); ++pit) {
		insert_package(*pit, to_vehicle_id, pickup_node, pickup_node, delivery_node, new_pickup_node, new_delivery_node);
		DPDP_ASSERT_ABORT(!new_pickup_node && !new_delivery_node);
	}
}

void Scheduler::remove_all_packages(int vehicle_id, std::list<const Package*>& packages_to_process)
{
	SchRoute* route = routes[vehicle_id];
	for (SchNode* n = route->first; n; n = n->succ)
	{
		packages_to_process.splice(packages_to_process.end(), n->pickup_packages);
	}
	route->clear();
	init_vehicle_route(vehicle_id, false);
}

void Scheduler::remove_packages(int vehicle_id, std::list<const Package*>& packages_to_process )
{
	for (PackageList::iterator pit = packages_to_process.begin(); pit != packages_to_process.end(); ++pit)
	{
		const Package* package = *pit;
		const int pid = package->id;

		SchNode* &from_node = pickup_nodes[pid];
		SchNode* &to_node = delivery_nodes[pid];

		if (from_node != NULL) {
			PackageList::iterator it = std::find(from_node->pickup_packages.begin(), from_node->pickup_packages.end(), package);
			DPDP_ASSERT_ABORT(it != from_node->pickup_packages.end());
			from_node->pickup_qty -= package->getDemand();
			from_node->pickup_packages.erase(it);
			from_node = NULL;
		}
		if( to_node != NULL ){
			PackageList::iterator it = std::find(to_node->delivery_packages.begin(), to_node->delivery_packages.end(), package);
			DPDP_ASSERT_ABORT(it != to_node->delivery_packages.end());
			to_node->delivery_qty -= package->getDemand();
			to_node->delivery_packages.erase(it);
			to_node = NULL;
		}
	}
	SchNode* succ_node = NULL;
	for (SchNode* node = routes[vehicle_id]->first; node; node = succ_node)
	{
		succ_node = node->succ;
		if (CURRENT_NODE == node->node_type) continue;
		if (node->pickup_packages.empty() && node->delivery_packages.empty()) {
			if (DESTINATION_NODE == node->node_type) continue;
			routes[vehicle_id]->remove(node);

			delete node;
		}
	}
}

bool Scheduler::swap_successors(const int vi, SchNode* node, SchNode* succ1, SchNode* succ2)
{
	DPDP_ASSERT_ABORT(node != NULL &&  succ1 != NULL && succ2 != NULL);
	if (succ1 == succ2 || !succ1->pickup_packages.empty() || !succ2->pickup_packages.empty()) return false;
	PackageList sub[5];
	int pos = 0;
	SchRoute* r = routes[vi];
	for (SchNode* n = r->first; n; n = n->succ)
		n->pos = pos++;
	if (succ1->pos > succ2->pos) {
		SchNode* t = succ1;
		succ1 = succ2;
		succ2 = t;
	}

	for (PackageList::iterator pit = node->pickup_packages.begin(); pit != node->pickup_packages.end(); ++pit)
	{
		const Package* package = *pit;
		int pid = package->id;
		if( delivery_nodes[pid]->pos < succ1->pos )
		{
			sub[0].push_back(package);
		}
		else if (delivery_nodes[pid]->pos == succ1->pos)
		{
			sub[1].push_back(package);
		}
		else if (delivery_nodes[pid]->pos > succ1->pos && delivery_nodes[pid]->pos < succ2->pos) 
		{
			sub[2].push_back(package);
		}
		else if(delivery_nodes[pid]->pos == succ2->pos)
		{
			sub[3].push_back(package);
		}
		else
		{
			sub[4].push_back(package);
		}
	}

	if (sub[1].size() != succ1->delivery_packages.size() || sub[3].size() != succ2->delivery_packages.size())
		return false;
	SchNode* prev_s1 = succ1->prev;
	SchNode* succ_s2 = succ2->succ;
	r->remove(succ1);
	r->remove(succ2);
	r->insert(prev_s1, succ2);
	if (succ_s2 != NULL)
		r->insert(succ_s2->prev, succ1);
	else
		r->push_back(succ1);

	node->pickup_packages.clear();
	node->pickup_packages.splice(node->pickup_packages.end(), sub[4]);
	node->pickup_packages.splice(node->pickup_packages.end(), sub[1]);
	node->pickup_packages.splice(node->pickup_packages.end(), sub[2]);
	node->pickup_packages.splice(node->pickup_packages.end(), sub[3]);
	node->pickup_packages.splice(node->pickup_packages.end(), sub[0]);
//	int status;
//	DPDP_ASSERT_ABORT(r->verifyRoute(status));
	return true;
}

bool Scheduler::swap_predecessors(const int vi, SchNode* node, SchNode* pred1, SchNode* pred2)
{
	DPDP_ASSERT_ABORT(node != NULL && pred1 != NULL && pred2 != NULL);
	if (GENERAL_NODE != pred1->node_type || GENERAL_NODE != pred2->node_type) return false;
	if (pred1 == pred2 || !pred1->delivery_packages.empty() || !pred2->delivery_packages.empty()) return false;
	PackageList sub[5];
	int pos = 0;
	SchRoute* r = routes[vi];
	for (SchNode* n = r->last; n; n = n->prev)
		n->pos = pos++;
	if (pred1->pos > pred2->pos) {
		SchNode* t = pred1;
		pred1 = pred2;
		pred2 = t;
	}

	for (PackageList::iterator pit = node->delivery_packages.begin(); pit != node->delivery_packages.end(); ++pit)
	{
		const Package* package = *pit;
		int pid = package->id;
		if (NULL == pickup_nodes[pid])
		{
			sub[4].push_back(package);
		}
		else if (pickup_nodes[pid]->pos < pred1->pos)
		{
			sub[0].push_back(package);
		}
		else if (pickup_nodes[pid]->pos == pred1->pos)
		{
			sub[1].push_back(package);
		}
		else if (pickup_nodes[pid]->pos > pred1->pos && pickup_nodes[pid]->pos < pred2->pos)
		{
			sub[2].push_back(package);
		}
		else if (pickup_nodes[pid]->pos == pred2->pos)
		{
			sub[3].push_back(package);
		}
		else
		{
			sub[4].push_back(package);
		}
	}

	if (sub[1].size() != pred1->pickup_packages.size() || sub[3].size() != pred2->pickup_packages.size())
		return false;
	SchNode* succ_p1 = pred1->succ;
	SchNode* prev_p2 = pred2->prev;
	r->remove(pred1);
	r->remove(pred2);
	r->insert(prev_p2, pred1);
	r->insert(succ_p1->prev, pred2);

	node->delivery_packages.clear();
	node->delivery_packages.splice(node->delivery_packages.end(), sub[0]);
	node->delivery_packages.splice(node->delivery_packages.end(), sub[3]);
	node->delivery_packages.splice(node->delivery_packages.end(), sub[2]);
	node->delivery_packages.splice(node->delivery_packages.end(), sub[1]);
	node->delivery_packages.splice(node->delivery_packages.end(), sub[4]);
//	int status;
//	DPDP_ASSERT_ABORT(r->verifyRoute(status));
	return true;
}

struct Slot
{
	int vehicle_id;
	SchNode* pickup, * delivery;
	int arrive_time;
	PackageList packages;
	bool invalid;
	Slot(int _v, SchNode* _p, SchNode* _d, int _at)
		: vehicle_id(_v), pickup(_p), delivery(_d), arrive_time(_at), invalid(false)
	{

	}
};

typedef std::list<Slot> SlotList;

struct SlotSchedule
{
	SlotList slots;
	Scheduler& sch;
	SchNode** pickup_nodes;
	SchNode** delivery_nodes;
	SlotSchedule(Scheduler& _sch, SchNode** _pickup_nodes, SchNode** _delivery_nodes)
		: sch(_sch), pickup_nodes(_pickup_nodes), delivery_nodes(_delivery_nodes)
	{

	}
	void xchange(const Package* p1, PackageList &pickup_p1, PackageList& delivery_p1, const Package* p2, PackageList&  pickup_p2, PackageList& delivery_p2)
	{
		PackageList::iterator pick1, deli1, pick2, deli2;

		pick1 = std::find(pickup_p1.begin(), pickup_p1.end(), p1);
		deli1 = std::find(delivery_p1.begin(), delivery_p1.end(), p1);
		pick2 = std::find(pickup_p2.begin(), pickup_p2.end(), p2);
		deli2 = std::find(delivery_p2.begin(), delivery_p2.end(), p2);

		DPDP_ASSERT_ABORT(pick1 != pickup_p1.end());
		DPDP_ASSERT_ABORT(pick2 != pickup_p2.end());
		DPDP_ASSERT_ABORT(deli1 != delivery_p1.end());
		DPDP_ASSERT_ABORT(deli2 != delivery_p1.end());

		*pick1 = p2;
		*deli1 = p2;
		*pick2 = p1;
		*deli2 = p1;
	}
	double evaluate_swap(SlotList::iterator s1, const Package* p1, SlotList::iterator s2, const Package* p2)
	{
		//dpdpPrintfTrace("\t\tstarted evaluate swap\n");
		int status1, status2;
		double value = DBL_MAX;

		PackageList &pickup_p1 = pickup_nodes[p1->id]->pickup_packages;
		PackageList& delivery_p1 = delivery_nodes[p1->id]->delivery_packages;

		PackageList &pickup_p2 = pickup_nodes[p2->id]->pickup_packages;
		PackageList &delivery_p2 = delivery_nodes[p2->id]->delivery_packages;

		SchRoute * route1 = sch.getRoute(s1->vehicle_id);
		SchRoute * route2 = sch.getRoute(s2->vehicle_id);

		xchange(p1, pickup_p1, delivery_p1, p2, pickup_p2, delivery_p2);

		if (route1->verifyRoute(status1) && route2->verifyRoute(status2))
			value = sch.evaluate();

		xchange(p2, pickup_p1, delivery_p1, p1, pickup_p2, delivery_p2);
		return value;
	}
	void swap(SlotList::iterator s1, const Package* p1, SlotList::iterator s2, const Package* p2)
	{
		int status1, status2;
		double value = DBL_MAX;
		PackageList& pickup_p1 = pickup_nodes[p1->id]->pickup_packages;
		PackageList& pickup_p2 = pickup_nodes[p2->id]->pickup_packages;
		PackageList& delivery_p1 = delivery_nodes[p1->id]->delivery_packages;
		PackageList& delivery_p2 = delivery_nodes[p2->id]->delivery_packages;
		xchange(p1, pickup_p1, delivery_p1, p2, pickup_p2, delivery_p2);

		double diff = p1->getDemand() - p2->getDemand();
		pickup_nodes[p1->id]->pickup_qty -= diff;
		delivery_nodes[p1->id]->delivery_qty -= diff;
		pickup_nodes[p2->id]->pickup_qty += diff;
		delivery_nodes[p2->id]->delivery_qty += diff;

		pickup_nodes[p1->id] = s2->pickup;
		delivery_nodes[p1->id] = s2->delivery;
		pickup_nodes[p2->id] = s1->pickup;
		delivery_nodes[p2->id] = s1->delivery;


		s1->packages.remove(p1);
		s1->packages.push_back(p2);
		s2->packages.remove(p2);
		s2->packages.push_back(p1);

	}



	// TODO : dont use it! it may not give correct results
	double evaluate_move(SlotList::iterator from_slot, PackageList::iterator pit, SlotList::iterator to_slot)
	{
		//dpdpPrintfTrace("\t\tstarted evaluate move\n");

		const Package* package = *pit;
		PackageList pickup_p = pickup_nodes[package->id]->pickup_packages;
		PackageList delivery_p = delivery_nodes[package->id]->delivery_packages;
		SchRoute* from_route = sch.getRoute(from_slot->vehicle_id);
		std::vector<SchNode*> node_order;
		bool found_pickup_node = false, found_delivery_node = false;
		for (SchNode* n = from_route->first; n; n = n->succ)
		{
			node_order.push_back(n);
			if (n == pickup_nodes[package->id])
				found_pickup_node = true;
			if (n == delivery_nodes[package->id])
				found_delivery_node = true;
		}
		DPDP_ASSERT_ABORT(found_pickup_node && found_delivery_node);

		move_between_nodes(from_slot, package, to_slot,false);

		double value = DBL_MAX;
		int status;

		SchRoute *route = sch.getRoute(to_slot->vehicle_id);
		if (route -> verifyRoute(status))
			value = sch.evaluate();

		from_route->len = 0;
		from_route->first = from_route->last = NULL;
		for (std::vector<SchNode*>::iterator nit = node_order.begin(); nit != node_order.end(); ++nit)
			from_route->push_back(*nit);
		move_between_nodes(to_slot, package, from_slot, false);
		pickup_nodes[package->id]->pickup_packages = pickup_p;
		pickup_nodes[package->id]->pickup_qty = SchNode::sum_demand(pickup_p);
		delivery_nodes[package->id]->delivery_packages = delivery_p;
		delivery_nodes[package->id]->delivery_qty = SchNode::sum_demand(delivery_p);
		//dpdpPrintfTrace("\t\tfinished evaluate move\n");
		return value;
	}
	void move(SlotList::iterator from_slot, PackageList::iterator pit, SlotList::iterator to_slot)
	{
		const Package* package = *pit;

		from_slot->packages.erase(pit);
		to_slot->packages.push_back(package);
		
		move_between_nodes(from_slot, package, to_slot, true);
	}

	void move_between_nodes(SlotList::iterator from_slot, const Package* package, SlotList::iterator to_slot, bool delete_unlinked_nodes)
	{
		int pid = package->id;
		DPDP_ASSERT_ABORT(from_slot->pickup == pickup_nodes[pid]);
		DPDP_ASSERT_ABORT(from_slot->delivery == delivery_nodes[pid]);

		pickup_nodes[pid]->remove_pickup(package);
		delivery_nodes[pid]->remove_delivery(package);
		SchRoute* route = sch.getRoute(from_slot->vehicle_id);
		if (pickup_nodes[pid]->delivery_packages.empty() && pickup_nodes[pid]->pickup_packages.empty() && pickup_nodes[pid]->node_type != DESTINATION_NODE) {
			route->remove(pickup_nodes[pid]);
			if (delete_unlinked_nodes) {
				from_slot->invalid = true;
				from_slot->pickup = NULL;
				dpdpPrintfTrace("from slot invalid\n");
				delete pickup_nodes[pid];
			}
		}
		if (delivery_nodes[pid]->delivery_packages.empty() && delivery_nodes[pid]->pickup_packages.empty()) {
			route->remove(delivery_nodes[pid]);
			if (delete_unlinked_nodes) {
				from_slot->invalid = true;
				from_slot->delivery = NULL;
				dpdpPrintfTrace("from slot invalid\n");
				delete delivery_nodes[pid];
			}
		}
		pickup_nodes[pid] = to_slot->pickup;
		delivery_nodes[pid] = to_slot->delivery;

		pickup_nodes[pid]->add_pickup(package);
		delivery_nodes[pid]->add_delivery(package);
	}

};
static bool incr_arrive_time(const Slot& a, const Slot& b)
{
	return a.arrive_time < b.arrive_time;
}

void Scheduler::save(std::vector<SchRoute*>& best_route)
{
	for (int vehicle_id = 0; vehicle_id < data.getNumVehicles(); ++vehicle_id)
	{
		if (best_route[vehicle_id]) delete best_route[vehicle_id];

		best_route[vehicle_id] = routes[vehicle_id]->copy();
	}
}

void Scheduler::splitPackagesToDeliveryNodes(const PackageList& _packages, const PackageList::const_reverse_iterator& from, SchRoute& route, bool carried_items )
{
	for( PackageList::const_reverse_iterator package_it = from; package_it != _packages.crend(); ++package_it )
	{
		if( route.empty() || route.back()->factory != (*package_it)->original_order->delivery_factory )
		{
			route.push_back(new SchNode(GENERAL_NODE, (*package_it)->original_order->delivery_factory));
		}
		SchNode* last_node = route.back();
		last_node->delivery_packages.push_back( *package_it );
		last_node->delivery_qty += (*package_it)->getDemand();
		delivery_nodes[(*package_it)->id] = last_node;

		if (carried_items) {
			last_node->carried_items = true;
		}
	}
}

void Scheduler::init_vehicle_route(int vid, bool insert_pickups_at_destination_node )
{
	SchRoute& route = *routes[vid];
	const Vehicle* vehicle = data.getVehicle(vid);
	const LSNode* destination = destinations[vid];


	route.clear();

	if (destination != NULL)
	{
		DPDP_ASSERT_ABORT(vehicle->hasDestination());

		/* destination -> first fixed visit (current facility is not relevant) */
		SchNode* destination_node = new SchNode(DESTINATION_NODE, destination->factory);
		destination_node->arrive_time = destination->arrive_time;
		destination_node->leave_time = destination->leave_time;
		destination_node->carried_items = !destination->delivery_packages.empty();

		for (PackageList::const_iterator package_it = destination->delivery_packages.cbegin(); package_it != destination->delivery_packages.cend(); ++package_it) {
			destination_node->delivery_packages.push_back(*package_it);
			destination_node->delivery_qty += (*package_it)->getDemand();
			delivery_nodes[(*package_it)->id] = destination_node;
		}

		if (insert_pickups_at_destination_node)
		{
			for (PackageList::const_iterator package_it = destination->pickup_packages.cbegin(); package_it != destination->pickup_packages.cend(); ++package_it) {
				destination_node->pickup_packages.push_back(*package_it); // NOTE : pickup may be not set by local search
				destination_node->pickup_qty += (*package_it)->getDemand();
				pickup_nodes[(*package_it)->id] = destination_node;
			}
		}
		route.push_back(destination_node);

		/* loaded items at destination -> further fixed visits */
		if (!destination_node->pickup_packages.empty())
		{
			splitPackagesToDeliveryNodes(destination_node->pickup_packages, destination_node->pickup_packages.crbegin(), route, false);
		}

		/* carrying items -> further fixed visits */
		if (!carrying_packages[vid].empty())
		{
			/* do not consider carrying items unloaded at destination  */
			std::list<const Package*>::const_reverse_iterator load_package_it = carrying_packages[vid].crbegin();

			for (PackageList::const_iterator unload_package_it = destination->delivery_packages.cbegin(); unload_package_it != destination->delivery_packages.cend(); ++unload_package_it)
			{
				DPDP_ASSERT_ABORT(load_package_it != carrying_packages[vid].crend());
				DPDP_ASSERT_ABORT((*load_package_it) == (*unload_package_it)); // unloaded item equals to the carrying item

				++load_package_it;
			}

			/* split */
			splitPackagesToDeliveryNodes(carrying_packages[vid], load_package_it, route, true);
		}
	}
	else // vehicle has no destination
	{
		DPDP_ASSERT_ABORT(vehicle->hasCurrentFactory()); // vehicle is either in a factory or on the road to its destination
		DPDP_ASSERT_ABORT(vehicle->isEmpty());           // impossible to transport items without a destination

		/* destination -> first fixed visit */
		SchNode* current_node = new SchNode(CURRENT_NODE, vehicle->current_factory);
		current_node->arrive_time = vehicle->arrive_time;
		current_node->leave_time = vehicle->leave_time;

		route.push_back(current_node);
	}
}
void Scheduler::init_routes()
{
	pickup_nodes.resize(allpackages.size(), NULL);
	delivery_nodes.resize(allpackages.size(), NULL);
	for( int vid = 0; vid < routes.size(); ++vid )
	{
		init_vehicle_route(vid, true);
#ifdef DPDP_DEBUG
		const Vehicle* vehicle= data.getVehicle(vid);
		SchRoute& route = *routes[vid];
		int status;
		if( !route.verifyRoute(  status ) )
			std::cerr << vehicle->input_vehicle->id << " route is invalid, status = " << status << std::endl;

		if (!route.verify_pickup_and_delivery_quantities() )
			std::cerr << vehicle->input_vehicle->id << " route is invalid due to pickup or delivery qunatitiy mismatch"<< std::endl;
#endif
	}
}

void Scheduler::simplify_route(int vehicle_id)
{
	SchRoute* r = routes[vehicle_id];
	SchNode* next_node;
	for (SchNode* n = r->first; n; n = next_node)
	{
		next_node = n->succ;
		if (n->node_type != GENERAL_NODE) continue;
		if (n->pickup_packages.empty() && n->delivery_packages.empty())
		{
			r->remove(n);
			delete n;
		}
	}
}
struct package_pickup_order
{
	const SchNode** delivery_nodes;

	package_pickup_order(const SchNode** _delivery_nodes) : delivery_nodes(_delivery_nodes)
	{
	}

	bool operator() (const Package* a, const Package* b) const
	{
		return delivery_nodes[a->id]->pos > delivery_nodes[b->id]->pos ||
			(delivery_nodes[a->id]->pos == delivery_nodes[b->id]->pos && a->original_order->completion_time > b->original_order->completion_time);
	}
};

struct package_delivery_order
{
	const SchNode** pickup_nodes;
	const int* carrying_packages_order;
	package_delivery_order(const SchNode** _pickup_nodes, const int* _carrying_packages_order) : pickup_nodes(_pickup_nodes), carrying_packages_order(_carrying_packages_order)
	{
	}

	bool operator () (const Package* a, const Package* b) const
	{
		const SchNode* node_a = pickup_nodes[a->id];
		const SchNode* node_b = pickup_nodes[b->id];
		if (node_a && node_b) {
			return node_a->pos > node_b->pos ||
				(node_a->pos == node_b->pos && a->original_order->completion_time < b->original_order->completion_time);
		}
		else if (node_a && !node_b)
			return true; // carrying packsges must be after freshly picked-up packages
		else if (!node_a && node_b)
			return false;
		else { // delivery must be in reverse pickup order
			return carrying_packages_order[a->id] > carrying_packages_order[b->id];
		}
	}
};

static void reorder_pickup_and_delivery_lists(SchRoute& route, std::vector<SchNode*>& nodes, const SchNode** pickup_nodes, const SchNode** delivery_nodes, const int* carrying_packages_order)
{
	int pos = 0;
	for (SchNode* node = route.first; node != NULL; node = node->succ)
		node->pos = pos++;

	package_pickup_order pick(delivery_nodes);
	package_delivery_order deli(pickup_nodes, carrying_packages_order);

	for (std::vector<SchNode*>::iterator sit = nodes.begin(); sit != nodes.end(); ++sit)
	{
		SchNode* n = *sit;

		n->pickup_packages.sort(pick);

		if (CURRENT_NODE != n->node_type)
			n->delivery_packages.sort(deli);
	}
}


bool SchRoute::verifyRoute( int& status ) const
{
	std::stack<const Package*> package_stack;
	double level = .0;

	status = SCH_VALID_ROUTE;
	for( PackageList::const_iterator package_it = carrying_packages.cbegin(); package_it != carrying_packages.cend(); ++package_it )
	{
		package_stack.push( *package_it );
		level += (*package_it)->getDemand();
	}

	for( SchNode* node = first; node; node = node->succ )
	{
		if (node->node_type != CURRENT_NODE && node->pickup_packages.empty() && node->delivery_packages.empty())
		{
			status = SCH_EMPTY_NODE;
			break;
		}
		for( PackageList::const_iterator pit = node->delivery_packages.cbegin(); pit != node->delivery_packages.cend(); ++pit )
		{
			const Package* package = *pit;

			if( package_stack.empty() || package_stack.top() != package )
			{
				status = SCH_BAD_PACKAGE_ORDER;
				return false;
			}

			level -= package->getDemand();

			package_stack.pop();
		}

		for( PackageList::const_iterator package_it = node->pickup_packages.cbegin(); package_it != node->pickup_packages.cend(); ++package_it )
		{
			const Package* package = (*package_it);

			level += package->getDemand();

			if( level > vehicle->capacity + 0.0001 ) {
				status = SCH_CAPACITY_VIOLATION;
				return false;
			}
			package_stack.push( package );
		}
	}

	return SCH_VALID_ROUTE == status;
}

bool SchRoute::verify_pickup_and_delivery_quantities() const
{
	for (SchNode* n = first; n; n = n->succ) {
		if (!n->verify_total_pickup_and_delivery()) return false;
	}
	return true;
}
/*
std::ostream& operator<<(std::ostream& os, const SchRoute& r)
{
	os << "[\n";
	for (const SchNode* node = r.first; node != 0; node = node->succ) {
		os << "factory = " << node->factory->id << ", arrive = " << node->arrive_time << ", leave = " << node->leave_time << "\n";
		os << "\tpickup list: [";
		for (std::list<const Package*>::const_iterator pit = node->pickup_packages.cbegin(); pit != node->pickup_packages.cend(); ++pit)
			(*pit)->printOrderItems(os);
		os << "]\n";
		os << "\tdelivery list: [";
		for (std::list<const Package*>::const_iterator pit = node->delivery_packages.cbegin(); pit != node->delivery_packages.cend(); ++pit)
			(*pit)->printOrderItemsReversed(os);
		os << "]\n";
	}
	os << "]\n";

	return os;
}
*/

void SchResource::add( SchNode* node, int duration, std::priority_queue<SchEvent*, std::vector<SchEvent*>, greater_time>& pqueue, bool force )
{
	if( force )
	{
		nodes.push_back( SchResourceSlot( node->arrive_time, node->leave_time, node ) );
		pqueue.push( new SchEvent( node->leave_time, node, SCH_EVENT_LEAVE ) );
		return;
	}

	if( nodes.size() < cap )
	{
		nodes.push_back( SchResourceSlot( node->arrive_time, node->arrive_time + duration, node ) );
		pqueue.push( new SchEvent( node->arrive_time + duration, node, SCH_EVENT_LEAVE ) );
	}
	else
	{
		int start_time = INT_MAX;

		std::list<SchResourceSlot>::reverse_iterator it = nodes.rbegin();
		for( int i = 0; i < cap; ++i, ++it )
		{
			if( it->end < start_time )
				start_time = it->end;
		}

		if( start_time < node->arrive_time )
			start_time = node->arrive_time;

		nodes.push_back( SchResourceSlot( start_time, start_time + duration, node ) );
		pqueue.push( new SchEvent( start_time + duration, node, SCH_EVENT_LEAVE ) );
	}
}

void SchResource::remove( SchNode* node )
{
	for( std::list<SchResourceSlot>::iterator it = nodes.begin(); it != nodes.end(); ++it )
	{
		if( it->node == node )
		{
			nodes.erase( it );
			break;
		}
	}
}
