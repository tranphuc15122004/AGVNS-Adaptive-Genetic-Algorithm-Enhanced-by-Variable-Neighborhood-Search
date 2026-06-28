#include "lssolver.h"
#include "lssolver_compaux.h"

#include "config.h"
#include "dpdp.h"
#include "probdata.h"
#include "scheduler.h"
#include "solverdata.h"
#include "timer.h"
#include "statistics.h"
#include "binpacking.h"
#include "pd.h"
#include "pd_ls.h"

#include <random>
#include <algorithm>
#include <set>
#include <utility>
#include <iostream>
#include <fstream>
#include <vector>
#include <cfloat>

constexpr char LSSOLVER_PICTURE_FILE[]           = "pictfile.tex";
constexpr char LSSOLVER_LOG_FILE[]               = "logfile.txt";
constexpr char LSSOLVER_ITEMINFO_FILE[]          = "iteminfo.gantt";
constexpr bool LSSOLVER_KEEP_DESTINATION_PICKUPS = true;

constexpr int LSSOLVER_LOOKAHEAD = 3;

/* turn on/off construction methopds */
constexpr int NUM_CONSTRUCTION_METHODS = 2;
static bool use_construction_method[NUM_CONSTRUCTION_METHODS] = { false, true };

/* search method: local search or tabu search */
constexpr bool LSSOLVER_USE_LOCAL_SEARCH = true;
constexpr bool LSSOLVER_USE_TABU_SEARCH  = false;
constexpr bool LSSOLVER_USE_LOCAL_SEARCH_WITH_RESCHEDULE = false;

constexpr bool LSSOLVER_USE_EVALUATE_SQUARED_TERM = true;
constexpr bool LSSOLVER_USE_SWAP_IMPROVE = false;
/* parameters to search */
constexpr long long LSSOLVER_LOCAL_SEARCH_TIME_LIMIT = 240; // seconds
constexpr long long GLOBAL_TIME_LIMIT                = 580; // seconds

/* other settings, mainly experimental */
constexpr bool LSSOLVER_REDISTRIBUTE_PACKAGES = false;
constexpr bool LSSOLVER_IMPROVE_SEQUENCES     = false; // KEEP IT TURNED OFF!! - Then, it should be removed... 

static long long remaining_time()
{
	return std::max<long long>(0, GLOBAL_TIME_LIMIT - GlobalTimer::getInstance().getElapsedSeconds());
}

void LocalSearchSolver::storePackage(Package* _pack)
{
	DPDP_ASSERT_ABORT(_pack != NULL);

	_pack->id = (int)packages.size();
	packages.push_back(_pack);
	packages[_pack->id] = _pack; // TODO: ez mire kell?
}

LocalSearchSolver::LocalSearchSolver( const ProbData* _probdata ) : probdata( _probdata )
{
}

LocalSearchSolver::~LocalSearchSolver()
{
	if( !packages.empty() )
	{
		for( int package_id = 0; package_id < packages.size(); ++package_id )
			delete packages[package_id];
	}

	for( std::vector<LSNode*>::iterator lit = destinations.begin(); lit != destinations.end(); ++lit )
	{
		if( *lit ) delete* lit;
	}
}

//void LocalSearchSolver::calcDesiredNumberOfDockings()
//{
//	const int num_fact = probdata->getNumFactories();
//	std::vector<std::list<const Package*> > pickup_packages(num_fact);
//	std::vector<std::list<const Package*> > delivery_packages(num_fact);
//	desired_number_of_dockings.resize(num_fact);
//	for (std::vector<Package*>::const_iterator pit = packages.begin(); pit != packages.end(); ++pit)
//	{
//		Package* p = *pit;
//		if(p->original_order->pickup_factory)
//			pickup_packages[p->original_order->pickup_factory->id].push_back(p);
//	
//		delivery_packages[p->original_order->delivery_factory->id].push_back(p);
//	}
//	double capacity = probdata->getVehicle(0)->capacity;
//	for (int f = 0; f < num_fact; ++f) 
//	{
//		std::vector<std::pair<double, std::list<const Package*> > > packing;
//		pack_items(pickup_packages[f], capacity, packing);
//		int num_pickups = packing.size();
//		
//		packing.clear();
//		pack_items(delivery_packages[f], capacity, packing);
//		int num_deliveries = packing.size();
//
//		desired_number_of_dockings[f] = std::max(num_pickups, num_deliveries);
//	}
//
//}


bool LocalSearchSolver::takeOffPackages( Scheduler& scheduler )
{
	bool improved_at_least_once = false;

	double best_value = scheduler.evaluate();
	double curr_value = .0;

	std::vector<int> package_count;
	countScheduledPackages(scheduler, package_count);

	for( int iteration = 1; ; ++iteration )
	{
		DPDP_ASSERT_ABORT(verifyPackagecount(scheduler, package_count));

		dpdpPrintfDebug( "[improve vehicles] iteration %d...\n", iteration );

		std::list< std::pair< int, SchNode* > > vehicles_to_improve;

		for( int vehicle_id = 0; vehicle_id < probdata->getNumVehicles(); ++vehicle_id )
		{
			SchRoute* route = scheduler.getRoute( vehicle_id );

			for( SchNode* node = route->first; node; node = node->succ )
			{
				if( node->waiting_time < 600 ) // TODO
					continue;

				if( CURRENT_NODE == node->node_type || DESTINATION_NODE == node->node_type)
					continue;

				if( !node->delivery_packages.empty() )
					continue;

				if( node->pickup_packages.empty() )
					continue;

				/* check delivery factories */
				const Factory* delivery_factory = node->pickup_packages.front()->original_order->delivery_factory;

				bool common_delivery = true;
				for( PackageList::const_iterator it = node->pickup_packages.cbegin(); common_delivery && it != node->pickup_packages.cend(); ++it )
				{
					if( (*it)->original_order->delivery_factory != delivery_factory )
						common_delivery = false;
				}

				if( !common_delivery )
					continue;

				/* store vehicle-node pair */
				vehicles_to_improve.push_back( std::make_pair( vehicle_id, node ) );
			}
		}

		if( vehicles_to_improve.empty() )
		{
			dpdpPrintfDebug( "[improve vehicles] there is no vehicle to improve\n" );
			break;
		}

		/* sort list and find improvment */
		vehicles_to_improve.sort( vehicle_schnode_comparator_waiting_time_decrease() );

		bool improved_in_this_iteration = false;

		for( std::list< std::pair< int, SchNode* > >::iterator it = vehicles_to_improve.begin(); it != vehicles_to_improve.end(); ++it )
		{
			if( !takeOffPackagesFromVehicle( scheduler, it->first, it->second->pickup_packages, true, best_value, curr_value ) )
				continue;

			best_value = curr_value;
			improved_in_this_iteration = true;

			break;
		}

		improved_at_least_once |= improved_in_this_iteration;

		if( !improved_in_this_iteration )
			break; // terminate
	}
	DPDP_ASSERT_ABORT(verifyPackagecount(scheduler, package_count));
	return improved_at_least_once;
}

struct FactoryStruct
{
	const Factory* factory;
	int waiting_time;
	std::set<int> visiting_vehicles;

	FactoryStruct() : factory( NULL ), waiting_time( 0 )
	{
	}
};

bool compare_factory_struct_decrease( const FactoryStruct& a, const FactoryStruct& b )
{
	return a.waiting_time > b.waiting_time;
}

bool LocalSearchSolver::takeOffPackages_2( Scheduler& scheduler )
{
	double best_value = scheduler.evaluate();
	double curr_value = .0;

	bool improved_at_least_once = false;
	bool improved_in_iteration = true;

	std::vector<int> package_count;
	countScheduledPackages( scheduler, package_count );

	for( int iteration = 1; improved_in_iteration; ++iteration )
	{
		improved_in_iteration = false;

		dpdpPrintfDebug( "[improve vehicles] iteration %d...\n", iteration );

		DPDP_ASSERT_ABORT( verifyPackagecount( scheduler, package_count ) );

		std::vector<FactoryStruct> facs;
		facs.resize( probdata->getNumFactories() );
		for( int factory_id = 0; factory_id < probdata->getNumFactories(); ++factory_id )
			facs[factory_id].factory = probdata->getFactory( factory_id );

		for( int vehicle_id = 0; vehicle_id < probdata->getNumVehicles(); ++vehicle_id )
		{
			const SchRoute* route = scheduler.getRoute( vehicle_id );

			for( SchNode* node = route->first; node != NULL; node = node->succ )
			{
				if( node->node_type != GENERAL_NODE )
					continue;

				facs[node->factory->id].visiting_vehicles.insert( vehicle_id );
				facs[node->factory->id].waiting_time += node->waiting_time;
			}
		}

		std::sort( facs.begin(), facs.end(), compare_factory_struct_decrease );

		for( std::vector<FactoryStruct>::iterator fac_it = facs.begin(); fac_it != facs.end(); ++fac_it )
		{
			if( fac_it->waiting_time < 100 ) // KEEP this boud, it improved the score on th server
				break;

			for( std::set<int>::iterator veh_it = fac_it->visiting_vehicles.begin(); veh_it != fac_it->visiting_vehicles.end(); ++veh_it )
			{
				SchRoute* route = scheduler.getRoute( *veh_it );
				SchNode* succ_node = NULL;
				for (SchNode* node = route->first; node; node = succ_node) {
					succ_node = node->succ;

					if (node->node_type != GENERAL_NODE)
						continue;

					if (node->factory != fac_it->factory)
						continue;

					if (node->pickup_packages.empty() && !node->delivery_packages.empty())
					{
						if (takeOffPackagesFromVehicle(scheduler, *veh_it, node->delivery_packages, false, best_value, curr_value))
						{
							best_value = curr_value;
							improved_in_iteration = true;
							goto TERMINATE_ITERATION;
						}
					}
				}
				SchNode* pred_node = NULL;
				for (SchNode* node = route->last; node; node = pred_node) {
					pred_node = node->prev;

					if (node->node_type != GENERAL_NODE)
						continue;

					if (node->factory != fac_it->factory)
						continue;

					if (!node->pickup_packages.empty() && node->delivery_packages.empty())
					{
						if (takeOffPackagesFromVehicle(scheduler, *veh_it, node->pickup_packages, true, best_value, curr_value))
						{
							best_value = curr_value;
							improved_in_iteration = true;
							goto TERMINATE_ITERATION;
						}
					}
				}
			}
		}

	TERMINATE_ITERATION:
		improved_at_least_once |= improved_in_iteration;
	}

	DPDP_ASSERT_ABORT( verifyPackagecount( scheduler, package_count ) );

	return improved_at_least_once;
}

struct DistibutionStruct
{
	int vehicle_id;
	SchNode* pickup_node;
	SchNode* delivery_node;
	double free_capacity;
	PackageList packages;

	DistibutionStruct() : vehicle_id( -1 ), pickup_node( NULL ), delivery_node( NULL ), free_capacity( .0 )
	{}
};

struct distribution_comparator_free_capacity_increase
{
	bool operator()( const DistibutionStruct& a, const DistibutionStruct& b ) const
	{
		return a.free_capacity < b.free_capacity;
	}
};

bool LocalSearchSolver::takeOffPackagesFromVehicle( Scheduler& scheduler, int from_vehicle_id, const PackageList& packages_to_redistribute, bool pickup_movement, const double initial_value, double& improved_value )
{
	if( packages_to_redistribute.empty() )
		return false;

	const Factory* pickup_factory = packages_to_redistribute.front()->original_order->pickup_factory;
	const Factory* delivery_factory = packages_to_redistribute.front()->original_order->delivery_factory;

	for( PackageList::const_iterator package_it = packages_to_redistribute.cbegin(); package_it != packages_to_redistribute.cend(); ++package_it )
	{
		if( (*package_it)->original_order->pickup_factory != pickup_factory )
			return false;

		if( (*package_it)->original_order->delivery_factory != delivery_factory )
			return false;

		if( NULL == scheduler.getPickupNode( *package_it ) )
			return false;
	}

	PackageList original_packages( packages_to_redistribute );  // NOTE : list must be copied!!!!
	PackageList remaining_packages( packages_to_redistribute ); // NOTE : list must be copied!!!!

	double free_capacity = .0;
	SchNode* pickup_node = NULL;
	SchNode* delivery_node = NULL;

	const int orig_length = scheduler.getRoute( from_vehicle_id )->len;
	SchNode* original_pickup_prev_node = scheduler.getPickupNode( original_packages.front() )->prev;
	SchNode* original_delivery_succ_node = scheduler.getDeliveryNode( original_packages.front() )->succ;

	/* sort packages by demand (decreasing) */
	remaining_packages.sort( package_comparator_demand_decrease() );

	/* calculate free capacities */
	std::list< DistibutionStruct > distribution;
	
	for( int vehicle_id = 0; vehicle_id < probdata->getNumVehicles(); ++vehicle_id )
	{
		if( vehicle_id == from_vehicle_id)
			continue;

		if( !scheduler.find_factory_nodes( vehicle_id, pickup_factory, delivery_factory, pickup_node, delivery_node, free_capacity ) )
			continue;

		if( free_capacity < DPDP_EPSILON )
			continue;

		DistibutionStruct temp;
		temp.vehicle_id = vehicle_id;
		temp.free_capacity = free_capacity;
		temp.pickup_node = pickup_node;
		temp.delivery_node = delivery_node;

		distribution.push_back( std::move( temp ) );
	}

	// TODO : check full capacities

	/* sort distribution (free capacity decreasing) */
	distribution.sort( distribution_comparator_free_capacity_increase() );
		
	/* find distribution */
	for( std::list<DistibutionStruct>::iterator it = distribution.begin(); it != distribution.end(); ++it )
	{
		for( PackageList::iterator package_it = remaining_packages.begin(); package_it != remaining_packages.end(); )
		{
			if( (*package_it)->getDemand() <= it->free_capacity + DPDP_EPSILON )
			{
				it->packages.push_back( *package_it );
				it->free_capacity -= (*package_it)->getDemand();
				package_it = remaining_packages.erase( package_it );

			}
			else
				++package_it;
		}
	}

	if( !remaining_packages.empty() )
		return false; // cannot distribute all of the packages

	/* distribute packages */
	for( std::list<DistibutionStruct>::iterator it = distribution.begin(); it != distribution.end(); ++it )
	{		
		scheduler.remove_packages( from_vehicle_id, it->packages ); // NOTE : packages_to_redistribute is going to be invalid!

		dpdpPrintfTrace("remove packages from V%d\n", it->vehicle_id + 1);
		for( PackageList::const_iterator package_it = it->packages.cbegin(); package_it != it->packages.cend(); ++package_it )
			scheduler.insert_package( *package_it, it->vehicle_id, it->pickup_node, it->delivery_node );
	}

	/* evaluate */
	SchRoute* new_route = scheduler.getRoute( from_vehicle_id );
	
	if( new_route->first->node_type == DESTINATION_NODE && new_route->first->pickup_packages.empty() && new_route->first->delivery_packages.empty() )
	{
		improved_value = std::numeric_limits<double>::max();
	}
	else
	{
		improved_value = scheduler.evaluate();

		if( improved_value <= initial_value )
		{
			dpdpPrintfDebug( "[improve vehicles] new value = %.3f\n", improved_value );

			return true;
		}
	}

	/* undo... */
	for( std::list<DistibutionStruct>::iterator it = distribution.begin(); it != distribution.end(); ++it )
		scheduler.remove_packages( it->vehicle_id, it->packages );

	bool pickup_deleted = pickup_movement || new_route->len < orig_length - 1;
	bool delivery_deleted = !pickup_movement || new_route->len < orig_length - 1;

	if( pickup_deleted )
	{
		SchNode* from_node = original_pickup_prev_node != NULL ? original_pickup_prev_node : new_route->first;
		new_route->insert( from_node, new SchNode( GENERAL_NODE, pickup_factory ) );
	}

	if( delivery_deleted )
	{
		SchNode* to_node = original_delivery_succ_node != NULL ? original_delivery_succ_node->prev : new_route->last;
		new_route->insert( to_node, new SchNode( GENERAL_NODE, delivery_factory ) );
	}

	for( PackageList::const_iterator package_it = original_packages.cbegin(); package_it != original_packages.cend(); ++package_it )
	{
		SchNode* from_node = original_pickup_prev_node != NULL ? original_pickup_prev_node->succ : new_route->first;
		SchNode* to_node = original_delivery_succ_node != NULL ? original_delivery_succ_node->prev : new_route->last;
		scheduler.insert_package( *package_it, from_vehicle_id, from_node, to_node );
	}

	return false;
}

bool LocalSearchSolver::swap_improve(Scheduler & sch)
{
	int iter = 0; 
	int next_route = 0;
	const int num_vehicles = probdata->getNumVehicles();
	double best_value = sch.evaluate();
	double orig_value = best_value;
	int last_improve_iter = -1;
	for (; iter < 5 * num_vehicles && last_improve_iter + num_vehicles >= iter; ++iter)
	{
		if (swap_improve_route(sch, next_route, best_value))
		{
			last_improve_iter = iter;
		}
		next_route = (next_route + 1) % num_vehicles;
	}

	return best_value < orig_value - DPDP_EPSILON;
}

bool LocalSearchSolver::swap_improve_route(Scheduler& sch, int vehicle_id, double &best_value)
{
	SchRoute* r = sch.getRoute(vehicle_id);
	if (r->len < 3) return false;
	for (SchNode* n = r->first; n!= r->last->prev; n = n->succ)
	{
		std::set<SchNode*> neighbors;
		for (PackageList::iterator pit = n->pickup_packages.begin(); pit != n->pickup_packages.end(); ++pit)
		{
			const Package* package = *pit;
			neighbors.insert(sch.getDeliveryNode(package));
		}
		// find an improving swap
		for (std::set<SchNode*>::iterator s1 = neighbors.begin(); s1 != neighbors.end(); ++s1)
		{
			std::set<SchNode*>::iterator s2 = s1;
			for (++s2; s2 != neighbors.end(); ++s2)
			{
				if (sch.swap_successors(vehicle_id, n, *s1, *s2))
				{
					double current_value = sch.evaluate();
					if (current_value < best_value - 10)
					{
						best_value = current_value;
						return true;
					}
				}
				sch.swap_successors(vehicle_id, n, *s1, *s2);
			}
		}
	}
	if (r->len < 4) return false;
	SchNode* end = r->first->succ->succ;
	for (SchNode* n = r->last; n != end; n = n->prev)
	{
		std::set<SchNode*> neighbors;
		for (PackageList::iterator pit = n->delivery_packages.begin(); pit != n->delivery_packages.end(); ++pit)
		{
			const Package* package = *pit;
			if(sch.getPickupNode(package) != NULL )
				neighbors.insert(sch.getPickupNode(package));
		}
		// find an improving swap
		for (std::set<SchNode*>::iterator s1 = neighbors.begin(); s1 != neighbors.end(); ++s1)
		{
			std::set<SchNode*>::iterator s2 = s1;
			for (++s2; s2 != neighbors.end(); ++s2)
			{
				if (sch.swap_predecessors(vehicle_id, n, *s1, *s2))
				{
					double current_value = sch.evaluate();
					if (current_value < best_value - 10)
					{
						best_value = current_value;
						return true;
					}
				}
				sch.swap_predecessors(vehicle_id, n, *s1, *s2);
			}
		}
	}

	return false;
}


int LocalSearchSolver::init()
{
	typedef std::list<const OrderItem*> ItemList;

	const int num_of_vehicles = probdata->getNumVehicles();
	const double vehicle_capacity = probdata->getVehicle(0)->capacity;
	std::set<const OrderItem*> destination_items;

	carrying_packages.resize(num_of_vehicles);
	destinations.resize(num_of_vehicles);
	for (int v = 0; v < probdata->getNumVehicles(); ++v)
	{
		destinations[v] = NULL;
		carrying_packages[v].clear(); //  in case of multiple inits...
	}

	/* create vehicle data */
	for (int v = 0; v < probdata->getNumVehicles(); ++v)
	{
		const Vehicle* vehicle = probdata->getVehicle(v);

		/* destination */
		if (vehicle->hasDestination())
		{
			destinations[v] = new LSNode();
			destinations[v]->factory = vehicle->destination->factory;
			destinations[v]->arrive_time = vehicle->destination->arrive_time;
			destinations[v]->leave_time = vehicle->destination->leave_time;
		}

		/* carrying items */
		if (!vehicle->carrying_items.empty())
		{
			ItemList::const_reverse_iterator carrying_item_it = vehicle->carrying_items.crbegin();

			/* create packages based on delivery items, if any - NOTE that items are in the order of unloading
			 *
			 * carrying_items :        ABCDEFGH <- carrying_item_it
			 * delivery_items : delivery_it -> HGFE
			 */
			if (vehicle->hasDestination() && !vehicle->destination->delivery_items.empty())
			{
				Package* current_package = new Package();

				for (ItemList::const_iterator delivery_it = vehicle->destination->delivery_items.cbegin(); delivery_it != vehicle->destination->delivery_items.cend(); ++delivery_it)
				{
					DPDP_ASSERT_ABORT(carrying_item_it != vehicle->carrying_items.crend());
					DPDP_ASSERT_ABORT(*carrying_item_it == *delivery_it);

					/* create new package if it is necessary (and store opened package) */
					if (!testItemOnPackage(current_package, *carrying_item_it, vehicle->capacity))
					{
						/* close and store current package */
						storePackage(current_package);
						destinations[v]->delivery_packages.push_back(current_package);
						carrying_packages[v].push_front(current_package);

						/* create new package */
						current_package = new Package();
					}

					/* push FRONT item in old/new package */
					current_package->push_front(*delivery_it);

					++carrying_item_it;
				}

				/* close and store opened package */
				storePackage(current_package);
				destinations[v]->delivery_packages.push_back(current_package);
				carrying_packages[v].push_front(current_package);
			}

			/* create packages - NOTE that carrying items are in the order of loading */
			if (carrying_item_it != vehicle->carrying_items.crend())
			{
				Package* current_package = new Package();

				for (; carrying_item_it != vehicle->carrying_items.crend(); ++carrying_item_it)
				{
					/* create new package if it is necessary (and store opened package) */
					if (!testItemOnPackage(current_package, *carrying_item_it, vehicle->capacity))
					{
						/* close and store current package */
						storePackage(current_package);
						carrying_packages[v].push_front(current_package);

						/* create new package */
						current_package = new Package();
					}

					/* push FRONT item in old/new package */
					current_package->push_front(*carrying_item_it);
				}

				/* close and store opened package */
				storePackage(current_package);
				carrying_packages[v].push_front(current_package);
			}
		}

		/* pick-up items */
		if (LSSOLVER_KEEP_DESTINATION_PICKUPS && vehicle->hasDestination() && !vehicle->destination->pickup_items.empty())
		{
			Package* current_package = new Package();
			current_package->pickup_dest = true;
			for (ItemList::const_iterator pickup_it = vehicle->destination->pickup_items.cbegin(); pickup_it != vehicle->destination->pickup_items.cend(); ++pickup_it)
			{
				destination_items.insert(*pickup_it);

				/* create new package if it is necessary (and store opened package) */
				if (!testItemOnPackage(current_package, *pickup_it, vehicle->capacity))
				{
					/* close and store current package */
					storePackage(current_package);
					destinations[v]->pickup_packages.push_back(current_package);

					/* create new package */
					current_package = new Package();
					current_package->pickup_dest = true;
				}

				/* push FRONT item in old/new package */
				current_package->push_front(*pickup_it);
			}

			/* close and store opened package */
			storePackage(current_package);
			destinations[v]->pickup_packages.push_back(current_package);
		}
	}

	/* create unallocated packages */
	for (int order_id = 0; order_id < probdata->getNumOrders(); ++order_id)
	{
		const Order* order = probdata->getOrder(order_id);

		if (order->unallocated_items.empty())
			continue;

		Package* current_package = new Package();

		for (ItemList::const_iterator item_it = order->unallocated_items.cbegin(); item_it != order->unallocated_items.cend(); ++item_it)
		{
			if (destination_items.find(*item_it) != destination_items.end())
				continue; // we kept items at destinations

			/* create new package if it is necessary (and store opened package) */
			if (!testItemOnPackage(current_package, *item_it, vehicle_capacity))
			{
				/* close and store current package */
				storePackage(current_package);
				unallocated_packages.push_back(current_package);

				/* create new package */
				current_package = new Package();
			}

			/* push FRONT item in old/new package */
			current_package->push_front(*item_it);
		}

		/* close and store opened package (it may be empty due to destination_items) */
		if (current_package->getOrderItems().empty())
			delete current_package;
		else
		{
			storePackage(current_package);
			unallocated_packages.push_back(current_package);
		}
	}

	return 0;
}

int LocalSearchSolver::orderPackages1(PackageList& packages_to_process)
{
	const int num_packages = (int)packages_to_process.size();
	packages_to_process.sort(GroupByPickup());
	PackageList::iterator next_pit;

	std::list<std::pair<int, PackageList> > date2pack;
	for (PackageList::iterator pit = packages_to_process.begin(); pit != packages_to_process.end(); pit = next_pit)
	{
		int min_completion_time = INT_MAX;
		for (next_pit = pit; next_pit != packages_to_process.end(); ++next_pit) {
			if ((*pit)->original_order->pickup_factory != (*next_pit)->original_order->pickup_factory ||
				(*pit)->original_order->delivery_factory != (*next_pit)->original_order->delivery_factory) break;
			if (min_completion_time > (*next_pit)->original_order->completion_time)
				min_completion_time = (*next_pit)->original_order->completion_time;
		}

		PackageList same_pickup_delivery;
		same_pickup_delivery.splice(same_pickup_delivery.begin(), packages_to_process, pit, next_pit);
		date2pack.push_back(std::make_pair(min_completion_time, same_pickup_delivery));
	}
	date2pack.sort(); // increasing min_completion_time order
	packages_to_process.clear();
	for (std::list<std::pair<int, PackageList> >::iterator it = date2pack.begin(); it != date2pack.end(); ++it) {
		packages_to_process.splice(packages_to_process.end(), it->second);
	}
	assert(packages_to_process.size() == num_packages);
	return 0;
}

int LocalSearchSolver::orderPackages3(std::list<std::pair<int, const Package*> >& packages_to_process, PackageList& ordered_packages, int ordering)
{
	std::list<std::pair<int, const Package*> >::iterator next_pit;
	std::vector<std::pair<double, std::list<const Package*> > > dempack;

	packages_to_process.sort(GroupByPickup2());
	for (std::list<std::pair<int, const Package*> >::iterator pit = packages_to_process.begin(); pit != packages_to_process.end(); pit = next_pit)
	{
		double demand = 0;
		int max_lateness = -INT_MAX;
		for (next_pit = pit; next_pit != packages_to_process.end(); ++next_pit) {
			if (pit->second->original_order->pickup_factory != next_pit->second->original_order->pickup_factory ||
				pit->second->original_order->delivery_factory != next_pit->second->original_order->delivery_factory) break;
			demand += next_pit->second->getDemand();
			if (next_pit->first > max_lateness)
				max_lateness = next_pit->first;
		}

		std::list<const Package*> same_pickup_delivery;
		for (std::list<std::pair<int, const Package*> >::iterator cit = pit; cit != next_pit; ++cit)
			same_pickup_delivery.push_back(cit->second);
		dempack.push_back(std::pair<int, std::list<const Package*> >());
		switch (ordering) {
		case 1:
			dempack.back().first = max_lateness;
			break;
		case 2: 
			dempack.back().first = demand;
			break;
		default:;
		}
		std::list<const Package*>& same = dempack.back().second;
		same.splice(same.end(), same_pickup_delivery);
	}
	std::sort(dempack.begin(), dempack.end(), DecrFirst<double>()); // decreasing order

	ordered_packages.clear();
	for (std::vector<std::pair<double, std::list<const Package*> > >::iterator it = dempack.begin(); it != dempack.end(); ++it) {
		ordered_packages.splice(ordered_packages.end(), it->second);
	}

	return 0;
}

int LocalSearchSolver::orderPackages2(PackageList& packages_to_process)
{
	const int num_packages = (int)packages_to_process.size();

	std::list<std::pair<int, const Package*> > urgent;
	std::list<std::pair<int, const Package*> > easy;

	const int current_time = calculateLatestUpdateTime();
	for (PackageList::iterator pit = packages_to_process.begin(); pit != packages_to_process.end(); ++pit)
	{
		const Package* pack = *pit;
		int travel_time = probdata->getTravelTime(pack->original_order->pickup_factory, pack->original_order->delivery_factory);
		int duration = getLoadingSeconds(pack->getDemand()) + travel_time + getUnloadingSeconds(pack->getDemand()) + DOCK_APPROACHING_TIME;
		int lateness = current_time + duration - pack->original_order->completion_time;
		if (lateness > -3600)
			urgent.push_back(std::make_pair(lateness, pack));
		else
			easy.push_back(std::make_pair(travel_time, pack));
	}

	urgent.sort(DecrLength());
	easy.sort(DecrLength());
	packages_to_process.clear();
	for (std::list<std::pair<int, const Package*> >::iterator pit = urgent.begin(); pit != urgent.end(); ++pit)
		packages_to_process.push_back(pit->second);
	for (std::list<std::pair<int, const Package*> >::iterator pit = easy.begin(); pit != easy.end(); ++pit)
		packages_to_process.push_back(pit->second);

	assert(packages_to_process.size() == num_packages);
	return 0;
}

template<class Compare>
void orderPackages(std::list<std::pair<int, const Package*> >& packages_to_order, Compare comp, PackageList& ordered_packages)
{
	ordered_packages.clear();
	packages_to_order.sort(comp);

	for (std::list<std::pair<int, const Package*> >::iterator pit = packages_to_order.begin(); pit != packages_to_order.end(); ++pit)
		ordered_packages.push_back(pit->second);
}

int LocalSearchSolver::dispatch(Scheduler& sch, std::list<const Package*>& packages_to_process, bool binpacking)
{
	const int num_vehicles = probdata->getNumVehicles();

	PackageList::iterator first_unproc_it;

	for (std::list<const Package* >::iterator pit = packages_to_process.begin(); pit != packages_to_process.end(); pit = first_unproc_it)
	{
		const Package* package = *pit;
		double best_value = std::numeric_limits<double>::max();
		SchNode* best_pos = NULL;
		int best_vehicle = -1;

		for (int vehicle_id = 0; vehicle_id < num_vehicles; ++vehicle_id)
		{
			SchNode* pos;
			double value;

			if (!sch.find_best_insert_pos(package, vehicle_id, pos, value))
				continue;

			if (NULL == best_pos || value < best_value)
			{
				best_pos = pos;
				best_value = value;
				best_vehicle = vehicle_id;
			}
		}

		if (best_vehicle >= 0)
		{
			DPDP_ASSERT_ABORT(best_pos != NULL);

			SchNode* from_node = 0;
			SchNode* to_node = 0;
			bool new_from_node;
			bool new_to_node;
			if (binpacking) {
				SchRoute& route = *sch.getRoute(best_vehicle);
				double remaining_capacity = probdata->getVehicle(best_vehicle)->capacity - SchNode::sum_demand(carrying_packages[best_vehicle]);

				for (SchNode* n = route.first; n; n = n->succ)
				{
					remaining_capacity -= (n->pickup_qty - n->delivery_qty);
					if (n == best_pos) break;
				}
				PackageList same;
				std::set<const Package*> packing;
				for (PackageList::iterator it = pit; it != packages_to_process.end(); ++it) {
					if ((*it)->original_order->pickup_factory != package->original_order->pickup_factory)
						break;

					if ((*it)->original_order->delivery_factory != package->original_order->delivery_factory)
						break;
					same.push_back(*it);
				}
				maximum_packing(same, remaining_capacity, packing);
				for (std::set<const Package*>::iterator it = packing.begin(); it != packing.end(); ++it) {
					sch.insert_package(*it, best_vehicle, best_pos, from_node, to_node, new_from_node, new_to_node);
				}
#ifdef DPDP_DEBUG
				int status;
				if (!sch.getRoute(best_vehicle)->verifyRoute(status))
				{
					abort();
				}
#endif
				PackageList::iterator next_pit = pit;
				bool unproc_one = false;
				for (; pit != packages_to_process.end(); pit = next_pit) {
					next_pit = pit;
					if ((*pit)->original_order->pickup_factory != package->original_order->pickup_factory)
						break;

					if ((*pit)->original_order->delivery_factory != package->original_order->delivery_factory)
						break;
					++next_pit;
					if (packing.find(*pit) == packing.end()) {
						if (!unproc_one) {
							unproc_one = true;
							first_unproc_it = pit;
						}
						continue;
					}
					packages_to_process.erase(pit);
				}
				if (!unproc_one)
					first_unproc_it = pit;

			}
			else
			{
				sch.insert_package(package, best_vehicle, best_pos, from_node, to_node, new_from_node, new_to_node);

				DPDP_ASSERT_ABORT(sch.getRoute(best_vehicle)->verify_pickup_and_delivery_quantities());
				PackageList::iterator next_pit = pit;
				++next_pit;
				first_unproc_it = next_pit;
				packages_to_process.erase(pit);

				bool unproc_one = false;
				for (pit = next_pit; pit != packages_to_process.end(); pit = next_pit)
				{
					if ((*pit)->original_order->pickup_factory != package->original_order->pickup_factory)
						break;

					if ((*pit)->original_order->delivery_factory != package->original_order->delivery_factory)
						break;

					++next_pit;
					if (!sch.add_package_with_test(*pit, best_vehicle, from_node, to_node))
					{
						if (!unproc_one)
						{
							first_unproc_it = pit;
							unproc_one = true;
						}

						continue;
					}

					packages_to_process.erase(pit);
				}
				if (!unproc_one)
					first_unproc_it = pit;
			}
		}
		else
		{
			first_unproc_it = pit;
			++first_unproc_it;
		}
	}

	return 0;
}
static bool common_pickup_delivery_factory(const Package* a, const Package* b)
{
	return (a->original_order->pickup_factory == b->original_order->pickup_factory && a->original_order->delivery_factory == b->original_order->delivery_factory);

}

void LocalSearchSolver::rescheduleDelayedVehicles(Scheduler& sch)
{
	const int num_vehicles = probdata->getNumVehicles();
	sch.evaluate();
	std::list<std::pair<int, const Package*> > sorted_packages;
	PackageList packages_to_process;

	std::map<const Factory*, std::list<std::pair<SchRoute*, SchNode*> > > bottlenecks;
	for (int vehicle_id = 0; vehicle_id < num_vehicles; ++vehicle_id)
	{
		SchRoute* route = sch.getRoute(vehicle_id);
		for (SchNode* node = route->first; node; node = node->succ)
		{
			 
			if (node->leave_time - node->duration >= node->arrive_time + 100 )
			{
				if( node->node_type != CURRENT_NODE)
					bottlenecks[node->factory].push_back(std::make_pair(route, node));
			}
		}
	}

#ifdef DPDP_PRINT
	for (std::map<const Factory*, std::list<std::pair<SchRoute*, SchNode*> > >::iterator mit = bottlenecks.begin(); mit != bottlenecks.end(); ++mit) {
		for (std::list<std::pair<SchRoute*, SchNode*> >::iterator it = mit->second.begin(); it != mit->second.end(); ++it)
		{
			SchNode* node = it->second;
			int wait_time = node->leave_time - node->duration - node->arrive_time;
			std::cout << "V" << it->first->vehicle->id + 1 << " waits at factory " << node->factory->inputfactory->id  << " for " << wait_time << " sec\n";
			sch.printRoute(std::cout, it->first->vehicle->id, true);
		}
	}
#endif
	return;
	for (int vehicle_id = 0; vehicle_id < num_vehicles; ++vehicle_id)
	{
		for (SchNode* node = sch.getRoute(vehicle_id)->first; node; node = node->succ)
		{
			if (bottlenecks.find(node->factory) != bottlenecks.end())
			{
				sch.remove_all_packages(vehicle_id, packages_to_process);
				break;
			}
		}
	}
	for (PackageList::iterator pit = packages_to_process.begin(); pit != packages_to_process.end(); ++pit)
	{
		const Package* p = *pit;

		int travel_time = probdata->getTravelTime(p->original_order->pickup_factory->id, p->original_order->delivery_factory->id);
		sorted_packages.push_back(std::make_pair(travel_time, p));
	}
	sorted_packages.sort(DecrLength());
	packages_to_process.clear();
	for (std::list<std::pair<int, const Package*> >::iterator pit = sorted_packages.begin(); pit != sorted_packages.end(); ++pit)
		packages_to_process.push_back(pit->second);
	dispatch(sch, packages_to_process);
}
//
struct Transport
{
	const Factory* pickup_factory;
	const double demand;
	std::list<std::pair<const Factory*, double> > delivery_factories;
	Transport(const Factory* _pickup, double _demand)
		: pickup_factory(_pickup), demand(_demand)
	{

	}
};

static bool decr_total_transportation_demand(const Transport& t1, const Transport& t2)
{
	return t1.demand > t2.demand;
}

static bool decr_transportation_demand(const std::pair<const Factory*, double>& a, const std::pair<const Factory*, double>& b)
{
	return a.second > b.second;
}

struct VehicleArrival
{
	int vehicle_id;
	int arrival_time;
	double remaining_capacity;
	SchNode* node;

	VehicleArrival(int _v, int _arrival_time, double _remaining_capacity, SchNode* _node)
		: vehicle_id(_v), arrival_time(_arrival_time), remaining_capacity(_remaining_capacity), node(_node)
	{
	}
};

static bool incr_arrival_time(const VehicleArrival& a, const VehicleArrival& b)
{
	return a.arrival_time < b.arrival_time;
}

static bool decr_demand(const std::pair<double, std::list<const Package*> >& a, const std::pair<double, std::list<const Package*> >& b)
{
	return a.first > b.first;
}

void LocalSearchSolver::calcArrivalTime(Scheduler& sch, int vehicle_id, const Factory* pickup_factory, int& arrival_time, double& remaining_capacity, SchNode*& route_node)
{
	SchRoute& route = *sch.getRoute(vehicle_id);

	remaining_capacity = probdata->getVehicle(vehicle_id)->capacity;

	if (route.len == 1 && route.first->factory == pickup_factory)
	{
		route_node = route.first;
		arrival_time = route.first->arrive_time;
		return;
	}

	std::vector<double> carried_demand(route.len, 0);
	int pos = 0;
	for (SchNode* n = route.first; n; n = n->succ)
		n->pos = pos++;

	double total_carried_demand = 0;
	for (PackageList::iterator pit = carrying_packages[vehicle_id].begin(); pit != carrying_packages[vehicle_id].end(); ++pit) {
		double d = (*pit)->getDemand();
		carried_demand[sch.getDeliveryNode(*pit)->pos] += d;
		total_carried_demand += d;
	}
	pos = 0;
	for (SchNode* n = route.first; n; n = n->succ)
	{
		total_carried_demand -= carried_demand[pos++];
		if (n->factory == pickup_factory) {
			arrival_time = n->arrive_time;
			route_node = n;
			remaining_capacity -= total_carried_demand;
			for (std::list<const Package*>::iterator pit = n->pickup_packages.begin(); pit != n->pickup_packages.end(); ++pit)
			{
				remaining_capacity -= (*pit)->getDemand();
			}
			return;
		}
	}
	route_node = NULL;
	arrival_time = route.last->leave_time + probdata->getTravelTime(route.last->factory, pickup_factory);
}



int LocalSearchSolver::constructSch(PackageList& packages_to_process, Scheduler& sch, std::vector<SchRoute*>& best_route, double &best_value)
{
	const int num_packages = (int)packages_to_process.size();
	const int num_vehicles = probdata->getNumVehicles();
	std::list< std::pair<int, const Package*> > urgent;
	std::list< std::pair<int, const Package*> > easy;
	const int current_time = calculateLatestUpdateTime();

	/* split packages : packages_to_process -> urgent, easy */
	for (PackageList::iterator pit = packages_to_process.begin(); pit != packages_to_process.end(); ++pit)
	{
		const Package* pack = *pit;
		int travel_time = probdata->getTravelTime(pack->original_order->pickup_factory, pack->original_order->delivery_factory);
		int duration = getLoadingSeconds(pack->getDemand()) + travel_time + getUnloadingSeconds(pack->getDemand()) + DOCK_APPROACHING_TIME;
		int lateness = current_time + duration - pack->original_order->completion_time;

		if (lateness > -3600)
			urgent.push_back(std::make_pair(lateness, pack));
		else
			easy.push_back(std::make_pair(travel_time, pack));
	}
	/* order urgent packages */
	orderPackages3(urgent, packages_to_process);
	dispatch(sch, packages_to_process);

	for (PackageList::iterator pit = packages_to_process.begin(); pit != packages_to_process.end(); ++pit)
	{
		const Package* pack = *pit;
		int travel_time = probdata->getTravelTime(pack->original_order->pickup_factory, pack->original_order->delivery_factory);
		easy.push_back(std::make_pair(travel_time, pack));
	}

	/* order easy packages */
	orderPackages(easy, DecrLength(), packages_to_process);
	dispatch(sch, packages_to_process);

	/* evaluate schedule */
	best_value = sch.evaluate();
	sch.save(best_route);

	return 0;
}

int LocalSearchSolver::constructSch_v2(PackageList& packages_to_process, Scheduler& sch, std::vector<SchRoute*>& best_route, double& best_value)
{
	const int num_packages = (int)packages_to_process.size();
	const int num_vehicles = probdata->getNumVehicles();
	std::list< std::pair<int, const Package*> > urgent;
	std::list< std::pair<int, const Package*> > easy;
	const int current_time = calculateLatestUpdateTime();

	/* split packages : packages_to_process -> urgent, easy */
	for (PackageList::iterator pit = packages_to_process.begin(); pit != packages_to_process.end(); ++pit)
	{
		const Package* pack = *pit;
		int travel_time = probdata->getTravelTime(pack->original_order->pickup_factory, pack->original_order->delivery_factory);
		int duration = getLoadingSeconds(pack->getDemand()) + travel_time + getUnloadingSeconds(pack->getDemand()) + DOCK_APPROACHING_TIME;
		int lateness = current_time + duration - pack->original_order->completion_time;

		if (lateness > -3600)
			urgent.push_back(std::make_pair(travel_time, pack));
		else
			easy.push_back(std::make_pair(travel_time, pack));
	}
	orderPackages(urgent, DecrLength(), packages_to_process);
	dispatch(sch, packages_to_process);

	for (PackageList::iterator pit = packages_to_process.begin(); pit != packages_to_process.end(); ++pit)
	{
		const Package* pack = *pit;
		int travel_time = probdata->getTravelTime(pack->original_order->pickup_factory, pack->original_order->delivery_factory);
		easy.push_back(std::make_pair(travel_time, pack));
	}
	orderPackages(easy, DecrLength(), packages_to_process);
	dispatch(sch, packages_to_process);


	/* evaluate schedule */
	best_value = sch.evaluate();
	sch.save(best_route);

	return 0;
}

int LocalSearchSolver::constructSch_v3(PackageList& packages_to_process, Scheduler& sch, std::vector<SchRoute*>& best_route, double& best_value)
{
	const int num_vehicles = probdata->getNumVehicles();
	const int num_factories = probdata->getNumFactories();
	sch.evaluate();
	int min_arrive_time = std::numeric_limits<int>::max();
	int vi_extend = -1;
	std::vector<PackageList> paf(num_factories);
	int num_packages = packages_to_process.size();
	for (PackageList::iterator pit = packages_to_process.begin(); pit != packages_to_process.end(); ++pit)
	{
		cPtr p = *pit;
		paf[p->original_order->pickup_factory->id].push_back(p);
	}
	while (num_packages > 0) {
		for (int vi = 0; vi < num_vehicles; ++vi)
		{
			if (sch.getRoute(vi)->last->arrive_time < min_arrive_time) {
				vi_extend = vi;
				min_arrive_time = sch.getRoute(vi)->last->arrive_time;
			}
		}
		SchRoute* route = sch.getRoute(vi_extend);
		SchNode* from_node = route->last;
		if (paf[from_node->factory->id].empty()) {
			int min_tt = std::numeric_limits<int>::max();
			int closest_f = -1;
			for (int f = 0; f < num_factories; ++f)
			{
				if (f == from_node->factory->id) continue;
				if (paf[f].empty()) continue;
				int tt = probdata->getTravelTime(probdata->getFactory(from_node->factory->id), probdata->getFactory(f));
				if (tt < min_tt) {
					min_tt = tt;
					closest_f = f;
				}
			}
			if (closest_f < 0) continue;
			SchNode* new_node = new SchNode(GENERAL_NODE, probdata->getFactory(closest_f));
			route->push_back(new_node);
			sch.evaluate();

			from_node = new_node;
		}
		PackageList& pl = paf[from_node->factory->id];
		pl.sort(GroupByPickup());
		PackageList::iterator next_it;
		std::list<std::pair<int, PackageList> > batch_lists;
		for (PackageList::iterator pit = pl.begin(); pit != pl.end(); pit = next_it)
		{
			double sum_demand = 0;
			PackageList batch;
			int min_due_date = std::numeric_limits<int>::max();
			for (next_it = pit; next_it != pl.end() && common_pickup_delivery_factory(*pit, *next_it); ++next_it)
			{
				sum_demand += (*next_it)->getDemand();
				batch.push_back(*next_it);
				if ((*next_it)->original_order->completion_time < min_due_date)
					min_due_date = (*next_it)->original_order->completion_time;
			}
			double load_time = getLoadingSeconds(sum_demand);

			int lateness = from_node->leave_time +
				probdata->getTravelTime(probdata->getFactory(from_node->factory->id), probdata->getFactory(batch.front()->original_order->delivery_factory->id));
			lateness -= min_due_date;

			batch_lists.push_back(std::move(std::make_pair(lateness, std::move(batch))));
		}
		batch_lists.sort(DecrFirst<int>());
		
		PackageList& batch = batch_lists.front().second;
		double sum_demand = 0;
		std::set<cPtr> assigned;
		double capacity = probdata->getVehicle(vi_extend)->capacity;
		for (PackageList::iterator it = batch.begin(); it != batch.end(); ++it)
		{
			if (sum_demand + (*it)->getDemand() <= capacity + DPDP_EPSILON) {
				sum_demand += (*it)->getDemand();
				assigned.insert(*it);
				bool new_from_node, new_to_node;
				SchNode* to_node;
				sch.insert_package(*it, vi_extend, from_node, from_node, to_node, new_from_node, new_to_node);
			}
		}
		num_packages -= assigned.size();
		for (PackageList::iterator it = pl.begin(); it != pl.end();) {
			if (assigned.find(*it) != assigned.end())
				it = pl.erase(it);
			else
				++it;
		}
		
	}
	best_value = sch.evaluate();
	sch.save(best_route);
	return 0;
}

LSSolution* LocalSearchSolver::solve( long long time_limit, int constr_method )
{
	std::vector<SchRoute*> best_route(probdata->getNumVehicles(), NULL);
	PackageList packages_to_process;
	LSSolution* solution = NULL;
	Scheduler scheduler(*probdata, packages, destinations, carrying_packages);

	try
	{
		/* initialize packages */
		for (PackageList::const_iterator package_it = unallocated_packages.cbegin(); package_it != unallocated_packages.cend(); ++package_it)
			packages_to_process.push_back(*package_it);

		/* initialize scheduler */
		scheduler.init_routes();

		double best_value = DBL_MAX;
		//	process_busy_factories(scheduler, packages_to_process);


		switch (constr_method)
		{
		case 0:
		{
			scheduler.use_squared_term(false);
			DPDP_CALL_THROW(constructSch_v3(packages_to_process, scheduler, best_route, best_value));
			PD pd(*probdata, packages, scheduler);
			pd.import_schedule();
			const bool improved = PDLocalSearch(&pd, probdata).run(LSSOLVER_LOCAL_SEARCH_TIME_LIMIT);
			//const bool improved = localsearchStart( scheduler, time_for_search );

			if (improved)
			{
				/* best route ... */
				scheduler.save(best_route);
				scheduler.use_squared_term(false);
				best_value = scheduler.evaluate();
			}
			break;
		}
		case 1:
		{
			scheduler.use_squared_term(LSSOLVER_USE_EVALUATE_SQUARED_TERM);
			DPDP_CALL_THROW(constructSch(packages_to_process, scheduler, best_route, best_value));
			if (LSSOLVER_USE_LOCAL_SEARCH) {
				localsearchStart(scheduler, LSSOLVER_LOCAL_SEARCH_TIME_LIMIT, best_route, best_value);
			}
			if (LSSOLVER_USE_TABU_SEARCH) {
				tabuSearch(scheduler, LSSOLVER_LOCAL_SEARCH_TIME_LIMIT, best_route, best_value);
			}
			if (LSSOLVER_USE_LOCAL_SEARCH_WITH_RESCHEDULE) {
				localSearchWithReschedule(scheduler, LSSOLVER_LOCAL_SEARCH_TIME_LIMIT, best_route, best_value);
			}

			break;
		}
		}

		//PD pd(*probdata, packages,  scheduler) ;
		//pd.import_schedule();

		//long long time_for_search = std::min( time_limit, std::min( LSSOLVER_LOCAL_SEARCH_TIME_LIMIT, remaining_time() ));

		//if( LSSOLVER_USE_LOCAL_SEARCH )
		//{
		//	const bool improved = PDLocalSearch( &pd, probdata ).run( time_for_search );
		//	//const bool improved = localsearchStart( scheduler, time_for_search );

		//	if( improved )
		//	{
		//		/* best route ... */
		//		scheduler.save( best_route );
		//		best_value = scheduler.evaluate();
		//	}
		//}

		//if( LSSOLVER_USE_TABU_SEARCH )
		//{
		//	tabuSearch( scheduler, time_for_search, best_route, best_value );
		//}

#ifdef DPDP_GEN_LOGFILES
#ifdef DPDP_COMPUTE_STATISTICS
		stat.write_schedule_stats(scheduler);
#endif
#endif
		solution = new LSSolution();
		solution->value = best_value;

		/* transform routes */
		for( int vid = 0; vid < probdata->getNumVehicles(); ++vid )
		{
			LSRoute* route = transformRoute( *best_route[vid] );

			if( route->checkDuplicateNodes() )
				dpdpPrintfWarn( "duplicate nodes on vehicle route V%d\n", vid + 1 );

			solution->routes.push_back(route);
		}

		/* distribute remaining packages */
		distributeRemainingPackages(solution, packages_to_process);
	}
	catch (...)
	{
		dpdpPrintfError( "some exception has occueured during calculation, no solution is found\n" );

		if( solution != NULL )
		{
			delete solution;
			solution = NULL;
		}
	}

	/* terminate (free memory) */
	for( int vid = 0; vid < probdata->getNumVehicles(); ++vid )
	{
		if( best_route[vid] != NULL )
			delete best_route[vid];
	}

	return solution;
}

int LocalSearchSolver::run()
{
	int retcode = 0;

	LSSolution* best_solution = NULL;

#ifdef DPDP_COMPUTE_STATISTICS
	Statistics stat(*probdata);
	stat.compute();
#endif
	/* initialize solver */
	DPDP_CALL( init() );



#ifdef DPDP_GEN_LOGFILES
	writeItemInfo();
#ifdef DPDP_COMPUTE_STATISTICS
	stat.writeStatistics();
#endif
#endif

	/* solve problem in multiple ways */
	long long num_solvers = 0;
	for (int i = 0; i < NUM_CONSTRUCTION_METHODS; ++i)
	{
		if (use_construction_method[i]) ++num_solvers;
	}
	DPDP_ASSERT_ABORT( 0 < num_solvers );

	for (int i = 0; i < NUM_CONSTRUCTION_METHODS; ++i)
	{
		if (use_construction_method[i])
		{
			LSSolution* solution = solve(GLOBAL_TIME_LIMIT / num_solvers, i);
			if( NULL ==best_solution || solution->value < best_solution->value ) 
			{
				if(NULL != best_solution) delete best_solution;
				best_solution = solution;
			}
		}
	}

	if( NULL == best_solution )
	{
		retcode = ERROR_SOLVING_GENERAL;
		goto TERMINATE;
	}

	/* process (write) best solution */
#ifdef DPDP_GEN_LOGFILES
	writeLogfile( best_solution );
#endif

	writeDestinationFile( best_solution );
	writeRouteFile( best_solution );

TERMINATE:
	if (NULL != best_solution)
		delete best_solution;

	return retcode;
}

int LocalSearchSolver::distributeRemainingPackages(LSSolution* solution, std::list<const Package*>& packages_to_process)
{
	int vehicle_id = 0;

	for (std::list<const Package*>::const_iterator package_it = packages_to_process.cbegin(); package_it != packages_to_process.cend(); ++package_it)
	{
		DPDP_CALL(pushBackPackageToRoute(solution->routes[vehicle_id], *package_it));
		vehicle_id = (vehicle_id + 1) % probdata->getNumVehicles();
	}

	return 0;
}

int LocalSearchSolver::distributeRemainingPackagesByScheduler(Scheduler& scheduler, PackageList& packages_to_distribute)
{
	int vehicle_id = -1;

	SchNode* temp_node_1;
	SchNode* temp_node_2;
	bool temp_bool_1;
	bool temp_bool_2;

	for (PackageList::const_iterator package_it = packages_to_distribute.cbegin(); package_it != packages_to_distribute.cend(); ++package_it)
	{
		for (int i = 0; i < probdata->getNumVehicles(); ++i)
		{
			vehicle_id = (vehicle_id + 1) % probdata->getNumVehicles();

			SchRoute* route = scheduler.getRoute(vehicle_id);

			if (route->last != NULL)
			{
				scheduler.insert_package(*package_it, vehicle_id, route->last, temp_node_1, temp_node_2, temp_bool_1, temp_bool_2);
				break;
			}
		}
	}

	return 0;
}

int LocalSearchSolver::pushBackPackageToRoute(LSRoute* route, const Package* package)
{
	DPDP_ASSERT(route != NULL);
	DPDP_ASSERT(package != NULL);

	/* pick-up */
	if (route->nodes.empty() || route->nodes.back()->factory != package->original_order->pickup_factory)
	{
		LSNode* pickup_node = new LSNode();
		pickup_node->factory = package->original_order->pickup_factory;
		pickup_node->arrive_time = 0;
		pickup_node->leave_time = 0;
		pickup_node->pickup_packages.push_back(package);

		route->nodes.push_back(pickup_node);
	}
	else
	{
		route->nodes.back()->pickup_packages.push_back(package);
	}

	/* delivery */
	LSNode* delivery_node = new LSNode();
	delivery_node->factory = package->original_order->delivery_factory;
	delivery_node->arrive_time = 0;
	delivery_node->leave_time = 0;
	delivery_node->delivery_packages.push_back(package);

	route->nodes.push_back(delivery_node);

	return 0;
}

bool LocalSearchSolver::testItemOnPackage(const Package* package, const OrderItem* item, const double capacity) const
{
	DPDP_ASSERT(package != NULL);
	DPDP_ASSERT(item != NULL);

	if (package->original_order != NULL && package->original_order != item->order)
		return false; // package must refer to a single order

	if (capacity + DPDP_EPSILON < package->getDemand() + item->demand)
		return false; // package must respect the capacity limit

	return true;
}

LSRoute* LocalSearchSolver::transformRoute(const SchRoute& original_route) const
{
	// TODO (hmarko) : 
	// - fiktiv elso elemet nem kellene beletenni
	// - ennek megfeleloen kellene allitani arrive and leav timokat

	typedef std::list<const Package*> MPList;
	typedef std::list<const OrderItem*> ItemList;

	LSRoute* transformed_route = NULL;
	LSNode* prev_node = NULL;

	transformed_route = new LSRoute();

	for (SchNode* node_it = original_route.first; node_it != NULL; node_it = node_it->succ)
	{
		if (node_it->delivery_packages.empty() && node_it->pickup_packages.empty() && node_it->node_type != DESTINATION_NODE)
			continue; // empty node should not be added

		LSNode* curr_node = NULL;

		/* check whether new node is needed */
		if (prev_node == NULL || prev_node->factory != node_it->factory)
		{
			curr_node = new LSNode();
			curr_node->factory = node_it->factory;
			curr_node->arrive_time = (node_it)->arrive_time; // TODO
			curr_node->leave_time = (node_it)->leave_time;   // TODO

			transformed_route->nodes.push_back(curr_node);
		}
		else
		{
			curr_node = prev_node;
		}

		/* copy lists */
		for (MPList::const_iterator package_it = (node_it)->delivery_packages.cbegin(); package_it != (node_it)->delivery_packages.cend(); ++package_it)
			curr_node->delivery_packages.push_back((*package_it));

		for (MPList::const_iterator package_it = (node_it)->pickup_packages.cbegin(); package_it != (node_it)->pickup_packages.cend(); ++package_it)
			curr_node->pickup_packages.push_back((*package_it));

		/* adjust data */
		prev_node = curr_node;
	}

	return transformed_route;
}

int LocalSearchSolver::writeLSNode(const LSNode* node, FILE* file) const
{
	typedef std::list<const OrderItem*> ItemList;

	DPDP_ASSERT(node != NULL);
	DPDP_ASSERT(file != NULL);

	char filebuffer[255];

	fputs("{\n", file); // main object >>>

	snprintf(filebuffer, 255, "\"factory_id\": \"%s\",\n", node->factory->inputfactory->id.c_str());
	fputs(filebuffer, file);

	snprintf(filebuffer, 255, "\"lng\": %f,\n", node->factory->inputfactory->longitude);
	fputs(filebuffer, file);

	snprintf(filebuffer, 255, "\"lat\": %f,\n", node->factory->inputfactory->latitude);
	fputs(filebuffer, file);

	snprintf(filebuffer, 255, "\"arrive_time\": %d,\n", node->arrive_time);
	fputs(filebuffer, file);

	snprintf(filebuffer, 255, "\"leave_time\": %d,\n", node->leave_time);
	fputs(filebuffer, file);

	int num_items = 0;
	for (PackageList::const_iterator package_it = node->pickup_packages.cbegin(); package_it != node->pickup_packages.cend(); ++package_it)
		num_items += (int)(*package_it)->getOrderItems().size();

	fputs("\"pickup_item_list\": [\n", file);
	for (PackageList::const_iterator package_it = node->pickup_packages.cbegin(); package_it != node->pickup_packages.cend(); ++package_it)
	{
		const ItemList& items = (*package_it)->getOrderItems();

		for (ItemList::const_iterator item_it = items.cbegin(); item_it != items.cend(); ++item_it)
		{
			--num_items;

			snprintf(filebuffer, 255, "\"%s\"", (*item_it)->input_order_item->id.c_str());
			fputs(filebuffer, file);

			if (0 < num_items)
				fputs(",", file);
			fputs("\n", file);
		}
	}
	fputs("],\n", file);

	DPDP_ASSERT(0 == num_items);

	for (PackageList::const_reverse_iterator package_it = node->delivery_packages.crbegin(); package_it != node->delivery_packages.crend(); ++package_it)
		num_items += (int)(*package_it)->getOrderItems().size();

	fputs("\"delivery_item_list\": [\n", file);
	for (PackageList::const_iterator package_it = node->delivery_packages.cbegin(); package_it != node->delivery_packages.cend(); ++package_it)
	{
		const ItemList& items = (*package_it)->getOrderItems();

		for (ItemList::const_reverse_iterator item_it = items.crbegin(); item_it != items.crend(); ++item_it)
		{
			--num_items;

			snprintf(filebuffer, 255, "\"%s\"", (*item_it)->input_order_item->id.c_str());
			fputs(filebuffer, file);

			if (0 < num_items)
				fputs(",", file);
			fputs("\n", file);
		}
	}
	fputs("]\n", file);

	DPDP_ASSERT(0 == num_items);

	fputs("}\n", file); // <<< main object

	return 0;
}

int LocalSearchSolver::writeDestinationFile(const LSSolution* solution) const
{
	DPDP_ASSERT(solution != NULL);

	FILE* file = NULL;
	char filebuffer[255];

	/* open file */
	file = fopen(OUTPUT_DESTINATION_FILE, "w");

	if (NULL == file)
	{
		dpdpPrintfError("could not open solution file \"%s\" for writing!\n", OUTPUT_DESTINATION_FILE);
		return ERROR_FILE_NOTFOUND;
	}

	fputs("{\n", file); // main object >>>

	for (int v = 0; v < probdata->getNumVehicles(); ++v)
	{
		const Vehicle* vehicle = probdata->getVehicle(v);
		const LSRoute* route = solution->routes[v];

		if (route->nodes.empty())
		{
			snprintf(filebuffer, 255, "\"%s\": null", vehicle->input_vehicle->id.c_str());
			fputs(filebuffer, file);
		}
		else
		{
			snprintf(filebuffer, 255, "\"%s\":\n", vehicle->input_vehicle->id.c_str());
			fputs(filebuffer, file);

			DPDP_CALL(writeLSNode(route->nodes[0], file));
		}

		if (v < probdata->getNumVehicles() - 1)
			fputs(",", file);
		fputs("\n", file);
	}

	fputs("}\n", file); // <<< main object

	fclose(file);

	return 0;
}

int LocalSearchSolver::writeLogfile(const LSSolution* sol) const
{
	std::ofstream f(LSSOLVER_LOG_FILE, std::ios::app);
	const std::vector<LSRoute*>& routes = sol->routes;
	f << routes.size() << std::endl;
	for (int v = 0; v < routes.size(); ++v) {
		const LSRoute* route = routes[v];
		const Vehicle* vehicle = probdata->getVehicle(v);
		const Factory* current_factory = vehicle->current_factory;
		const Factory* destination_factory = (vehicle->destination != NULL ? vehicle->destination->factory : NULL);
		f << vehicle->input_vehicle->id << ' ' << (current_factory != NULL ? current_factory->inputfactory->id : "0");
		f << ' ' << (destination_factory != NULL ? destination_factory->inputfactory->id : "0");
		double demand = 0;
		for (PackageList::const_iterator pit = carrying_packages[v].begin(); pit != carrying_packages[v].end(); ++pit)
			demand += (*pit)->getDemand();

		f << ' ' << demand;

		f << ' ' << vehicle->arrive_time / 600 << ' ' << vehicle->leave_time / 600;
		if (vehicle->destination) {
			f << ' ' << vehicle->destination->arrive_time / 600 << ' ' << vehicle->destination->leave_time / 600;
		}
		else {
			f << " 0 0";
		}
		for (int i = 0; i < route->nodes.size(); ++i) {
			if (route->nodes[i]->factory != destination_factory) {
				f << ' ' << route->nodes[i]->factory->inputfactory->id << ' ' << route->nodes[i]->arrive_time / 600 << ' ' << route->nodes[i]->leave_time / 600;

				break;
			}
		}
		f << std::endl;

	}
	//	f << std::endl;

	f << packages.size() << std::endl;
	for (std::vector<Package*> ::const_iterator pit = packages.cbegin(); pit != packages.cend(); ++pit) {
		const Package* pack = *pit;
		f << pack->original_order->long_id << ' ' << pack->original_order->pickup_factory->inputfactory->id << ' ' << pack->original_order->delivery_factory->inputfactory->id << std::endl;
	}

	return 0;
}

void LocalSearchSolver::writeItemInfo()
{
	std::ofstream file;
	file.open(LSSOLVER_ITEMINFO_FILE, std::ios_base::app);

	file << "TIMEINFO" << ";";
	file << calculateLatestUpdateTime() << "\n";

	for (int vehicle_id = 0; vehicle_id < probdata->getNumVehicles(); ++vehicle_id)
	{
		const Vehicle* vehicle = probdata->getVehicle(vehicle_id);

		for (std::list<const OrderItem*>::const_iterator item_it = vehicle->carrying_items.cbegin(); item_it != vehicle->carrying_items.cend(); ++item_it)
		{
			file << "ITEMINFO" << ";";
			file << (*item_it)->input_order_item->id << ";";
			file << (*item_it)->demand << ";";
			file << (*item_it)->creation_time << ";";
			file << (*item_it)->completion_time << ";";
			file << vehicle->input_vehicle->id << ";";
			file << vehicle->update_time << ";";
			file << (*item_it)->pickup_factory->inputfactory->id << ";";
			file << (*item_it)->delivery_factory->inputfactory->id << "\n";
		}
	}

	file.close();
}

int LocalSearchSolver::writeRouteFile(const LSSolution* solution) const
{
	DPDP_ASSERT(solution != NULL);
	DPDP_ASSERT(solution->routes.size() == probdata->getNumVehicles());

	FILE* file = NULL;
	char filebuffer[255];

	/* open file */
	file = fopen(OUTPUT_ROUTE_FILE, "w");

	if (NULL == file)
	{
		dpdpPrintfError("could not open solution file \"%s\" for writing!\n", OUTPUT_DESTINATION_FILE);
		return ERROR_FILE_NOTFOUND;
	}

	fputs("{\n", file); // main object >>>

	for (int v = 0; v < probdata->getNumVehicles(); ++v)
	{
		//		const Vehicle* vehicle = probdata->getVehicle( v );
		const LSRoute* route = solution->routes[v];

		snprintf(filebuffer, 255, "\"%s\": [\n", probdata->getVehicle(v)->input_vehicle->id.c_str());
		fputs(filebuffer, file);

		for (int i = 1; i < route->nodes.size(); ++i) // first node should not written into this file but into the destination file
		{
			DPDP_CALL(writeLSNode(route->nodes[i], file));

			if (i < route->nodes.size() - 1)
				fputs(",", file);
			fputs("\n", file);
		}

		fputs("]", file);
		if (v < probdata->getNumVehicles() - 1)
			fputs(",", file);
		fputs("\n", file);
	}

	fputs("}\n", file); // <<< main object

	fclose(file);

	return 0;
}

int LocalSearchSolver::writeRouteFileFromSchedule(Scheduler* scheduler) const
{
	DPDP_ASSERT_ABORT(scheduler != NULL);

	FILE* file = NULL;
	char filebuffer[255];

	/* open file */
	file = fopen(OUTPUT_ROUTE_FILE, "w");

	if (NULL == file)
	{
		dpdpPrintfError("could not open solution file \"%s\" for writing!\n", OUTPUT_DESTINATION_FILE);
		return ERROR_FILE_NOTFOUND;
	}

	fputs("{\n", file); // main object >>>

	for (int vehicle_id = 0; vehicle_id < probdata->getNumVehicles(); ++vehicle_id)
	{
		const SchRoute& route = *scheduler->getRoute(vehicle_id);

		snprintf(filebuffer, 255, "\"%s\": [\n", probdata->getVehicle(vehicle_id)->input_vehicle->id.c_str());
		fputs(filebuffer, file);

		for (SchNode* node = route.first; node != NULL; node = node->succ)
		{
			if (route.first == node)
				continue; // first node should not written into this file but into the destination file

			DPDP_CALL(writeSchNode(node, file));

			if (node->succ != NULL)
				fputs(",", file);
			fputs("\n", file);
		}

		fputs("]", file);
		if (vehicle_id < probdata->getNumVehicles() - 1)
			fputs(",", file);
		fputs("\n", file);
	}

	fputs("}\n", file); // <<< main object

	fclose(file);

	return 0;
}

int LocalSearchSolver::writeDestinationFileFromSchedule(Scheduler* scheduler) const
{
	DPDP_ASSERT(scheduler != NULL);

	FILE* file = NULL;
	char filebuffer[255];

	/* open file */
	file = fopen(OUTPUT_DESTINATION_FILE, "w");

	if (NULL == file)
	{
		dpdpPrintfError("could not open solution file \"%s\" for writing!\n", OUTPUT_DESTINATION_FILE);
		return ERROR_FILE_NOTFOUND;
	}

	fputs("{\n", file); // main object >>>

	for (int vehicle_id = 0; vehicle_id < probdata->getNumVehicles(); ++vehicle_id)
	{
		const Vehicle* vehicle = probdata->getVehicle(vehicle_id);
		const SchRoute& route = *scheduler->getRoute(vehicle_id);

		if (NULL == route.first)
		{
			snprintf(filebuffer, 255, "\"%s\": null", vehicle->input_vehicle->id.c_str());
			fputs(filebuffer, file);
		}
		else
		{
			snprintf(filebuffer, 255, "\"%s\":\n", vehicle->input_vehicle->id.c_str());
			fputs(filebuffer, file);

			DPDP_CALL(writeSchNode(route.first, file));
		}

		if (vehicle_id < probdata->getNumVehicles() - 1)
			fputs(",", file);
		fputs("\n", file);
	}

	fputs("}\n", file); // <<< main object

	fclose(file);

	return 0;
}

int LocalSearchSolver::writeSchNode(const SchNode* node, FILE* file) const
{
	typedef std::list<const OrderItem*> ItemList;

	DPDP_ASSERT(node != NULL);
	DPDP_ASSERT(file != NULL);

	char filebuffer[255];

	fputs("{\n", file); // main object >>>

	snprintf(filebuffer, 255, "\"factory_id\": \"%s\",\n", node->factory->inputfactory->id.c_str());
	fputs(filebuffer, file);

	snprintf(filebuffer, 255, "\"lng\": %f,\n", node->factory->inputfactory->longitude);
	fputs(filebuffer, file);

	snprintf(filebuffer, 255, "\"lat\": %f,\n", node->factory->inputfactory->latitude);
	fputs(filebuffer, file);

	snprintf(filebuffer, 255, "\"arrive_time\": %d,\n", node->arrive_time);
	fputs(filebuffer, file);

	snprintf(filebuffer, 255, "\"leave_time\": %d,\n", node->leave_time);
	fputs(filebuffer, file);

	int num_items = 0;
	for (PackageList::const_iterator package_it = node->pickup_packages.cbegin(); package_it != node->pickup_packages.cend(); ++package_it)
		num_items += (int)(*package_it)->getOrderItems().size();

	fputs("\"pickup_item_list\": [\n", file);
	for (PackageList::const_iterator package_it = node->pickup_packages.cbegin(); package_it != node->pickup_packages.cend(); ++package_it)
	{
		const ItemList& items = (*package_it)->getOrderItems();

		for (ItemList::const_iterator item_it = items.cbegin(); item_it != items.cend(); ++item_it)
		{
			--num_items;

			snprintf(filebuffer, 255, "\"%s\"", (*item_it)->input_order_item->id.c_str());
			fputs(filebuffer, file);

			if (0 < num_items)
				fputs(",", file);
			fputs("\n", file);
		}
	}
	fputs("],\n", file);

	DPDP_ASSERT(0 == num_items);

	for (PackageList::const_reverse_iterator package_it = node->delivery_packages.crbegin(); package_it != node->delivery_packages.crend(); ++package_it)
		num_items += (int)(*package_it)->getOrderItems().size();

	fputs("\"delivery_item_list\": [\n", file);
	for (PackageList::const_iterator package_it = node->delivery_packages.cbegin(); package_it != node->delivery_packages.cend(); ++package_it)
	{
		const ItemList& items = (*package_it)->getOrderItems();

		for (ItemList::const_reverse_iterator item_it = items.crbegin(); item_it != items.crend(); ++item_it)
		{
			--num_items;

			snprintf(filebuffer, 255, "\"%s\"", (*item_it)->input_order_item->id.c_str());
			fputs(filebuffer, file);

			if (0 < num_items)
				fputs(",", file);
			fputs("\n", file);
		}
	}
	fputs("]\n", file);

	DPDP_ASSERT(0 == num_items);

	fputs("}\n", file); // <<< main object

	return 0;
}

int LocalSearchSolver::calculateLatestUpdateTime() const
{
	int lastUpdateTime = -1;
	const Vehicle* vehicle = NULL;

	for (int vehicle_id = 0; vehicle_id < probdata->getNumVehicles(); ++vehicle_id)
	{
		vehicle = probdata->getVehicle(vehicle_id);

		if (lastUpdateTime < vehicle->update_time)
			lastUpdateTime = vehicle->update_time;
	}

	return lastUpdateTime;
}

void LocalSearchSolver::countScheduledPackages(Scheduler& sch, std::vector<int>& package_count) const
{
	package_count.resize(packages.size());
	for (int i = 0; i < package_count.size(); ++i) {
		package_count[i] = 0;
	}
	for (int i = 0; i < probdata->getNumVehicles(); ++i) {
		SchRoute* route = sch.getRoute(i);
		for (SchNode* n = route->first; n; n = n->succ)
		{
			for (PackageList::iterator pit = n->pickup_packages.begin(); pit != n->pickup_packages.end(); ++pit) {
				package_count[(*pit)->id]++;
			}
			for (PackageList::iterator pit = n->delivery_packages.begin(); pit != n->delivery_packages.end(); ++pit) {
				package_count[(*pit)->id]++;
			}
		}
	}
}

bool LocalSearchSolver::verifyPackagecount(Scheduler& sch, const std::vector<int>& package_count) const
{
	bool ok = true;
	for (int vi = 0; vi < probdata->getNumVehicles(); ++vi) {
		SchRoute* route = sch.getRoute(vi);
		int status;
		if (!route->verifyRoute(status)) {
			dpdpPrintfError("Route of V%d is bad , status: %d\n", vi + 1, status);
			sch.printRoute(std::cerr, vi, false);
			ok = false;
		}
	}
	std::vector<int> current_package_count;
	countScheduledPackages(sch, current_package_count);
	for (int i = 0; i < package_count.size(); ++i)
		if (current_package_count[i] != current_package_count[i])
		{
			dpdpPrintfError("count of package %d  differs  ", i);
			ok = false;
		}
	return ok;
}

void LocalSearchSolver::localsearchStart(Scheduler& scheduler, const long long seconds_limits, std::vector<SchRoute*>& best_routes, double& best_value)
{
	dpdpPrintfTrace("start local search...\n");

	Timer ls_timer;
	ls_timer.setTimeLimit(seconds_limits);
	ls_timer.start();


	std::vector<int> package_count;
	countScheduledPackages(scheduler, package_count);
	int iteration = 1;
	for (; iteration < 100; ++iteration)
	{
		if (ls_timer.timeLimitReached())
		{
			dpdpPrintfDebug("[local search] time limit (%lld seconds) is reached (elapsed time: %lld seconds)\n", seconds_limits, ls_timer.getElapsedSeconds());
			break;
		}

		dpdpPrintfDebug("[local search] iteration %d...\n", iteration);

		if (!localsearchFindBestNeighbor(scheduler, &ls_timer, best_value) )
		{
			break;
		}
	}
	if( iteration >= 2 ) scheduler.save(best_routes);
	dpdpPrintfTrace("local search  ended after %d iteration(s) (elapsed time: %lld seconds)\n", iteration, ls_timer.getElapsedSeconds());
	DPDP_ASSERT_ABORT(verifyPackagecount(scheduler, package_count));

}

void LocalSearchSolver::localSearchWithReschedule(Scheduler& scheduler, const long long seconds_limits, std::vector<SchRoute*>& best_routes, double& best_value)
{
	dpdpPrintfTrace("start local search...\n");
	dpdpPrintfTrace("initial value: %.3f\n", best_value);

	Timer ls_timer;
	ls_timer.setTimeLimit(seconds_limits);
	ls_timer.start();

	std::vector<int> package_count;
	countScheduledPackages(scheduler, package_count);

	if( LSSOLVER_USE_SWAP_IMPROVE )
		swap_improve(scheduler);
	int iteration = 1;
	int num_consecutive_improve = 0;
	double best_neighbor_value = best_value;
	int num_reschedule = 0;
	for ( ; iteration < 100; ++iteration)
	{
		if (ls_timer.timeLimitReached())
		{
			dpdpPrintfDebug("[local search] time limit (%lld seconds) is reached (elapsed time: %lld seconds)\n", seconds_limits, ls_timer.getElapsedSeconds());
			break;
		}

		dpdpPrintfDebug("[local search] iteration %d...\n", iteration);

		if( localsearchFindBestNeighbor( scheduler, &ls_timer, best_neighbor_value ) )
		{
			++num_consecutive_improve;
		}
		else if( iteration == 1 || num_consecutive_improve > 0 )
		{
			if( best_neighbor_value < best_value - DPDP_EPSILON )
			{
				scheduler.save( best_routes );
				best_value = best_neighbor_value;
			}

			if( ++num_reschedule > 1 )
				break;

			takeOffPackages_2( scheduler );

			if (LSSOLVER_USE_SWAP_IMPROVE)
				swap_improve(scheduler);

			best_neighbor_value = scheduler.evaluate();
			num_consecutive_improve = 0;
		}
		else break;
	}

	if( best_neighbor_value < best_value - DPDP_EPSILON )
	{
		scheduler.save( best_routes );
		best_value = best_neighbor_value;
	}

	dpdpPrintfTrace( "local search  ended after %d iteration(s) (elapsed time: %lld seconds)\n", iteration, ls_timer.getElapsedSeconds() );
	DPDP_ASSERT_ABORT( verifyPackagecount( scheduler, package_count ) );
}

void LocalSearchSolver::tabuSearch(Scheduler& scheduler, const long long seconds_limits, std::vector<SchRoute*>& best_solution, double& best_sol_value)
{
	dpdpPrintfTrace("start tabu search...\n");

	Timer ls_timer;
	ls_timer.setTimeLimit(seconds_limits);
	ls_timer.start();

	best_sol_value = scheduler.evaluate();
	double best_neighbor_value = DBL_MAX;
	scheduler.save(best_solution);

	std::vector<int> package_count;
	countScheduledPackages(scheduler, package_count);
	TabuList tabu(20);

	for (int iteration = 1; iteration < 100; ++iteration)
	{
		if (ls_timer.timeLimitReached())
		{
			dpdpPrintfDebug("[tabu search] time limit (%lld seconds) is reached (elapsed time: %lld seconds)\n", seconds_limits, ls_timer.getElapsedSeconds());
			break;
		}

		dpdpPrintfDebug("[tabu search] iteration %d...\n", iteration);

		if (!tabusearchMove(scheduler, &ls_timer, iteration, tabu, best_sol_value, best_neighbor_value)) break;

		if(best_neighbor_value <= best_sol_value-DPDP_EPSILON)
		{
			scheduler.save(best_solution);
			best_sol_value = best_neighbor_value;

		}
	}
	DPDP_ASSERT_ABORT(verifyPackagecount(scheduler, package_count));
}

bool LocalSearchSolver::tabusearchMove(Scheduler& scheduler, const Timer* timer, int iter, TabuList& tabu, const double best_sol_value, double &best_neighbor_value)
{
#ifdef DPDP_DEBUG
	std::vector<int> init_package_count;
	countScheduledPackages(scheduler, init_package_count);
#endif

	int best_sender_id = -1;
	int best_receiver_id = -1;
	SchNode* best_sender_node = NULL;
	SchNode* best_receiver_node = NULL;

	PackageList best_list;
	SchNode* neighbor_position;
	double neighbor_value;
	best_neighbor_value = DBL_MAX;

	/* find improvement */
	for (int sender_id = 0; sender_id < probdata->getNumVehicles(); ++sender_id)
	{
		/* check time limit */
		if (timer != NULL && timer->timeLimitReached())
		{
			dpdpPrintfDebug("[tabu search] time limit has been reached (elapsed time: %lld seconds)\n", timer->getElapsedSeconds());
			goto MOVE_TO_BEST_NEIGHBOR;
		}

		/* go through possible packages */
		SchRoute& sender_route = *scheduler.getRoute(sender_id);

		std::list< std::pair<SchNode*, PackageList > > possible_lists_to_send; // list of (node,(list,...,list)) pairs
		_localsearchGetGroupedPackageLists(sender_route, possible_lists_to_send);

		for (std::list< std::pair<SchNode*, PackageList> >::iterator list_it = possible_lists_to_send.begin(); list_it != possible_lists_to_send.end(); ++list_it)
		{
			/* for all vehicles : try to send package list */
			for (int receiver_id = 0; receiver_id < probdata->getNumVehicles(); ++receiver_id)
			{
				if (sender_id == receiver_id)
					continue;

				/* check time limit */
				if (timer != NULL && timer->timeLimitReached())
				{
					dpdpPrintfDebug("[tabu search] time limit has been reached (elapsed time: %lld seconds)\n", timer->getElapsedSeconds());
					goto MOVE_TO_BEST_NEIGHBOR;
				}

				/* find best move */
				const bool valid_move = scheduler.find_best_move(list_it->second, sender_id, list_it->first, receiver_id, neighbor_position, neighbor_value);

#ifdef DPDP_DEBUG
				DPDP_ASSERT_ABORT(verifyPackagecount(scheduler, init_package_count));
#endif

				if (valid_move)
				{
					bool tabu_move = false;
					for (PackageList::iterator pit = list_it->second.begin(); pit != list_it->second.end(); ++pit) {
						if (tabu.is_tabu(receiver_id, (*pit)->id, iter)) {
							tabu_move = true;
							break;
						}
					}
					if (neighbor_value > best_sol_value - DPDP_EPSILON && (neighbor_value >= best_neighbor_value - DPDP_EPSILON || tabu_move))
						continue;

					best_sender_id = sender_id;
					best_receiver_id = receiver_id;
					best_neighbor_value = neighbor_value;
					best_sender_node = list_it->first;
					best_receiver_node = neighbor_position;
					best_list = list_it->second;
				}
			}
		}
	}
MOVE_TO_BEST_NEIGHBOR:

#ifdef DPDP_DEBUG
	DPDP_ASSERT_ABORT(verifyPackagecount(scheduler, init_package_count));

#endif


	if (NULL == best_receiver_node)
	{
		dpdpPrintfDebug("[tabu search] no valid neighbor is found\n");
		return false;
	}

	//#ifdef DPDP_DEBUG
	//	std::cerr << "move packages: (";
	//	for (PackageList::const_iterator pit = best_list.begin(); pit != best_list.end(); ++pit)
	//		std::cerr << " " << (*pit)->original_order->long_id << " (" << (*pit)->original_order->pickup_factory->id << "->" << (*pit)->original_order->delivery_factory->id << ")";
	//	std::cerr << ") from V" << best_sender_id + 1 << " to V" << best_receiver_id + 1 << std::endl;;
	//	std::cerr << "routes before the move:\n";
	//	scheduler.printRoute(std::cerr, best_sender_id, true);
	//	scheduler.printRoute(std::cerr, best_receiver_id, true);
	//	std::cerr << std::endl;
	//#endif


	scheduler.move_packages(best_list, best_sender_id, best_sender_node, best_receiver_id, best_receiver_node);
	for (PackageList::iterator pit = best_list.begin(); pit != best_list.end(); ++pit)
	{
		tabu.make_tabu(best_sender_id, (*pit)->id, iter);
	}
	//#ifdef DPDP_DEBUG
	//	std::cerr << "and after the move:\n";
	//	scheduler.printRoute(std::cerr, best_sender_id, true);
	//	scheduler.printRoute(std::cerr, best_receiver_id, true);
	//	std::cerr << std::endl;
	//#endif


#ifdef DPDP_DEBUG
	DPDP_ASSERT_ABORT(verifyPackagecount(scheduler, init_package_count));
#endif

	dpdpPrintfDebug("[tabu search] best neighbor value   : %.3f\n", best_neighbor_value);

	return true;
}


bool LocalSearchSolver::localsearchFindBestNeighbor(Scheduler& scheduler, const Timer* timer, double &best_neighbor_value)
{
#ifdef DPDP_DEBUG
	std::vector<int> init_package_count;
	countScheduledPackages(scheduler, init_package_count);
#endif

	int best_sender_id = -1;
	int best_receiver_id = -1;
	SchNode* best_sender_node = NULL;
	SchNode* best_receiver_node = NULL;
	PackageList best_list;
	SchNode* current_position;
	double current_value;

	/* determine current value */

	best_neighbor_value = scheduler.evaluate();

	dpdpPrintfDebug("[local search] initial value: %.3f\n", best_neighbor_value);

	/* find improvement */
	for (int sender_id = 0; sender_id < probdata->getNumVehicles(); ++sender_id)
	{
		/* check time limit */
		if (timer != NULL && timer->timeLimitReached())
		{
			dpdpPrintfDebug("[local search] time limit has been reached (elapsed time: %lld seconds)\n", timer->getElapsedSeconds());
			goto MOVE_TO_BEST_NEIGHBOR;
		}

		/* go through possible packages */
		SchRoute& sender_route = *scheduler.getRoute(sender_id);

		std::list< std::pair<SchNode*, PackageList > > possible_lists_to_send; // list of (node,(list,...,list)) pairs
		_localsearchGetGroupedPackageLists(sender_route, possible_lists_to_send);

		for (std::list< std::pair<SchNode*, PackageList> >::iterator list_it = possible_lists_to_send.begin(); list_it != possible_lists_to_send.end(); ++list_it)
		{
			/* for all vehicles : try to send package list */
			for (int receiver_id = 0; receiver_id < probdata->getNumVehicles(); ++receiver_id)
			{
				if (sender_id == receiver_id)
					continue;

				/* check time limit */
				if (timer != NULL && timer->timeLimitReached())
				{
					dpdpPrintfDebug("[local search] time limit has been reached (elapsed time: %lld seconds)\n", timer->getElapsedSeconds());
					goto MOVE_TO_BEST_NEIGHBOR;
				}

				/* find best move */
				const bool find_best_move = scheduler.find_best_move(list_it->second, sender_id, list_it->first, receiver_id, current_position, current_value);

#ifdef DPDP_DEBUG
				DPDP_ASSERT_ABORT(verifyPackagecount(scheduler, init_package_count));
#endif

				if (find_best_move)
				{
					if (best_neighbor_value < current_value + DPDP_EPSILON)
						continue;

					best_sender_id = sender_id;
					best_receiver_id = receiver_id;
					best_neighbor_value = current_value;
					best_sender_node = list_it->first;
					best_receiver_node = current_position;
					best_list = list_it->second;
				}
			}
		}
	}

#ifdef DPDP_DEBUG
	DPDP_ASSERT_ABORT(verifyPackagecount(scheduler, init_package_count));

#endif

MOVE_TO_BEST_NEIGHBOR:

	if (NULL == best_receiver_node)
	{
		dpdpPrintfDebug("[local search] no improvements found\n");
		return false;
	}

//#ifdef DPDP_DEBUG
//	std::cerr << "move packages: (";
//	for (PackageList::const_iterator pit = best_list.begin(); pit != best_list.end(); ++pit)
//		std::cerr << " " << (*pit)->original_order->long_id << " (" << (*pit)->original_order->pickup_factory->inputfactory->id << "->" << (*pit)->original_order->delivery_factory->inputfactory->id << ")";
//	std::cerr << ") from V" << best_sender_id + 1 << " to V" << best_receiver_id + 1 << std::endl;;
//	std::cerr << "routes before the move:\n";
//	scheduler.printRoute(std::cerr, best_sender_id, true);
//	scheduler.printRoute(std::cerr, best_receiver_id, true);
//	std::cerr << std::endl;
//#endif


	scheduler.move_packages(best_list, best_sender_id, best_sender_node, best_receiver_id, best_receiver_node);

	scheduler.simplify_route(best_sender_id);
//#ifdef DPDP_DEBUG
//	std::cerr << "and after the move:\n";
//	scheduler.printRoute(std::cerr, best_sender_id, true);
//	scheduler.printRoute(std::cerr, best_receiver_id, true);
//	std::cerr << std::endl;
//#endif


#ifdef DPDP_DEBUG
	DPDP_ASSERT_ABORT(verifyPackagecount(scheduler, init_package_count));
#endif

	dpdpPrintfDebug("[local search] best value   : %.3f\n", best_neighbor_value);

	return true;
}

void LocalSearchSolver::_localsearchGetGroupedPackageLists(const SchRoute& route, std::list<std::pair<SchNode*, PackageList>>& package_lists)
{
	package_lists.clear();

	for (SchNode* node = route.first; node != NULL; node = node->succ)
	{
		if (CURRENT_NODE == node->node_type)
			continue; // packages cannot be removed from this node

		PackageList::const_iterator next_it;
		for (PackageList::const_iterator package_it = node->pickup_packages.cbegin(); package_it != node->pickup_packages.cend(); package_it = next_it)
		{
			/* collect packages with the same delivery factory */
			PackageList grouped_packages;
			grouped_packages.push_back(*package_it);

			next_it = package_it;
			for (++next_it; next_it != node->pickup_packages.cend(); ++next_it)
			{
				if ((*next_it)->original_order->delivery_factory != (*package_it)->original_order->delivery_factory)
					break; // next package corresponds to another group

				grouped_packages.push_back(*next_it);
			}

			/* add group to the list */
			package_lists.push_back(std::make_pair(node, std::move(grouped_packages)));
		}
	}
}

bool LocalSearchSolver::_localsearchHasLateOrders(const SchRoute& route, const int* order_latenesses)
{
	DPDP_ASSERT_ABORT(order_latenesses != NULL);

	for (SchNode* node = route.first; node != NULL; node = node->succ)
	{
		for (PackageList::const_iterator package_it = node->pickup_packages.cbegin(); package_it != node->pickup_packages.cend(); ++package_it)
		{
			if (0 < order_latenesses[(*package_it)->original_order->id])
				return true;
		}
	}

	return false;
}

//int LocalSearchSolver::dispatcher_with_lookahead(Scheduler& sch, std::list<const Package*>& packages_to_process)
//{
//	const double capacity = probdata->getVehicle(0)->capacity;
//	const int num_vehicles = probdata->getNumVehicles();
//	const int num_packages_to_process = packages_to_process.size();
//	int num_packages_assigned = 0;
//
//	while (!packages_to_process.empty()) {
//
//		std::vector<PackageList> package_lists;
//		std::vector<PackageList> packages_to_insert(LSSOLVER_LOOKAHEAD);
//		double insertion_value = DBL_MAX;
//		SchNode* insertion_position = NULL;
//		int insertion_vehicle = -1;
//		int best_index_i = -1;
//		PackageList::iterator next_it;
//
//		int lookahead_size = 0;
//		for (PackageList::iterator pit = packages_to_process.begin(); lookahead_size < LSSOLVER_LOOKAHEAD &&  pit != packages_to_process.end(); pit = next_it) {
//			next_it = pit;
//			for (++next_it; next_it != packages_to_process.end(); ++next_it)
//			{
//				if (!common_pickup_delivery_factory(*pit, *next_it)) break;
//			}
//			package_lists.push_back(PackageList());
//			package_lists.back().splice(package_lists.back().end(), packages_to_process, pit, next_it);
//			++lookahead_size;
//		}
//		// evaluate each list
//		for (int i = 0; i < lookahead_size; ++i) {
//			if (SchNode::sum_demand(package_lists[i]) <= capacity + DPDP_EPSILON)
//			{
//				packages_to_insert[i].splice(packages_to_insert[i].end(), package_lists[i]);
//			}
//			else
//			{
//				// solve bin packing problem heuristically
//				std::vector<std::pair<double, PackageList> > packing;
//				pack_items(package_lists[i], capacity, packing);
//				// choose max demand subset
//				int k = 0; // index of packing vector of greatest demand
//				for (int j = 1; j < packing.size(); ++j)
//				{
//					if (packing[j].first > packing[k].first)
//					{
//						k = j;
//					}
//				}
//				packages_to_insert[i].splice(packages_to_insert[i].end(), packing[k].second);
//			}
//
//			for (int vehicle_id = 0; vehicle_id < num_vehicles; ++vehicle_id) {
//				SchNode* pos ;
//				double value ;
//				if( sch.find_best_insert_pos(packages_to_insert[i], vehicle_id, pos, value) )
//				{
//					if (value < insertion_value - DPDP_EPSILON)
//					{
//						insertion_position = pos;
//						insertion_value = value;
//						insertion_vehicle = vehicle_id;
//						best_index_i = i;
//					}
//				}
//			}
//
//		}
//		DPDP_ASSERT_ABORT(best_index_i >= 0);
//		SchNode* from_node, * to_node;
//		bool new_from_node, new_to_node;
//		sch.insert_packages(packages_to_insert[best_index_i], *sch.getRoute(insertion_vehicle), insertion_position, from_node, to_node, new_from_node, new_to_node);
//		num_packages_assigned += packages_to_insert[best_index_i].size();
//
//		// move remaining packages back to the main list
//		for (int i = lookahead_size -1; i >= 0; --i)
//		{
//			if (i == best_index_i) {
//				if (package_lists[i].empty()) continue;
//				for (PackageList::reverse_iterator rit = package_lists[i].rbegin(); rit != package_lists[i].rend(); ++rit) {
//					if( std::find(packages_to_insert[i].begin(), packages_to_insert[i].end(), *rit) == packages_to_insert[i].end() )
//						packages_to_process.push_front(*rit);
//				}
//			}
//			else
//			{
//				if (package_lists[i].empty()) {
//					for (PackageList::reverse_iterator rit = packages_to_insert[i].rbegin(); rit != packages_to_insert[i].rend(); ++rit) {
//						packages_to_process.push_front(*rit);
//					}
//				}
//				else 
//					for (PackageList::reverse_iterator rit = package_lists[i].rbegin(); rit != package_lists[i].rend(); ++rit) {
//						packages_to_process.push_front(*rit);
//					}
//			}
//		}
//		DPDP_ASSERT_ABORT(num_packages_assigned + packages_to_process.size() == num_packages_to_process);
//	}
//	return 0;
//}

//LSSolution* LocalSearchSolver::solveStrategy2( long long time_limit )
//{
//	LSSolution* solution_to_return = NULL;
//
//	std::vector<SchRoute*> best_route( probdata->getNumVehicles(), NULL );
//	PackageList packages_to_process;
//	Scheduler scheduler( *probdata, packages, destinations, carrying_packages );
//
//	try
//	{
//		/* collect unallocated packages */
//		for( PackageList::const_iterator package_it = unallocated_packages.cbegin(); package_it != unallocated_packages.cend(); ++package_it )
//			packages_to_process.push_back( *package_it );
//
//		/* initialize scheduler */
//		scheduler.init_routes();
//
//		// special treatment of busy factories
//		//process_busy_factories(scheduler, stat, packages_to_process);
//
//		/* dispatch packages */
//		DispatcherInitial dispatcher( &scheduler, (int)packages.size() );
//		DPDP_CALL_THROW( dispatcher.run( packages_to_process ) );
//
//		
//		scheduler.save(best_route);
//
//		double best_value = scheduler.evaluate();
//
//		long long time_for_search = std::min( LSSOLVER_LOCAL_SEARCH_TIME_LIMIT, remaining_time() );
//
//		if( LSSOLVER_STRATEGY_2_USE_LOCAL_SEARCH )
//		{
//			const bool improved = localsearchStart( scheduler, time_for_search );
//
//			if( improved )
//			{
//				/* best route ... */
//				scheduler.save( best_route );
//				best_value = scheduler.evaluate();
//			}
//		}
//
//		if( LSSOLVER_STRATEGY_2_USE_TABU_SEARCH )
//		{
//			tabuSearch( scheduler, time_for_search, best_route, best_value );
//		}
//
//#ifdef DPDP_GEN_LOGFILES
//		stat.write_schedule_stats( scheduler );
//#endif
//		solution_to_return = new LSSolution();
//		solution_to_return->value = best_value;
//
//		/* transform routes */
//		for( int vid = 0; vid < probdata->getNumVehicles(); ++vid ) {
//			LSRoute* route = transformRoute( *best_route[vid] );
//
//			if( route->checkDuplicateNodes() )
//				dpdpPrintfWarn( "duplicate nodes on vehicle route V%d\n", vid + 1 );
//
//			solution_to_return->routes.push_back( route );
//		}
//
//		/* distribute remaining packages */
//		distributeRemainingPackages( solution_to_return, packages_to_process );
//	}
//	catch( ... )
//	{
//		dpdpPrintfError( "some exception has occuured during calculation, no solution is found\n" );
//
//		if( solution_to_return != NULL )
//		{
//			delete solution_to_return;
//			solution_to_return = NULL;
//		}
//	}
//
//	/* terminate (free memory) */
//	for( int vid = 0; vid < probdata->getNumVehicles(); ++vid )
//	{
//		if( best_route[vid] != NULL )
//			delete best_route[vid];
//	}
//
//	return solution_to_return;
//}

//int LocalSearchSolver::constructScheduleForStrategy2( Scheduler& schedule, PackageList& packages_to_process, std::vector<SchRoute*>& best_route )
//{
//	PackageList* packages_at_factories = NULL;
//	int* package_latenesses = NULL;
//	const int now = calculateLatestUpdateTime();
//
//	/* divide packages (based on pickup factory) */
//	packages_at_factories = new PackageList[probdata->getNumFactories()];
//
//	for( PackageList::const_iterator package_it = packages_to_process.cbegin(); package_it != packages_to_process.cend(); ++package_it )
//		packages_at_factories[(*package_it)->original_order->pickup_factory->id].push_back( *package_it );
//	packages_to_process.clear();
//
//	/* sort packages */
//	package_latenesses = new int[packages.size()];
//	std::memset( package_latenesses, 0, sizeof( int ) * packages.size() );
//	for( PackageList::const_iterator package_it = packages_to_process.cbegin(); package_it != packages_to_process.cend(); ++package_it )
//		package_latenesses[(*package_it)->id] = calculatePackageLateness( *package_it, now );
//
//	for( int factory_id = 0; factory_id < probdata->getNumFactories(); ++factory_id )
//		packages_at_factories[factory_id].sort( comparator_package_lateness_decr( package_latenesses ) );
//
//	/* dispatch */
//	{
//		int urgent_factory = -1;
//
//		for( int factory_id = 0; factory_id < probdata->getNumFactories(); ++factory_id )
//		{
//		}
//	}
//
//	/* put back unprocessed packages */
//	for( int factory_id = 0; factory_id < probdata->getNumFactories(); ++factory_id )
//		packages_to_process.insert( packages_to_process.end(), packages_at_factories[factory_id].begin(), packages_at_factories[factory_id].end() );
//
//	/* free memory */
//	if( packages_at_factories != NULL )
//		delete[] packages_at_factories;
//
//	if( package_latenesses )
//		delete[] package_latenesses;
//
//	return 0;
//}

// <<<<< STRATEGY 2
