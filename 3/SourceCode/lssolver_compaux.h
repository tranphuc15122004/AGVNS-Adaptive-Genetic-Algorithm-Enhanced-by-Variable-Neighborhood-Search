#ifndef _DPDP_LSSOLVER_COMPAUX_H_
#define _DPDP_LSSOLVER_COMPAUX_H_

struct EarlierPackage
{
	bool operator()( const Package* a, const Package* b ) const
	{
		return a->original_order->completion_time < b->original_order->completion_time;
	}
};

struct GroupByPickup
{
	bool operator()( const Package* a, const Package* b ) const
	{
		return a->original_order->pickup_factory->id < b->original_order->pickup_factory->id ||
			(a->original_order->pickup_factory->id == b->original_order->pickup_factory->id &&
				a->original_order->delivery_factory->id < b->original_order->delivery_factory->id) ||
			(a->original_order->pickup_factory->id == b->original_order->pickup_factory->id &&
				a->original_order->delivery_factory->id == b->original_order->delivery_factory->id &&
				a->original_order->completion_time < b->original_order->completion_time);
	}
};

struct GroupByPickup2
{
	bool operator()( std::pair<int, const Package*> &pa, std::pair<int, const Package*>& pb ) const
	{
		const Package* a = pa.second;
		const Package* b = pb.second;

		if( a->original_order->pickup_factory->id < b->original_order->pickup_factory->id )
			return true;

		if( ( a->original_order->pickup_factory->id == b->original_order->pickup_factory->id )
			&& ( a->original_order->delivery_factory->id < b->original_order->delivery_factory->id ) )
			return true;

		if( (a->original_order->pickup_factory->id == b->original_order->pickup_factory->id)
			&& (a->original_order->delivery_factory->id == b->original_order->delivery_factory->id)
			&& (pa.first > pb.first) )
			return true;

		return false;
	}
};


template<class T>
struct DecrFirst
{
	bool operator()( std::pair<T, std::list<const Package*> >& pa, std::pair<T, std::list<const Package*> >& pb ) const
	{
		return pa.first > pb.first;
	}
};

struct IncrLength
{
	bool operator() ( const std::pair<int, const Package*> &a, const std::pair<int, const Package*>& b ) const
	{
		return a.first < b.first ||
			(a.first == b.first && a.second->original_order->pickup_factory->id < b.second->original_order->pickup_factory->id) ||
			(a.first == b.first && a.second->original_order->pickup_factory->id == b.second->original_order->pickup_factory->id
				&& a.second->original_order->delivery_factory->id < b.second->original_order->delivery_factory->id);
	}
};

struct DecrLength
{
	bool operator() ( const std::pair<int, const Package*>& a, const std::pair<int, const Package*>& b ) const
	{
		return a.first > b.first ||
			(a.first == b.first && a.second->original_order->pickup_factory->id < b.second->original_order->pickup_factory->id) ||
			(a.first == b.first && a.second->original_order->pickup_factory->id == b.second->original_order->pickup_factory->id
				&& a.second->original_order->delivery_factory->id < b.second->original_order->delivery_factory->id);
	}
};

struct package_comparator_demand_increase
{
	bool operator()( const Package* a, const Package* b ) const
	{
		return a->getDemand() < b->getDemand();
	}
};

struct package_comparator_demand_decrease
{
	bool operator()( const Package* a, const Package* b ) const
	{
		return a->getDemand() > b->getDemand();
	}
};

struct vehicle_schnode_comparator_waiting_time_decrease
{
	bool operator()( const std::pair< int, SchNode* >& a, const std::pair< int, SchNode* >& b ) const
	{
		return a.second > b.second;
	}
};

#endif
