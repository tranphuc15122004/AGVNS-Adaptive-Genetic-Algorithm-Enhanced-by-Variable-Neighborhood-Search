#ifndef _DPDP_LSSOLVER_H_
#define _DPDP_LSSOLVER_H_

#include "solverdata.h"
#include "scheduler.h"
#include "timer.h"
#include "statistics.h"
#include <list>
#include <vector>
#include <set>

class ProbData;
struct OrderItem;
struct RouteNode;
struct Vehicle;

class TabuList
{
	std::map<int, int> tabu_moves;
public:

	TabuList() : tabu_len(5)
	{
	}
	TabuList(int _len) : tabu_len(_len)
	{
	}

	int tabu_len;


	void make_tabu(int vehicle_id, int package_id, int iter)
	{
		tabu_moves[hash(vehicle_id, package_id)] = iter + tabu_len;
	}

	inline bool is_tabu(int vehicle_id, int package_id, int iter) const
	{
		std::map<int, int>::const_iterator it = tabu_moves.find(hash(vehicle_id, package_id));
		if (it == tabu_moves.end()) return false;
		return it->second >= iter;
	}

	int hash(int vehicle_id, int package_id) const {
		return 100000 * vehicle_id + package_id;
	}
};

class LocalSearchSolver
{
private:
	const ProbData* probdata;
	//std::vector<int> desired_number_of_dockings;
private:
	std::vector<Package*> packages;
	void storePackage( Package* package );

private: // all of the allocated packages are in one of these data, thus DO NOT REMOVE PACKAGES FROM THESE!!!
	std::vector<PackageList> carrying_packages; // array of list of carrying packages
	std::vector<LSNode*>  destinations;         // array of destinations
	PackageList unallocated_packages;           // list of unallocated packages (sequenceable packages)

public:
	LocalSearchSolver( const ProbData* _probdata );
	~LocalSearchSolver();

private:
	
	int init();

private:
	int constructSch(PackageList& packages_to_process, Scheduler& sch, std::vector<SchRoute*>& best_route, double& best_value);
	int constructSch_v2(PackageList& packages_to_process, Scheduler& sch, std::vector<SchRoute*>& best_route, double& best_value);
	int constructSch_v3(PackageList& packages_to_process, Scheduler& sch, std::vector<SchRoute*>& best_route, double& best_value);

	void calcArrivalTime( Scheduler& sch, int vehicle_id, const Factory* pickup_factory, int& arrival_time, double& remaining_capacity, SchNode*& node );

private:
	/// <summary>
	/// Distributes the given packages amoung the vehicles.
	/// WARN : very dummy approach!
	/// </summary>
	/// <param name="solution">Current solution.</param>
	/// <param name="packages_to_process">Packages to distribute.</param>
	/// <returns>Return code.</returns>
	int distributeRemainingPackages( LSSolution* solution, std::list<const Package*>& packages_to_process );
	int distributeRemainingPackagesByScheduler( Scheduler& scheduler, PackageList& packages_to_distribute );

	int orderPackages1(std::list<const Package*> &packages_to_process);
	int orderPackages2(std::list<const Package*>& packages_to_process);
	int orderPackages3(std::list<std::pair<int, const Package*> >& packages_to_process, std::list<const Package*>& ordered_packages, int ordering = 0);

	int dispatch(Scheduler& sch, std::list<const Package*>& packages_to_process, bool binpacking = false);

	void rescheduleDelayedVehicles(Scheduler& sch);
	void countScheduledPackages(Scheduler& sch, std::vector<int>& package_count) const;
	bool verifyPackagecount(Scheduler& sch, const std::vector<int>& package_count) const;

	LSSolution* solve(long long time_limit, int constr_method);

public:
	/// <summary>
	/// Starts the algorithm.
	/// </summary>
	/// <returns>Return code.</returns>
	int run();

private:
	int pushBackPackageToRoute( LSRoute* route, const Package* package );
	
private:
	/// <summary>
	/// Tests whether the given item can be added to the given package.
	/// </summary>
	/// <param name="package">Package to insert into.</param>
	/// <param name="item">Item to insert.</param>
	/// <param name="capacity">Capacity limit.</param>
	/// <returns>true if and only if the item can be added to the package.</returns>
	bool testItemOnPackage( const Package* package, const OrderItem* item, const double capacity ) const;

private:
	/// <summary>
	/// Transforms route.
	/// - consecutive nodes with the same factory are merged
	/// </summary>
	/// <param name="original_route"></param>
	/// <returns>Transformed route.</returns>
	LSRoute* transformRoute( const SchRoute& original_route ) const;

private:
	/// <summary>
	/// Writes the given node into the given file.
	/// </summary>
	/// <param name="node">Pointer to the node (may NOT be NULL).</param>
	/// <param name="file">Pointer to an OPENED file.</param>
	/// <returns>Return code.</returns>
	int writeLSNode( const LSNode* node, FILE* file ) const;

	/// <summary>
	/// Writes destination file for the given solution.
	/// </summary>
	/// <param name="solution">Solution to write.</param>
	/// <returns>Return code.</returns>
	int writeDestinationFile( const LSSolution* solution ) const;

	/// <summary>
	/// Writes route file for the given solution.
	/// </summary>
	/// <param name="solution"></param>
	/// <returns></returns>
	int writeRouteFile( const LSSolution* solution ) const;

	/// <summary>
	/// Writes route file for the given schedule.
	/// </summary>
	/// <param name="scheduler">Scheduler with the current solution.</param>
	/// <returns>Return code.</returns>
	int writeRouteFileFromSchedule( Scheduler* scheduler ) const; // TODO : test !

	/// <summary>
	/// Writes destination file for the given schedule.
	/// </summary>
	/// <param name="solution">Scheduler with the current solution.</param>
	/// <returns>Return code.</returns>
	int writeDestinationFileFromSchedule( Scheduler* scheduler ) const; // TODO : test !

	/// <summary>
	/// Writes the given node into the given file.
	/// </summary>
	/// <param name="node">Pointer to the node (may NOT be NULL).</param>
	/// <param name="file">Pointer to an OPENED file.</param>
	/// <returns>Return code.</returns>
	int writeSchNode( const SchNode* node, FILE* file ) const;

private:
	/// <summary>
	/// Writes logfile for the given solution.
	/// </summary>
	/// <param name=</param>
	/// <returns></returns>
	int writeLogfile( const LSSolution* solution ) const;

	/// <summary>
	/// Writes auxiliary iteminfo file for debugging purpose.
	/// </summary>
	void writeItemInfo();

private:
	/// <summary>
	/// Returns the latest update time of the vehicles.
	/// </summary>
	/// <returns>Latest update time, if any, -1 otherwise.</returns>
	int calculateLatestUpdateTime() const;

private:
	/// <summary>
	/// Starts local search with the current state of the given scheduler.
	/// </summary>
	/// <param name="scheduler">Scheduler = current solution.</param>
	/// <param name="seconds_limits">Time limit in seconds.</param>
	/// <returns>True iff improvements has been made (and thus solution has been changed).</returns>
	void localsearchStart( Scheduler& scheduler, const long long seconds_limits, std::vector<SchRoute*>& best_routes, double& best_value);

	void localSearchWithReschedule(Scheduler& scheduler, const long long seconds_limits, std::vector<SchRoute*>& best_routes, double& best_value);

	bool tabusearchMove(Scheduler& scheduler, const Timer* timer, TabuList& tabu);

	void tabuSearch(Scheduler& scheduler, const long long seconds_limits, std::vector<SchRoute*>& best_routes, double& best_value);
	/// <summary>
	/// Steps to the best neighbor, if any, of the given scheduler.
	/// </summary>
	/// <param name="scheduler">Scheduler = current solution.</param>
	/// <param name="timer">Timer for checking elapsed time and time limit.</param>
	/// <returns>True iff improvements has been made (and thus solution has been changed).</returns>
	bool localsearchFindBestNeighbor( Scheduler& scheduler, const Timer* timer, double& best_neighbor_value);

	bool tabusearchMove(Scheduler& scheduler, const Timer* timer, int iter, TabuList& tabu, const double best_sol_value, double& new_solution_value);

	bool localsearchFindBestNeighbor_2(Scheduler& scheduler, const Timer* timer);

	/// <summary>
	/// Collects the packages with the same pickup and delivery factories along the given route.
	/// </summary>
	/// <param name="route">Route.</param>
	/// <param name="package_lists">List to append group-lists to.</param>
	void _localsearchGetGroupedPackageLists( const SchRoute& route, std::list< std::pair<SchNode*, PackageList>>& package_lists );

	bool _localsearchHasLateOrders( const SchRoute& route, const int* order_latenesses );

	bool redistributePackages( Scheduler& scheduler, const Timer* timer );

private:
	int calculatePackageDuration( const Package* package ) const
	{
		DPDP_ASSERT_ABORT( package != NULL );

		return getLoadingSeconds( package->getDemand() )
			+ probdata->getTravelTime( package->original_order->pickup_factory, package->original_order->delivery_factory )
			+ getUnloadingSeconds( package->getDemand() )
			+ DOCK_APPROACHING_TIME;
	}

	int calculatePackageLateness( const Package* package, const int now ) const
	{
		DPDP_ASSERT_ABORT( package != NULL );

		return now + calculatePackageDuration( package ) - package->original_order->completion_time;
	}

	//void calcDesiredNumberOfDockings();

private:
	bool takeOffPackages( Scheduler& scheduler );
	bool takeOffPackagesFromVehicle( Scheduler& scheduler, int vehicle_id, const PackageList& packages_to_redistribute, bool pickup_movement, const double initial_value, double& improved_value );
	bool takeOffPackages_2( Scheduler& scheduler );

	bool swap_improve(Scheduler & sch);
	bool swap_improve_route(Scheduler& sch, int vehicle_id, double &best_value);
};

#endif
