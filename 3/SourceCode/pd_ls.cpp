#include "pd_ls.h"

#include "pd.h"
#include "solverdata.h"
#include "timer.h"
#include <stack>

constexpr int LS_ITERATION_LIMIT = 512;

constexpr bool LS_NEIGHBOR_GROUPTRANSFER_APPLY     = true;
constexpr bool LS_NEIGHBOR_COMPONENTTRANSFER_APPLY = true;
constexpr bool LS_FIXED_DESTINATION_PICKUPS = false;

void PDMovement::applyWithEvaluation(PD* parent)
{
	apply(parent);
	evaluated_value = parent->evaluate();
}

void PDSimpleRemoval::copy_to(PDSimpleRemoval*& copy)
{
	if (NULL == copy)
		copy = new PDSimpleRemoval;

	copy->package = this->package;
	copy->component = this->component;
	copy->from_vehicle = this->from_vehicle;
	copy->from_pickup_pred = this->from_pickup_pred;
	copy->from_delivery_succ = this->from_delivery_succ;

	copy->evaluated_value = this->evaluated_value;
}

void PDSimpleRemoval::apply(PD* parent)
{
	DPDP_ASSERT_ABORT(parent->getPickupNode(package) != NULL);
	DPDP_ASSERT_ABORT(parent->getDeliveryNode(package) != NULL);

	/* save original state */
	from_vehicle = parent->getVehicleID(package);
	from_pickup_pred = parent->getPickupNode(package)->route_pred;
	from_delivery_succ = parent->getDeliveryNode(package)->route_succ;

	/* apply */
	if( component )
		parent->remove_interval( parent->getPickupNode( package ), parent->getDeliveryNode( package ) );
	else
		parent->remove( package );
}

void PDSimpleRemoval::undo(PD* parent)
{
	DPDP_ASSERT_ABORT(0 <= from_vehicle);
	DPDP_ASSERT_ABORT(from_pickup_pred != NULL);
	DPDP_ASSERT_ABORT(from_delivery_succ != NULL);

	if( component )
		parent->insert_interval( parent->getPickupNode( package ), parent->getDeliveryNode( package ), from_vehicle, from_pickup_pred );
	else
		parent->insert(package, from_vehicle, from_pickup_pred, from_delivery_succ);
}

void PDSimpleInsertion::apply(PD* parent)
{
	if (component)
	{
		DPDP_ASSERT_ABORT(package != NULL);
		DPDP_ASSERT_ABORT(0 <= to_vehicle);
		DPDP_ASSERT_ABORT(to_pickup_pred != NULL);

		parent->insert_interval( parent->getPickupNode( package ), parent->getDeliveryNode( package ), to_vehicle, to_pickup_pred );
	}
	else
	{
		DPDP_ASSERT_ABORT(package != NULL);
		DPDP_ASSERT_ABORT(0 <= to_vehicle);
		DPDP_ASSERT_ABORT(to_pickup_pred != NULL);
		DPDP_ASSERT_ABORT(to_delivery_succ != NULL);

		parent->insert(package, to_vehicle, to_pickup_pred, to_delivery_succ);
	}
}

void PDSimpleInsertion::undo(PD* parent)
{
	DPDP_ASSERT_ABORT(package != NULL);

	if( component )
		parent->remove_interval( parent->getPickupNode( package ), parent->getDeliveryNode( package ) );
	else
		parent->remove(package);
}

void PDSimpleInsertion::copy_to(PDSimpleInsertion*& copy)
{
	if (NULL == copy)
		copy = new PDSimpleInsertion;

	copy->package = this->package;
	copy->component = this->component;
	copy->to_vehicle = this->to_vehicle;
	copy->to_pickup_pred = this->to_pickup_pred;
	copy->to_delivery_succ = this->to_delivery_succ;

	copy->evaluated_value = this->evaluated_value;
}

void PDGroupRemoval::apply(PD* parent)
{
	/* save initial state */
	from_pred_first = first_interval.first->route_pred;
	from_succ_second = second_interval.second->route_succ;
	from_vehicle = parent->getVehicleID( first_interval.first->package );

	parent->remove_two_intervals(
		first_interval.first, first_interval.second,
		second_interval.first, second_interval.second
	);
}

void PDGroupRemoval::undo(PD* parent)
{
	DPDP_ASSERT_ABORT( from_pred_first != NULL );
	DPDP_ASSERT_ABORT( from_succ_second != NULL );

	/* insert intervals */
	parent->insert_two_intervals(
		first_interval.first, first_interval.second,
		second_interval.first, second_interval.second,
		from_vehicle,
		from_pred_first, from_succ_second
	);
}

void PDGroupRemoval::copy_to( PDGroupRemoval *& copy )
{
	if( NULL == copy )
		copy = new PDGroupRemoval;

	copy->first_interval = this->first_interval;
	copy->second_interval = this->second_interval;
	copy->from_pred_first = this->from_pred_first;
	copy->from_succ_second = this->from_succ_second;
	copy->from_vehicle = this->from_vehicle;

	copy->evaluated_value = this->evaluated_value;
}

void PDGroupInsertion::apply(PD* parent)
{
	DPDP_ASSERT_ABORT( to_pred_first != NULL );
	DPDP_ASSERT_ABORT( to_succ_second != NULL );

	/* insert intervals */
	parent->insert_two_intervals(
		first_interval.first, first_interval.second,
		second_interval.first, second_interval.second,
		to_vehicle,
		to_pred_first, to_succ_second
	);
}

void PDGroupInsertion::undo(PD* parent)
{
	/* remove intervals */
	parent->remove_two_intervals(
		first_interval.first, first_interval.second,
		second_interval.first, second_interval.second
	);
}

void PDGroupInsertion::copy_to( PDGroupInsertion *& copy )
{
	if( NULL == copy )
		copy = new PDGroupInsertion;

	copy->first_interval = this->first_interval;
	copy->second_interval = this->second_interval;
	copy->to_pred_first = this->to_pred_first;
	copy->to_succ_second = this->to_succ_second;
	copy->to_vehicle = this->to_vehicle;

	copy->evaluated_value = this->evaluated_value;
}

void PDSimpleTransfer::apply(PD* parent)
{
	DPDP_ASSERT_ABORT(removal.package == insertion.package);

	removal.apply(parent);
	insertion.apply(parent);
}

void PDSimpleTransfer::undo(PD* parent)
{
	DPDP_ASSERT_ABORT(removal.package == insertion.package);

	insertion.undo(parent);
	removal.undo(parent);
}

void PDGroupTransfer::apply( PD* parent )
{
	removal.apply( parent );
	insertion.apply( parent );
}

void PDGroupTransfer::undo( PD* parent )
{
	insertion.undo( parent );
	removal.undo( parent );
}

PDLocalSearch::PDLocalSearch(PD* _parent, const ProbData* _probdata) : parent(_parent), probdata(_probdata), actual_value(.0)
{
}

bool PDLocalSearch::run(long long time_limit)
{
	Timer ls_timer;
	ls_timer.setTimeLimit(time_limit);
	ls_timer.start();

	bool improved_at_least_once = false;

	actual_value = parent->evaluate();

	dpdpPrintfDebug("[local search] start with initial solution of value %.3f\n", actual_value);

	for (int iteration = 1; iteration <= LS_ITERATION_LIMIT; ++iteration)
	{
		dpdpPrintfDebug("[local search] iteration %d...\n", iteration);

		if (ls_timer.timeLimitReached())
		{
			dpdpPrintfDebug("[local search] time limit (%lld seconds) has been reached: (%lld) seconds\n", time_limit, ls_timer.getElapsedSeconds());
			break;
		}

		if (stepToBestNeighbor(ls_timer))
			improved_at_least_once = true;
		else
			break;
	}

	return improved_at_least_once;
}

bool PDLocalSearch::stepToBestNeighbor(const Timer& timer)
{
	PDMovement* best_movement = NULL;
	PDMovement* curr_movement = NULL;

	int neighborhood = 0;

	for( bool all_neighbors_are_checked = false; !all_neighbors_are_checked; )
	{
		if( timer.timeLimitReached() )
		{
			dpdpPrintfDebug( "[local search] time limit has been reached: (%lld) seconds\n", timer.getElapsedSeconds() );
			break;
		}

		switch( neighborhood )
		{
			case 0:
			{
				curr_movement = LS_NEIGHBOR_GROUPTRANSFER_APPLY ? findBestGroupTransfer() : NULL;
			}
			break;
			case 1:
			{
				curr_movement = LS_NEIGHBOR_COMPONENTTRANSFER_APPLY ? findBestTransfer( true ) : NULL;
			}
			break;
			default:
			{
				all_neighbors_are_checked = true;
			}
			break;
		}

		if( all_neighbors_are_checked )
			break;

		++neighborhood;

		if( NULL == curr_movement )
			continue;

		if( NULL == best_movement || curr_movement->evaluated_value + DPDP_EPSILON < best_movement->evaluated_value )
		{
			dpdpPrintfDebug( "[local search] improved solution: %.3f\n", curr_movement->evaluated_value );

			if( best_movement != NULL )
				delete best_movement;

			best_movement = curr_movement;
			curr_movement = NULL;

			/* restart */
			neighborhood = 0;
		}
		else // no improvement
		{
			delete curr_movement;
			curr_movement = NULL;
		}
	}

	/* go to best neighbor */
	if( best_movement != NULL )
	{
		best_movement->apply( parent );
		actual_value = parent->evaluate();
		delete best_movement;
		return true;
	}

	return false;
}

PDSimpleInsertion* PDLocalSearch::findBestInsertation(const Package* package, const bool component)
{
	DPDP_ASSERT_ABORT(package != NULL);

	return findBestInsertation(parent->getPickupNode(package), parent->getDeliveryNode(package), component);
}

PDSimpleInsertion* PDLocalSearch::findBestInsertation(PDNode* pickup_node, PDNode* delivery_node, bool component)
{
	PDSimpleInsertion* best_insertation = NULL;

	for (int vehicle_id = 0; vehicle_id < probdata->getNumVehicles(); ++vehicle_id)
	{
		PDSimpleInsertion* curr_insertation = findBestInsertationOnVehicle(pickup_node, delivery_node, vehicle_id, component);

		if (NULL == curr_insertation)
			continue;

		if (NULL == best_insertation || curr_insertation->evaluated_value + DPDP_EPSILON < best_insertation->evaluated_value)
			curr_insertation->copy_to(best_insertation);

		delete curr_insertation;
	}

	return best_insertation;
}

PDGroupInsertion* PDLocalSearch::findBestInsertationOfPackageOnVehicle(PDNode* pickup_node_first, PDNode* pickup_node_last, PDNode* delivery_node_first, PDNode* delivery_node_last, const int to_vehicle)
{
	DPDP_ASSERT_ABORT(pickup_node_first != NULL);
	DPDP_ASSERT_ABORT(pickup_node_last != NULL);
	DPDP_ASSERT_ABORT(delivery_node_first != NULL);
	DPDP_ASSERT_ABORT(delivery_node_last != NULL);
	DPDP_ASSERT_ABORT(pickup_node_first->delivery_pair == delivery_node_last);
	DPDP_ASSERT_ABORT(pickup_node_last->delivery_pair == delivery_node_first);

	PDGroupInsertion* best_insertion = NULL;
	double best_value = actual_value;
	PDGroupInsertion curr_insertion;
	curr_insertion.to_vehicle = to_vehicle;
	curr_insertion.first_interval.first = pickup_node_first;
	curr_insertion.first_interval.second = pickup_node_last;
	curr_insertion.second_interval.first = delivery_node_first;
	curr_insertion.second_interval.second = delivery_node_last;
	double curr_value = .0;

	const PDRoute& route = parent->getRoute(to_vehicle);

	/* find possible insertations
	*
	*  p_node should be
	*  - the last one in a sequence of delivery nodes or
	*  - a pickup node
	*  to insert pickup_node after
	*
	*  d_node should be
	*  - a pickup node or
	*  - the dummy end node
	*  - or the closing delivery node of the tightest component which contains p_node
	* to insert delivery_node before
	*/

	double max_pickup = 0;
	double level = 0;
	for (PDNode* node = pickup_node_first; node != pickup_node_last->route_succ; node = node->route_succ)
	{
		max_pickup += node->package->getDemand();
	}

	level = route.initial_residual_capacity;

	for (PDNode* p_node = route.begin; p_node != route.end; p_node = p_node->route_succ)
	{
		if (p_node->pickup_node()) {
			level -= p_node->package->getDemand();
		}
		else if (p_node->delivery_node()) {
			level += p_node->package->getDemand();
		}
		if (level < -DPDP_EPSILON)
			return best_insertion;

		if( p_node->route_succ->get_node_type() == PDNODE_CI_DELIVERY )
			continue;

		if( level < max_pickup - DPDP_EPSILON )
			continue;

		// TODO (kist) : atnezni
		if( p_node == route.begin && route.first_pickup_factory != NULL && pickup_node_first->getFactory() != route.first_pickup_factory )
			continue; // 'mandatory first pickup factor rule' is active and violated

		PDNode* d_node = p_node->route_succ;

		if (p_node->pickup_node() && d_node->pickup_node())
		{
			if (p_node->package->original_order->pickup_factory == d_node->package->original_order->pickup_factory) {
				if (p_node->package->original_order->delivery_factory == d_node->package->original_order->delivery_factory)
					continue;

				d_node = d_node->delivery_pair->route_succ;
			}
		}
		else if (p_node->pickup_node() && d_node->delivery_node())
		{
			DPDP_ASSERT_ABORT(p_node->delivery_pair == d_node);
		}
		else if (p_node->delivery_node() && d_node->pickup_node())
		{
			if (p_node->package->original_order->delivery_factory == d_node->package->original_order->pickup_factory) {
				d_node = d_node->delivery_pair->route_succ;
			}
		}
		else if (p_node->delivery_node() && d_node->delivery_node())
		{
			if (p_node->package->original_order->delivery_factory == d_node->package->original_order->delivery_factory)
				continue;
		}
		PDNode* last_node_before = route.end;
		if (p_node->pickup_node())
		{
			last_node_before = p_node->delivery_pair;
		}

		double max_interval_demand = 0;
		double interval_demand = 0;
		for (PDNode* node = p_node->route_succ; node != d_node; node = node->route_succ) {
			if (node->pickup_node()) {
				interval_demand += node->package->getDemand();
				if (interval_demand > max_interval_demand)
					max_interval_demand = interval_demand;
			}
			else if (node->delivery_node())
				interval_demand -= node->package->getDemand();
		}
		DPDP_ASSERT_ABORT(std::fabs(interval_demand) < DPDP_EPSILON);

		do
		{
			if( level + DPDP_EPSILON < max_interval_demand + max_pickup )
				break;
			
			/* apply + evaluate + undo */
			curr_insertion.to_pred_first = p_node;
			curr_insertion.to_succ_second = d_node;

			curr_insertion.applyWithEvaluation( parent );

			if( NULL == best_insertion || curr_insertion.evaluated_value + DPDP_EPSILON < best_value )
			{
				best_value = curr_insertion.evaluated_value;
				curr_insertion.copy_to( best_insertion );
			}

			curr_insertion.undo( parent );

			if (d_node->pickup_node()) {
				PDNode* node = d_node;
				d_node = d_node->delivery_pair->route_succ;
				double interval_demand = 0;
				for (; node != d_node; node = node->route_succ) {
					if (node->pickup_node()) {
						interval_demand += node->package->getDemand();
						if (interval_demand > max_interval_demand)
							max_interval_demand = interval_demand;
					}
					else if (node->delivery_node())
						interval_demand -= node->package->getDemand();
				}
				DPDP_ASSERT_ABORT(std::fabs(interval_demand) < DPDP_EPSILON);
			}
			else {
				break;
			}
		} while (d_node != last_node_before);

		return best_insertion;
	}
}

PDSimpleInsertion* PDLocalSearch::findBestInsertationOfComponentOnVehicle(PDNode* pickup_node, PDNode* delivery_node, const int to_vehicle)
{
	DPDP_ASSERT_ABORT(pickup_node != NULL);
	DPDP_ASSERT_ABORT(delivery_node != NULL);
	DPDP_ASSERT_ABORT(pickup_node->delivery_pair == delivery_node);

	PDSimpleInsertion* best_insertation = NULL;
	double best_value = actual_value;
	PDSimpleInsertion curr_insertation;
	const PDRoute& route = parent->getRoute(to_vehicle);

	curr_insertation.package = pickup_node->package;
	curr_insertation.component = true;

	double max_pickup = 0;
	double level = 0;
	for (PDNode* node = pickup_node; node != delivery_node; node = node->route_succ)
	{
		if (node->pickup_node())
			level += node->package->getDemand();
		else if( node->delivery_node())
			level -= node->package->getDemand();

		if (level > max_pickup)
			max_pickup = level;
	}

	level = route.initial_residual_capacity;

	for (PDNode* node = route.begin; node != route.end; node = node->route_succ)
	{
		if (node->pickup_node()) {
			level -= node->package->getDemand();
		}
		else if (node->delivery_node() ) {
			level += node->package->getDemand();
		}
		if (level < -DPDP_EPSILON)
			return best_insertation;

		if (node->route_succ->get_node_type() == PDNODE_CI_DELIVERY) continue;

		if (level < max_pickup - DPDP_EPSILON) continue;

		PDNode* succ = node->route_succ;

		if (node->get_node_type() == succ->get_node_type())
		{
			DPDP_ASSERT_ABORT(node->pickup_node() || node->delivery_node());
			// both are pickup nodes or both are delivery nodes
			if (node->pickup_node() ) {
				if (node->package->original_order->pickup_factory == succ->package->original_order->pickup_factory)
					continue;
			}
			else {
				if (node->package->original_order->delivery_factory == succ->package->original_order->delivery_factory)
					continue;
			}
		}
		else if (node->delivery_node() && succ->pickup_node()) {
			if (node->package->original_order->delivery_factory == succ->package->original_order->pickup_factory)
				continue;

		}
		else if (node->pickup_node() && succ->delivery_node()) {
			DPDP_ASSERT_ABORT(node->delivery_pair == succ);
			if (node->package->original_order->pickup_factory == succ->package->original_order->delivery_factory)
				continue;
		}

		curr_insertation.to_vehicle = to_vehicle;
		curr_insertation.to_pickup_pred = node;
		curr_insertation.to_delivery_succ = NULL;
		curr_insertation.applyWithEvaluation(parent); // set evaluated_value

		if (curr_insertation.evaluated_value + DPDP_EPSILON < best_value)
		{
			best_value = curr_insertation.evaluated_value;
			curr_insertation.copy_to(best_insertation);
		}
		curr_insertation.undo(parent);
	}

	return best_insertation;
}

PDSimpleTransfer* PDLocalSearch::findBestTransfer(const bool component)
{
	PDSimpleTransfer* best_transfer = NULL;
	double best_value = actual_value;

	PDSimpleRemoval current_removal;
	current_removal.component = component;
	PDSimpleInsertion* current_insertion = NULL;

	for (int from_vehicle_id = 0; from_vehicle_id < probdata->getNumVehicles(); ++from_vehicle_id)
	{
		const PDRoute& from_route = parent->getRoute(from_vehicle_id);

		const Factory* pickup_factory = NULL;
		const Factory* delivery_factory = NULL;

		for (PDNode* pickup_node = from_route.begin->route_succ; pickup_node != from_route.end; pickup_node = pickup_node->route_succ) // from first non-dummy node to last non-dummy node
		{
			if (!pickup_node->pickup_node())
				continue;

			cPtr package = pickup_node->package;
			if (package->original_order->pickup_factory == pickup_factory && package->original_order->delivery_factory == delivery_factory)
				continue;

			pickup_factory = package->original_order->pickup_factory;
			delivery_factory = package->original_order->delivery_factory;

			/* remove package/component */
			current_removal.package = pickup_node->package;
			current_removal.apply(parent);

			/* find best insertion */
			current_insertion = findBestInsertation(pickup_node, pickup_node->delivery_pair, component);

			if (current_insertion != NULL)
			{
				if (current_insertion->evaluated_value + DPDP_EPSILON < best_value)
				{
					best_value = current_insertion->evaluated_value;

					if (NULL == best_transfer)
						best_transfer = new PDSimpleTransfer;

					PDSimpleRemoval* removal = &(best_transfer->removal);
					PDSimpleInsertion* insertion = &(best_transfer->insertion);

					current_removal.copy_to(removal);
					current_insertion->copy_to(insertion);
					best_transfer->evaluated_value = current_insertion->evaluated_value;
				}

				/* undo insertion */
				delete current_insertion;
			}

			/* undo removal */
			current_removal.undo(parent);
		}
	}

	return best_transfer;
}

PDGroupTransfer* PDLocalSearch::findBestGroupTransfer()
{
	PDGroupTransfer* best_transfer = NULL;
	double best_value = actual_value;

	PDGroupRemoval current_removal;
	PDGroupInsertion* current_insertion = NULL;

	for( int from_vehicle_id = 0; from_vehicle_id < probdata->getNumVehicles(); ++from_vehicle_id )
	{
		const PDRoute& from_route = parent->getRoute( from_vehicle_id );

		for( PDNode* pickup_node = from_route.begin->route_succ; pickup_node != from_route.end; pickup_node = pickup_node->route_succ )
		{
			if( !pickup_node->pickup_node() || (LS_FIXED_DESTINATION_PICKUPS && pickup_node->package->pickup_dest) )
				continue;

			current_removal.first_interval.first = pickup_node; // begin of the first interval

			PDNode* delivery_node = pickup_node->delivery_pair;

			while( true )
			{
				if( !pickup_node->route_succ->pickup_node() )
					break;
				if (LS_FIXED_DESTINATION_PICKUPS && pickup_node->route_succ->package->pickup_dest)
					break;
				if( pickup_node->package->original_order->pickup_factory != pickup_node->route_succ->package->original_order->pickup_factory )
					break;
				if( pickup_node->package->original_order->delivery_factory != pickup_node->route_succ->package->original_order->delivery_factory )
					break;

				if( !delivery_node->route_pred->delivery_node() )
					break;
				if( delivery_node->route_pred->pickup_pair != pickup_node->route_succ )
					break;

				delivery_node = delivery_node->route_pred;
				pickup_node = pickup_node->route_succ;
			}

			current_removal.first_interval.second = pickup_node; // end of first interval NOTE : possibly end = begin
			
			current_removal.second_interval.first = current_removal.first_interval.second->delivery_pair; // delivery node of the LAST pickup
			current_removal.second_interval.second = current_removal.first_interval.first->delivery_pair; // delivery node of the FIRST pickup

			/* check first pickup factory of the route */
			// TODO (kist) : atnezni
			const Factory* first_pickup_factory = parent->getRoute( from_vehicle_id ).first_pickup_factory;

			if( first_pickup_factory != NULL && current_removal.first_interval.first->route_pred->dummy_begin_node() ) // 'mandatory first pickup node rule' is active and relevant
			{
				DPDP_ASSERT_ABORT( pickup_node->getFactory() == first_pickup_factory );

				const PDNode* first_node_after_removal = pickup_node->route_succ;

				if( first_node_after_removal == current_removal.second_interval.first )
					first_node_after_removal = current_removal.second_interval.second->route_succ;

				if( first_node_after_removal->dummy_end_node() )
					continue;
				if( first_node_after_removal->delivery_node() )
					continue;
				if( first_node_after_removal->pickup_node() && first_node_after_removal->getFactory() != first_pickup_factory )
					continue;
			}

			/* remove package group */
			current_removal.apply( parent );

			/* find best insertion */
			for( int to_vehicle_id = 0; to_vehicle_id < probdata->getNumVehicles(); ++to_vehicle_id )
			{
				current_insertion = findBestInsertationOfPackageOnVehicle(
					current_removal.first_interval.first,
					current_removal.first_interval.second,
					current_removal.second_interval.first,
					current_removal.second_interval.second,
					to_vehicle_id
				);

				if( current_insertion != NULL )
				{
					if( current_insertion->evaluated_value + DPDP_EPSILON < best_value )
					{
						best_value = current_insertion->evaluated_value;

						if( NULL == best_transfer )
							best_transfer = new PDGroupTransfer;

						PDGroupRemoval* removal = &(best_transfer->removal);
						PDGroupInsertion* insertion = &(best_transfer->insertion);

						current_removal.copy_to( removal );
						current_insertion->copy_to( insertion );
						best_transfer->evaluated_value = current_insertion->evaluated_value;
					}

					delete current_insertion;
				}
			}

			/* undo removal */
			current_removal.undo( parent );
		}
	}

	return best_transfer;
}
