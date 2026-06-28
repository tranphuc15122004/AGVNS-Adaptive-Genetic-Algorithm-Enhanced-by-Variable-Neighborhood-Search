#pragma once

#include <list>
#include <set>

#include "solverdata.h"

// Pack items into the least number of bins. Each item has a size (first) and an id (second).
extern void pack_items(std::list<const Package*>& items, double capacity, std::vector<std::pair<double, std::list<const Package*> > >& packing);

extern void maximum_packing(std::list<const Package*>&  packages_to_deliver, double capacity, std::set<const Package*>& packages_to_assign);


