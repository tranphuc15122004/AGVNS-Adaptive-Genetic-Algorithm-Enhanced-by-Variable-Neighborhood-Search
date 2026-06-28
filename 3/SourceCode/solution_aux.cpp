//#include "solution_aux.h"
//
//std::ostream& operator<<(std::ostream& os, const SeqRoute& r)
//{
//	os << "[\n" ;
//	for (std::list<RouteNode*>::const_iterator nit = r.nodes.cbegin(); nit != r.nodes.end(); ++nit) {
//		RouteNode* node = *nit;
//		os << "factory = " << node->factory->id << ", arrive = " << node->arrive_time << ", leave = " << node->leave_time << "\n";
//		os << "\tpickup list: [";
//		for (std::list<const Package*>::const_iterator pit = node->pickup_packages.cbegin(); pit != node->pickup_packages.cend(); ++pit)
//			(*pit)->printOrderItems(os);
//		os << "]\n";
//		os << "\tdelivery list: [";
//		for (std::list<const Package*>::const_iterator pit = node->delivery_packages.cbegin(); pit != node->delivery_packages.cend(); ++pit)
//			(*pit)->printOrderItemsReversed(os);
//		os << "]\n";
//	}
//	os << "]\n";
//
//	return os;
//}
//
//

