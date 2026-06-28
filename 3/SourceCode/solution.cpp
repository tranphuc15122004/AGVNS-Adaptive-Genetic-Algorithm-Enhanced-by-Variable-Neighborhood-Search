//#include <vector>
//#include <algorithm>
//#include <set>
//#include <stack>
//#include <iostream>
//
//#include "config.h"

//Sequencer::Sequencer(const ProbData* _probdata, int _num_packages) : probdata(_probdata), num_packages(_num_packages),
//pickup_nodes(NULL), delivery_nodes(NULL)
//{
//	DPDP_ASSERT_ABORT(_probdata != NULL);
//	DPDP_ASSERT_ABORT(0 <= _num_packages);
//
//	pickup_nodes = new RouteNode * [num_packages];
//	std::memset(pickup_nodes, 0, num_packages * sizeof(RouteNode*));
//	delivery_nodes = new RouteNode * [num_packages];
//	std::memset(delivery_nodes, 0, num_packages * sizeof(RouteNode*));
//}
//
//struct package_pickup_order
//{
//	const Sequencer* sequencer;
//
//	package_pickup_order( const Sequencer* sequencer ) : sequencer( sequencer )
//	{
//	}
//
//	bool operator() (const Package* a, const Package *b) const
//	{
//		return sequencer->getDeliveryNode( a->id )->pos > sequencer->getDeliveryNode( b->id )->pos ||
//			(sequencer->getDeliveryNode(a->id)->pos == sequencer->getDeliveryNode(b->id)->pos && a->original_order->long_id < b->original_order->long_id);
//	}
//};
//
//struct package_delivery_order
//{
//	const Sequencer* sequencer;
//
//	package_delivery_order( const Sequencer* sequencer ) : sequencer( sequencer )
//	{
//	}
//
//	bool operator () (const Package* a, const Package *b) const
//	{
//		return sequencer->getPickupNode( a->id )->pos > sequencer->getPickupNode( b->id )->pos ||
//			(sequencer->getPickupNode(a->id)->pos == sequencer->getPickupNode(b->id)->pos && a->original_order->long_id > b->original_order->long_id);
//	}
//};
//
//bool Sequencer::toposort(std::vector<RouteNode*>& graph) const 
//{
//	std::list<RouteNode*> zerodeg_nodes;
//	for (std::vector<RouteNode*>::const_iterator nit = graph.begin(); nit != graph.end(); ++nit)
//		(*nit)->indeg = 0;
//	for (std::vector<RouteNode*>::const_iterator nit = graph.begin(); nit != graph.end(); ++nit) {
//		RouteNode* node = *nit;
//		for (std::set<RouteNode*>::iterator it = node->succ_nodes.begin(); it != node->succ_nodes.end(); ++it) {
//			(*it)->indeg++;
//		}
//	}
//	for (std::vector<RouteNode*>::const_iterator nit = graph.begin(); nit != graph.end(); ++nit) {
//		RouteNode* node = *nit;
//		if (!node->indeg) zerodeg_nodes.push_back(node);
//		node->pos = -1;
//	}
//	int p = 0;
//	while (!zerodeg_nodes.empty()) {
//		RouteNode* node = zerodeg_nodes.front();
//		zerodeg_nodes.pop_front();
//		node->pos = p++;
//		for (std::set<RouteNode*>::iterator it = node->succ_nodes.begin(); it != node->succ_nodes.end(); ++it) {
//			RouteNode* succ_node = *it;
//			succ_node->indeg--;
//			if( !(succ_node->indeg) ) zerodeg_nodes.push_back(succ_node);
//		}
//	}
//	for (std::vector<RouteNode*>::const_iterator nit = graph.begin(); nit != graph.end(); ++nit) {
//		if ((*nit)->pos < 0) return false;
//	}
//	return true;
//}
//
//SeqRoute* Sequencer::findBestRoute( const Vehicle* vehicle, const LSNode* destination, const std::list<const Package*>& carrying_packages, const std::list<const Package*>& sequenceable_packages, int &status )
//{
//	typedef std::list< const Package* > PackageList;
//	typedef std::list<const OrderItem*> ItemList;
//
//	DPDP_ASSERT_ABORT( vehicle != NULL );
//
//	SeqRoute* route_to_return = NULL;
//	const int first_pos = 1;
//	
//	std::vector<RouteNode*> factory_to_routenode(probdata->getNumFactories());
//	status = ROUTE_STATUS_UNDETERMINED;
//
//	for (std::vector<RouteNode*>::iterator it = factory_to_routenode.begin(); it != factory_to_routenode.end(); ++it)
//		*it = NULL;
//
//	/* Step 1 : future visits */
//	/* collect all factories that occur in pickup or delivery of OrderItems in movable_items */
//	std::vector<RouteNode*> future_visits;
//	for (PackageList::const_iterator package_it = sequenceable_packages.begin(); package_it != sequenceable_packages.end(); ++package_it)
//	{
//		const Package* pack = *package_it;
//		//assert(pack->id >= 0 && pack->id < num_packages);
//		const Factory* pickup_factory = pack->original_order->pickup_factory;
//		const Factory* delivery_factory = pack->original_order->delivery_factory;
//
//		RouteNode* pickup_node = factory_to_routenode[pickup_factory->id];
//		if (NULL == pickup_node)
//		{
//			pickup_node = new RouteNode();
//			pickup_node->factory = pickup_factory;
//			pickup_node->node_type = GENERAL_NODE;
//			factory_to_routenode[pickup_factory->id] = pickup_node;
//			future_visits.push_back(pickup_node);
//		}
//
//		pickup_node->pickup_packages.push_back(pack); // must be reordered before evaluation
//
//
//		RouteNode* delivery_node = factory_to_routenode[delivery_factory->id];
//		if (NULL == delivery_node)
//		{
//			delivery_node = new RouteNode();
//			delivery_node->factory = delivery_factory;
//			delivery_node->node_type = GENERAL_NODE;
//			factory_to_routenode[delivery_factory->id] = delivery_node;
//			future_visits.push_back(delivery_node);
//		}
//
//		delivery_node->delivery_packages.push_back(*package_it); // must be reordered before evaluation
//
//		pickup_nodes[pack->id] = pickup_node;
//		delivery_nodes[pack->id] = delivery_node;
//
//		pickup_node->succ_nodes.insert(delivery_node);
//	}
//	if (!toposort(future_visits))
//	{
//		for (std::vector<RouteNode*>::iterator it = future_visits.begin(); it != future_visits.end(); ++it)
//			delete* it;
//
//		status = ROUTE_STATUS_INFEASIBLE_CIRCULAR_SHIPMENT;
//		return NULL;
//	}
//
//	/* Step 2 : fixed visits */
//	std::vector<RouteNode*> fixed_visits;
//	if( destination != NULL )
//	{
//		DPDP_ASSERT_ABORT( vehicle->hasDestination() );
//
//		/* destination -> first fixed visit (current facility is not relevant) */
//		RouteNode* destination_node = new RouteNode();
//		destination_node->factory = destination->factory;
//		destination_node->arrive_time = destination->arrive_time;
//		destination_node->leave_time = destination->leave_time;
//		destination_node->node_type = DESTINATION_NODE;
//
//		for( PackageList::const_iterator package_it = destination->delivery_packages.cbegin(); package_it != destination->delivery_packages.cend(); ++package_it )
//			destination_node->delivery_packages.push_back( *package_it );
//
//		for( PackageList::const_iterator package_it = destination->pickup_packages.cbegin(); package_it != destination->pickup_packages.cend(); ++package_it )
//			destination_node->pickup_packages.push_back( *package_it ); // NOTE : pickup may be not set by local search
//
//		fixed_visits.push_back( destination_node );
//
//		/* loaded items at destination -> further fixed visits */
//		if( !destination_node->pickup_packages.empty() )
//		{
//			splitPackagesToDeliveryNodes( destination_node->pickup_packages, destination_node->pickup_packages.crbegin(), fixed_visits );
//		}
//
//		/* carrying items -> further fixed visits */
//		if( !carrying_packages.empty() )
//		{
//			/* do not consider carrying items unloaded at destination  */
//			std::list<const Package*>::const_reverse_iterator load_package_it = carrying_packages.crbegin();
//
//			for( PackageList::const_iterator unload_package_it = destination->delivery_packages.cbegin(); unload_package_it != destination->delivery_packages.cend(); ++unload_package_it )
//			{
//				DPDP_ASSERT_ABORT( load_package_it != carrying_packages.crend() );
//				DPDP_ASSERT_ABORT( (*load_package_it) == (*unload_package_it) ); // unloaded item equals to the carrying item
//
//				++load_package_it;
//			}
//
//			/* split */
//			splitPackagesToDeliveryNodes( carrying_packages, load_package_it, fixed_visits );
//		}
//	}
//	else // vehicle has no destination
//	{
//		DPDP_ASSERT_ABORT( vehicle->hasCurrentFactory() ); // vehicle is either in a factory or on the road to its destination
//		DPDP_ASSERT_ABORT( vehicle->isEmpty() );           // impossible to transport items without a destination
//
//		/* destination -> first fixed visit */
//		RouteNode* current_node = new RouteNode();
//		current_node->factory = vehicle->current_factory;
//		current_node->arrive_time = vehicle->arrive_time;
//		current_node->leave_time = vehicle->leave_time;
//		current_node->node_type = CURRENT_NODE;
//
//		fixed_visits.push_back( current_node );
//
//		// TODO : if the vehicle gets a route, this node must be ommited (first visiting node should be the destination)
//	}
//
//	for( std::vector<RouteNode*>::iterator it = fixed_visits.begin(); it != fixed_visits.end(); ++it )
//		(*it)->fixed_package_order = true;
//
//
//	const int route_length = future_visits.size() + fixed_visits.size();
//
//	RouteNode** route = new RouteNode * [route_length];
//
//	for( int i = 0; i < first_pos; ++i )
//		route[i] = fixed_visits[i];
//	for (int i = first_pos; i < route_length; ++i)
//		route[i] = NULL;
//
//	int *future_visits_perm = new int[future_visits.size()];
//
//	for( int k = 0; k < future_visits.size(); ++k )
//		future_visits_perm[k] = k;
//
//	// crossed[k] = the number of arcs from some node in 0..k to some node in k+1..future_visits.size()-1 in a permutation of future_visits.
//	int *crossed = new int[future_visits.size()];
//
//	// go through all permutations of future_visits_perm
//
//	do
//	{
//		// check feasibily of permuation
//		for( int k = 0; k < future_visits.size(); ++k )
//		{
//			route[k + first_pos] = future_visits[future_visits_perm[k]];
//			crossed[k] = 0;
//		}
//		bool bad_sequence = false;
//		for( int k = 0; !bad_sequence && k < future_visits.size(); ++k )
//		{
//			std::set<RouteNode*>& succ_nodes = route[k + first_pos]->succ_nodes;
//			//std::set<RouteNode*>& succ_nodes = successors[route[k + first_pos]];
//			//std::set<RouteNode*> &succ_nodes = successors[route[k + first_pos]->id];
//			for( std::set<RouteNode*>::iterator sit = succ_nodes.begin(); !bad_sequence && sit != succ_nodes.end(); ++sit ) {
//				bool found = false;
//				for( int l = k + 1; !found && l < future_visits.size(); ++l ) {
//					found = route[l + first_pos] == *sit;
//					++crossed[l - 1];
//				}
//				if( !found ) bad_sequence = true;
//			}
//		}
//		if( bad_sequence ) continue;
//		// create complete node order for future_visits combined with fixed_visits
//		// try to split future_visits into two disjoint parts
//		for( int m = 0; m <= future_visits.size(); ++m ) {
//			// check the sequence fixed_visits[0..first_pos-1],future_visits[0..m-1],fixed_visits[first_pos..fixed_visits.size()-1],future_visits[m..future_visits.size()-1]
//			if( m > 0 && crossed[m - 1] > 0 ) continue;
//			int pp = first_pos;
//			for( int k = 0; k < m; ++k )
//				route[pp++] = future_visits[future_visits_perm[k]];
//			for( int k = first_pos; k < fixed_visits.size(); ++k )
//				route[pp++] = fixed_visits[k];
//			for( int k = m; k < future_visits.size(); ++k )
//				route[pp++] = future_visits[future_visits_perm[k]];
//
//			// set route nodes' positions
//			for( int p = future_visits.size() + fixed_visits.size() - 1; p >= 0; --p )
//				route[p]->pos = p;
//
//			// reorder pickup and delivery lists
//			for( int p = future_visits.size() + fixed_visits.size() - 1; p >= 0; --p ) {
//				if( route[p]->fixed_package_order ) continue;
//				route[p]->pickup_packages.sort( package_pickup_order( this ) );
//				route[p]->delivery_packages.sort( package_delivery_order( this ) );
//			}
//
//			/* check feasibility of the route and update best route, if needed */
//			int route_status = ROUTE_STATUS_UNDETERMINED;
//			double route_value;
//			int retcode = evaluateRoute( vehicle,carrying_packages, route, route_length, route_status, route_value );
//			DPDP_ASSERT_ABORT( 0 == retcode );
//
//			if( ROUTE_STATUS_FEASIBLE == route_status )
//			{
//				if( NULL == route_to_return )
//				{
//					/* allocate route */
//					route_to_return = new SeqRoute();
//
//					/* store route */
//					route_to_return->estimated_value = route_value;
//					route_to_return->nodes.clear();
//					for( int node_seq = 0; node_seq < route_length; ++node_seq )
//						route_to_return->nodes.push_back( new RouteNode( *route[node_seq] ) ); // copy node!
//
//					//std::cerr << vehicle->input_vehicle->id << "\n";
//					//std::cerr << *route_to_return << std::endl;
//				}
//				else if( route_value < route_to_return->estimated_value )
//				{
//					/* free existing route */
//					for( std::list<RouteNode*>::iterator it = route_to_return->nodes.begin(); it != route_to_return->nodes.end(); ++it )
//						delete *it;
//
//					/* store route */
//					route_to_return->estimated_value = route_value;
//					route_to_return->nodes.clear();
//					for( int node_seq = 0; node_seq < route_length; ++node_seq )
//						route_to_return->nodes.push_back( new RouteNode( *route[node_seq] ) ); // copy node!
//
//					//std::cerr << vehicle->input_vehicle->id << "\n";
//					//std::cerr << *route_to_return << std::endl;
//				}
//			}
//		}
//	} while( std::next_permutation( future_visits_perm, future_visits_perm + future_visits.size() ) );
//
//	if (route_to_return != NULL)
//		status = ROUTE_STATUS_FEASIBLE;
//
//	/* free memory */
//	for (std::vector<RouteNode*>::iterator it = fixed_visits.begin(); it != fixed_visits.end(); ++it)
//		delete* it;
//	for (std::vector<RouteNode*>::iterator it = future_visits.begin(); it != future_visits.end(); ++it)
//		delete* it;
//
//	if( route ) delete[] route;
//	if( crossed ) delete[] crossed;
//	if( future_visits_perm ) delete[] future_visits_perm;
//
//	return route_to_return;
//}
//
//int Sequencer::evaluateRoute( const Vehicle* vehicle, const std::list<const Package*>& carrying_packages, RouteNode** route, const int route_length, int &status, double & route_value )
//{
//	typedef std::list<const Package*> PackageList;
//	typedef std::list<const OrderItem*> ItemList;
//	typedef std::map<const Order*, int> OrderIntMap;
//
//	DPDP_ASSERT( vehicle != NULL );
//	DPDP_ASSERT( route != NULL );
//	DPDP_ASSERT( 0 <= route_length );
//
//	int estimated_time = 0;            // estimated moment
//	double current_level = .0;         // currently loadad amount of items (unit : standard pallets)
//	OrderIntMap completion_times;      // Order -> completion time | TODO : split order-re nem valid...
//	const RouteNode* prev_node = NULL;
//	double total_distance = .0;
//	std::stack<const Package*> package_stack;
//
//	status = ROUTE_STATUS_UNDETERMINED;
//
//	/* initial status of the vehicle */
//	for( PackageList::const_iterator package_it = carrying_packages.cbegin(); package_it != carrying_packages.cend(); ++package_it )
//	{
//		current_level += (*package_it)->getDemand();
//		package_stack.push( *package_it );
//	}
//
//	if( !vehicle->checkCapacity( current_level ) )
//	{
//		status = ROUTE_STATUS_INFEASIBLE_CAPACITY;
//		return 0;
//	}
//
//	/* start time */
//	estimated_time = vehicle->update_time;
//
//	if( vehicle->hasCurrentFactory() )
//		estimated_time = vehicle->leave_time;
//
//	if( vehicle->hasDestination() )
//		estimated_time = vehicle->destination->arrive_time + DOCK_APPROACHING_TIME;
//
//	/* route */
//	for( int node_seq = 0; node_seq < route_length; ++node_seq )
//	{
//		RouteNode* curr_node = route[node_seq];
//
//		if( prev_node != NULL && prev_node != curr_node )
//		{
//			estimated_time += probdata->getTravelTime( prev_node->factory, curr_node->factory );
//			//estimated_time += probdata->getLeastTravelTime( prev_node->factory, curr_node->factory );
//			if( GENERAL_NODE == curr_node->node_type )
//				curr_node->arrive_time = estimated_time;
//			if(prev_node->factory !=  curr_node->factory )
//				estimated_time += DOCK_APPROACHING_TIME;
//			total_distance += probdata->getDistance( prev_node->factory, curr_node->factory );
//			//total_distance += probdata->getDistanceOfLeastTimeTravel( prev_node->factory, curr_node->factory );
//		}
//
//		/* unload items */
//		for( std::list<const Package*>::const_iterator package_it = curr_node->delivery_packages.cbegin(); package_it != curr_node->delivery_packages.cend(); ++package_it )
//		{
//			const Package* package = (*package_it);
//			const double demand = package->getDemand();
//
//			if( package_stack.empty() || package_stack.top() != package )
//			{
//				status = ROUTE_STATUS_INFEASIBLE_LIFO;
//				return 0;
//			}
//			package_stack.pop();
//
//			current_level -= demand;
//
//			/* set/update completion time */
//			estimated_time += getUnloadingSeconds( demand );
//
//			OrderIntMap::iterator find = completion_times.find( package->original_order );
//
//			if( completion_times.end() == find )
//				completion_times.insert( std::make_pair( package->original_order, estimated_time ) );
//			else
//				find->second = estimated_time;
//		}
//
//		/* load items */
//		for( std::list<const Package*>::const_iterator package_it = curr_node->pickup_packages.cbegin(); package_it != curr_node->pickup_packages.cend(); ++package_it )
//		{
//			const Package *package = (*package_it);
//			const double demand = package->getDemand();
//			
//			package_stack.push( package );
//
//			current_level += demand;
//
//			estimated_time += getLoadingSeconds( demand );
//		}
//
//		if (GENERAL_NODE == curr_node->node_type)
//			curr_node->leave_time = estimated_time;
//
//		if( !vehicle->checkCapacity( current_level ) )
//		{
//			status = ROUTE_STATUS_INFEASIBLE_CAPACITY;
//			return 0;
//		}
//
//		prev_node = curr_node;
//	}
//
//	if( !package_stack.empty() )
//	{
//		status = ROUTE_STATUS_INFEASIBLE_LIFO;
//		return 0;
//	}
//
//	/* calculate value (LAMBDA * total_lateness + total_distance) */
//
//	long total_lateness = 0;
//
//	for( OrderIntMap::const_iterator it = completion_times.cbegin(); it != completion_times.cend(); ++it )
//	{
//		if( it->second <= it->first->completion_time )
//			continue; // no lateness
//
//		total_lateness += it->second - it->first->completion_time;
//	}
//
//	route_value = ((double)CONFIG_LAMBDA/3600.0) * total_lateness
//		+ (1 / (double)probdata->getNumVehicles()) * total_distance;
//
//	status = ROUTE_STATUS_FEASIBLE;
//	return 0;
//}
//
//void Sequencer::splitPackagesToDeliveryNodes( const std::list<const Package*>& packages, const std::list<const Package*>::const_reverse_iterator& from, std::vector<RouteNode*>& storage )
//{
//	for( std::list<const Package*>::const_reverse_iterator package_it = from; package_it != packages.crend(); ++package_it )
//	{
//		if( storage.empty() || storage.back()->factory != (*package_it)->original_order->delivery_factory )
//		{
//			RouteNode* new_node = new RouteNode();
//			new_node->factory = (*package_it)->original_order->delivery_factory;
//			new_node->delivery_packages.push_back( *package_it );
//			new_node->node_type = GENERAL_NODE;
//			storage.push_back( new_node );
//		}
//		else
//		{
//			storage.back()->delivery_packages.push_back( *package_it );
//		}
//	}
//}
