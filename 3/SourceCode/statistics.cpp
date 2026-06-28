#include "statistics.h"

#include <fstream>
#include <set>

constexpr char STATISTICS_LOG_FILE[] = "statistics.txt";

Statistics::Statistics(const ProbData& _probdata)
	: probdata(_probdata), num_factories(_probdata.getNumFactories()), num_vehicles(_probdata.getNumVehicles()), visiting_vehicles(NULL)
{

}
void Statistics::compute()
{
	node_to_node_demand = new double* [num_factories];
	total_pickup = new double[num_factories];
	total_delivery = new double[num_factories];
	visiting_vehicles = new int[num_factories];
	for (int f = 0; f < num_factories; ++f)
	{
		node_to_node_demand[f] = new double[num_factories];
		std::memset(node_to_node_demand[f], 0, num_factories * sizeof(double));
		total_pickup[f] = 0;
		total_delivery[f] = 0;
	}

	const int num_items = probdata.getNumUnallocatedOrderItems();
	for (int i = 0; i < num_items; ++i) {
		const OrderItem* oi = probdata.getUnallocatedOrderItem(i);
		total_pickup[oi->pickup_factory->id] += oi->demand;
		total_delivery[oi->delivery_factory->id] += oi->demand;
		node_to_node_demand[oi->pickup_factory->id][oi->delivery_factory->id] += oi->demand;
	}
}
Statistics::~Statistics()
{
	delete [] total_pickup;
	delete[] total_delivery;
	for (int f = 0; f < num_factories; ++f)
		delete [] node_to_node_demand[f];
	delete [] node_to_node_demand;

	delete [] visiting_vehicles;
}

void Statistics::writeStatistics()
{
	std::ofstream file(STATISTICS_LOG_FILE, std::ios::app);

	file << "******************************************\n";
	for (int f1 = 0; f1 < num_factories; ++f1) {
		if (total_pickup[f1] > DPDP_EPSILON || total_delivery[f1] > DPDP_EPSILON) {
			file << probdata.getFactory(f1)->inputfactory->id << " " << total_pickup[f1] << " " << total_delivery[f1] << std::endl;
		}
	}
	for (int f1 = 0; f1 < num_factories; ++f1) {
		for (int f2 = 0; f2 < num_factories; ++f2) {
			if( node_to_node_demand[f1][f2] >= 14.99 )
				file << probdata.getFactory(f1)->inputfactory->id << " " << probdata.getFactory(f2)->inputfactory->id << " " << node_to_node_demand[f1][f2] << std::endl;

		}
	}
	file.close();
}

void Statistics::count_visiting_vehicles(Scheduler& sch)
{
	std::memset(visiting_vehicles, 0, num_factories * sizeof(int));
	for (int vehicle_id = 0; vehicle_id < num_vehicles; ++vehicle_id)
	{
		SchRoute* r = sch.getRoute(vehicle_id);
		for (SchNode* node = r->first; node; node = node->succ)
		{
			if (node->node_type == CURRENT_NODE) continue;
			visiting_vehicles[node->factory->id]++;
		}
	}
}

void Statistics::write_schedule_stats(Scheduler& sch)
{
	std::ofstream file(STATISTICS_LOG_FILE, std::ios::app);
	//count_visiting_vehicles(sch);
	//file << "numer of vehicle visits at the factories:\n";
	//for (int f = 0; f < num_factories; ++f) {
	//	if (visiting_vehicles[f] > 0) {
	//		file << probdata.getFactory(f)->inputfactory->id << ' ' << visiting_vehicles[f] << ", ref: " << ref[f] << std::endl;
	//	}
	//}

	file << "vehilces visiting large demand factories:\n";
	for (int f = 0; f < num_factories; ++f) {
		if (total_pickup[f] <= 14.0 && total_delivery[f] <= 14.0)
			continue;

		file << "vehicles visiting factory " << probdata.getFactory(f)->inputfactory->id << std::endl;
		for (int vehicle_id = 0; vehicle_id < num_vehicles; ++vehicle_id) {
			const SchRoute * route = sch.getRoute(vehicle_id);
			for (SchNode* n = route->first; n; n = n->succ) {
				if (n->factory->id == f)
					sch.printRoute(file, vehicle_id, true);
			}
		}
	}
	file.close();
}
