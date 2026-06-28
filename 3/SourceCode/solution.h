#ifndef _DPDP_SOLUTION_H_
#define _DPDP_SOLUTION_H_

//#include "solution_aux.h"
//
//#include <vector>
//
//constexpr int ROUTE_STATUS_UNDETERMINED        = -1; // status of the route is not determined yet
//constexpr int ROUTE_STATUS_FEASIBLE            =  0; // route is feasible
//constexpr int ROUTE_STATUS_INFEASIBLE_LIFO     =  1; // route is infeasible due to LIFO violation
//constexpr int ROUTE_STATUS_INFEASIBLE_CAPACITY =  2; // route is infeasible due to vehicle capacity violation!
//constexpr int ROUTE_STATUS_INFEASIBLE_CIRCULAR_SHIPMENT = 3; // route is infeasible due to circular shipment
//
//class Sequencer
//{
//private:
//	const ProbData* probdata; // problem data
//	const int num_packages;
//	RouteNode** pickup_nodes;
//	RouteNode** delivery_nodes;
//
//public:
//	inline RouteNode* getPickupNode( const int package_id ) const
//	{
//		return pickup_nodes[package_id];
//	}
//
//	inline RouteNode* getDeliveryNode( const int package_id ) const
//	{
//		return delivery_nodes[package_id];
//	}
//
//public:
//	Sequencer(const ProbData* _probdata, int _num_packages);
//
//	~Sequencer()
//	{
//		if( pickup_nodes )
//			delete[] pickup_nodes;
//
//		if( delivery_nodes )
//			delete[] delivery_nodes;
//	}
//
//public:
//	/// <summary>
//	/// Returns the best feasible route, if any.
//	/// </summary>
//	/// <param name="vehicle">Vehicle.</param>
//	/// <param name="destination">Destination of the vehicle (may be NULL).</param>
//	/// <param name="carried_packages">List of carrying packeges.</param>
//	/// <param name="movable_packages">List of movable packages.</param>
//	/// <param name="status">Reference to store status.</param>
//	/// <returns>Pointer to the best route (or NULL if there is no easible route).
//	/// NOTE : route is only valid as long as the corresponding Sequencer object exists!
//	/// NOTE : freeing route is the respoinsible of the caller!
//	///</returns>
//	SeqRoute* findBestRoute( const Vehicle* vehicle, const LSNode* destination, const std::list<const Package*>& carried_packages, const std::list<const Package*>& sequenceable_packages, int &status );
//
//	/// <summary>
//	/// Evaluates the given route.
//	/// WARN : it is assumed that package lists of the nodes are sorted in the correct order!
//	/// </summary>
//	/// <param name="vehicle">Vehicle to the route belongs to.</param>
//	/// <param name="destination">Destination of the vehicle (may be NULL).</param>
//	/// <param name="carrying_packages">List of carrying packages.</param>
//	/// <param name="route">Route to evalute.</param>
//	/// <param name="route_length">Length of the route.</param>
//	/// <param name="status">Reference to store status.</param>
//	/// <param name="route_value">Pointer to store value.</param>
//	/// <returns>Return code.</returns>
//	int evaluateRoute( const Vehicle* vehicle, const std::list<const Package*>& carrying_packages, RouteNode** route, const int route_length, int& status, double &route_value );
//
//	/// <summary>
//	/// Returns true if and only if the graph does not contain a directed cycle  
//	/// </summary>
//	/// <param name="graph">graph nodes</param>
//	/// <returns>true if and only if graph admits a toposort
//	///</returns>
//	bool toposort(std::vector<RouteNode*>& graph) const;
//private:
//	/// <summary>
//	/// Creates nodes for the given delivery packages and appends them at the end of the given vector.
//	/// Note that packages may be stored in an existing node (that is, the last element of the given vector).
//	/// </summary>
//	/// <param name="packages">A list of packages in the order of loading.</param>
//	/// <param name="from">A reverse iterator to indicate the start of the list. (List is processed backwards due to LIFO constraint).</param>
//	/// <param name="storage">Vector where new nodes append to.</param>	
//	void splitPackagesToDeliveryNodes( const std::list<const Package*>& packages, const std::list<const Package*>::const_reverse_iterator& from, std::vector<RouteNode*>& storage );
//};

#endif
