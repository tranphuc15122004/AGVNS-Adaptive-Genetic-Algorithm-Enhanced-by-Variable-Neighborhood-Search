#ifndef _DPDP_SOLUTION_AUX_H_
#define _DPDP_SOLUTION_AUX_H_

//#include "dpdp.h"
//#include "probdata.h"
//#include "solverdata.h"
//#include "config.h"
//
//#include <list>
//#include <ostream>
//#include <set>
//
//constexpr auto UNSPECIFIED_NODE = -1;
//constexpr auto CURRENT_NODE = 0;
//constexpr auto DESTINATION_NODE = 1;
//constexpr auto GENERAL_NODE = 2;
//
//
//struct RouteNode
//{
//	const Factory* factory;                       // pointer to the factory
//	std::list<const Package*> delivery_packages; // list of delivery packages in order of unloading
//	std::list<const Package*> pickup_packages;   // list of pickup packages in order of loading
//	int arrive_time;                              // arrive time
//	int leave_time;                               // leave time
//	int pos;									  // position in the route
//	bool carried_items;
//	int indeg;
//	std::set<RouteNode*>  succ_nodes;
//	int node_type;
//
//	RouteNode() : factory( NULL ), arrive_time( 0 ), leave_time( 0 ), pos( -1 ), carried_items( false ), indeg( 0 ), node_type( UNSPECIFIED_NODE )
//	{
//	}
//
//	int getLoadingTime() const
//	{
//		double load = 0;
//		for( std::list<const Package*>::const_iterator package_it = pickup_packages.cbegin(); package_it != pickup_packages.cend(); ++package_it )
//			load += (*package_it)->getDemand();
//
//		return getLoadingSeconds( load );
//	}
//
//	int getUnloadingTime() const
//	{
//		double unload = 0;
//		for( std::list<const Package*>::const_iterator package_it = delivery_packages.cbegin(); package_it != delivery_packages.cend(); ++package_it )
//			unload += (*package_it)->getDemand();
//
//		return getUnloadingSeconds( unload );
//	}
//};
//
//struct SeqRoute
//{
//	std::list<RouteNode*> nodes;
//	double estimated_value;
//
//	SeqRoute() : estimated_value( DPDP_INFINITY_DBL )
//	{
//	}
//
//	~SeqRoute()
//	{
//		clear();
//	}
//
//	void clear()
//	{
//		for (std::list<RouteNode*>::iterator it = nodes.begin(); it != nodes.end(); ++it)
//			delete* it;
//	}
//};
//
//std::ostream& operator << (std::ostream& , const SeqRoute&);
//
//#endif
