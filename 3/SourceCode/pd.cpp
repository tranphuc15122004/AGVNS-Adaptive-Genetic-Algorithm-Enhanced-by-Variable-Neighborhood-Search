#include "pd.h"
#include "dpdp.h"

constexpr bool PD_SET_FIRST_PICK_FACTORY = false;

void PDRoute::insert_node_before(PDNode* node, PDNode* before)
{
	DPDP_ASSERT_ABORT(before != NULL && node != NULL && before != begin);
	node->route_pred = before->route_pred;
	before->route_pred->route_succ = node;
	node->route_succ = before;
	before->route_pred = node;
}


void PDRoute::insert_node_after(PDNode* node, PDNode* after)
{
	DPDP_ASSERT_ABORT(after != NULL && node != NULL && after != end);
	node->route_pred = after;
	node->route_succ = after->route_succ;
	after->route_succ = node;
	node->route_succ->route_pred = node;
}
void PDRoute::insert_interval_after(PDNode* first, PDNode *last, PDNode* after)
{
	DPDP_ASSERT_ABORT(after != NULL && first != NULL && last != NULL);
	first->route_pred = after;
	last->route_succ = after->route_succ;
	after->route_succ = first;
	last->route_succ->route_pred = last;
}
void PDRoute::remove_node(PDNode* node)
{
	DPDP_ASSERT_ABORT(node != NULL);
	node->route_pred->route_succ = node->route_succ;
	node->route_succ->route_pred = node->route_pred;
	node->route_pred = NULL;
	node->route_succ = NULL;
}

void PDRoute::remove_interval(PDNode* first, PDNode* last)
{
	DPDP_ASSERT_ABORT(first != NULL && last != NULL);

	first->route_pred->route_succ = last->route_succ;
	last->route_succ->route_pred = first->route_pred;
	first->route_pred = last->route_succ = NULL;

}

PDRoute::PDRoute()
	: begin(new PDNode(NULL, PDNODE_DUMMY_BEIGN)), end(new PDNode(NULL, PDNODE_DUMMY_END)), sch_route(NULL), vehicle_id(-1), good_route(false), initial_residual_capacity(0), first_pickup_factory( NULL )
{
	begin->route_succ = end;
	end->route_pred = begin;
}

PDRoute::~PDRoute()
{
	delete begin;
	delete end;
}

void PDRoute::update_sch_route()
{
	DPDP_ASSERT_ABORT(NULL != sch_route);
	SchNode* first_route_node = sch_route->first;
	SchNode* second_route_node = NULL;
	first_route_node->pickup_packages.clear();
	first_route_node->pickup_qty = first_route_node->delivery_qty = 0;
	first_route_node->delivery_packages.clear();
	if (CURRENT_NODE == sch_route->first->node_type && sch_route->first->succ != NULL 
		&& DESTINATION_NODE == sch_route->first->succ->node_type) {
		second_route_node = sch_route->first->succ;
		second_route_node->pickup_packages.clear();
		second_route_node->delivery_packages.clear();
		second_route_node->pickup_qty = second_route_node->delivery_qty = 0;
		SchNode* sn = NULL;
		for (SchNode* n = second_route_node->succ; n; n = sn)
		{
			sn = n->succ;
			sch_route->remove(n);
			delete n;
		}
	}
	else {
		SchNode* sn = NULL;
		for (SchNode* n = first_route_node->succ; n; n = sn)
		{
			sn = n->succ;
			sch_route->remove(n);
			delete n;
		}
	}
	SchNode* n = first_route_node;
	for (PDNode* node = begin->route_succ; node != end; node = node->route_succ)
	{
		cPtr package = node->package;
		
		if (node->get_node_type() == PDNODE_PICKUP)
		{
			while (n!= NULL && package->original_order->pickup_factory != n->factory)
			{
				n = n->succ;
			}
			if (NULL == n)
			{
				n = new SchNode(GENERAL_NODE, package->original_order->pickup_factory);
				sch_route->push_back(n);
			}
			n->add_pickup(package);
			node->sch_node = n;
		}
		else {
			while (n!= NULL && package->original_order->delivery_factory != n->factory)
			{
				n = n->succ;
			}
			if (NULL == n)
			{
				n = new SchNode(GENERAL_NODE, package->original_order->delivery_factory);
				sch_route->push_back(n);
			}
			n->append_delivery(package);
			node->sch_node = n;
		}
	}
	good_route = true;
}

bool PDRoute::check_capacity() const
{

	double level = initial_residual_capacity;
	for (PDNode* node = begin->route_succ; node != end; node = node->route_succ) {
		if (node->get_node_type() == PDNODE_PICKUP)
			level -= node->package->getDemand();
		else
			level += node->package->getDemand();

		if (level < -DPDP_EPSILON) return false;
	}

	return true;
}

PD::PD(const ProbData& _data, std::vector<Package*>& _packages, Scheduler& _scheduler)
	: data(_data), packages(_packages), scheduler(_scheduler)
{
	pickup_nodes = new PDNode * [packages.size()];
	delivery_nodes = new PDNode * [packages.size()];
	vehicle_ids = new int[packages.size()];
	routes.resize(data.getNumVehicles());
	sch_routes.resize(data.getNumVehicles(), NULL);
	std::set<cPtr> carried_set;
	for (int i = 0; i < sch_routes.size(); ++i)
	{
		sch_routes[i] = scheduler.getRoute(i);
		routes[i].vehicle_id = i;
		routes[i].initial_residual_capacity = data.getVehicle(i)->capacity;
		for (PackageList::const_iterator pit = sch_routes[i]->carrying_packages.begin(); pit != sch_routes[i]->carrying_packages.end(); ++pit) {
			carried_set.insert(*pit);
			routes[i].initial_residual_capacity -= (*pit)->getDemand();
		}

		// TODO (kist) : atnezni
		if ( PD_SET_FIRST_PICK_FACTORY )
		{
			const Vehicle* vehicle = data.getVehicle( i );
			if( vehicle->hasDestination() && vehicle->destination->delivery_items.empty() && !vehicle->destination->pickup_items.empty() )
				routes[i].first_pickup_factory = vehicle->destination->factory;
		}
	}

	for (std::vector<Package*>::iterator it = packages.begin(); it != packages.end(); ++it)
	{
		const Package* package = (cPtr)(*it);
		if (carried_set.find(package) == carried_set.end()) {
			delivery_nodes[package->id] = new PDNode(package, PDNODE_DELIVERY);
			pickup_nodes[package->id] = new PDNode(package, PDNODE_PICKUP);
			pickup_nodes[package->id]->delivery_pair = delivery_nodes[package->id];
			delivery_nodes[package->id]->pickup_pair = pickup_nodes[package->id];
		}
		else {
			pickup_nodes[package->id] = NULL;
			delivery_nodes[package->id] = new PDNode(package, PDNODE_CI_DELIVERY);
		}
	}
}
PD::~PD()
{
	delete[]vehicle_ids;
	for (int i = 0; i < packages.size(); ++i)
	{
		delete pickup_nodes[i];
		delete delivery_nodes[i];
	}
	delete[] pickup_nodes;
	delete[] delivery_nodes;
}
void PD::move(cPtr _package, int to_vehicle_id, PDNode* pickup_after, PDNode* delivery_before)
{
	routes[vehicle_ids[_package->id]].good_route = false;
	routes[vehicle_ids[_package->id]].remove_node(pickup_nodes[_package->id]);
	routes[vehicle_ids[_package->id]].remove_node(delivery_nodes[_package->id]);
	routes[to_vehicle_id].insert_node_after(pickup_nodes[_package->id], pickup_after);
	routes[to_vehicle_id].insert_node_after(delivery_nodes[_package->id], delivery_before->route_pred);
	vehicle_ids[_package->id] = to_vehicle_id;
	routes[to_vehicle_id].good_route = false;
}

void PD::move_interval(cPtr _package, int to_vehicle_id, PDNode* pickup_after)
{
	routes[vehicle_ids[_package->id]].good_route = false;
	routes[vehicle_ids[_package->id]].remove_interval(pickup_nodes[_package->id], delivery_nodes[_package->id]);
	routes[to_vehicle_id].insert_interval_after(pickup_nodes[_package->id], delivery_nodes[_package->id], pickup_after);
	for (PDNode* node = pickup_nodes[_package->id]; node != routes[to_vehicle_id].end; node = node->route_succ) {
		vehicle_ids[node->package->id] = to_vehicle_id;
		if (node == delivery_nodes[_package->id])  break;
	}
	routes[to_vehicle_id].good_route = false;
}

double PD::evaluate()
{
	for (PDRouteVect::iterator rit = routes.begin(); rit != routes.end(); ++rit)
	{
		if (!rit->good_route)
		{
			rit->update_sch_route();
			int status;
			if (!rit->sch_route->verifyRoute(status)) {
				// TODO remove this before testing on server
				scheduler.printRoute(std::cerr, rit->vehicle_id, false);
				abort();
			}
		}
	}


	return scheduler.evaluate();
}

void PD::import_schedule()
{
	const int num_vehicles = data.getNumVehicles();
	for (int vehicle_id = 0; vehicle_id < num_vehicles; ++vehicle_id) {
		SchRoute* route = scheduler.getRoute(vehicle_id);
		PDRoute & pd_route = routes[vehicle_id];
		pd_route.vehicle_id = vehicle_id;
		pd_route.good_route = true;
		pd_route.sch_route = route;
		for (SchNode* n = route->first; n; n = n->succ) {
			for (PackageList::iterator pit = n->delivery_packages.begin(); pit != n->delivery_packages.end(); ++pit)
			{
				pd_route.push_back(delivery_nodes[(*pit)->id]);
				delivery_nodes[(*pit)->id]->sch_node = n;
				vehicle_ids[(*pit)->id] = vehicle_id;
			}
			for (PackageList::iterator pit = n->pickup_packages.begin(); pit != n->pickup_packages.end(); ++pit)
			{
				pd_route.push_back(pickup_nodes[(*pit)->id]);
				pickup_nodes[(*pit)->id]->sch_node = n;
				vehicle_ids[(*pit)->id] = vehicle_id;
			}
		}
	}
}

void PD::insert( cPtr _package, int to_vehicle_id, PDNode* pickup_after, PDNode* delivery_before )
{
	DPDP_ASSERT_ABORT( 0 <= to_vehicle_id && to_vehicle_id < data.getNumVehicles() );
	DPDP_ASSERT_ABORT( pickup_after != NULL );
	DPDP_ASSERT_ABORT( delivery_before != NULL );

	PDNode* pickup_node = getPickupNode( _package );
	PDNode* delivery_node = getDeliveryNode( _package );

	DPDP_ASSERT_ABORT( NULL == pickup_node->route_pred && NULL == pickup_node->route_succ );
	DPDP_ASSERT_ABORT( NULL == delivery_node->route_pred && NULL == delivery_node->route_succ );

	PDRoute& route = routes[to_vehicle_id];
	route.good_route = false;
	vehicle_ids[_package->id] = to_vehicle_id;
	route.insert_node_after( pickup_node, pickup_after );
	route.insert_node_before( delivery_node, delivery_before );
}

void PD::insert_interval( PDNode *first, PDNode *last, int to_vehicle_id, PDNode * pickup_after )
{
	DPDP_ASSERT_ABORT( 0 <= to_vehicle_id && to_vehicle_id < data.getNumVehicles() );
	DPDP_ASSERT_ABORT( pickup_after != NULL );
	DPDP_ASSERT_ABORT( NULL == first->route_pred );
	DPDP_ASSERT_ABORT( NULL == last->route_succ );

	PDRoute& route = routes[to_vehicle_id];
	route.insert_interval_after( first, last, pickup_after );
	for( PDNode* node = first; node != last->route_succ; node = node->route_succ )
		vehicle_ids[node->package->id] = to_vehicle_id;
	route.good_route = false;
}

void PD::insert_two_intervals(PDNode* first1, PDNode* last1, PDNode* first2, PDNode* last2, int to_vehicle_id, PDNode* pickup_after1, PDNode *delivery_before2)
{
	DPDP_ASSERT_ABORT(0 <= to_vehicle_id && to_vehicle_id < data.getNumVehicles());
	DPDP_ASSERT_ABORT(pickup_after1 != NULL);
	DPDP_ASSERT_ABORT(delivery_before2 != NULL);
	DPDP_ASSERT_ABORT(NULL == first1->route_pred);
	DPDP_ASSERT_ABORT(NULL == last1->route_succ);
	DPDP_ASSERT_ABORT(NULL == first2->route_pred);
	DPDP_ASSERT_ABORT(NULL == last2->route_succ);

	PDRoute& route = routes[to_vehicle_id];
	route.insert_interval_after(first1, last1, pickup_after1);
	route.insert_interval_after(first2, last2, delivery_before2->route_pred);
	for (PDNode* node = first1; node != last1->route_succ; node = node->route_succ) {
		vehicle_ids[node->package->id] = to_vehicle_id;
	}
	route.good_route = false;
}
void PD::remove( cPtr package )
{
	DPDP_ASSERT_ABORT( package != NULL && vehicle_ids[package->id] >= 0 );

	PDRoute& route = routes[vehicle_ids[package->id]];
	route.good_route = false;
	route.remove_node( pickup_nodes[package->id] );
	route.remove_node( delivery_nodes[package->id] );
	vehicle_ids[package->id] = -1;
}

void PD::remove_interval( PDNode *first, PDNode *last )
{
	DPDP_ASSERT_ABORT( vehicle_ids[first->package->id] >= 0 );

	PDRoute& route = routes[vehicle_ids[first->package->id]];
	route.good_route = false;
	route.remove_interval(first, last);
	for (PDNode* node = first; node != last->route_succ; node = node->route_succ) {
		vehicle_ids[node->package->id] = -1;
	}
}

void PD::remove_two_intervals(PDNode* first1, PDNode* last1, PDNode* first2, PDNode* last2)
{
	DPDP_ASSERT_ABORT(vehicle_ids[first1->package->id] >= 0);

	PDRoute& route = routes[vehicle_ids[first1->package->id]];
	route.good_route = false;
	route.remove_interval(first1, last1);
	route.remove_interval(first2, last2);
	for (PDNode* node = first1; node != last1->route_succ; node = node->route_succ) {
		vehicle_ids[node->package->id] = -1;
	}
}

PDNode* PD::get_first_insertion_point(int to_vehicle_id)
{
	PDRoute& route = routes[to_vehicle_id];
	PDNode* node;
	for (node = route.begin->route_succ; node != route.end; node = node->route_succ)
	{
		if (node->get_node_type() != PDNODE_CI_DELIVERY) break;
	}
	return node->route_pred;
}
