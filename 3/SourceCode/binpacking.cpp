#include "binpacking.h"
#include <algorithm>
#include "dpdp.h"

static bool decr_items(const Package* a, const Package* b)
{
	return a->getDemand() > b->getDemand();
}
static void first_fit_decr(std::list<const Package* >& items, double capacity, std::vector<std::pair<double, std::list<const Package*> > >& packing)
{
	packing.clear();
	for (std::list<const Package * >::iterator it = items.begin(); it != items.end(); ++it) {
		
		bool item_packed = false;
		const Package* package = *it;
		for(std::vector<std::pair<double, std::list<const Package*> > >::iterator lit = packing.begin(); !item_packed && lit != packing.end(); ++lit)
		{
			if (lit->first + package->getDemand() <= capacity + DPDP_EPSILON)
			{
				lit->first += package->getDemand();
				lit->second.push_back(package);
				item_packed = true;
			}
		}
		if (!item_packed) {
			packing.push_back(std::make_pair(package->getDemand(),std::list<const Package*>()));
			packing.back().second.push_back(package);
		}
	}
}
void pack_items(std::list<const Package* >& items, double capacity, std::vector<std::pair<double, std::list<const Package*> > >& packing)
{

	items.sort(decr_items);

	first_fit_decr(items, capacity, packing);

}

static void MDB(std::list<const Package*>& items, std::list<const Package*>::iterator next_item, std::set<const Package*> &best_sol,
	double &best_slack, std::list<const Package*>& current_sol, double current_slack, bool &optimal)
{
	for (std::list<const Package*>::iterator it = next_item; !optimal && it != items.end(); ++it)
	{
		if ((*it)->getDemand() <= current_slack + DPDP_EPSILON) {
			current_sol.push_back(*it);
			next_item = it;
			++next_item;
			MDB(items, next_item, best_sol, best_slack, current_sol, current_slack - (*it)->getDemand(), optimal);
			if (best_slack <= DPDP_EPSILON) optimal = true;
			current_sol.pop_back();
		}
	}
	if (current_slack < best_slack - DPDP_EPSILON) {
		best_slack = current_slack;
		best_sol.clear();
		for(std::list<const Package *>::iterator  pit = current_sol.begin(); pit != current_sol.end(); ++pit)
			best_sol.insert(*pit);
	}
}
void maximum_packing(std::list<const Package*>& items, double capacity, std::set<const Package*>& packages_to_assign)
{
	items.sort(decr_items);
	
	packages_to_assign.clear();
	std::list<const Package*> current_sol;
	double best_slack = capacity;
	bool optimal = false;;
	MDB(items, items.begin(), packages_to_assign, best_slack, current_sol, capacity, optimal);
}
